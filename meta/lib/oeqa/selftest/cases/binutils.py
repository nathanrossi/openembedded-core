# SPDX-License-Identifier: MIT
import os
import sys
import re
import logging
from oeqa.selftest.case import OESelftestTestCase
from oeqa.utils.commands import bitbake, get_bb_var, get_bb_vars

def parse_values(content, gold = False):
    suffix = ": " if not gold else " "
    for i in content:
        for v in ["PASS", "FAIL", "XPASS", "XFAIL", "UNRESOLVED", "UNSUPPORTED", "UNTESTED", "ERROR", "WARNING"]:
            if i.startswith(v + suffix):
                name = i[len(v) + len(suffix):].strip()
                if v == "FAIL" and gold: # clean off exit status on gold
                    name = name.split(" (exit status:")[0]
                yield name, v
                break

class BinutilsCrossSelfTest(OESelftestTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls.tc, "extraresults"):
            cls.tc.extraresults = {}

    def test_binutils(self):
        self.run_binutils("binutils")

    def test_gas(self):
        self.run_binutils("gas")

    def test_ld(self):
        self.run_binutils("ld")

    def test_gold(self):
        self.run_binutils("gold")

    def test_libiberty(self):
        self.run_binutils("libiberty")

    def run_binutils(self, suite):
        features = []
        features.append('MAKE_CHECK_TARGETS = "check-{0}"'.format(suite))
        self.write_config("\n".join(features))

        tune_arch = get_bb_var("TUNE_ARCH")
        recipe = "binutils-cross-{0}".format(tune_arch)
        bb_vars = get_bb_vars(["B", "TARGET_SYS", "T"], recipe)
        builddir, target_sys, tdir = bb_vars["B"], bb_vars["TARGET_SYS"], bb_vars["T"]

        bitbake("{0} -c check".format(recipe))

        failed = 0
        def add_result(test, result):
            nonlocal failed
            self.tc.extraresults["binutils.{}.{}".format(suite, test)] = {"status" : result}
            if result == "FAIL":
                self.logger.info("failed: '{}'".format(test))
                failed += 1

        if suite in ["binutils", "gas", "ld"]:
            sumspath = os.path.join(builddir, suite, "{0}.sum".format(suite))
            if not os.path.exists(sumspath):
                sumspath = os.path.join(builddir, suite, "testsuite", "{0}.sum".format(suite))
            with open(sumspath, "r") as f:
                for test, result in parse_values(f):
                    add_result(test, result)
        elif suite in ["gold"]:
            # gold tests are not dejagnu, so no sums file
            logspath = os.path.join(builddir, suite, "testsuite")
            if os.path.exists(logspath):
                for t in os.listdir(logspath):
                    if not t.endswith(".log") or t == "test-suite.log":
                        continue
                    with open(os.path.join(logspath, t), "r") as f:
                        for test, result in parse_values(f, gold = True):
                            add_result(test, result)
            else:
                self.skipTest("Target does not use {0}".format(suite))
        elif suite in ["libiberty"]:
            # libiberty tests are not dejagnu, no sums or log files
            logpath = os.path.join(tdir, "log.do_check")
            if os.path.exists(logpath):
                with open(logpath, "r") as f:
                    logdata = f.read()
                m = re.search(r"entering directory\s+'[^\r\n]+?libiberty/testsuite'.*?$(.*?)" +
                    "^[^\r\n]+?leaving directory\s+'[^\r\n]+?libiberty/testsuite'.*?$",
                    logdata, re.DOTALL | re.MULTILINE | re.IGNORECASE)
                if m is not None:
                    for test, result in parse_values(m.group(1).splitlines()):
                        add_result(test, result)

        self.assertEqual(failed, 0)


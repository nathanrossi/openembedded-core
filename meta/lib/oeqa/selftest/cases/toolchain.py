# SPDX-License-Identifier: MIT
import os
import sys
import time
import datetime
import tempfile
import contextlib
import re
import logging
import socket
from oeqa.selftest.case import OESelftestTestCase
from oeqa.utils.commands import bitbake, get_bb_var, get_bb_vars, runqemu, Command

class Results:
    _dejagnu_test_results = [
        ("PASS", "passed"), ("FAIL", "failed"),
        ("XPASS", "epassed"), ("XFAIL", "efailed"),
        ("UNRESOLVED", "unresolved"), ("UNSUPPORTED", "unsupported"), ("UNTESTED", "untested"),
        ("ERROR", "error"), ("WARNING", "warning"),
        ]

    def __init__(self, filtered = None):
        self.filtered = filtered or []
        self.ignored = []
        for v, f in self._dejagnu_test_results:
            setattr(self, f, [])

    def filter(self, tests):
        self.filtered += tests

    def parse_file(self, path, **kwargs):
        with open(path, "r") as f:
            self.parse_values(f, **kwargs)

    def parse_values(self, content, arch = None, gold = False):
        suffix = ": " if not gold else " "
        for i in content:
            for v, f in self._dejagnu_test_results:
                if i.startswith(v + suffix):
                    name = i[len(v) + len(suffix):].strip()
                    if self.filtered is not None and f == "failed":
                        if gold:
                            name = name.split(" (exit status:")[0]
                        if self.check_filtered(name, arch = arch):
                            self.ignored.append(name)
                            break
                    getattr(self, f).append(name)
                    break

    def check_filtered(self, name, arch = None):
        for i in self.filtered:
            iname, iarch = i, None
            if isinstance(i, (list, tuple)):
                iname, iarch = i

            if iname != name:
                continue
            if iarch is None or arch is None:
                return True

            # match arch pattern
            if re.match(iarch, arch, re.IGNORECASE):
                return True
        return False

    def __repr__(self):
        return "P:{} F:{} XP:{} XF:{} UR:{} US:{} UT:{} E:{} W:{} I:{}".format(
                len(self.passed), len(self.failed), len(self.epassed), len(self.efailed),
                len(self.unresolved), len(self.unsupported), len(self.untested),
                len(self.error), len(self.warning), len(self.ignored))

class OEToolchainSelfTestCase(OESelftestTestCase):
    default_installed_packages = []

    def setUp(self):
        super().setUp()
        self.results = Results()

    @contextlib.contextmanager
    def prepare_qemu(self, packages = None):
        tune_arch = get_bb_var("TUNE_ARCH")

        # build core-image-minimal with required packages
        features = []
        features.append('IMAGE_FEATURES += "ssh-server-openssh"')
        features.append('CORE_IMAGE_EXTRA_INSTALL += "{0}"'.format(" ".join(packages or self.default_installed_packages)))
        self.write_config("\n".join(features))
        bitbake("core-image-minimal")

        params = ["nographic"]
        qemuparams = []
        if "x86_64" in tune_arch:
            params += ["kvm", "kvm-vhost"]
            # qemuparams += ["-smp", "4"]

        with runqemu("core-image-minimal", runqemuparams = " ".join(params), qemuparams = " ".join(qemuparams)) as qemu:
            # validate that SSH is working
            status, _ = qemu.run("uname")
            self.assertEqual(status, 0)

            yield qemu

class BinutilsSelfTest(OEToolchainSelfTestCase):
    """
    Test cases for binutils
    """
    def test_cross_binutils(self):
        self.run_cross_binutils("binutils")
        self.assertEqual(len(self.results.failed), 0)

    def test_cross_binutils_gas(self):
        self.results.filter([
            ("POWER9 tests", "powerpc"),
            ])
        self.run_cross_binutils("gas")
        self.assertEqual(len(self.results.failed), 0)

    def test_cross_binutils_ld(self):
        self.results.filter([
            "Dump pr21978.so",
            ("Build pr22263-1", "arm|riscv64"),

            # TODO: verify
            ("indirect5c dynsym", "riscv64"),
            ("indirect5d dynsym", "riscv64"),
            ("ld-scripts/size-1", "riscv64"),

            # TODO: these failures are due to an issue with how mips sets up relocs/dynamic symbols
            ("indirect5a dynsym", "mips"),
            ("indirect5b dynsym", "mips"),
            ("indirect5c dynsym", "mips"),
            ("indirect5d dynsym", "mips"),
            ("indirect6c dynsym", "mips"),
            ("indirect6d dynsym", "mips"),
            ("Build libpr16496b.so", "mips"),
            ("vers24a", "mips"),
            ("vers24b", "mips"),
            ("vers24c", "mips"),
            ("--gc-sections with --defsym", "mips"),
            ("--gc-sections with KEEP", "mips"),
            ("--gc-sections with __start_SECTIONNAME", "mips"),
            ("PR ld/13229", "mips"),
            ("ld-plugin/lto-3r", "mips"),
            ("ld-plugin/lto-5r", "mips"),
            ("PR ld/19317 (2)", "mips"),
            ("PR ld/15323 (4)", "mips"),
            ("PR ld/19317 (3)", "mips"),
            ("shared (non PIC)", "mips"),
            ("shared (PIC main, non PIC so)", "mips"),
            ])
        self.run_cross_binutils("ld")
        self.assertEqual(len(self.results.failed), 0)

    def test_cross_binutils_gold(self):
        self.results.filter([
            ("script_test_10.sh", "mips"), # (abi sections break ordering)
            ])
        self.run_cross_binutils("gold")
        self.assertEqual(len(self.results.failed), 0)

    def test_cross_binutils_libiberty(self):
        self.run_cross_binutils("libiberty")
        self.assertEqual(len(self.results.failed), 0)

    def run_cross_binutils(self, suite):
        # configure ssh target
        features = []
        features.append('MAKE_CHECK_TARGETS = "check-{0}"'.format(suite))
        self.write_config("\n".join(features))

        recipe = "binutils-cross-{0}".format(get_bb_var("TUNE_ARCH"))
        bitbake("{0} -c check".format(recipe))

        bb_vars = get_bb_vars(["TUNE_ARCH", "B", "TARGET_SYS", "T"], recipe)
        tune_arch, builddir, target_sys, tdir = bb_vars["TUNE_ARCH"], bb_vars["B"], bb_vars["TARGET_SYS"], bb_vars["T"]

        if suite in ["binutils", "gas", "ld"]:
            sumspath = os.path.join(builddir, suite, "{0}.sum".format(suite))
            if not os.path.exists(sumspath):
                sumspath = os.path.join(builddir, suite, "testsuite", "{0}.sum".format(suite))
            self.results.parse_file(sumspath, arch = tune_arch)
        elif suite in ["gold"]:
            # gold tests are not dejagnu, so no sums file
            logspath = os.path.join(builddir, suite, "testsuite")
            if os.path.exists(logspath):
                for t in os.listdir(logspath):
                    if t.endswith(".log") and t != "test-suite.log":
                        self.results.parse_file(os.path.join(logspath, t), arch = tune_arch, gold = True)
            else:
                self.skipTest("Target does not use {0}".format(suite))
        elif suite in ["libiberty"]:
            # libiberty tests are not dejagnu, no sums or log files
            logpath = os.path.join(tdir, "log.do_check")
            lines = ""
            if os.path.exists(logpath):
                with open(logpath, "r") as f:
                    m = re.search(r"entering directory\s+'[^\r\n]+?libiberty/testsuite'.*?$(.*?)" +
                        "^[^\r\n]+?leaving directory\s+'[^\r\n]+?libiberty/testsuite'.*?$",
                        f.read(), re.DOTALL | re.MULTILINE | re.IGNORECASE)
                    if m is not None:
                        lines = m.group(1).splitlines()
            self.results.parse_values(lines, arch = tune_arch)
        self.logger.info("{} - {} summary {}".format(tune_arch, suite, repr(self.results)))

class GccSelfTest(OEToolchainSelfTestCase):
    """
    Test cases for gcc and gcc-runtime.
    """
    def test_cross_gcc(self):
        self.results.filter([
            # posion options are not listed in --help of gcc
            'compiler driver --help=warnings option(s): "^ +-.*[^:.]$" absent from output: "  -Wpoison-system-directories Warn for -I and -L options using system directories if cross compiling"',

            # known failures (reported by other distros/users)
            ("gcc.target/arm/polytypes.c  (test for warnings, line 30)", "arm"), # test has incorrect pattern for warning
            ("gcc.target/arm/pr43920-2.c scan-assembler-times pop 2", "arm"),
            (r"gcc.target/arm/addr-modes-float.c scan-assembler vst3.8\t{d[02468], d[02468], d[02468]}, \\[r[0-9]+\\]!", "arm"),
            ("gcc.target/i386/pr57193.c scan-assembler-times movdqa 2", "i686|x86_64"),
            (r"gcc.target/i386/pr81563.c scan-assembler-times movl[\\t ]*-4\\(%ebp\\),[\\t ]*%edi 1", "i686"),
            (r"gcc.target/i386/pr81563.c scan-assembler-times movl[\\t ]*-8\\(%ebp\\),[\\t ]*%esi 1", "i686"),
            (r"gcc.target/i386/pr90178.c scan-assembler-times xorl[\\t ]*\\%eax,[\\t ]*%eax 1", "i686|x86_64"),

            # fail on arm due to march flag conflicts (gcc patch skipping for -march=armv7ve)
            # (r"gcc.target/arm/atomic_loaddi_1.c scan-assembler-times ldrexd\tr[0-9]+, r[0-9]+, \\[r[0-9]+\\] 1", "arm"),
            # (r"gcc.target/arm/atomic_loaddi_4.c scan-assembler-times ldrexd\tr[0-9]+, r[0-9]+, \\[r[0-9]+\\] 1", "arm"),
            # (r"gcc.target/arm/atomic_loaddi_7.c scan-assembler-times ldrexd\tr[0-9]+, r[0-9]+, \\[r[0-9]+\\] 1", "arm"),

            # TODO:
            ("gcc.target/i386/pr57275.c execution test", "i686|x86_64"),

            # TODO: these fail sometimes due to timing?
            "gcc.dg/tree-prof/time-profiler-2.c scan-ipa-dump-times profile \"Read tp_first_run: 0\" 2",
            "gcc.dg/tree-prof/time-profiler-2.c scan-ipa-dump-times profile \"Read tp_first_run: 2\" 1",
            "gcc.dg/tree-prof/time-profiler-2.c scan-ipa-dump-times profile \"Read tp_first_run: 3\" 1",
            # TODO: this one fails sometimes due to large output data which gets truncated
            "c-c++-common/builtins.c  -Wc++-compat  (test for excess errors)",
            ])

        self.results.filter([
            # i686/x86_64 usermode failures
            ("gcc.c-torture/execute/loop-2f.c   -O0  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2f.c   -O1  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2f.c   -O2  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2f.c   -O2 -flto -fno-use-linker-plugin -flto-partition=none  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2f.c   -O2 -flto -fuse-linker-plugin -fno-fat-lto-objects  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2f.c   -O3 -fomit-frame-pointer -funroll-loops -fpeel-loops -ftracer -finline-functions  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2f.c   -O3 -g  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2f.c   -Os  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -O0  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -O1  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -O2  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -O2 -flto -fno-use-linker-plugin -flto-partition=none  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -O2 -flto -fuse-linker-plugin -fno-fat-lto-objects  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -O3 -fomit-frame-pointer -funroll-loops -fpeel-loops -ftracer -finline-functions  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -O3 -g  execution test", "i686"),
            ("gcc.c-torture/execute/loop-2g.c   -Os  execution test", "i686"),
            ("gcc.dg/pr59833.c execution test", "i686"),
            ("gcc.dg/pr61441.c execution test", "i686"),
            ("gcc.target/i386/bmi2-pdep32-1.c execution test", "i686|x86_64"),
            ("gcc.target/i386/bmi2-pdep64-1.c execution test", "x86_64"),
            ("gcc.target/i386/bmi2-pext32-1.c execution test", "i686|x86_64"),
            ("gcc.target/i386/bmi2-pext64-1.c execution test", "x86_64"),
            ("gcc.target/i386/sse4_1-ceil-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_1-ceilf-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_1-floor-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_1-floorf-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_1-rint-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_1-rintf-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_1-round-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_1-roundf-sfix-vec.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_2-pcmpistri-1.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_2-pcmpistri-2.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_2-pcmpistrm-1.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4_2-pcmpistrm-2.c execution test", "i686|x86_64"),
            ("gcc.target/i386/sse4a-insert.c execution test", "i686|x86_64"),
            ])

        self.gcc_cross_run_check("gcc")
        self.assertEqual(len(self.results.failed), 0)

    def test_cross_gxx(self):
        self.gcc_cross_run_check("g++")
        self.assertEqual(len(self.results.failed), 0)

    def test_gcc_runtime_libatomic(self):
        self.gcc_runtime_run_check("libatomic")
        self.assertEqual(len(self.results.failed), 0)

    def test_gcc_runtime_libgomp(self):
        self.gcc_runtime_run_check("libgomp")
        self.assertEqual(len(self.results.failed), 0)

    def test_gcc_runtime_libstdcxx(self):
        common_32_pattern = "arm|i686|powerpc|mips"
        self.results.filter([
            # common - 32bit - usermode issue
            ("27_io/filesystem/iterators/caching.cc execution test", common_32_pattern),
            ("27_io/filesystem/iterators/directory_iterator.cc execution test", common_32_pattern),
            ("27_io/filesystem/iterators/pop.cc execution test", common_32_pattern),
            ("27_io/filesystem/iterators/recursion_pending.cc execution test", common_32_pattern),
            ("27_io/filesystem/iterators/recursive_directory_iterator.cc execution test", common_32_pattern),
            ("27_io/filesystem/operations/canonical.cc execution test", common_32_pattern),
            ("27_io/filesystem/operations/copy.cc execution test", common_32_pattern),
            ("27_io/filesystem/operations/create_directories.cc execution test", common_32_pattern),
            ("27_io/filesystem/operations/is_empty.cc execution test", common_32_pattern),
            ("27_io/filesystem/operations/remove_all.cc execution test", common_32_pattern),
            ("experimental/filesystem/iterators/directory_iterator.cc execution test", common_32_pattern),
            ("experimental/filesystem/iterators/pop.cc execution test", common_32_pattern),
            ("experimental/filesystem/iterators/recursive_directory_iterator.cc execution test", common_32_pattern),
            ("experimental/filesystem/operations/copy.cc execution test", common_32_pattern),
            ("experimental/filesystem/operations/create_directories.cc execution test", common_32_pattern),
            ("experimental/filesystem/operations/is_empty.cc execution test", common_32_pattern),
            ("experimental/filesystem/operations/remove_all.cc execution test", common_32_pattern),

            ("30_threads/condition_variable/54185.cc execution test", "arm"), # memory leak
            ("ext/rope/pthread7-rope.cc execution test", "arm"), # memory leak
            ])
        self.gcc_runtime_run_check("libstdc++-v3")
        self.assertEqual(len(self.results.failed), 0)

    def test_gcc_runtime_libssp(self):
        self.gcc_runtime_check_skip("libssp")
        self.gcc_runtime_run_check("libssp")
        self.assertEqual(len(self.results.failed), 0)

    def test_gcc_runtime_libitm(self):
        self.gcc_runtime_check_skip("libitm")
        self.gcc_runtime_run_check("libitm")
        self.assertEqual(len(self.results.failed), 0)

    def gcc_run_check(self, recipe, suite, target_prefix = "check-", ssh = None):
        target = target_prefix + suite.replace("gcc", "gcc").replace("g++", "c++")

        # configure ssh target
        features = []
        features.append('MAKE_CHECK_TARGETS = "{0}"'.format(target))
        if ssh is not None:
            features.append('BUILD_TEST_TARGET = "ssh"')
            features.append('BUILD_TEST_HOST = "{0}"'.format(ssh))
            features.append('BUILD_TEST_HOST_USER = "root"')
            features.append('BUILD_TEST_HOST_PORT = "22"')
        self.write_config("\n".join(features))

        bitbake("{0} -c check".format(recipe))

        bb_vars = get_bb_vars(["TUNE_ARCH", "B", "TARGET_SYS"], recipe)
        tune_arch, builddir, target_sys = bb_vars["TUNE_ARCH"], bb_vars["B"], bb_vars["TARGET_SYS"]

        sumspath = os.path.join(builddir, "gcc", "testsuite", suite, "{0}.sum".format(suite))
        if not os.path.exists(sumspath): # check in target dirs
            sumspath = os.path.join(builddir, target_sys, suite, "testsuite", "{0}.sum".format(suite))
        if not os.path.exists(sumspath): # handle libstdc++-v3 -> libstdc++
            sumspath = os.path.join(builddir, target_sys, suite, "testsuite", "{0}.sum".format(suite.split("-")[0]))
        self.results.parse_file(sumspath, arch = tune_arch)

        self.logger.info("{} - {} {} summary {}".format(tune_arch, recipe, suite, repr(self.results)))
        for i in self.results.failed:
            self.logger.info("{} - {} {} failed {}".format(tune_arch, recipe, suite, i))

    def gcc_cross_run_check(self, suite):
        return self.gcc_run_check("gcc-cross-{0}".format(get_bb_var("TUNE_ARCH")), suite)

    def gcc_runtime_check_skip(self, suite):
        targets = get_bb_var("RUNTIMETARGET", "gcc-runtime").split()
        if suite not in targets:
            self.skipTest("Target does not use {0}".format(suite))

    def gcc_runtime_run_check(self, suite):
        return self.gcc_run_check("gcc-runtime", suite, target_prefix = "check-target-")

class GccSelfTestSystemEmulated(GccSelfTest):
    """
    Test cases for gcc and gcc-runtime. With target execution run on a QEMU
    system emulated target (via runqemu).
    """
    default_installed_packages = ["libgcc", "libstdc++", "libatomic", "libgomp"]

    def gcc_run_check(self, *args, **kwargs):
        # wrap the execution with a qemu instance
        with self.prepare_qemu() as qemu:
            return super().gcc_run_check(*args, **kwargs, ssh = qemu.ip)

class GlibcSelfTest(OEToolchainSelfTestCase):
    """
    Test cases for glibc
    """
    _expected_fail_usermode = [
        "elf/tst-dlopenrpath", # relies on "cp"
        "elf/tst-ptrguard1", # relies on system()
        "elf/tst-ptrguard1-static", # relies on system()
        "elf/tst-stackguard1", # relies on system()
        "elf/tst-stackguard1-static", # relies on system()
        "libio/bug-mmap-fflush", # relies on system()
        "nptl/tst-cancel21-static", # ??
        "nptl/tst-cancel7", # relies on system()
        "nptl/tst-cancelx7", # relies on system()
        "nptl/tst-exec2", # relies on shell
        "nptl/tst-exec3", # relies on shell
        "nptl/tst-oddstacklimit", # relies on system
        "nptl/tst-popen1", # relies on "echo"
        "nptl/tst-stack4", # ??
        "nptl/tst-stackguard1", # relies on system()
        "nptl/tst-stackguard1-static", # relies on system()
        "posix/tst-execl2", # relies on "cp", "chmod", system()
        "posix/tst-execle2", # relies on "cp", "chmod", system()
        "posix/tst-execlp2", # relies on "cp", "chmod", system()
        "posix/tst-execv2", # relies on "cp", "chmod", system()
        "posix/tst-execve2", # relies on "cp", "chmod", system()
        "posix/tst-execvp2", # relies on "cp", "chmod", system()
        "posix/tst-execvp3", # relies on shell, "echo"
        "posix/tst-execvpe2", # relies on "cp", "chmod", system()
        "posix/tst-fexecve", # relies on /bin/sh
        "posix/tst-vfork3", # relies on /bin/sh, and "echo"
        "posix/wordexp-test", # relies on shell
        "stdio-common/tst-popen", # relies on "echo"
        "stdio-common/tst-popen2", # same
        "stdlib/tst-system", # relies on shell (system())
        "nptl/test-cond-printers", # relies on python3
        "nptl/test-condattr-printers", # relies on python3
        "nptl/test-mutex-printers", # relies on python3
        "nptl/test-mutexattr-printers", # relies on python3
        "nptl/test-rwlock-printers", # relies on python3
        "nptl/test-rwlockattr-printers", # relies on python3
        "gmon/tst-gmon-gprof", # requires gprof
        "gmon/tst-gmon-pie-gprof", # requires gprof
        "gmon/tst-gmon-static-gprof", # requires gprof
        ]

    _expected_fail_usermode_unchecked = [
        "dirent/list", # ??
        "dirent/tst-scandir", # ??
        "elf/check-localplt", # ??
        "elf/tst-env-setuid", # requires root?
        "elf/tst-env-setuid-tunables", # requires root?
        "inet/test_ifindex", # ??
        "io/tst-fts", # ?? (same as dirent/list?)
        "io/tst-fts-lfs", # ?? (same as dirent/list?)
        "libio/tst-vtables", # qemu generates error message which is tested against known values and fails
        "localedata/bug-setlocale1", # ??
        "localedata/bug-setlocale1-static", # ??
        "malloc/tst-dynarray-at-fail", # qemu generates error message which is tested against known values and fails
        "malloc/tst-dynarray-fail", # ??
        "malloc/tst-malloc-tcache-leak", # timeout too low
        "malloc/tst-malloc-thread-fail", # ??
        "malloc/tst-malloc-usable-tunables", # ??
        "misc/check-installed-headers-c", # kernel headers expected fail
        "misc/test-errno-linux", # ??
        "misc/tst-clone2", # ??
        "misc/tst-clone3", # ??
        "nptl/tst-align-clone", # ??
        "nptl/tst-basic7", # ?? - memory?
        "nptl/tst-cond-except", # ?? - not supported
        "nptl/tst-cond24", # arm known fail
        "nptl/tst-cond25", # ?? - not supported
        "nptl/tst-create-detached", # ?? - memory?
        "nptl/tst-exec4", # ??
        "nptl/tst-getpid1", # ??
        "nptl/tst-robust-fork", # ?? - not supported
        "nptl/tst-setuid3", # ??
        "posix/test-errno", # ?? - syscall differences
        "posix/tst-exec", # ?? - something with exec format error??
        "posix/tst-exec-static", # ?? - something with exec format error??
        "posix/tst-execvpe5", # ?? - something with exec format error??
        "posix/tst-posix_spawn-setsid", # ??
        "posix/tst-regcomp-truncated", # timeout
        "posix/tst-spawn", # ??
        "posix/tst-spawn-static", # ??
        "posix/tst-spawn2", # ??
        "posix/tst-spawn4", # ??
        "rt/tst-mqueue3", # ??
        "rt/tst-mqueue5", # ??
        "rt/tst-mqueue6", # ??
        "rt/tst-mqueue7", # ??
        "stdlib/bug-fmtmsg1", # bug in check-test-wrapper
        "stdlib/tst-secure-getenv", # ??
        "timezone/tst-tzset", # creates 4GB file!
        ]

    def test_glibc(self):
        self.results.filter(self._expected_fail_usermode)
        self.glibc_run_check()

    def glibc_run_check(self, ssh = None):
        # configure ssh target
        features = []
        if ssh is not None:
            features.append('BUILD_TEST_TARGET = "ssh"')
            features.append('BUILD_TEST_HOST = "{0}"'.format(ssh))
            features.append('BUILD_TEST_HOST_USER = "root"')
            features.append('BUILD_TEST_HOST_PORT = "22"')
            # force single threaded test execution
            features.append('EGLIBCPARALLELISM_task-check_pn-glibc-testsuite = "PARALLELMFLAGS="-j1""')

        self.write_config("\n".join(features))

        bitbake("glibc-testsuite -c check")

        tune_arch = get_bb_var("TUNE_ARCH")
        builddir = get_bb_var("B", "glibc-testsuite")
        self.results.parse_file(os.path.join(builddir, "tests.sum"), arch = tune_arch)
        self.logger.info("{} - glibc summary {}".format(tune_arch, repr(self.results)))

@contextlib.contextmanager
def unfs_server(directory, logger = None):
    def find_port(tcp = True):
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM)
            s.bind(("", 0))
            port = s.getsockname()[1]
        finally:
            if s is not None:
                s.close()
        return port

    unfs_sysroot = get_bb_var("RECIPE_SYSROOT_NATIVE", "unfs3-native")
    if not os.path.exists(os.path.join(unfs_sysroot, "usr", "bin", "unfsd")):
        # build native tool
        bitbake("unfs3-native -c addto_recipe_sysroot")

    exports = None
    cmd = None
    try:
        # create the exports file
        with tempfile.NamedTemporaryFile(delete = False) as exports:
            exports.write("{0} (rw,no_root_squash,no_all_squash,insecure)\n".format(directory).encode())

        # find some ports for the server
        nfsport, mountport = find_port(False), find_port(False)

        nenv = dict(os.environ)
        nenv['PATH'] = "{0}/sbin:{0}/usr/sbin:{0}/usr/bin:".format(unfs_sysroot) + nenv.get('PATH', '')
        cmd = Command(["unfsd", "-d", "-p", "-N", "-e", exports.name, "-n", str(nfsport), "-m", str(mountport)],
                bg = True, env = nenv, output_log = logger)
        cmd.run()
        yield nfsport, mountport
    finally:
        if cmd is not None:
            cmd.stop()
        if exports is not None:
            # clean up exports file
            os.unlink(exports.name)

class GlibcSelfTestSystemEmulated(GlibcSelfTest):
    default_installed_packages = [
        "glibc-charmaps",
        "libgcc",
        "libstdc++",
        "libatomic",
        "libgomp",
        "python3",
        "python3-pexpect",
        "nfs-utils",
        ]

    # clear all usermode filters
    _expected_fail_usermode = []

    def glibc_run_check(self):
        # use the base work dir, as the nfs mount, since the recipe directory may not exist
        tmpdir = get_bb_var("BASE_WORKDIR")
        # setup nfs
        with unfs_server(tmpdir) as (nfsport, mountport):
            self.logger.info("Got unfs up, ports = %d - %d", nfsport, mountport)
            with self.prepare_qemu() as qemu:
                # setup nfs mount
                if qemu.run("mkdir -p \"{0}\"".format(tmpdir))[0] != 0:
                    raise Exception("Failed to setup NFS mount directory on target")

                mountcmd = "mount -o noac,nfsvers=3,port={0},udp,mountport={1} \"{2}:{3}\" \"{3}\"".format(nfsport, mountport, qemu.server_ip, tmpdir)
                status, output = qemu.run(mountcmd)
                if status != 0:
                    raise Exception("Failed to setup NFS mount on target ({})".format(repr(output)))

                super().glibc_run_check(ssh = qemu.ip)


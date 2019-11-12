#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Modified for use in OE by Richard Purdie, 2018
#
# Modified by: Corey Goldberg, 2013
#   License: GPLv2+
#
# Original code from:
#   Bazaar (bzrlib.tests.__init__.py, v2.6, copied Jun 01 2013)
#   Copyright (C) 2005-2011 Canonical Ltd
#   License: GPLv2+

import os
import sys
import traceback
import unittest
import subprocess
import testtools
import threading
import time
import io
import json
import subunit

from queue import Queue
from itertools import cycle
from subunit import ProtocolTestCase, TestProtocolClient
from subunit.test_results import AutoTimingTestResultDecorator
from testtools import ThreadsafeForwardingResult, iterate_tests
from testtools.content import Content
from testtools.content_type import ContentType
from oeqa.utils.commands import get_test_layer

import bb.utils
import oe.path

_all__ = [
    'ConcurrentTestSuite',
    'fork_for_tests',
    'partition_tests',
]

#
# Patch the version from testtools to allow access to _test_start and allow
# computation of timing information and threading progress
#
class BBThreadsafeForwardingResult(ThreadsafeForwardingResult):

    def __init__(self, target, semaphore, threadnum, totalinprocess, totaltests):
        super(BBThreadsafeForwardingResult, self).__init__(target, semaphore)
        self.threadnum = threadnum
        self.totalinprocess = totalinprocess
        self.totaltests = totaltests

    def _add_result_with_semaphore(self, method, test, *args, **kwargs):
        self.semaphore.acquire()
        try:
            if self._test_start:
                self.result.starttime[test.id()] = self._test_start.timestamp()
                self.result.threadprogress[self.threadnum].append(test.id())
                totalprogress = sum(len(x) for x in self.result.threadprogress.values())
                self.result.progressinfo[test.id()] = "%s: %s/%s %s/%s (%ss) (%s)" % (
                    self.threadnum,
                    len(self.result.threadprogress[self.threadnum]),
                    self.totalinprocess,
                    totalprogress,
                    self.totaltests,
                    "{0:.2f}".format(time.time()-self._test_start.timestamp()),
                    test.id())
        finally:
            self.semaphore.release()
        super(BBThreadsafeForwardingResult, self)._add_result_with_semaphore(method, test, *args, **kwargs)

class ProxyTestResult:
    # a very basic TestResult proxy, in order to modify add* calls
    def __init__(self, target):
        self.result = target

    def _addResult(self, method, test, *args, exception = False, **kwargs):
        return method(test, *args, **kwargs)

    def addError(self, test, err = None, **kwargs):
        self._addResult(self.result.addError, test, err, exception = True, **kwargs)

    def addFailure(self, test, err = None, **kwargs):
        self._addResult(self.result.addFailure, test, err, exception = True, **kwargs)

    def addSuccess(self, test, **kwargs):
        self._addResult(self.result.addSuccess, test, **kwargs)

    def addExpectedFailure(self, test, err = None, **kwargs):
        self._addResult(self.result.addExpectedFailure, test, err, exception = True, **kwargs)

    def addUnexpectedSuccess(self, test, **kwargs):
        self._addResult(self.result.addUnexpectedSuccess, test, **kwargs)

    def __getattr__(self, attr):
        return getattr(self.result, attr)

class ExtraResultsDecoderTestResult(ProxyTestResult):
    class RemotedSubTest:
        def __init__(self, testcase, idstring):
            self.testcase = testcase
            self.idstring = idstring

        def id(self):
            return self.idstring

        def __str__(self):
            return self.idstring

        def shortDescription(self):
            return self.testcase.shortDescription()

    class _StringException(testtools.testresult.real._StringException, AssertionError):
        pass

    @staticmethod
    def decodeexception(outcome):
        failure = outcome.get("failure", False)
        if failure:
            exceptiontype = ExtraResultsDecoderTestResult._StringException
        else:
            exceptiontype = testtools.testresult.real._StringException
        return (exceptiontype, exceptiontype(outcome.get("exception")), None)

    @staticmethod
    def jsondecode(content):
        data = bytearray()
        for b in content.iter_bytes():
            data += b
        return json.loads(data.decode())

    def _addResult(self, method, test, *args, exception = False, **kwargs):
        if "details" in kwargs and "extraresults" in kwargs["details"]:
            if isinstance(kwargs["details"]["extraresults"], Content):
                kwargs = kwargs.copy()
                kwargs["details"] = kwargs["details"].copy()
                kwargs["details"]["extraresults"] = self.jsondecode(kwargs["details"]["extraresults"])
        if "details" in kwargs and "subtests" in kwargs["details"]:
            for subtest, outcome in self.jsondecode(kwargs["details"]["subtests"]).items():
                if outcome is None:
                    self.result.addSubTest(test, self.RemotedSubTest(test, subtest), None, **kwargs)
                else:
                    # convert traceback string to outcome info
                    self.result.addSubTest(test, self.RemotedSubTest(test, subtest),
                        self.decodeexception(outcome), **kwargs)
        if "details" in kwargs and "forced_unknown" in kwargs["details"]:
            return None # "unknown" result
        return method(test, *args, **kwargs)

class ExtraResultsEncoderTestResult(ProxyTestResult):
    def __init__(self, target):
        super().__init__(target)
        self.subtests = [] # the test/subtest objects are not hashable
        self.subtested = []

    @staticmethod
    def jsonencode(content):
        encoder = lambda : [json.dumps(content).encode()]
        return Content(ContentType("application", "json", {'charset': 'utf8'}), encoder)

    def _addResult(self, method, test, *args, exception = False, **kwargs):
        newdetails = {}

        if hasattr(test, "extraresults"):
            newdetails["extraresults"] = self.jsonencode(test.extraresults)

        # encode the subtests into the details object if they exist
        entry = next((i for i in self.subtests if i[0] == test), None)
        if entry is not None:
            # clean up, to speed up later lookups
            self.subtests.remove(entry)
            self.subtested.append(test)

            subtests = {}
            for subtest, outcome in entry[1]:
                if outcome is None:
                    subtests[subtest.id()] = None
                else:
                    # generate traceback of the exception, use testtools to generate it
                    content = testtools.content.TracebackContent(outcome, subtest)
                    data = bytearray()
                    for b in content.iter_bytes():
                        data += b
                    subtests[subtest.id()] = {
                            "failure": issubclass(outcome[0], test.failureException),
                            "exception" : data.decode()
                            }
            newdetails["subtests"] = self.jsonencode(subtests)

        # if using details, need to encode any exceptions into the details obj,
        # testtools does not handle "err" and "details" together.
        if len(newdetails) != 0 and exception and (len(args) >= 1 and args[0] is not None):
            newdetails["traceback"] = testtools.content.TracebackContent(args[0], test)
            args = []

        # inject details is there are any newly modified/added entries
        if len(newdetails) != 0:
            kwargs = kwargs.copy()
            if "details" in kwargs:
                kwargs["details"] = kwargs["details"].copy()
                kwargs["details"].update(newdetails)
            else:
                kwargs["details"] = newdetails

        return method(test, *args, **kwargs)

    def addSubTest(self, test, subtest, outcome, **kwargs):
        for (i, subtests) in self.subtests:
            if i != test:
                continue
            subtests.append((subtest, outcome))
            return
        self.subtests.append((test, [(subtest, outcome)]))

    def stopTest(self, test):
        # if a testcase using subTest does not assert or similar it will be
        # considered "unknown", but the subtest information still needs to be
        # sent to the parent, dummy send a success that is ignored by the
        # decoder
        subtests = next((st for t, st in self.subtests if t == test), [])
        if any(outcome is not None for _, outcome in subtests) and test not in self.subtested:
            empty = Content(ContentType("application", "empty", {'charset': 'utf8'}), lambda : [b""])
            self._addResult(self.addSuccess, test, details = {"forced_unknown": empty})

#
# We have to patch subunit since it doesn't understand how to handle addError
# outside of a running test case. This can happen if classSetUp() fails
# for a class of tests. This unfortunately has horrible internal knowledge.
#
def outSideTestaddError(self, offset, line):
    """An 'error:' directive has been read."""
    test_name = line[offset:-1].decode('utf8')
    self.parser._current_test = subunit.RemotedTestCase(test_name)
    self.parser.current_test_description = test_name
    self.parser._state = self.parser._reading_error_details
    self.parser._reading_error_details.set_simple()
    self.parser.subunitLineReceived(line)

subunit._OutSideTest.addError = outSideTestaddError


#
# A dummy structure to add to io.StringIO so that the .buffer object
# is available and accepts writes. This allows unittest with buffer=True
# to interact ok with subunit which wants to access sys.stdout.buffer.
#
class dummybuf(object):
   def __init__(self, parent):
       self.p = parent
   def write(self, data):
       self.p.write(data.decode("utf-8"))

#
# Taken from testtools.ConncurrencyTestSuite but modified for OE use
#
class ConcurrentTestSuite(unittest.TestSuite):

    def __init__(self, suite, processes):
        super(ConcurrentTestSuite, self).__init__([suite])
        self.processes = processes

    def run(self, result):
        tests, totaltests = fork_for_tests(self.processes, self)
        try:
            threads = {}
            queue = Queue()
            semaphore = threading.Semaphore(1)
            result.threadprogress = {}
            for i, (test, testnum) in enumerate(tests):
                result.threadprogress[i] = []
                process_result = BBThreadsafeForwardingResult(
                        ExtraResultsDecoderTestResult(result),
                        semaphore, i, testnum, totaltests)
                # Force buffering of stdout/stderr so the console doesn't get corrupted by test output
                # as per default in parent code
                process_result.buffer = True
                # We have to add a buffer object to stdout to keep subunit happy
                process_result._stderr_buffer = io.StringIO()
                process_result._stderr_buffer.buffer = dummybuf(process_result._stderr_buffer)
                process_result._stdout_buffer = io.StringIO()
                process_result._stdout_buffer.buffer = dummybuf(process_result._stdout_buffer)
                reader_thread = threading.Thread(
                    target=self._run_test, args=(test, process_result, queue))
                threads[test] = reader_thread, process_result
                reader_thread.start()
            while threads:
                finished_test = queue.get()
                threads[finished_test][0].join()
                del threads[finished_test]
        except:
            for thread, process_result in threads.values():
                process_result.stop()
            raise
        finally:
            for test in tests:
                test[0]._stream.close()

    def _run_test(self, test, process_result, queue):
        try:
            try:
                test.run(process_result)
            except Exception:
                # The run logic itself failed
                case = testtools.ErrorHolder(
                    "broken-runner",
                    error=sys.exc_info())
                case.run(process_result)
        finally:
            queue.put(test)

def removebuilddir(d):
    delay = 5
    while delay and os.path.exists(d + "/bitbake.lock"):
        time.sleep(1)
        delay = delay - 1
    # Deleting these directories takes a lot of time, use autobuilder
    # clobberdir if its available
    clobberdir = os.path.expanduser("~/yocto-autobuilder-helper/janitor/clobberdir")
    if os.path.exists(clobberdir):
        try:
            subprocess.check_call([clobberdir, d])
            return
        except subprocess.CalledProcessError:
            pass
    bb.utils.prunedir(d, ionice=True)

def fork_for_tests(concurrency_num, suite):
    result = []
    if 'BUILDDIR' in os.environ:
        selftestdir = get_test_layer()

    test_blocks = partition_tests(suite, concurrency_num)
    # Clear the tests from the original suite so it doesn't keep them alive
    suite._tests[:] = []
    totaltests = sum(len(x) for x in test_blocks)
    for process_tests in test_blocks:
        numtests = len(process_tests)
        process_suite = unittest.TestSuite(process_tests)
        # Also clear each split list so new suite has only reference
        process_tests[:] = []
        c2pread, c2pwrite = os.pipe()
        # Clear buffers before fork to avoid duplicate output
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid == 0:
            ourpid = os.getpid()
            try:
                newbuilddir = None
                stream = os.fdopen(c2pwrite, 'wb', 1)
                os.close(c2pread)

                # Create a new separate BUILDDIR for each group of tests
                if 'BUILDDIR' in os.environ:
                    builddir = os.environ['BUILDDIR']
                    newbuilddir = builddir + "-st-" + str(ourpid)
                    newselftestdir = newbuilddir + "/meta-selftest"

                    bb.utils.mkdirhier(newbuilddir)
                    oe.path.copytree(builddir + "/conf", newbuilddir + "/conf")
                    oe.path.copytree(builddir + "/cache", newbuilddir + "/cache")
                    oe.path.copytree(selftestdir, newselftestdir)

                    for e in os.environ:
                        if builddir in os.environ[e]:
                            os.environ[e] = os.environ[e].replace(builddir, newbuilddir)

                    subprocess.check_output("git init; git add *; git commit -a -m 'initial'", cwd=newselftestdir, shell=True)

                    # Tried to used bitbake-layers add/remove but it requires recipe parsing and hence is too slow
                    subprocess.check_output("sed %s/conf/bblayers.conf -i -e 's#%s#%s#g'" % (newbuilddir, selftestdir, newselftestdir), cwd=newbuilddir, shell=True)

                    os.chdir(newbuilddir)

                    for t in process_suite:
                        if not hasattr(t, "tc"):
                            continue
                        cp = t.tc.config_paths
                        for p in cp:
                            if selftestdir in cp[p] and newselftestdir not in cp[p]:
                                cp[p] = cp[p].replace(selftestdir, newselftestdir)
                            if builddir in cp[p] and newbuilddir not in cp[p]:
                                cp[p] = cp[p].replace(builddir, newbuilddir)

                # Leave stderr and stdout open so we can see test noise
                # Close stdin so that the child goes away if it decides to
                # read from stdin (otherwise its a roulette to see what
                # child actually gets keystrokes for pdb etc).
                newsi = os.open(os.devnull, os.O_RDWR)
                os.dup2(newsi, sys.stdin.fileno())

                subunit_client = TestProtocolClient(stream)
                # Force buffering of stdout/stderr so the console doesn't get corrupted by test output
                # as per default in parent code
                subunit_client.buffer = True
                subunit_result = AutoTimingTestResultDecorator(subunit_client)
                process_suite.run(ExtraResultsEncoderTestResult(subunit_result))
                if ourpid != os.getpid():
                    os._exit(0)
                if newbuilddir:
                    removebuilddir(newbuilddir)
            except:
                # Don't do anything with process children
                if ourpid != os.getpid():
                    os._exit(1)
                # Try and report traceback on stream, but exit with error
                # even if stream couldn't be created or something else
                # goes wrong.  The traceback is formatted to a string and
                # written in one go to avoid interleaving lines from
                # multiple failing children.
                try:
                    stream.write(traceback.format_exc().encode('utf-8'))
                except:
                    sys.stderr.write(traceback.format_exc())
                finally:
                    if newbuilddir:
                        removebuilddir(newbuilddir)
                    stream.flush()
                    os._exit(1)
            stream.flush()
            os._exit(0)
        else:
            os.close(c2pwrite)
            stream = os.fdopen(c2pread, 'rb', 1)
            test = ProtocolTestCase(stream)
            result.append((test, numtests))
    return result, totaltests

def partition_tests(suite, count):
    # Keep tests from the same class together but allow tests from modules
    # to go to different processes to aid parallelisation.
    modules = {}
    for test in iterate_tests(suite):
        m = test.__module__ + "." + test.__class__.__name__
        if m not in modules:
            modules[m] = []
        modules[m].append(test)

    # Simply divide the test blocks between the available processes
    partitions = [list() for _ in range(count)]
    for partition, m in zip(cycle(partitions), modules):
        partition.extend(modules[m])

    # No point in empty threads so drop them
    return [p for p in partitions if p]


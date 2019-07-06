require glibc_${PV}.bb

# handle PN differences
FILESEXTRAPATHS_prepend := "${THISDIR}/glibc:"

# strip provides
PROVIDES = ""
# setup depends
INHIBIT_DEFAULT_DEPS = ""

DEPENDS += "glibc-locale libgcc gcc-runtime"

# remove the initial depends
DEPENDS_remove = "libgcc-initial"
DEPENDS_remove = "linux-libc-headers"
DEPENDS_remove = "virtual/${TARGET_PREFIX}libc-initial"
DEPENDS_remove = "virtual/${TARGET_PREFIX}gcc-initial"

inherit qemu

DEPENDS += "${@'qemu-native' if d.getVar('BUILD_TEST_TARGET') == 'user' else ''}"

BUILD_TEST_TARGET ??= "user"
BUILD_TEST_SINGLE ??= ""
BUILD_TEST_HOST ??= "localhost"
BUILD_TEST_HOST_USER ??= "root"
BUILD_TEST_HOST_PORT ??= "2222"

generate_test_wrapper_user[dirs] += "${WORKDIR}"
python generate_test_wrapper_user() {
    sysroot = d.getVar("RECIPE_SYSROOT")
    qemu_binary = qemu_target_binary(d)
    if not qemu_binary:
        bb.fatal("Missing target qemu linux-user binary")

    args = [qemu_binary]
    args += (d.getVar("QEMU_OPTIONS") or "").split()
    #args += ["-E", "LD_DEBUG=all"]
    formattedargs = " ".join("\"{0}\"".format(i) if (" " in i) else i for i in args)
    testwrapper = os.path.join(d.getVar("WORKDIR"), "check-test-wrapper")
    with open(testwrapper, "w") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("sysroot = \"{0}\"\n".format(sysroot))
        f.write("qemuargs = [\n")
        for i in args:
            if "\"" in i:
                i = i.replace("\"", "\\\"")
            f.write("    \"{0}\",\n".format(i))
        f.write("    ]\n")

        script = r"""
import sys
import os
import subprocess

args = sys.argv[1:]
libpaths = [sysroot + "/usr/lib", sysroot + "/lib"]

if args[0] == "env":
    args.pop(0)
    while "=" in args[0]:
        key, val = args.pop(0).split("=", 1)
        if key == "LD_LIBRARY_PATH":
            libpaths += val.split(":")
        else:
            os.environ[key] = val
if args[0] == "cp":
    # ignore copies, the filesystem is the same
    sys.exit(0)

qemuargs += ["-L", sysroot]
qemuargs += ["-E", "LD_LIBRARY_PATH={}".format(":".join(libpaths))]
try:
    r = subprocess.run(qemuargs + args, timeout = 1800)
    sys.exit(r.returncode)
except subprocess.TimeoutExpired:
    sys.exit(-1)
"""
        for i in script.splitlines():
            f.write(i + "\n")

    os.chmod(testwrapper, 0o755)
}

generate_test_wrapper_ssh[dirs] += "${WORKDIR}"
python generate_test_wrapper_ssh() {
    testwrapper = os.path.join(d.getVar("WORKDIR"), "check-test-wrapper")
    with open(testwrapper, "w") as f:
        f.write("%s\n" % "#!/usr/bin/env python3")
        f.write("host = \"{0}\"\n".format(d.getVar("BUILD_TEST_HOST")))
        f.write("user = \"{0}\"\n".format(d.getVar("BUILD_TEST_HOST_USER")))
        f.write("port = \"{0}\"\n".format(d.getVar("BUILD_TEST_HOST_PORT")))

        script = r"""
import sys
import os
import subprocess

args = ["ssh", "-p", port, "-o", "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no", "{0}@{1}".format(user, host), "sh", "-c"]

command = ""
#command += "export TIMEOUTFACTOR=10000; "
command += " ".join(["'%s'" % i.replace("'", r"'\''") for i in ["cd", os.getcwd()]]) + "; "
command += " ".join(["'%s'" % i.replace("'", r"'\''") for i in sys.argv[1:]])
args.append("\"%s\"" % command)

r = subprocess.run(args)
sys.exit(r.returncode)
"""
        for i in script.splitlines():
            f.write(i + "\n")
    os.chmod(testwrapper, 0o755)
}

python () {
    if "ssh" in d.getVar("BUILD_TEST_TARGET") or d.getVar("BUILD_TEST_SINGLE") == "1":
        # limit ssh to single job execution
        d.setVar("EGLIBCPARALLELISM_task-check", "PARALLELMFLAGS=\"-j1\"")
}

do_check[dirs] += "${B}"
do_check[prefuncs] += "generate_test_wrapper_${BUILD_TEST_TARGET}"
do_check[nostamp] = "1"
do_check () {
    # clean out previous test results
    oe_runmake tests-clean
    # makefiles don't clean entirely (and also sometimes fails due to too many args)
    find ${B} -type f -name "*.out" -delete
    find ${B} -type f -name "*.test-result" -delete
    find ${B}/catgets -name "*.cat" -delete
    find ${B}/conform -name "symlist-*" -delete
    [ ! -e ${B}/timezone/testdata ] || rm -rf ${B}/timezone/testdata

    oe_runmake -i test-wrapper='${WORKDIR}/check-test-wrapper' check
}
addtask do_check after do_compile


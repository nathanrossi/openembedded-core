inherit cross
PROVIDES = "virtual/${TARGET_PREFIX}binutils"

PN = "binutils-cross-${TARGET_ARCH}"
BPN = "binutils"

# Ignore how TARGET_ARCH is computed.
TARGET_ARCH[vardepvalue] = "${TARGET_ARCH}"

INHIBIT_DEFAULT_DEPS = "1"
INHIBIT_AUTOTOOLS_DEPS = "1"

SRC_URI += "file://0002-binutils-cross-Do-not-generate-linker-script-directo.patch"

# Specify lib-path else we use a load of search dirs which we don't use
# and mean the linker scripts have to be relocated.
EXTRA_OECONF += "--with-sysroot=${STAGING_DIR_TARGET} \
                --disable-install-libbfd \
                --enable-poison-system-directories \
                --with-lib-path==${target_base_libdir}:=${target_libdir} \
                "
do_install () {
	oe_runmake 'DESTDIR=${D}' install

	# We don't really need these, so we'll remove them...
	rm -rf ${D}${STAGING_DIR_NATIVE}${libdir_native}/libiberty.a
	rm -rf ${D}${STAGING_DIR_NATIVE}${prefix_native}/${TARGET_SYS}
	rm -rf ${D}${STAGING_DIR_NATIVE}${prefix_native}/lib/ldscripts
	rm -rf ${D}${STAGING_DIR_NATIVE}${prefix_native}/share/info
	rm -rf ${D}${STAGING_DIR_NATIVE}${prefix_native}/share/locale
	rm -rf ${D}${STAGING_DIR_NATIVE}${prefix_native}/share/man
	rmdir ${D}${STAGING_DIR_NATIVE}${prefix_native}/share || :
	rmdir ${D}${STAGING_DIR_NATIVE}${prefix_native}/${libdir}/gcc-lib || :
	rmdir ${D}${STAGING_DIR_NATIVE}${prefix_native}/${libdir}64/gcc-lib || :
	rmdir ${D}${STAGING_DIR_NATIVE}${prefix_native}/${libdir} || :
	rmdir ${D}${STAGING_DIR_NATIVE}${prefix_native}/${libdir}64 || :
	rmdir ${D}${STAGING_DIR_NATIVE}${prefix_native}/${prefix} || :
}

EXTRA_OEMAKE_prepend_task-check = "${PARALLEL_MAKE} "
MAKE_CHECK_TARGETS ??= "check-binutils check-gas check-gold check-ld check-libiberty"

python () {
    # crosssdk deps have different virtual targets
    if bb.data.inherits_class('crosssdk', d):
        d.appendVarFlag("do_check", "depends", " virtual/${TARGET_PREFIX}gcc-crosssdk:do_populate_sysroot")
        d.appendVarFlag("do_check", "depends", " virtual/nativesdk-${TARGET_PREFIX}compilerlibs:do_populate_sysroot")
    else:
        d.appendVarFlag("do_check", "depends", " virtual/${TARGET_PREFIX}gcc:do_populate_sysroot")
        d.appendVarFlag("do_check", "depends", " virtual/${TARGET_PREFIX}compilerlibs:do_populate_sysroot")
}

do_check[depends] += "dejagnu-native:do_populate_sysroot expect-native:do_populate_sysroot"
do_check[depends] += "virtual/libc:do_populate_sysroot"
do_check[dirs] = "${B}"
do_check[nostamp] = "1"
do_check() {
    # need to inject CC and CXX as the target CC and CXX with sysroot
    oe_runmake -i ${MAKE_CHECK_TARGETS} \
        RUNTESTFLAGS=" \
            CC='${TARGET_PREFIX}gcc --sysroot=${STAGING_DIR_TARGET} ${TUNE_CCARGS}' \
            CXX='${TARGET_PREFIX}g++ --sysroot=${STAGING_DIR_TARGET} ${TUNE_CCARGS}' \
            "
}
addtask check after do_compile


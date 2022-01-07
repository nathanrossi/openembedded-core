inherit gnat
require gcc-configure-common.inc

EXTRA_OECONF_PATHS = " \
    --with-sysroot=/not/exist \
    --with-build-sysroot=${STAGING_DIR_TARGET} \
    "

setup_for_environment() {
    # Setup these vars for cross building only
    # ... because foo_FOR_TARGET apparently gets misinterpreted inside the
    # gcc build stuff when the build is producing a cross compiler - i.e.
    # when the 'current' target is the 'host' system, and the host is not
    # the target (because the build is actually making a cross compiler!)
    if [ "${BUILD_SYS}" != "${HOST_SYS}" ]; then
        export CC_FOR_TARGET="${CC}"
        export GCC_FOR_TARGET="${CC}"
        export CXX_FOR_TARGET="${CXX}"
        export GNATBIND_FOR_TARGET="${GNATBIND}"
        export GNATLINK_FOR_TARGET="${GNATLINK}"
        export GNATMAKE_FOR_TARGET="${GNATMAKE}"
        export AS_FOR_TARGET="${HOST_PREFIX}as"
        export LD_FOR_TARGET="${HOST_PREFIX}ld"
        export NM_FOR_TARGET="${HOST_PREFIX}nm"
        export AR_FOR_TARGET="${HOST_PREFIX}ar"
        export GFORTRAN_FOR_TARGET="gfortran"
        export RANLIB_FOR_TARGET="${HOST_PREFIX}ranlib"
    fi
    export CC_FOR_BUILD="${BUILD_CC}"
    export CXX_FOR_BUILD="${BUILD_CXX}"
    export CFLAGS_FOR_BUILD="${BUILD_CFLAGS}"
    export CPPFLAGS_FOR_BUILD="${BUILD_CPPFLAGS}"
    export CXXFLAGS_FOR_BUILD="${BUILD_CXXFLAGS}"
    export LDFLAGS_FOR_BUILD="${BUILD_LDFLAGS}"
    export CFLAGS_FOR_TARGET="${TARGET_CFLAGS}"
    export CPPFLAGS_FOR_TARGET="${TARGET_CPPFLAGS}"
    export CXXFLAGS_FOR_TARGET="${TARGET_CXXFLAGS}"
    export LDFLAGS_FOR_TARGET="${TARGET_LDFLAGS}"
}

do_configure () {
    setup_for_environment

    rm -rf ${B}/${TARGET_SYS}/libada/
    mkdir -p ${B}/${TARGET_SYS}/libada/
    cd ${B}/${TARGET_SYS}/libada/
    chmod a+x ${S}/libada/configure

    ${S}/libada/configure ${CONFIGUREOPTS} ${EXTRA_OECONF}
}

EXTRACONFFUNCS += "extract_stashed_builddir"
do_configure[depends] += "${COMPILERDEP}"

do_compile () {
    setup_for_environment

    cd ${B}/${TARGET_SYS}/libada/
    oe_runmake MULTIBUILDTOP=${B}/${TARGET_SYS}/libada/ libada
}

do_install () {
    cd ${B}/${TARGET_SYS}/libada/
    oe_runmake 'DESTDIR=${D}' MULTIBUILDTOP=${B}/${TARGET_SYS}/libada/ install


    # HACK: ?
    mkdir -p ${D}${libdir}/${TARGET_SYS}/gcc/${TARGET_SYS}/${BINV}
    mv ${D}${libdir}/gcc/${TARGET_SYS}/${BINV}/* ${D}${libdir}/${TARGET_SYS}/gcc/${TARGET_SYS}/${BINV}/

    # HACK: ?
    install ${B}/${TARGET_SYS}/gcc/ada/rts/libgnat-11.so ${D}${libdir}/${TARGET_SYS}/gcc/${TARGET_SYS}/${BINV}/adalib/

    chown -R root:root ${D}
}

INHIBIT_DEFAULT_DEPS = "1"
DEPENDS = "gcc-runtime gcc-cross-${TARGET_ARCH}"

BBCLASSEXTEND = "nativesdk"

PACKAGES = " \
    ${PN}-dbg \
    libada \
    libada-dev \
    libada-staticdev \
    "

LICENSE_${PN} = "GPL-3.0-with-GCC-exception"
LICENSE_${PN}-dev = "GPL-3.0-with-GCC-exception"
LICENSE_${PN}-dbg = "GPL-3.0-with-GCC-exception"

FILES_${PN} = "${libdir}/libada.so.*"
FILES_${PN}-dev = " \
    ${libdir}/libada*.so \
    ${libdir}/libada.spec \
    ${libdir}/libada.la \
    ${libdir}/gcc/${TARGET_SYS}/${BINV}/libadabegin.* \
    ${libdir}/gcc/${TARGET_SYS}/${BINV}/libcaf_single* \
    ${libdir}/gcc/${TARGET_SYS}/${BINV}/finclude/ \
    ${libdir}/gcc/${TARGET_SYS}/${BINV}/include/ \
    "
FILES_${PN}-staticdev = "${libdir}/libada.a"

INSANE_SKIP_${MLPREFIX}libada-dev = "staticdev"

do_package_write_ipk[depends] += "virtual/${MLPREFIX}libc:do_packagedata"
do_package_write_deb[depends] += "virtual/${MLPREFIX}libc:do_packagedata"
do_package_write_rpm[depends] += "virtual/${MLPREFIX}libc:do_packagedata"

python __anonymous () {
    f = d.getVar("ADA")
    if "ada" not in f:
        raise bb.parse.SkipRecipe("libada needs ada support to be enabled in the compiler")
}

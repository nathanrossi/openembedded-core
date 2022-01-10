
GNAT_RTS_DIR = "${STAGING_LIBDIR}/gcc/${TARGET_SYS}/11.2.0/"

export GNATBIND = "${HOST_PREFIX}gnatbind"
export GNATLINK = "${HOST_PREFIX}gnatlink"
export GNATMAKE = '${HOST_PREFIX}gnatmake --RTS="${GNAT_RTS_DIR}" ${TOOLCHAIN_OPTIONS} --GCC="${CC}" --GNATBIND="${GNATBIND}" --GNATLINK="${GNATLINK}"'
export GNATLS = "${HOST_PREFIX}gnatls"

export BUILD_GNATBIND = "${BUILD_PREFIX}gnatbind"
export BUILD_GNATLINK = "${BUILD_PREFIX}gnatlink"
export BUILD_GNATMAKE = '${BUILD_PREFIX}gnatmake --GCC="${BUILD_CC}" --GNATBIND="${BUILD_GNATBIND}" --GNATLINK="${BUILD_GNATLINK}"'
export BUILD_GNATLS = "${BUILD_PREFIX}gnatls"

# remap target to native (BUILD) values when recipe is native
GNATBIND:class-native = "${BUILD_GNATBIND}"
GNATLINK:class-native = "${BUILD_GNATLINK}"
GNATMAKE:class-native = "${BUILD_GNATMAKE}"
GNATLS:class-native = "${BUILD_GNATLS}"



export GNATBIND = "${HOST_PREFIX}gnatbind"
export GNATLINK = "${HOST_PREFIX}gnatlink"
export GNATMAKE = '${HOST_PREFIX}gnatmake --GCC=${CC} --GNATBIND="${GNATBIND}" --GNATLINK="${GNATLINK}"'
export GNATLS = '${HOST_PREFIX}gnatls'

export BUILD_GNATBIND = "${BUILD_PREFIX}gnatbind"
export BUILD_GNATLINK = "${BUILD_PREFIX}gnatlink"
export BUILD_GNATMAKE = '${BUILD_PREFIX}gnatmake --GCC=${BUILD_CC} --GNATBIND="${BUILD_GNATBIND}" --GNATLINK="${BUILD_GNATLINK}"'
export BUILD_GNATLS = '${BUILD_PREFIX}gnatls'


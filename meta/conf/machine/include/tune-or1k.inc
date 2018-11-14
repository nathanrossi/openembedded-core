DEFAULTTUNE ?= "or1k"

require conf/machine/include/or1k/arch-or1k.inc

AVAILTUNES += "or1k"
TUNE_FEATURES_tune-or1k = "or1k"
PACKAGE_EXTRA_ARCHS_tune-or1k = "${TUNE_PKGARCH}"

AVAILTUNES += "or1ksim"
TUNE_FEATURES_tune-or1ksim = "or1k cmov ror sign-extend setflag-imm shift-imm hard-multiply hard-divide"
PACKAGE_EXTRA_ARCHS_tune-or1ksim = "${TUNE_PKGARCH}"


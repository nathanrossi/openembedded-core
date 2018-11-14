# Architecture name
TUNE_ARCH = "or1k"

# Architecture feature and override
TUNEVALID[or1k] = "OpenRISC 1000"
MACHINEOVERRIDES =. "${@bb.utils.contains("TUNE_FEATURES", "or1k", "or1k:", "", d)}"

# General features
TUNEVALID[cmov] = "Enable l.cmov instruction"
TUNEVALID[ror] = "Enable l.rori instruction"
TUNEVALID[sign-extend] = "Enable sign-extension instructions"
TUNEVALID[setflag-imm] = "Enable set flag immediate instructions"
TUNEVALID[shift-imm] = "Enable shift and rotate immediate instructions"

# Feature compiler args
TUNE_CCARGS += "${@bb.utils.contains("TUNE_FEATURES", "cmov", "-mcmov", "", d)}"
TUNE_CCARGS += "${@bb.utils.contains("TUNE_FEATURES", "ror", "-mror", "", d)}"
TUNE_CCARGS += "${@bb.utils.contains("TUNE_FEATURES", "sign-extend", "-msext", "", d)}"
TUNE_CCARGS += "${@bb.utils.contains("TUNE_FEATURES", "setflag-imm", "-msfimm", "", d)}"
TUNE_CCARGS += "${@bb.utils.contains("TUNE_FEATURES", "shift-imm", "-mshftimm", "", d)}"


# math features
TUNEVALID[hard-multiply] = "Hardware multiply instructions"
TUNEVALID[hard-divide] = "Hardware divide instructions"

# Compiler args
TUNE_CCARGS += "${@bb.utils.contains('TUNE_FEATURES', 'hard-multiply', '-mhard-mul', '-msoft-mul', d)}"
TUNE_CCARGS += "${@bb.utils.contains('TUNE_FEATURES', 'hard-divide', '-mhard-div', '-msoft-div', d)}"

# default to soft FPU
TARGET_FPU = "fpu-soft"

# Feature package architecture formatting
TUNE_PKGARCH = "or1k"
TUNE_PKGARCH .= "${@bb.utils.contains("TUNE_FEATURES", "cmov", "c", "", d)}"
TUNE_PKGARCH .= "${@bb.utils.contains("TUNE_FEATURES", "ror", "r", "", d)}"
TUNE_PKGARCH .= "${@bb.utils.contains("TUNE_FEATURES", "sign-extend", "s", "", d)}"
TUNE_PKGARCH .= "${@bb.utils.contains("TUNE_FEATURES", "setflag-imm", "f", "", d)}"
TUNE_PKGARCH .= "${@bb.utils.contains("TUNE_FEATURES", "shift-imm", "i", "", d)}"
TUNE_PKGARCH .= "${@bb.utils.contains("TUNE_FEATURES", "hard-multiply", "-mul", "", d)}"
TUNE_PKGARCH .= "${@bb.utils.contains("TUNE_FEATURES", "hard-divide", "-div", "", d)}"


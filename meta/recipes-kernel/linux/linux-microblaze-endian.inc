
do_configure_prepend_microblaze () {
    if [ "${TARGET_ARCH}" = "microblaze" ]; then
        echo "CONFIG_CPU_BIG_ENDIAN=y" >> ${B}/.config
    fi
}


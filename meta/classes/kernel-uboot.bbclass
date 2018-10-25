uboot_prep_kimage() {
	SUFFIX=$1

	if [ -e arch/${ARCH}/boot/compressed/vmlinux$SUFFIX ]; then
		vmlinux_path="arch/${ARCH}/boot/compressed/vmlinux$SUFFIX"
		linux_suffix=""
		linux_comp="none"
	elif [ -e arch/${ARCH}/boot/Image$SUFFIX ] ; then
		vmlinux_path="vmlinux$SUFFIX"
		linux_suffix=".gz"
		linux_comp="gzip"
	elif [ -e arch/${ARCH}/boot/vmlinuz.bin$SUFFIX ]; then
		rm -f linux.bin
		cp -l arch/${ARCH}/boot/vmlinuz.bin$SUFFIX linux.bin$SUFFIX
		vmlinux_path=""
		linux_suffix=""
		linux_comp="none"
	else
		vmlinux_path="vmlinux$SUFFIX"
		linux_suffix=".gz"
		linux_comp="gzip"
	fi

	[ -n "${vmlinux_path}" ] && ${OBJCOPY} -O binary -R .note -R .comment -S "${vmlinux_path}" linux.bin$SUFFIX

	if [ "${linux_comp}" != "none" ] ; then
		gzip -9 linux.bin$SUFFIX
		mv -f "linux.bin$SUFFIX${linux_suffix}" linux.bin$SUFFIX
	fi

	echo "${linux_comp}"
}

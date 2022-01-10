SUMMARY = "Ada example hello world"
LICENSE = "MIT"

inherit gnat

do_configure[noexec] = "1"

DEPENDS += "libada"

do_compile() {
    cat << __EOF > ${WORKDIR}/hello-world.adb
with Text_IO; use Text_IO;
procedure hello is
begin
    Put_Line("Hello world!");
end hello;
__EOF
    ${GNATMAKE}  -o hello-world ${WORKDIR}/hello-world.adb
}

BBCLASSEXTEND += "native nativesdk"


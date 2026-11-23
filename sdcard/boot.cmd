# Modero DCD-U-Boot boot script — load our kernel + DTB and boot Debian.
setenv bootargs console=ttymxc0,115200 root=/dev/mmcblk0p1 rootwait rw
echo "== Modero: loading /boot/zImage + dtb from mmc ${mmcdev}:1 =="
load mmc ${mmcdev}:1 ${loadaddr} /boot/zImage
load mmc ${mmcdev}:1 ${fdt_addr} /boot/imx6q-sabresd.dtb
echo "== booting =="
bootz ${loadaddr} - ${fdt_addr}

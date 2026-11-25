setenv bootargs console=ttymxc0,115200 root=/dev/mmcblk1p2 rootwait rw
echo "MODERO: load kernel + dtb, disable phantom SD write-protect, boot"
fatload mmc 1:1 0x12000000 zImage
fatload mmc 1:1 0x18000000 imx6q-sabresd.dtb
fdt addr 0x18000000
fdt resize
fdt set /soc/bus@2100000/mmc@2194000 disable-wp
bootz 0x12000000 - 0x18000000

MODULES "y"
BLK_DEV_INITRD "y"

RTLWIFI_USB:satisfy { y, recursive = true }
VIRTIO_MMIO "y"
VIRTIO_MEM:satisfy { m, recursive = true }

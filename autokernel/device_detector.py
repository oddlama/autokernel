from . import log

import re
import glob

class PciDevice:
    """
    A class used to parse all information from a modalias file
    related to a pci device.
    """
    modalias_regex = '([0-9a-z]*):v([0-9A-Z*]*)d([0-9A-Z*]*)sv([0-9A-Z*]*)sd([0-9A-Z*]*)bc([0-9A-Z*]*)sc([0-9A-Z*]*)i([0-9A-Z*]*)'

    def __init__(self, modalias):
        self.modalias = modalias.replace('*', '')

        m = re.match(PciDevice.modalias_regex, self.modalias)
        if not m:
            raise Exception("Could not parse modalias for PciDevice")

        self.vendor = m.group(2)
        self.device = m.group(3)
        self.subvendor = m.group(4)
        self.subdevice = m.group(5)
        self.bus_class = m.group(6)
        self.bus_subclass = m.group(7)
        self.interface = m.group(8)

    def __str__(self):
        return "PciDevice{{vendor={}, device={}, subvendor={}, subdevice={}, bus_class={}, bus_subclass={}, interface={}}}".format(
            self.vendor, self.device, self.subvendor, self.subdevice, self.bus_class, self.bus_subclass, self.interface)

class DeviceDetector:
    """
    This detector parses information in the kernel's sysfs to detect
    devices attached to available buses. It exposes this information in
    a common format so it can be compared to a option database later.
    """

    def __init__(self):
        """
        Initialize the detector and collects device information from the
        different buses on the sysfs.
        """

        log.info("Inspecting sysfs to find devices")
        self._detect_pci_devices()
        self._detect_usb_devices()

    def _detect_pci_devices(self):
        log.info("Parsing PCI device nodes")

        self.pci_devices = [PciDevice(modalias) for modalias \
            in self._read_modaliases('/sys/bus/pci/devices/*/modalias')]

        log.info(" - found {} devices".format(len(self.pci_devices)))
        if log.verbose_output:
            for device in self.pci_devices:
                log.verbose(" - {}".format(device))

    def _detect_usb_devices(self):
        log.info("Parsing USB device nodes")

        self.usb_devices = [UsbDevice(modalias) for modalias \
            in self._read_modaliases('/sys/bus/usb/devices/*/modalias')]

        log.info(" - found {} devices".format(len(self.usb_devices)))
        if log.verbose_output:
            for device in self.usb_devices:
                log.verbose(" - {}".format(device))

    def _read_modaliases(self, path):
        modaliases = set()
        for file_name in glob.glob(path):
            with open(file_name, 'r', encoding='utf-8') as file:
                modaliases.update(file.read().splitlines())
        return modaliases

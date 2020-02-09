from . import log

import re
import glob

def create_modalias_regex(options):
    """
    Creates a regex to match the given modalias options
    """
    modalias_regex = '([0-9a-z]*):'
    for _, alias in options:
        modalias_regex += '{}(?P<{}>[0-9A-Z*]*)'.format(alias, alias)
    return re.compile(modalias_regex)

class ModaliasDevice:
    """
    A base class used for devices classes which get their information
    by parsing a modalias file.
    """

    def __init__(self, modalias):
        """
        Parses the modalias line and initializes device information
        """

        # Save modalias information
        self.modalias = modalias

        # Create regex to Save modalias information
        modalias_options = self._get_modalias_options()
        modalias_regex = self._create_modalias_regex(modalias_options)

        # Match the modalias against the regex
        matches = modalias_regex.match(self.modalias)
        if not matches:
            raise Exception("Could not parse modalias")

        # Assign attributes from the match groups
        for i, (option, alias) in enumerate(modalias_options):
            setattr(self, option, matches.group(alias))

    def __str__(self):
        """
        Returns a string representation of this object
        """

        name = "{}{{".format(self.__class__.__name__)
        name += ', '.join(['{}={}'.format(option, getattr(self, option)) \
                    for option, alias in self._get_modalias_options()])
        name += '}'
        return name

    @classmethod
    def _get_modalias_options(cls):
        """
        Returns the modalias options of the derived class
        """
        return cls.modalias_options

    @classmethod
    def _create_modalias_regex(cls, modalias_options):
        """
        Creates (or retrieves) a compiled regex for the classes' modalias options
        """
        # If we have previously compiled a regex, return it
        if hasattr(cls, 'modalias_regex'):
            return cls.modalias_regex

        # Otherwise create a new regex and save it in the derived class
        cls.modalias_regex = create_modalias_regex(modalias_options)
        return cls.modalias_regex

class PciDevice(ModaliasDevice):
    modalias_options = [
            ('vendor', 'v'),
            ('device', 'd'),
            ('subvendor', 'sv'),
            ('subdevice', 'sd'),
            ('bus_class', 'bc'),
            ('bus_subclass', 'sc'),
            ('interface', 'i'),
        ]

class UsbDevice(ModaliasDevice):
    modalias_options = [
            ('device_vendor', 'v'),
            ('device_product', 'p'),
            ('bcddevice', 'd'),
            ('device_class', 'dc'),
            ('device_subclass', 'dsc'),
            ('device_protocol', 'dp'),
            ('interface_class', 'ic'),
            ('interface_subclass', 'isc'),
            ('interface_protocol', 'ip'),
        ]

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
        """
        Parses devices from the pci sysfs nodes
        """

        log.info("Parsing PCI device nodes")

        self.pci_devices = [PciDevice(modalias) for modalias \
            in self._read_modaliases('/sys/bus/pci/devices/*/modalias')]

        log.info(" - found {} devices".format(len(self.pci_devices)))
        if log.verbose_output:
            for device in self.pci_devices:
                log.verbose(" - {}".format(device))

    def _detect_usb_devices(self):
        """
        Parses devices from the usb sysfs nodes
        """

        log.info("Parsing USB device nodes")

        self.usb_devices = [UsbDevice(modalias) for modalias \
            in self._read_modaliases('/sys/bus/usb/devices/*/modalias')]

        log.info(" - found {} devices".format(len(self.usb_devices)))
        if log.verbose_output:
            for device in self.usb_devices:
                log.verbose(" - {}".format(device))

    def _read_modaliases(self, path):
        """
        Reads all modaliases from the given glob path
        """

        modaliases = set()
        for file_name in glob.glob(path):
            with open(file_name, 'r', encoding='utf-8') as file:
                modaliases.update(file.read().splitlines())
        return modaliases

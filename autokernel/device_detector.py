from . import log

import re
import glob

def create_modalias_regex(options):
    """
    Creates a regex to match the given modalias options
    """
    modalias_regex = '([0-9a-z]*):'
    for alias, _ in options:
        modalias_regex += '{}([0-9A-Z*]*)'.format(alias, alias)
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
        for i, (alias, option) in enumerate(modalias_options):
            setattr(self, option, matches.group(i + 2))

    def __str__(self):
        """
        Returns a string representation of this object
        """

        name = "{}{{".format(self.__class__.__name__)
        name += ', '.join(['{}={}'.format(option, getattr(self, option)) \
                    for alias, option in self._get_modalias_options()])
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

    @classmethod
    def _get_sysfs_path_to_modaliases(cls):
        """
        Returns a globbable path to all modalias files in the kernel sysfs for the device type
        """
        return cls.modalias_sysfs_path

    @staticmethod
    def preprocess_modaliases(modaliases):
        """
        Allows a derived class to modify all modaliases before parsing, by
        overriding this method
        """
        return modaliases

    @classmethod
    def read_modaliases(cls):
        """
        Reads all modaliases from the given glob path
        """

        modaliases = set()
        for file_name in glob.glob(cls._get_sysfs_path_to_modaliases()):
            # Open modalias file
            with open(file_name, 'r', encoding='utf-8') as file:
                # Iterate over lines
                for line in file.readlines():
                    # Strip trailing whitespace
                    line = line.strip()
                    if line:
                        # Only add if line not empty
                        modaliases.add(line)

        # Return modaliases, after giving derived classes a chance to modify them
        return cls.preprocess_modaliases(modaliases)

    @classmethod
    def detect_devices(cls):
        log.info("Parsing '{}'".format(cls.modalias_sysfs_path))
        devices = [cls(modalias) for modalias in cls.read_modaliases()]

        # Log all devices, if we are in verbose mode
        log.info(" - found {} devices".format(len(devices)))
        if log.verbose_output:
            for d in devices:
                log.verbose(" - {}".format(d))

        return devices


class PciDevice(ModaliasDevice):
    modalias_sysfs_path = '/sys/bus/pci/devices/*/modalias'
    modalias_options = [
            ('v' , 'vendor'      ),
            ('d' , 'device'      ),
            ('sv', 'subvendor'   ),
            ('sd', 'subdevice'   ),
            ('bc', 'bus_class'   ),
            ('sc', 'bus_subclass'),
            ('i' , 'interface'   ),
        ]

class UsbDevice(ModaliasDevice):
    modalias_sysfs_path = '/sys/bus/usb/devices/*/modalias'
    modalias_options = [
            ('v'  , 'device_vendor'     ),
            ('p'  , 'device_product'    ),
            ('d'  , 'bcddevice'         ),
            ('dc' , 'device_class'      ),
            ('dsc', 'device_subclass'   ),
            ('dp' , 'device_protocol'   ),
            ('ic' , 'interface_class'   ),
            ('isc', 'interface_subclass'),
            ('ip' , 'interface_protocol'),
        ]

class AcpiDevice(ModaliasDevice):
    modalias_sysfs_path = '/sys/bus/acpi/devices/*/modalias'
    modalias_options = [
            ('' , 'id'),
        ]

    @staticmethod
    def preprocess_modaliases(modaliases):
        return []

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

        # A list with all device classes
        device_classes = [
            PciDevice,
            UsbDevice,
            AcpiDevice,
        ]

        # For each device class, detect devices in sysfs.
        self.devices = []
        for cls in device_classes:
            self.devices.extend(cls.detect_devices())

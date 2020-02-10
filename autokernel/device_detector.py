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
            val = matches.group(i + 2)
            if not val:
                raise Exception("Modalias line is missing information for this device type")
            setattr(self, option, val)

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
        # Create list of devices from modaliases
        devices = []
        for modalias in cls.read_modaliases():
            try:
                devices.append(cls(modalias))
            except Exception:
                pass

        # Log all devices, if we are in verbose mode
        log.info("Found {:2d} devices in '{}'".format(len(devices), cls.modalias_sysfs_path))
        if log.verbose_output:
            for d in devices:
                log.verbose(" - {}".format(d))

        return devices


class AcpiDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse acpi devices
    """

    modalias_sysfs_path = '/sys/bus/acpi/devices/*/modalias'
    modalias_options = [
            ('id', 'id'),
        ]

    @staticmethod
    def preprocess_modaliases(original_modaliases):
        """
        Contents of acpi modalias files can contain several ids per device.
        Split these to create one acpi device per id.
        """
        modaliases = set()
        for m in original_modaliases:
            if not m.startswith('acpi:'):
                continue

            # Split on ':' and filter empty results
            acpi_ids = filter(None, m[len('acpi:'):].split(':'))
            for id in acpi_ids:
                modaliases.add('acpi:id{}'.format(id))

        return modaliases

class HdaudioDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse hdaudio devices
    """

    modalias_sysfs_path = '/sys/bus/hdaudio/devices/*/modalias'
    modalias_options = [
            ('v', 'vendor'     ),
            ('r', 'revision'   ),
            ('a', 'api_version'),
        ]

class HidDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse hid devices
    """

    modalias_sysfs_path = '/sys/bus/hid/devices/*/modalias'
    modalias_options = [
            ('b', 'bus'        ),
            ('v', 'vendor'     ),
            ('p', 'product'    ),
            ('d', 'driver_data'),
        ]

class PciDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse pci devices
    """

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

class PcmciaDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse pcmcia devices
    """

    modalias_sysfs_path = '/sys/bus/pcmcia/devices/*/modalias'
    modalias_options = [
            ('m'  , 'manf_id'  ),
            ('c'  , 'card_id'  ),
            ('f'  , 'func_id'  ),
            ('fn' , 'function' ),
            ('pfn', 'device_no'),
            ('pa' , 'prod_id_1'),
            ('pb' , 'prod_id_2'),
            ('pc' , 'prod_id_3'),
            ('pd' , 'prod_id_4'),
        ]

class PlatformDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse platform devices
    """

    modalias_sysfs_path = '/sys/bus/platform/devices/*/modalias'
    modalias_options = [
            ('', 'name'),
        ]

class SdioDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse sdio devices
    """

    modalias_sysfs_path = '/sys/bus/sdio/devices/*/modalias'
    modalias_options = [
            ('c', 'class'),
            ('v', 'vendor'),
            ('d', 'device'),
        ]

class SerioDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse serio devices
    """

    modalias_sysfs_path = '/sys/bus/serio/devices/*/modalias'
    modalias_options = [
            ('ty' , 'type' ),
            ('pr' , 'proto'),
            ('id' , 'id'   ),
            ('ex' , 'extra'),
        ]

class UsbDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse usb devices
    """

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

class VirtioDevice(ModaliasDevice):
    """
    Specializes ModaliasDevice to parse virtio devices
    """

    modalias_sysfs_path = '/sys/bus/virtio/devices/*/modalias'
    modalias_options = [
            ('v', 'vendor'),
            ('d', 'device'),
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

        log.info("Parsing modalias information in sysfs")

        # A list with all device classes
        device_classes = [
            AcpiDevice,
            HdaudioDevice,
            HidDevice,
            PciDevice,
            PcmciaDevice,
            PlatformDevice,
            SdioDevice,
            SerioDevice,
            UsbDevice,
            VirtioDevice,
            # TODO PnpDevice (parse id file, no special regex)
            # TODO I2cDevice (parse ...)
        ]

        # For each device class, detect devices in sysfs.
        self.devices = []
        for cls in device_classes:
            self.devices.extend(cls.detect_devices())

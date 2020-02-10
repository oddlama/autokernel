from . import log

import re
import glob
import subprocess

class Node:
    """
    A base class used for all nodes
    """

    @classmethod
    def detect_nodes(cls):
        """
        Detects and returns a list of all nodes on the system.
        """
        raise Exception("missing implementation for detect_nodes() on derived class '{}'".format(cls.__name__))

    @classmethod
    def log_nodes(cls, nodes):
        # Log all nodes, if we are in verbose mode
        log.info("Found {:2d} {} nodes".format(len(nodes), cls.node_type))
        if log.verbose_output:
            for n in nodes:
                log.verbose(" - {}".format(n))

class SysfsNode(Node):
    """
    A base class used for nodes which get their information
    by parsing a sysfs file.
    """

    def __init__(self, sysfs_line):
        """
        Parses the given sysfs line and matches it against the regex to extract information
        """

        # Create regex to extract information
        options = self._get_options()
        regex = self._create_regex(options)

        # Match the sysfs line against the regex
        matches = regex.match(sysfs_line)
        if not matches:
            raise Exception("Could not parse sysfs line")

        # Assign attributes from the match groups
        for alias, option in options:
            val = matches.group(option)
            if not val:
                raise Exception("Sysfs line is missing information for this parser")
            setattr(self, option, val)

    def __str__(self):
        """
        Returns a string representation of this object
        """

        name = "{}{{".format(self.__class__.__name__)
        name += ', '.join(['{}={}'.format(option, getattr(self, option)) \
                    for alias, option in self._get_options()])
        name += '}'
        return name

    @classmethod
    def _get_options(cls):
        """
        Returns the options of the derived class
        """
        return cls.options

    @classmethod
    def create_regex(cls, options):
        raise Exception("missing implementation for create_regex() on derived class '{}'".format(cls.__name__))

    @classmethod
    def _create_regex(cls, options):
        """
        Creates (or retrieves) a compiled regex for the classes' options
        """
        # If we have previously compiled a regex, return it
        if hasattr(cls, 'regex'):
            return cls.regex

        # Otherwise create a new regex and save it in the derived class
        cls.regex = cls.create_regex(options)
        return cls.regex

    @classmethod
    def _get_sysfs_path(cls):
        """
        Returns a globbable path to all files in the kernel sysfs for the node type.
        If the property is not set, it returns cls.default_sysfs_path()
        """
        if hasattr(cls, 'sysfs_path'):
            return cls.sysfs_path

        return cls.default_sysfs_path()

    @classmethod
    def default_sysfs_path(cls):
        raise Exception("missing implementation for default_sysfs_path() on derived class '{}'".format(cls.__name__))

    @staticmethod
    def preprocess_sysfs_lines(sysfs_lines):
        """
        Allows a derived class to modify all lines before parsing, by
        overriding this method
        """
        return sysfs_lines

    @classmethod
    def read_sysfs_lines(cls):
        """
        Reads all lines from the given glob path
        """

        lines = set()
        for file_name in glob.glob(cls._get_sysfs_path()):
            # Open sysfs file
            with open(file_name, 'r', encoding='utf-8') as file:
                # Iterate over lines
                for line in file.readlines():
                    # Strip trailing whitespace
                    line = line.strip()
                    if line:
                        # Only add if line not empty
                        lines.add(line)

        # Return lines, after giving derived classes a chance to modify them
        return cls.preprocess_sysfs_lines(lines)

    @classmethod
    def detect_nodes(cls):
        # Create list of nodes from sysfs lines
        nodes = []
        for sysfs_line in cls.read_sysfs_lines():
            try:
                nodes.append(cls(sysfs_line))
            except Exception:
                pass

        cls.log_nodes(nodes)
        return nodes

class ModaliasNode(SysfsNode):
    """
    A base class used for devices classes which get their information
    by parsing a modalias file.
    """

    @classmethod
    def default_sysfs_path(cls):
        """
        Get the default sysfs path for derived nodes
        """
        return '/sys/bus/{}/devices/*/modalias'.format(cls.node_type)

    @classmethod
    def create_regex(cls, options):
        """
        Creates a regex to match the given modalias options
        """
        regex = '([0-9a-z]*):'
        for alias, option in options:
            regex += '{}(?P<{}>[0-9A-Z*]*)'.format(alias, option)
        return re.compile(regex)

class AcpiDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse acpi devices
    """

    node_type = 'acpi'
    options = [
            ('id', 'id'),
        ]

    @staticmethod
    def preprocess_sysfs_lines(sysfs_lines):
        """
        Contents of acpi modalias files can contain several ids per device.
        Split these to create one acpi device per id.
        """
        modaliases = set()
        for l in sysfs_lines:
            if not l.startswith('acpi:'):
                continue

            # Split on ':' and filter empty results
            acpi_ids = filter(None, l[len('acpi:'):].split(':'))
            for id in acpi_ids:
                modaliases.add('acpi:id{}'.format(id))

        return modaliases

class HdaudioDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse hdaudio devices
    """

    node_type = 'hdaudio'
    options = [
            ('v', 'vendor'     ),
            ('r', 'revision'   ),
            ('a', 'api_version'),
        ]

class HidDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse hid devices
    """

    node_type = 'hid'
    options = [
            ('b', 'bus'        ),
            ('v', 'vendor'     ),
            ('p', 'product'    ),
            ('d', 'driver_data'),
        ]

class PciDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse pci devices
    """

    node_type = 'pci'
    options = [
            ('v' , 'vendor'      ),
            ('d' , 'device'      ),
            ('sv', 'subvendor'   ),
            ('sd', 'subdevice'   ),
            ('bc', 'bus_class'   ),
            ('sc', 'bus_subclass'),
            ('i' , 'interface'   ),
        ]

class PcmciaDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse pcmcia devices
    """

    node_type = 'pcmcia'
    options = [
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

class PlatformDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse platform devices
    """

    node_type = 'platform'
    options = [
            ('', 'name'),
        ]

class SdioDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse sdio devices
    """

    node_type = 'sdio'
    options = [
            ('c', 'class'),
            ('v', 'vendor'),
            ('d', 'device'),
        ]

class SerioDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse serio devices
    """

    node_type = 'serio'
    options = [
            ('ty' , 'type' ),
            ('pr' , 'proto'),
            ('id' , 'id'   ),
            ('ex' , 'extra'),
        ]

class UsbDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse usb devices
    """

    node_type = 'usb'
    options = [
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

class VirtioDevice(ModaliasNode):
    """
    Specializes ModaliasNode to parse virtio devices
    """

    node_type = 'virtio'
    options = [
            ('v', 'vendor'),
            ('d', 'device'),
        ]

class PnpDevice(SysfsNode):
    """
    Specializes SysfsNode to parse pnp devices
    """

    node_type = 'pnp'
    sysfs_path = '/sys/bus/pnp/devices/*/id'
    options = [
            ('n', 'name'),
        ]

    @classmethod
    def create_regex(cls, options):
        """
        Creates a regex to match the given pnp id
        """
        regex = ''
        return re.compile('')
        for alias, _ in options:
            regex += '(?P<{}>.*)'.format(alias)
        return re.compile(regex)

class I2cDevice(SysfsNode):
    """
    Specializes SysfsNode to parse i2c devices
    """

    node_type = 'i2c'
    sysfs_path = '/sys/bus/i2c/devices/*/name'
    options = [
            ('n', 'name'),
        ]

    @classmethod
    def create_regex(cls, options):
        """
        Creates a regex to match the given i2c name
        """
        regex = ''
        return re.compile('')
        for alias, _ in options:
            regex += '(?P<{}>.*)'.format(alias)
        return re.compile(regex)

class FsTypeNode(Node):
    """
    Specializes Node to gather used filesystems
    """
    node_type = 'filesystem'

    def __init__(self, fstype):
        """
        Initialize a fstype node
        """

        self.fstype = fstype

    def __str__(self):
        """
        Returns a string representation of this object
        """

        return 'FsTypeNode{{fstype={}}}'.format(self.fstype)

    @classmethod
    def detect_nodes(cls):
        fstypes = subprocess.run(['findmnt', '-A', '-n', '-o', 'FSTYPE'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip().split('\n')

        # Create list of nodes from fstypes
        nodes = []
        for fstype in set(fstypes):
            try:
                nodes.append(FsTypeNode(fstype))
            except Exception:
                pass

        cls.log_nodes(nodes)
        return nodes

class NodeDetector:
    """
    This detector parses information in the kernel's sysfs to detect
    devices attached to available buses, and other kernel configuration related
    information on the system. It exposes this information in
    a common format so it can be compared to a option database later.
    """

    def __init__(self):
        """
        Initialize the detector and collects system information.
        """

        log.info("Gathering system information")

        # A list with all device classes
        node_classes = [
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
            PnpDevice,
            I2cDevice,
            FsTypeNode,
        ]

        # For each node class, detect nodes in sysfs.
        self.nodes = []
        for cls in node_classes:
            self.nodes.extend(cls.detect_nodes())

from . import log
from .subsystem import Subsystem

import re
import glob
import subprocess
from pathlib import Path

class NodeParserException(Exception):
    pass

class Node:
    """
    A base class used for all nodes. Must expose a self.data member which is either an instance
    of the correct node type for the used subsystem (See Subsystem.create_node()), or a list of
    said type (to represent multiple nodes).
    """

    @classmethod
    def detect_nodes(cls):
        """
        Detects and returns a list of all nodes on the system.
        """
        raise NodeParserException("missing implementation for detect_nodes() on derived class '{}'".format(cls.__name__))

    @classmethod
    def log_nodes(cls, nodes):
        # Log all nodes, if we are in verbose mode
        log.info("Found {:2d} {} nodes".format(len(nodes), cls.node_type))
        if log.verbose_output:
            for n in nodes:
                log.verbose(" - {}".format(n))

    def __str__(self):
        """
        Returns a string representation of this object
        """
        if type(self.data) is list:
            return '[' + ', '.join(self.data) + ']'
        return str(self.data)

class SysfsNode(Node):
    """
    A base class used for nodes which get their information
    by parsing a sysfs file.
    """

    @classmethod
    def get_sysfs_files(cls):
        """
        Returns all files in the sysfs to parse.
        """
        if hasattr(cls, 'sysfs_path'):
            return glob.glob(cls.sysfs_path)

        raise Exception("Missing sysfs_path or get_sysfs_files() implementation on derived class {}".format(cls.__name__))

    @classmethod
    def read_sysfs_lines(cls):
        """
        Reads all lines from the given glob path
        """

        lines = set()
        for file_name in cls.get_sysfs_files():
            # Open sysfs file
            with open(file_name, 'r', encoding='utf-8') as file:
                # Iterate over lines
                for line in file:
                    # Strip trailing whitespace
                    line = line.strip()
                    if line:
                        # Only add if line is not empty
                        lines.add(line)

        # Return lines, after giving derived classes a chance to modify them
        return lines

    @classmethod
    def detect_nodes(cls):
        # Create list of nodes from sysfs lines
        nodes = []
        for sysfs_line in cls.read_sysfs_lines():
            try:
                nodes.append(cls(sysfs_line))
            except NodeParserException as e:
                log.verbose(repr(e))

        cls.log_nodes(nodes)
        return nodes

def create_modalias_token_parser(subsystem, subsystem_regex_str, options):
    class Data:
        def __init__(self, modalias):
            """
            Matches the modalias against the given options and extracts the data.
            """

            # Match the sysfs line against the regex
            m = Data._get_regex().match(modalias)
            if not m:
                raise NodeParserException("Could not parse sysfs line")

            # Assign attributes from the match groups
            for option in options:
                val = m.group(option[1])
                if not val:
                    raise NodeParserException("Could not match modalias for parser '{}'".format(subsystem_regex_str))
                setattr(self, option[1], val)

        @staticmethod
        def _get_regex():
            """
            Gets or creates a regex to match the given modalias options
            """

            if not hasattr(Data, 'regex'):
                regex = '{}:'.format(subsystem_regex_str)
                for option in options:
                    alias = option[0]
                    optname = option[1]
                    part_regex = "[0-9A-Z*]*" if len(option) <= 2 else option[2]
                    regex += '{}(?P<{}>{})'.format(alias, optname, part_regex)
                Data.regex = re.compile(regex)

            return Data.regex

    return Data

def create_modalias_split_parser(subsystem, subsystem_str, delim):
    class Data:
        def __init__(self, modalias):
            """
            Extracts all fields from the modalias line by splitting on delim
            """

            self.values = filter(None, modalias[len(subsystem_str) + 1:].split(delim))

    return Data

class ModaliasNode(SysfsNode):
    """
    A base class used for devices classes which get their information
    by parsing a modalias file.
    """

    node_type = 'modalias'
    data_types = {
        'acpi': create_modalias_split_parser(Subsystem.acpi, 'acpi', ':'),
        'hdaudio': create_modalias_token_parser(Subsystem.hda, 'hdaudio', [
                ('v', 'vendor'     ),
                ('r', 'revision'   ),
                ('a', 'api_version'),
            ]),
        'hid': create_modalias_token_parser(Subsystem.hid, 'hid', [
                ('b', 'bus'        ),
                ('v', 'vendor'     ),
                ('p', 'product'    ),
                ('d', 'driver_data'),
            ]),
        'input': create_modalias_token_parser(Subsystem.input, 'input', [
                ('b',  'bustype'),
                ('v',  'vendor' ),
                ('p',  'product'),
                ('e',  'version'),
                ('-e', 'list',   '.*'),
            ]),
        'pci': create_modalias_token_parser(Subsystem.pci, 'pci', [
                ('v' , 'vendor'      ),
                ('d' , 'device'      ),
                ('sv', 'subvendor'   ),
                ('sd', 'subdevice'   ),
                ('bc', 'bus_class'   ),
                ('sc', 'bus_subclass'),
                ('i' , 'interface'   ),
            ]),
        'pcmcia': create_modalias_token_parser(Subsystem.pcmcia, 'pcmcia', [
                ('m'  , 'manf_id'  ),
                ('c'  , 'card_id'  ),
                ('f'  , 'func_id'  ),
                ('fn' , 'function' ),
                ('pfn', 'device_no'),
                ('pa' , 'prod_id_1'),
                ('pb' , 'prod_id_2'),
                ('pc' , 'prod_id_3'),
                ('pd' , 'prod_id_4'),
            ]),
        'platform': create_modalias_token_parser(Subsystem.platform, 'platform', [
                ('', 'name'), # Empty alias '' is used to match whole rest of line
            ]),
        'sdio': create_modalias_token_parser(Subsystem.sdio, 'sdio', [
                ('c', 'class' ),
                ('v', 'vendor'),
                ('d', 'device'),
            ]),
        'serio': create_modalias_token_parser(Subsystem.serio, 'serio', [
                ('ty' , 'type' ),
                ('pr' , 'proto'),
                ('id' , 'id'   ),
                ('ex' , 'extra'),
            ]),
        'usb': create_modalias_token_parser(Subsystem.usb, 'usb', [
                ('v'  , 'device_vendor'     ),
                ('p'  , 'device_product'    ),
                ('d'  , 'bcddevice'         ),
                ('dc' , 'device_class'      ),
                ('dsc', 'device_subclass'   ),
                ('dp' , 'device_protocol'   ),
                ('ic' , 'interface_class'   ),
                ('isc', 'interface_subclass'),
                ('ip' , 'interface_protocol'),
            ]),
        'virtio': create_modalias_token_parser(Subsystem.virtio, 'virtio', [
                ('v', 'vendor'),
                ('d', 'device'),
            ]),
        }

    def __init__(self, modalias):
        """
        Parses the given modalias
        """

        # Extract subsystem name from modalias
        self.modalias_subsystem = modalias[:modalias.index(':')]

        # If a data_type exists, create it to parse the modalias
        if self.modalias_subsystem not in self.data_types:
            raise NodeParserException("No parser for modalias subsystem '{}'".format(self.modalias_subsystem))
        self.data = self.data_types[self.modalias_subsystem](modalias)

    @classmethod
    def get_sysfs_files(cls):
        """
        Finds and returns all modalias files in /sys
        """

        # We use find here, because python raises an OSError when it reaches efivars directory. Probably
        return filter(None, [i.decode('utf-8') for i in subprocess.run(['find', '/sys', '-type', 'f', '-name', 'modalias', '-print0'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.split(b'\0')])

class PnpNode(SysfsNode):
    """
    Specializes SysfsNode to parse pnp devices
    """

    node_type = 'pnp'
    sysfs_path = '/sys/bus/pnp/devices/*/id'

    def __init__(self, sysfs_line):
        """
        Initialize pnp node
        """
        self.data = Subsystem.pnp.create_node({'id': sysfs_line})

class I2cNode(SysfsNode):
    """
    Specializes SysfsNode to parse i2c devices
    """

    node_type = 'i2c'
    sysfs_path = '/sys/bus/i2c/devices/*/name'

    def __init__(self, sysfs_line):
        """
        Initialize i2c node
        """
        self.data = Subsystem.i2c.create_node({'name': sysfs_line})

class FsTypeNode(Node):
    """
    Specializes Node to gather used filesystems
    """
    node_type = 'filesystem'

    def __init__(self, fstype):
        """
        Initialize fstype node
        """
        self.data = Subsystem.fs.create_node({'fstype': fstype})

    @classmethod
    def detect_nodes(cls):
        fstypes = subprocess.run(['findmnt', '-A', '-n', '-o', 'FSTYPE'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip().split('\n')

        # Create list of nodes from fstypes
        nodes = []
        for fstype in set(fstypes):
            try:
                nodes.append(FsTypeNode(fstype))
            except NodeParserException as e:
                log.verbose(repr(e))

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
            ModaliasNode,
            PnpNode,
            I2cNode,
            FsTypeNode,
        ]

        # For each node class, detect nodes in sysfs.
        self.nodes = []
        for cls in node_classes:
            self.nodes.extend(cls.detect_nodes())

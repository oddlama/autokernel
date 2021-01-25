from . import log
from .subsystem import Subsystem

import re
import glob
import subprocess

class NodeParserException(Exception):
    pass

class Node:
    """
    A base class used for all nodes. Must expose a self.data member which is either an instance
    of the correct node type for the used subsystem (See Subsystem.create_node()), or a list of
    said type (to represent multiple nodes).
    """

    node_type = None
    nodes = [] # Must be overwritten

    @classmethod
    def detect_nodes(cls):
        """
        Detects and returns a list of all nodes on the system.
        """
        raise NodeParserException("missing implementation for detect_nodes() on derived class '{}'".format(cls.__name__))

    @classmethod
    def log_nodes(cls, nodes):
        # Log all nodes, if we are in verbose mode
        log.info("  {:3d} {} nodes".format(len(nodes), cls.node_type))
        for n in nodes:
            log.verbose(" - {}".format(n))

    def __str__(self):
        """
        Returns a string representation of this object
        """
        return '[' + ', '.join([str(i) for i in self.nodes]) + ']'

class LineParserNode(Node):
    """
    A node superclass for line based parsing
    """
    @classmethod
    def get_lines(cls):
        """
        Returns an iterable of lines to parse
        """
        raise ValueError("Missing get_lines() method implementation on derived class {}".format(cls.__name__))

    @classmethod
    def detect_nodes(cls):
        # Create list of nodes from lines
        nodes = []
        for line in cls.get_lines():
            try:
                nodes.append(cls(line))
            except NodeParserException as e:
                log.verbose(str(e))

        cls.log_nodes(nodes)
        return nodes

class SysfsNode(LineParserNode):
    """
    A base class used for nodes which get their information
    by parsing a sysfs file.
    """

    sysfs_path = None

    @classmethod
    def get_sysfs_files(cls):
        """
        Returns all files in the sysfs to parse.
        """
        if hasattr(cls, 'sysfs_path'):
            return glob.glob(cls.sysfs_path)

        raise ValueError("Missing sysfs_path or get_sysfs_files() implementation on derived class {}".format(cls.__name__))

    @classmethod
    def get_lines(cls):
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

def create_modalias_token_parser(subsystem, subsystem_regex_str, options):
    class Parser:
        @staticmethod
        def parse(modalias):
            """
            Matches the modalias against the given options and extracts the data,
            which is returned as a subsystem node, or list of subsystem nodes
            """

            # Match the sysfs line against the regex
            m = Parser._get_regex().match(modalias)
            if not m:
                raise NodeParserException("Could not parse sysfs line")

            # Assign attributes from the match groups
            data = {}
            for option in options:
                val = m.group(option[1])
                if not val:
                    raise NodeParserException("Could not match modalias for parser '{}'".format(subsystem_regex_str))
                data[option[1]] = val

            return [subsystem.create_node(data)]

        @staticmethod
        def _get_regex():
            """
            Gets or creates a regex to match the given modalias options
            """

            if not hasattr(Parser, 'regex'):
                regex = '{}:'.format(subsystem_regex_str)
                for option in options:
                    alias = option[0]
                    optname = option[1]
                    part_regex = "[0-9A-Z*]*" if len(option) <= 2 else option[2]
                    regex += '{}(?P<{}>{})'.format(alias, optname, part_regex)
                Parser.regex = re.compile(regex)

            return Parser.regex

    return Parser()

def create_modalias_split_parser(subsystem, subsystem_str, delim, attr_name='value'):
    class Parser:
        @staticmethod
        def parse(modalias):
            """
            Extracts all fields from the modalias line by splitting on delim.
            The data is returned as a subsystem node, or list of subsystem nodes
            """

            values = filter(None, modalias[len(subsystem_str) + 1:].split(delim))
            return [subsystem.create_node({attr_name: v}) for v in values]

    return Parser()

class ModaliasNode(SysfsNode):
    """
    A base class used for devices classes which get their information
    by parsing a modalias file.
    """

    node_type = 'modalias'
    modalias_parsers = {
        'acpi': create_modalias_split_parser(Subsystem.acpi, 'acpi', ':', attr_name='id'),
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
        'platform': create_modalias_split_parser(Subsystem.platform, 'platform', ':', attr_name='name'),
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
        if self.modalias_subsystem not in self.modalias_parsers:
            raise NodeParserException("No parser for modalias subsystem '{}'".format(self.modalias_subsystem))
        self.nodes = self.modalias_parsers[self.modalias_subsystem].parse(modalias)

    @classmethod
    def get_sysfs_files(cls):
        """
        Finds and returns all modalias files in /sys
        """

        # We use find here, because python raises an OSError when it reaches efivars directory.
        # Also we use check=False, as these errors will cause find to always exit with status 1.
        return filter(None, [i.decode() for i in subprocess.run(['find', '/sys', '-type', 'f', '-name', 'modalias', '-print0'], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.split(b'\0')])

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
        self.nodes = [Subsystem.pnp.create_node({'id': sysfs_line})]

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
        self.nodes = [Subsystem.i2c.create_node({'name': sysfs_line})]

class FsTypeNode(LineParserNode):
    """
    Specializes Node to gather used filesystems
    """
    node_type = 'filesystem'

    def __init__(self, line):
        """
        Initialize fstype node
        """
        self.nodes = [Subsystem.fs.create_node({'fstype': line})]

    @classmethod
    def get_lines(cls):
        fstypes = subprocess.run(['findmnt', '-A', '-n', '-o', 'FSTYPE'], check=True, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()
        return set(fstypes)

class ModuleNode(LineParserNode):
    """
    Specializes Node to gather used modules
    """
    node_type = 'module'

    def __init__(self, line):
        """
        Initialize module node
        """
        self.nodes = [Subsystem.module.create_node({'name': line})]

    @classmethod
    def get_lines(cls):
        """
        Returns all module names of loaded modules
        """
        try:
            with open('/proc/modules', 'r') as f:
                return set([line.split(' ')[0] for line in f])
        except FileNotFoundError:
            return set()

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
            ModuleNode,
        ]

        # For each node class, detect nodes in sysfs.
        self.nodes = []
        for cls in node_classes:
            self.nodes.extend(cls.detect_nodes())

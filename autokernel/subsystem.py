import re

class WildcardTokenType:
    """
    Do not use this class, instead use the wildcard_token instance!
    This is to provide a common toke to signal that "any value" is acceptable
    """
    pass # pylint: disable=unnecessary-pass

# The wildcard token instance
wildcard_token = WildcardTokenType()

class SubsystemNode:
    parameters = []
    mandatory = None

    def __init__(self, subsystem, data):
        """
        Initialize node from dictionary with data
        """
        self.subsystem = subsystem
        for param in self.parameters:
            if param in data:
                setattr(self, param, self._parse_parameter(param, data[param]))
            else:
                setattr(self, param, None)

    def __str__(self):
        """
        Returns a string representation of this object
        """
        s = '{}{{'.format(self.__class__.__name__)
        s += ', '.join(['{}={}'.format(param, self._param_to_str(param)) \
                    for param in self.parameters])
        s += '}'
        return s

    def get_canonical_name(self):
        """
        Returns a canonical name suitable to be used as a filename
        """
        clsname = self.__class__.__name__
        if clsname.endswith('Node'):
            clsname = clsname[:-4]
        s = '_'.join([clsname] + ['{}'.format(self._param_to_str(param)) \
                    for param in self.parameters])
        return re.sub(r'[^a-zA-Z0-9_-]+', '', s).lower()

    def _parse_parameter(self, param, p):
        # pylint: disable=comparison-with-callable
        if p == wildcard_token:
            return p

        ptype = self.parameters[param]
        if ptype == str:
            return "'{}'".format(p)
        elif ptype == hex:
            return int(p, 16)

    def _param_to_str(self, param):
        # pylint: disable=comparison-with-callable
        p = getattr(self, param)
        ptype = self.parameters[param]
        if ptype == str:
            return p
        elif ptype == hex:
            return hex(p)

    def match_score(self, other):
        """
        Compares self to other and returns a positive integer if the nodes match,
        representing the amount of parameters matched, excluding wildcard parameters.
        Returns 0 if nodes did not match.
        """
        score = 0

        for p in self.parameters:
            a = getattr(self, p)
            b = getattr(other, p)

            if a is wildcard_token or b is wildcard_token:
                # Wildcard tokens always match, but don't increase score.
                continue

            # If a or b is None, it will not match
            if not a or not b:
                return 0

            # If a != b, values do not match.
            if a != b:
                return 0

            # Parameter matches, increase score
            score += 1

        # All parameters have passed comparison checks
        return score

    def _get_mandatory(self):
        return self.mandatory or self.parameters

    def get_ambiguity_threshold(self):
        return len(self._get_mandatory())

class AcpiNode(SubsystemNode):
    parameters = {'id': str}

class FsNode(SubsystemNode):
    parameters = {'fstype': str}

class HdaNode(SubsystemNode):
    parameters = {'vendor': hex, 'revision': hex}
    mandatory = ['vendor']

class HidNode(SubsystemNode):
    parameters = {'bus': hex, 'vendor': hex, 'product': hex}
    mandatory = ['vendor', 'product']

class I2cNode(SubsystemNode):
    parameters = {'id': str}

class InputNode(SubsystemNode):
    parameters = {'bustype': hex, 'vendor': hex, 'product': hex}
    mandatory = ['vendor', 'product']

class ModuleNode(SubsystemNode):
    parameters = {'name': str}

class PciNode(SubsystemNode):
    parameters = {'vendor': hex, 'device': hex, 'subvendor': hex, 'subdevice': hex}
    mandatory = ['vendor', 'device']

class PcmciaNode(SubsystemNode):
    parameters = {'manf_id': hex, 'card_id': hex, 'func_id': hex, 'function': hex, 'device_no': hex, 'prod_id_1': str, 'prod_id_2': str, 'prod_id_3': str, 'prod_id_4': str}
    mandatory = ['manf_id', 'card_id']

class PlatformNode(SubsystemNode):
    parameters = {'name': str}

class PnpNode(SubsystemNode):
    parameters = {'id': str}

class SdioNode(SubsystemNode):
    parameters = {'class': hex, 'vendor': hex, 'device': hex}
    mandatory = ['vendor', 'device']

class SerioNode(SubsystemNode):
    parameters = {'type': hex, 'proto': hex, 'id': hex, 'extra': hex}
    mandatory = ['type']

class SpiNode(SubsystemNode):
    parameters = {'id': str}

class UsbNode(SubsystemNode):
    parameters = {'device_vendor': hex, 'device_product': hex, 'device_class': hex, 'device_subclass': hex, 'device_protocol': hex, 'interface_class': hex, 'interface_subclass': hex, 'interface_protocol': hex}
    mandatory = ['device_vendor']

class VirtioNode(SubsystemNode):
    parameters = {'vendor': hex, 'device': hex}

class Subsystem:
    """
    A class representing a subsystem (it stores the related node class)
    """

    all = []

    def __init__(self, name, node_type):
        """
        Initializes a subsystem
        """
        self.name = name
        self.node_type = node_type

        # Append to master list
        Subsystem.all.append(self)

    def __str__(self):
        """
        Returns a string representation of this object
        """
        return self.name

    def create_node(self, *args, **kwargs):
        """
        Creates a node of correct type with given arguments
        """
        return self.node_type(self, *args, **kwargs)

Subsystem.acpi     = Subsystem('acpi'    , AcpiNode    )
Subsystem.fs       = Subsystem('fs'      , FsNode      )
Subsystem.hda      = Subsystem('hda'     , HdaNode     )
Subsystem.hid      = Subsystem('hid'     , HidNode     )
Subsystem.i2c      = Subsystem('i2c'     , I2cNode     )
Subsystem.input    = Subsystem('input'   , InputNode   )
Subsystem.module   = Subsystem('module'  , ModuleNode  )
Subsystem.pci      = Subsystem('pci'     , PciNode     )
Subsystem.pcmcia   = Subsystem('pcmcia'  , PcmciaNode  )
Subsystem.platform = Subsystem('platform', PlatformNode)
Subsystem.pnp      = Subsystem('pnp'     , PnpNode     )
Subsystem.sdio     = Subsystem('sdio'    , SdioNode    )
Subsystem.serio    = Subsystem('serio'   , SerioNode   )
Subsystem.spi      = Subsystem('spi'     , SpiNode     )
Subsystem.usb      = Subsystem('usb'     , UsbNode     )
Subsystem.virtio   = Subsystem('virtio'  , VirtioNode  )

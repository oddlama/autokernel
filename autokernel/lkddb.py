from . import log
from .subsystem import Subsystem, wildcard_token
from . import kconfig as atk_kconfig

import os
import bz2
import re
import shlex
import requests
from datetime import datetime, timezone
import dateutil.parser


class EntryParsingException(Exception):
    pass

class UnkownLkddbSubsystemException(Exception):
    pass

class EntryData:
    """
    A class representing additional information about and entry,
    such as the configuration options or the source
    """
    def __init__(self, config_options, source):
        self.config_options = config_options
        self.source = source

class Entry:
    """
    Associates a node to entry data
    """
    def __init__(self, node, data):
        self.node = node
        self.data = data

class SplitParser:
    """
    A parser which creates one node per argument, while discarding empty arguments.
    """

    attr_name = None
    def parse(self, arguments):
        """
        Parses the arguments into a several data objects, one per argument.
        Must return a list.
        """
        attr_name = self.attr_name
        # Create one node per argument, but filter out wildcard_token
        return [{attr_name: a} for a in arguments if a is not wildcard_token]

class ParamParser:
    """
    A parser which matches one argument for each parameter (sequetially).
    """

    parameters = []
    discard_extra = False
    mandatory = None

    def parse(self, arguments):
        """
        Parses the arguments into a single data object.
        Must return a list.
        """

        mandatory = self.mandatory or self.parameters

        # Ensure the amount of arguments is equal to the required amount
        if len(arguments) != len(self.parameters) and not self.discard_extra:
            raise EntryParsingException("parser requires exactly {} arguments but {} were given".format(len(self.parameters), len(arguments)))
        elif len(arguments) < len(self.parameters):
            raise EntryParsingException("parser requires at least {} arguments but only {} were given".format(len(self.parameters), len(arguments)))

        # Create data dictionary and insert all arguments
        data = {}
        for i, parameter in enumerate(self.parameters):
            # Skip this entry completely, if it is missing mandatory data
            if parameter in mandatory and arguments[i] is wildcard_token:
                return []

            data[parameter] = arguments[i]

        return [data]

class AcpiParser(ParamParser):
    subsystem = Subsystem.acpi
    parameters = ['id']

class FsParser(ParamParser):
    subsystem = Subsystem.fs
    parameters = ['fstype']

class HdaParser(ParamParser):
    subsystem = Subsystem.hda
    parameters = ['vendor']
    discard_extra = True

class HidParser(ParamParser):
    subsystem = Subsystem.hid
    parameters = ['bus', 'vendor', 'product']
    mandatory = ['vendor', 'product']

class I2cParser(ParamParser):
    subsystem = Subsystem.i2c
    parameters = ['id']

class I2cSndParser(ParamParser):
    subsystem = Subsystem.i2c
    parameters = ['id']

class InputParser(ParamParser):
    subsystem = Subsystem.input
    parameters = ['bustype', 'vendor', 'product']
    mandatory = ['vendor', 'product']
    discard_extra = True

class ModuleParser(ParamParser):
    subsystem = Subsystem.module
    parameters = ['name']
    discard_extra = True

class PciParser(ParamParser):
    subsystem = Subsystem.pci
    parameters = ['vendor', 'device', 'subvendor', 'subdevice']
    mandatory = ['vendor', 'device']
    discard_extra = True

class PcmciaParser(ParamParser):
    subsystem = Subsystem.pcmcia
    parameters = ['manf_id', 'card_id', 'func_id', 'function', 'device_no', 'prod_id_1', 'prod_id_2', 'prod_id_3', 'prod_id_4']
    mandatory = ['manf_id', 'card_id']

class PlatformParser(ParamParser):
    subsystem = Subsystem.platform
    parameters = ['name']
    discard_extra = True

class PnpParser(SplitParser):
    subsystem = Subsystem.pnp
    attr_name = 'id'

class SdioParser(ParamParser):
    subsystem = Subsystem.sdio
    parameters = ['class', 'vendor', 'device']
    mandatory = ['vendor', 'device']

class SerioParser(ParamParser):
    subsystem = Subsystem.serio
    parameters = ['type', 'proto', 'id', 'extra']
    mandatory = ['type']

class SpiParser(ParamParser):
    subsystem = Subsystem.spi
    parameters = ['id']

class UsbParser(ParamParser):
    subsystem = Subsystem.usb
    parameters = ['device_vendor', 'device_product', 'device_class', 'device_subclass', 'device_protocol', 'interface_class', 'interface_subclass', 'interface_protocol']
    mandatory = ['device_vendor']
    discard_extra = True

class VirtioParser(ParamParser):
    subsystem = Subsystem.virtio
    parameters = ['vendor', 'device']
    mandatory = ['vendor']

class Lkddb:
    """
    A configuration database provider for the lkddb project
    """

    lkddb_url = 'https://cateee.net/sources/lkddb/lkddb.list.bz2'
    lkddb_file = '/tmp/lkddb.list.bz2'
    lkddb_line_regex = re.compile('^(?P<lkddb_subsystem>[a-zA-Z0-9_-]*) (?P<arguments>.*) : (?P<config_options>[^:]*) : (?P<source>[^:]*)$')

    # Wildcards either only dots (.) or empty arguments
    wildcard_regex = re.compile(r'^(\.+|)$')
    entry_types = {
            'acpi':      AcpiParser(),
            'fs':        FsParser(),
            'hda':       HdaParser(),
            'hid':       HidParser(),
            'i2c':       I2cParser(),
            'i2c-snd':   I2cSndParser(),
            'input':     InputParser(),
            'module':    ModuleParser(),
            'pci':       PciParser(),
            'pcmcia':    PcmciaParser(),
            'platform':  PlatformParser(),
            'pnp':       PnpParser(),
            'sdio':      SdioParser(),
            'serio':     SerioParser(),
            'spi':       SpiParser(),
            'usb':       UsbParser(),
            'virtio':    VirtioParser(),
        }

    def __init__(self):
        """
        Init the database (load and parse).
        """
        self._fetch_db()
        self._load_db()

    def find_options(self, node):
        """
        Tries to match the given data dictionary to a database entry in the same subsystem.
        Returns the list of kernel options for all matched nodes, or an empty list if
        no match could be found.
        """

        if node.subsystem not in self.entries:
            return []

        # Match node against all nodes in the database with the same subsystem
        # and collect the corresponding options
        matching_entries = []
        for entry in self.entries[node.subsystem]:
            score = entry.node.match_score(node)
            if score > 0:
                matching_entries.append((score, entry))

        # Sort by score
        matching_entries.sort(key=lambda x: x[0], reverse=True)

        # Return if we have no matches
        if len(matching_entries) == 0:
            return []

        # If there are at least two matches, and the first two have the same score,
        # the matches could be ambiguous, and we dont want to select ambiguous matches.
        if len(matching_entries) >= 2:
            best_score = matching_entries[0][0]
            if best_score == matching_entries[1][0]:
                # A match can only be ambiguous, if the score is below the ambiguity_threshold
                # defined in the node. (e.g. a node with only one parameter can never be ambiguous)
                if best_score < node.get_ambiguity_threshold():
                    log.warn("Ambiguous matches for node: {}".format(node))
                    return []

        # Get best entry by score
        best_entry = matching_entries[0][1]
        # Add all config options to the set
        return best_entry.data.config_options

    def _fetch_db(self):
        """
        Downloads the newest lkddb file.
        """

        def has_newer_version():
            req = requests.head(self.lkddb_url)
            url_time = req.headers['last-modified']
            url_date = dateutil.parser.parse(url_time)
            file_time = datetime.fromtimestamp(os.path.getmtime(self.lkddb_file), timezone.utc)
            return url_date > file_time

        if not os.path.exists(self.lkddb_file) or has_newer_version():
            log.info("Downloading lkddb database")
            r = requests.get(self.lkddb_url, allow_redirects=True)
            with open(self.lkddb_file, 'wb') as f:
                f.write(r.content)

    def _load_db(self):
        """
        Downlads the newest lkddb.list file (if necessary), and
        loads the contained information.
        """

        log.verbose("Parsing lkddb database")
        self.entries = {}

        valid_lines = 0
        with bz2.open(self.lkddb_file, 'r') as f:
            for line_nr, line in enumerate(f, start=1):
                if self._parse_lkddb_line(line.decode('utf-8'), line_nr):
                    valid_lines += 1

        log.info("Loaded {} lkddb entries".format(valid_lines))

    def _parse_lkddb_line(self, line, line_nr):
        """
        Parses a line in the lkddb file and creates an entry if it is valid.
        """
        if line[0] == '#' or line.startswith('kver'):
            # Skip comments and kver line
            return False

        try:
            subsystem, data_list, entry_data = self._parse_entry(line)
            if not subsystem:
                return False

            for data in data_list:
                self._add_entry(subsystem, subsystem.create_node(data), entry_data)
            return True
        except EntryParsingException as e:
            log.warn('Could not parse entry at lkddb:{}: {}'.format(line_nr, str(e)))
            return False
        except UnkownLkddbSubsystemException:
            pass

    def _parse_entry(self, line):
        # Match regex
        m = Lkddb.lkddb_line_regex.match(line)
        if not m:
            # Skip lines that could not be matched
            raise EntryParsingException("Regex mismatch")

        # Split line information
        lkddb_subsystem = m.group('lkddb_subsystem')
        arguments = m.group('arguments')
        source = m.group('source')

        if source.startswith('arch/'):
            if not source.startswith('arch/{}/'.format(atk_kconfig.get_arch())):
                # We skip entries that do not match our architecture
                return None, None, None

        # Validate that each config option starts with CONFIG_,
        # remove the prefix and make a unique set.
        config_options = list()
        for c in filter(None, m.group('config_options').split(' ')):
            if not c.startswith('CONFIG_'):
                # Skip entries with invalid options
                raise EntryParsingException("All config options must start with 'CONFIG_', but '{}' did not.".format(c))

            # Skip unknown config options
            if c == 'CONFIG__UNKNOWN__':
                continue

            # remove this CONFIG_ prefix and add to set
            opt = c[len('CONFIG_'):]
            if opt not in config_options:
                config_options.append(opt)

        # Split arguments on space while preserving quoted strings
        arguments = shlex.split(arguments)
        # Replace wildcards with wildcard tokens
        arguments = [wildcard_token if Lkddb.wildcard_regex.match(a) else a for a in arguments]

        # Get the subsystem and parameters for the entry
        if lkddb_subsystem not in Lkddb.entry_types:
            raise UnkownLkddbSubsystemException("'{}'".format(lkddb_subsystem))

        # Return subsystem, list of parsed data and associated entry data
        entry_data = EntryData(config_options, source)
        entry_parser = Lkddb.entry_types[lkddb_subsystem]
        return entry_parser.subsystem, entry_parser.parse(arguments), entry_data

    def _add_entry(self, subsystem, node, entry_data):
        """
        Adds a new entry for the given node and entry_data to the index
        """
        # Add empty list in dictionary if key doesn't exist
        if subsystem not in self.entries:
            self.entries[subsystem] = []

        # Append node to list
        self.entries[subsystem].append(Entry(node, entry_data))


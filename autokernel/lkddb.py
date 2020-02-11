from . import log
from .subsystem import Subsystem, wildcard_token

import os
import bz2
import re
import shlex
import urllib.request


class EntryParsingException(Exception):
    pass

class UnkownLkddbSubsystemException(Exception):
    pass

def create_lkddb_split_args_parser(attr_name):
    """
    Creates a parser which creates one node per argument, while discarding empty arguments.
    """
    class Parser:
        @staticmethod
        def parse(arguments):
            """
            Parses the arguments into a several data objects, one per argument.
            Must return a list.
            """
            # Filter empty arguments
            arguments = filter(None, arguments)
            return [{attr_name: a} for a in arguments]

    return Parser()

def create_lkddb_param_parser(parameters, discard_extra_arguments=False, empty_args_are_wildcards=False):
    """
    Creates a parser which matches one argument for each parameter (sequetially).
    """
    class Parser:
        @staticmethod
        def parse(arguments):
            """
            Parses the arguments into a single data object.
            Must return a list.
            """
            # Ensure the amount of arguments is equal to the required amount
            if len(arguments) != len(parameters) and not discard_extra_arguments:
                raise EntryParsingException("parser requires exactly {} arguments but {} were given".format(len(parameters), len(arguments)))
            elif len(arguments) < len(parameters):
                raise EntryParsingException("parser requires at least {} arguments but only {} were given".format(len(parameters), len(arguments)))

            # Create data dictionary and insert all arguments
            data = {}
            for i, parameter in enumerate(parameters):
                if empty_args_are_wildcards and not arguments[i]:
                    data[parameter] = wildcard_token
                else:
                    data[parameter] = arguments[i]

            return [data]

    return Parser()

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

class Lkddb:
    """
    A configuration database provider for the lkddb project
    """

    lkddb_url = 'https://cateee.net/sources/lkddb/lkddb.list.bz2'
    # TODO cache file?
    lkddb_file = '/tmp/lkddb.list.bz2'
    lkddb_line_regex = re.compile('^(?P<lkddb_subsystem>[a-zA-Z0-9_-]*) (?P<arguments>.*) : (?P<config_options>[^:]*) : (?P<source>[^:]*)$')

    wildcard_regex = re.compile('^\.+$')
    entry_types = {
            'acpi':      (Subsystem.acpi,     create_lkddb_param_parser(['name'])),
            'fs':        (Subsystem.fs,       create_lkddb_param_parser(['fstype'])),
            'hda':       (Subsystem.hda,      create_lkddb_param_parser(['vendor'], discard_extra_arguments=True)),
            'hid':       (Subsystem.hid,      create_lkddb_param_parser(['bus', 'vendor', 'product'])),
            'i2c':       (Subsystem.i2c,      create_lkddb_param_parser(['name'])),
            'i2c-snd':   (Subsystem.i2c,      create_lkddb_param_parser(['name'])),
            'input':     (Subsystem.input,    create_lkddb_param_parser(['bustype', 'vendor', 'product'], discard_extra_arguments=True)),
            'pci':       (Subsystem.pci,      create_lkddb_param_parser(['vendor', 'device', 'subvendor', 'subdevice', 'class_mask'])),
            'pcmcia':    (Subsystem.pcmcia,   create_lkddb_param_parser(['manf_id', 'card_id', 'func_id', 'function', 'device_no', 'prod_id_1', 'prod_id_2', 'prod_id_3', 'prod_id_4'], empty_args_are_wildcards=True)),
            'platform':  (Subsystem.platform, create_lkddb_param_parser(['name'], discard_extra_arguments=True)),
            'pnp':       (Subsystem.pnp,      create_lkddb_split_args_parser('id')),
            'sdio':      (Subsystem.sdio,     create_lkddb_param_parser(['class', 'vendor', 'device'])),
            'serio':     (Subsystem.serio,    create_lkddb_param_parser(['type', 'proto', 'id', 'extra'])),
            'spi':       (Subsystem.spi,      create_lkddb_param_parser(['name'])),
            'usb':       (Subsystem.usb,      create_lkddb_param_parser(['device_vendor', 'device_product', 'device_class', 'device_subclass', 'device_protocol', 'interface_class', 'interface_subclass', 'interface_protocol'], discard_extra_arguments=True)),
            'virtio':    (Subsystem.virtio,   create_lkddb_param_parser(['vendor', 'device'])),
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
        matching_config_options = set()
        for entry in self.entries[node.subsystem]:
            if entry.node.matches(node):
                # Add all config options to the set
                matching_config_options.update(entry.data.config_options)

        return matching_config_options

    def _fetch_db(self):
        """
        Downloads the newest lkddb file.
        """

        log.info("Downloading lkddb database")
        # TODO only when upstream version is newer
        if not os.path.exists(self.lkddb_file):
            urllib.request.urlretrieve(self.lkddb_url, self.lkddb_file)

    def _load_db(self):
        """
        Downlads the newest lkddb.list file (if necessary), and
        loads the contained information.
        """

        log.info("Parsing lkddb database")
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
            subsystem, data_list, entry_data = self._parse_entry(line, line_nr)
            for data in data_list:
                self._add_entry(subsystem, subsystem.create_node(data), entry_data)
            return True
        except EntryParsingException as e:
            log.warn('Could not parse entry at lkddb:{}: {}'.format(line_nr, str(e)))
            return False
        except UnkownLkddbSubsystemException:
            pass

    def _parse_entry(self, line, line_nr):
        # Match regex
        m = Lkddb.lkddb_line_regex.match(line)
        if not m:
            # Skip lines that could not be matched
            raise EntryParsingException("Regex mismatch")

        # Split line information
        lkddb_subsystem = m.group('lkddb_subsystem')
        arguments = m.group('arguments')
        config_options = filter(None, m.group('config_options').split(' '))
        source = m.group('source')

        # Validate that each config option starts with CONFIG_
        opts = set()
        for c in config_options:
            if not c.startswith('CONFIG_'):
                # Skip entries with invalid options
                raise EntryParsingException("All config options must start with 'CONFIG_', but '{}' did not.".format(c))
            opts.add(c[len('CONFIG_'):])

        # ... and remove this CONFIG_ prefix
        config_options = opts

        # Split arguments on space while preserving quoted strings
        arguments = shlex.split(arguments)
        # Replace wildcards with wildcard tokens
        arguments = [wildcard_token if Lkddb.wildcard_regex.match(p) else p for p in arguments]

        # Get the subsystem and parameters for the entry
        if lkddb_subsystem not in Lkddb.entry_types:
            raise UnkownLkddbSubsystemException("'{}'".format(lkddb_subsystem))

        # Return subsystem, list of parsed data and associated entry data
        entry_data = EntryData(config_options, source)
        subsystem, entry_parser = Lkddb.entry_types[lkddb_subsystem]
        return subsystem, entry_parser.parse(arguments), entry_data

    def _add_entry(self, subsystem, node, entry_data):
        """
        Adds a new entry for the given node and entry_data to the index
        """
        # Add empty list in dictionary if key doesn't exist
        if subsystem not in self.entries:
            self.entries[subsystem] = []

        # Append node to list
        self.entries[subsystem].append(Entry(node, entry_data))


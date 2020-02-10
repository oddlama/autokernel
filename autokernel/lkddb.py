from . import log
from .subsystem import Subsystem, wildcard_token

import bz2
import re
import shlex
import urllib.request


class EntryParsingException(Exception):
    pass

class UnkownLkddbSubsystemException(Exception):
    pass

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
           'acpi':      (Subsystem.acpi, ['name']),
           #'fs':        [],
           #'hda':       [],
           #'hid':       [],
           #'i2c':       [],
           #'i2c-snd':   [],
           #'input':     [],
           'pci':       (Subsystem.pci, ['vendor', 'device', 'subvendor', 'subdevice', 'class_mask']),
           #'pcmcia':    [],
           #'platform':  [],
           #'pnp':       [],
           #'sdio':      [],
           #'serio':     [],
           #'spi':       [],
           #'usb':       [],
           #'virtio':    [],
        }

    def __init__(self):
        """
        Init the database (load and parse).
        """
        self._fetch_db()
        self._load_db()

    def find_options(self, subsystem, subsystem_node):
        """
        Tries to match the given data dictionary to a database entry in the same subsystem.
        Returns the list of kernel options for all matched nodes, or an empty list if
        no match could be found.
        """

        if subsystem not in self.nodes:
            return []

        #TODO for e in self.nodes[subsystem]:
        #TODO     if e.match(data):

    def _fetch_db(self):
        """
        Downloads the newest lkddb file.
        """

        log.info("Downloading lkddb database")
        urllib.request.urlretrieve(self.lkddb_url, self.lkddb_file)

    def _load_db(self):
        """
        Downlads the newest lkddb.list file (if necessary), and
        loads the contained information.
        """

        log.info("Parsing lkddb database")
        self.nodes = {}

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
        if line[0] == '#':
            # Skip comments
            return False

        try:
            subsystem, data = self._parse_entry(line, line_nr)
            self._add_node(subsystem, subsystem.create_node(data))
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
        for c in config_options:
            if not c.startswith('CONFIG_'):
                # Skip entries with invalid options
                raise EntryParsingException("All config options must start with 'CONFIG_', but '{}' did not.".format(c))

        # ... and remove this CONFIG_ prefix
        config_options = [c[len('CONFIG_'):] for c in config_options]

        # Split arguments on space while preserving quoted strings
        arguments = shlex.split(arguments)
        # Replace wildcards with wildcard tokens
        arguments = [wildcard_token if Lkddb.wildcard_regex.match(p) else p for p in arguments]

        # Get the subsystem and parameters for the entry
        if lkddb_subsystem not in Lkddb.entry_types:
            raise UnkownLkddbSubsystemException("'{}'".format(lkddb_subsystem))

        subsystem, entry_parameters = Lkddb.entry_types[lkddb_subsystem]

        # Ensure the amount of arguments is equal to the required amount
        if len(arguments) != len(entry_parameters):
            raise EntryParsingException("{} requires {} parameters but {} were given".format(self.__class__.__name__, len(entry_parameters), len(arguments)))

        # Create data dictionary and insert all arguments
        data = {}
        for i, parameter in enumerate(entry_parameters):
            data[parameter] = arguments[i]

        return subsystem, data

    def _add_node(self, subsystem, node):
        """
        Adds the given node to all stored nodes (indexed by subsystem)
        """
        # Add empty list in dictionary if key doesn't exist
        if subsystem not in self.nodes:
            self.nodes[subsystem] = []

        # Append node to list
        self.nodes[subsystem].append(node)


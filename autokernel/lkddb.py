from . import log
from .subsystem import Subsystem, wildcard_token

import bz2
import re
import shlex
import urllib.request

class EntryParseException(Exception):
    pass

class Entry:
    wildcard_regex = re.compile('^\.+$')

    def __init__(self, arguments, config_options, source):
        self.arguments = self._parse_arguments(arguments)
        self.config_options = config_options
        self.source = source

    @classmethod
    def _get_parameters(cls):
        return cls.parameters

    def _parse_arguments(self, arguments):
        # Split on space while preserving quoted strings
        arguments = shlex.split(arguments)
        # Replace wildcards with wildcard tokens
        arguments = [wildcard_token if Entry.wildcard_regex.match(p) else p for p in arguments]

        # Get the parameter names from the derived class
        parameters = self._get_parameters()
        # Ensure the amount of arguments is equal to the required amount
        if len(arguments) != len(parameters):
            raise EntryParseException("{} requires {} parameters but {} were given".format(self.__class__.__name__, len(parameters), len(arguments)))

    def get_config_options(self):
        return self.config_options

    def get_source(self):
        return self.source

class AcpiEntry(Entry):
    parameters = ['name']

class PciEntry(Entry):
    parameters = ['vendor', 'device', 'subvendor', 'subdevice', 'class_mask']

entry_classes = {
       'acpi':      AcpiEntry,
       #'fs':        FsEntry,
       #'hda':       HdaEntry,
       #'hid':       HidEntry,
       #'i2c':       I2cEntry,
       #'i2c-snd':   I2cEntry,
       #'input':     InputEntry,
       'pci':       PciEntry,
       #'pcmcia':    PcmciaEntry,
       #'platform':  PlatformEntry,
       #'pnp':       PnpEntry,
       #'sdio':      SdioEntry,
       #'serio':     SerioEntry,
       #'spi':       SpiEntry,
       #'usb':       UsbEntry,
       #'virtio':    VirtioEntry,
    }

def get_entry_class(subsystem):
    """
    Returns the entry class for a given subsystem
    """
    return entry_classes.get(subsystem)

class Lkddb:
    """
    A configuration database provider for the lkddb project
    """

    lkddb_url = 'https://cateee.net/sources/lkddb/lkddb.list.bz2'
    # TODO cache file?
    lkddb_file = '/tmp/lkddb.list.bz2'
    lkddb_line_regex = re.compile('^(?P<subsystem>[a-zA-Z0-9_-]*) (?P<parameters>.*) : (?P<config_options>[^:]*) : (?P<source>[^:]*)$')

    def __init__(self):
        """
        Init the database (load and parse).
        """
        self._fetch_db()
        self._load_db()

    def find_options(self, subsystem, data):
        """
        Tries to match the given data dictionary to a database entry in the same subsystem.
        Returns the list of kernel options for all matched entries, or an empty list if
        no match could be found.
        """

        if subsystem not in self.entries:
            return []

        #TODO for e in self.entries[subsystem]:
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
        if line[0] == '#':
            # Skip comments
            return False

        # Match regex
        m = Lkddb.lkddb_line_regex.match(line)
        if not m:
            # Skip lines that could not be matched
            return False

        # Split information
        subsystem = m.group('subsystem')
        parameters = m.group('parameters')
        config_options = filter(None, m.group('config_options').split(' '))
        source = m.group('source')

        # Validate that each config option starts with CONFIG_
        for c in config_options:
            if not c.startswith('CONFIG_'):
                # Skip entries with invalid options
                return False

        # ... and remove this CONFIG_ prefix
        config_options = [c[len('CONFIG_'):] for c in config_options]

        entry_cls = get_entry_class(subsystem)
        if not entry_cls:
            # Skip lines with an unkown subsystem
            return False

        try:
            entry = entry_cls(parameters, config_options, source)
        except EntryParseException as e:
            log.warn('Could not parse entry at lkddb:{}: {}'.format(line_nr, repr(e)))
            return False

        self._add_entry(subsystem, entry)
        return True

    def _add_entry(self, subsystem, entry):
        """
        Adds the given entry to all stored entries (indexed by subsystem)
        """
        # Add empty list in dictionary if key doesn't exist
        if subsystem not in self.entries:
            self.entries[subsystem] = []

        # Append entry to list
        self.entries[subsystem].append(entry)


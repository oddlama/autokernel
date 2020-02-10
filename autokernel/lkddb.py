from . import log

import re
import bz2
import urllib.request

class Entry:
    def __init__(self, subsystem, config_options, source):
        self.subsystem = subsystem
        self.config_options = config_options
        self.source = source

    @staticmethod
    def from(subsystem, parameters, config_options, source):
        'acpi':
        'fs':
        'hda':
        'hid':
        'i2c':
        'i2c-snd':
        'input':
        'kver':
        'module':
        'of':
        'parisc':
        'pci':
        'pci_epf':
        'pcmcia':
        'platform':
        'pnp':
        'rpmsg':
        'sdio':
        'sdw':
        'serio':
        'slim':
        'spi':
        'ssb':
        'tc':
        'usb':
        'vio':
        'virtio':
        'zorro':


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
        self._parse_db()

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
        self.entries = []

        valid_lines = 0
        with bz2.open(self.lkddb_file, 'r') as f:
            for line in f:
                if self._parse_lkddb_line(line.decode('utf-8')):
                    valid_lines += 1

        log.info("Loaded {} lkddb entries".format(valid_lines))

    def _parse_lkddb_line(self, line):
        if line[0] == '#':
            # Skip comments
            return False

        # Match regex
        m = Lkddb.lkddb_line_regex.match(line)
        if not m:
            # Skip lines that could not be matched
            return False

        subsystem = m.group('subsystem')
        parameters = m.group('parameters')
        config_options = m.group('config_options').split(' ')
        source = m.group('source')

        self.entries.append(Entry.from(subsystem, parameters, config_options, source))
        return True

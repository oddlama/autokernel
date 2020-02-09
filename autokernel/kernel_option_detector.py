from . import log

import os

class KernelOptionDetector:
    def __init__(self):
        log.info("Inspecting current system")
        self.detect_pci_options()

    def detect_pci_options(self):
        log.info("Detecting PCI devices")

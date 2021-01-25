import re

__version__ = '0.9.8'
version_info = tuple(int(p) for p in
                     re.match(r'(\d+).(\d+).(\d+)', __version__).groups())

__all__ = ('__version__', 'version_info')

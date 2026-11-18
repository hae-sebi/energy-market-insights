"""Access to the SMARD.de chart data API (Bundesnetzagentur, CC BY 4.0).

An ``__init__.py`` turns a folder into a Python package. The imports below
re-export the most important names, so users can write the short form
``from emi.smard import SmardClient`` instead of ``from emi.smard.client import ...``.
"""

from emi.smard.client import SmardClient, SmardError
from emi.smard.series import REGION, SERIES, Series

# `__all__` lists the public names of this package (what `from emi.smard import *` exports).
__all__ = ["REGION", "SERIES", "Series", "SmardClient", "SmardError"]

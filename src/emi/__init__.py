"""energy-market-insights: day-ahead price forecasting and load shifting based on SMARD data."""

from importlib.metadata import PackageNotFoundError, version

# Read the version number from the installed package metadata (which comes from
# pyproject.toml), so it is defined in exactly one place.
try:
    __version__ = version("energy-market-insights")
except PackageNotFoundError:  # running from a source checkout without installation
    __version__ = "0.0.0"

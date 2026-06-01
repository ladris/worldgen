"""DEM providers."""

from .base import DEMProvider, get_provider, register_provider, available_providers
from . import synthetic  # noqa: F401  (registers SyntheticProvider)
from . import opentopography  # noqa: F401  (registers OpenTopographyProvider)

__all__ = [
    "DEMProvider", "get_provider", "register_provider", "available_providers",
]

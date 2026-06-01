"""Dynamic World Streaming — Python terrain service.

Turns real-world DEM data into a deterministic, seamlessly-tileable grid of
heightmaps that an Unreal Engine runtime can stream in as a player explores.

See ``docs/ARCHITECTURE.md`` and ``docs/CONTRACT.md`` for the design.
"""

from .config import ProjectConfig
from .tile_grid import WorldGrid, TileIndex, TileBounds

__all__ = ["ProjectConfig", "WorldGrid", "TileIndex", "TileBounds"]

__version__ = "2.0.0-dev"
SCHEMA_VERSION = "1.0"

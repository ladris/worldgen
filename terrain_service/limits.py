"""Resource limits and request bounds for the terrain service.

The service accepts requests that drive array allocations, generation work, and
outbound API calls. Without bounds, a single crafted request (e.g. a negative
tile ``level`` or a huge edit ``radius_m``) can exhaust memory or CPU. These
constants are the guardrails; they are enforced at the HTTP boundary and again
defensively in the core. Tune them for your deployment, but never remove them.
"""

from __future__ import annotations

# --- tile addressing -------------------------------------------------------

# Level 0 is native resolution; higher levels are coarser (downsampled). Negative
# levels would *upsample* and blow up the sample grid, so they are rejected.
MIN_TILE_LEVEL = 0
MAX_TILE_LEVEL = 24

# Tiles are addressable far from the origin, but absurd indices serve no purpose
# and (with a real DEM provider) amplify outbound fetches. Keep it generous but
# finite: 1e7 tiles ≈ millions of km in any direction.
MAX_ABS_TILE_INDEX = 10_000_000

# --- prestage --------------------------------------------------------------

MAX_PRESTAGE_TILES = 1024

# --- edits -----------------------------------------------------------------

# An edit is rebuilt on a mosaic spanning all affected tiles. Bound both the
# number of tiles and the total mosaic dimensions so a large radius cannot
# allocate an enormous array.
MAX_EDIT_AFFECTED_TILES = 64           # e.g. up to an 8x8 block
MAX_EDIT_MOSAIC_SAMPLES_PER_SIDE = 8192
MAX_EDIT_ITERATIONS = 64
MAX_EDIT_RADIUS_M = 100_000.0          # hard ceiling; tile/mosaic caps also apply


def validate_tile_level(level: int) -> None:
    if not (MIN_TILE_LEVEL <= level <= MAX_TILE_LEVEL):
        raise ValueError(
            f"level must be in [{MIN_TILE_LEVEL}, {MAX_TILE_LEVEL}], got {level}"
        )


def validate_tile_index(x: int, y: int) -> None:
    if abs(x) > MAX_ABS_TILE_INDEX or abs(y) > MAX_ABS_TILE_INDEX:
        raise ValueError(
            f"tile index out of range (|x|,|y| <= {MAX_ABS_TILE_INDEX})"
        )


def validate_tile(level: int, x: int, y: int) -> None:
    validate_tile_level(level)
    validate_tile_index(x, y)

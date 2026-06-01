"""Absolute, project-wide elevation encoding (CONTRACT §2).

Every tile encodes metres → uint16 with the *same* linear map derived from the
project's elevation range, so the Unreal Z-scale is one constant for the whole
world and heights are continuous across every tile boundary. This is the
property that makes vertical seams impossible.
"""

from __future__ import annotations

import numpy as np

U16_MAX = 65535


def fill_nodata(elev_m: np.ndarray, nodata: float | None = None) -> np.ndarray:
    """Replace NoData / NaN samples so the streamed world has no holes.

    Uses nearest-valid fill via a cheap iterative flood from valid neighbours,
    falling back to the array mean if an entire tile is void. Operates on a
    float copy and never mutates the input.
    """
    a = elev_m.astype(np.float64, copy=True)
    invalid = ~np.isfinite(a)
    if nodata is not None:
        invalid |= (a == nodata)

    if not invalid.any():
        return a
    if invalid.all():
        # Whole tile is void (e.g. ocean gap); flat-fill at the project floor's
        # neutral value. Caller still records honest tile_min/max from this.
        a[:] = 0.0
        return a

    a[invalid] = np.nan
    # Iterative neighbour averaging until all holes are filled. Tiles are small
    # and holes are typically thin, so this converges quickly.
    for _ in range(max(a.shape)):
        nan_mask = np.isnan(a)
        if not nan_mask.any():
            break
        filled = a.copy()
        # Shifted neighbour stacks; average over finite ones.
        neigh = np.stack([
            _shift(a, 1, 0), _shift(a, -1, 0),
            _shift(a, 0, 1), _shift(a, 0, -1),
        ])
        with np.errstate(invalid="ignore"):
            mean = np.nanmean(neigh, axis=0)
        take = nan_mask & np.isfinite(mean)
        filled[take] = mean[take]
        a = filled
    # Any stragglers → global mean of valid samples.
    if np.isnan(a).any():
        a[np.isnan(a)] = np.nanmean(a)
    return a


def _shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.full_like(a, np.nan)
    ys_src = slice(max(0, -dy), a.shape[0] - max(0, dy))
    ys_dst = slice(max(0, dy), a.shape[0] - max(0, -dy))
    xs_src = slice(max(0, -dx), a.shape[1] - max(0, dx))
    xs_dst = slice(max(0, dx), a.shape[1] - max(0, -dx))
    out[ys_dst, xs_dst] = a[ys_src, xs_src]
    return out


def encode_absolute(elev_m: np.ndarray, project_min_m: float,
                    project_max_m: float) -> np.ndarray:
    """Encode elevation (metres) → uint16 using the project-wide range."""
    span = project_max_m - project_min_m
    if span <= 0:
        raise ValueError("project_max_m must exceed project_min_m")
    norm = (elev_m.astype(np.float64) - project_min_m) / span
    scaled = np.rint(norm * U16_MAX)
    return np.clip(scaled, 0, U16_MAX).astype(np.uint16)


def decode_absolute(u16: np.ndarray, project_min_m: float,
                    project_max_m: float) -> np.ndarray:
    """Inverse of :func:`encode_absolute` → metres."""
    span = project_max_m - project_min_m
    return project_min_m + (u16.astype(np.float64) / U16_MAX) * span

"""Tests for absolute elevation encoding and NoData filling."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terrain_service.elevation import (
    encode_absolute, decode_absolute, fill_nodata, U16_MAX,
)


def test_encode_endpoints():
    arr = np.array([[-500.0, 9000.0]])
    enc = encode_absolute(arr, -500.0, 9000.0)
    assert enc[0, 0] == 0
    assert enc[0, 1] == U16_MAX


def test_encode_decode_roundtrip_within_precision():
    rng = np.random.default_rng(0)
    elev = rng.uniform(-500, 9000, size=(64, 64))
    enc = encode_absolute(elev, -500.0, 9000.0)
    dec = decode_absolute(enc, -500.0, 9000.0)
    precision = (9000.0 - (-500.0)) / U16_MAX
    assert np.max(np.abs(dec - elev)) <= precision


def test_absolute_encoding_is_consistent_across_tiles():
    """Two tiles covering different elevation sub-ranges must encode a shared
    height to the *same* uint16 — the core anti-seam property."""
    shared_edge_elev = np.array([1234.5, 1235.0, 1240.0])
    tile_a = np.concatenate([shared_edge_elev, [1000.0, 1100.0]])
    tile_b = np.concatenate([shared_edge_elev, [3000.0, 3200.0]])
    enc_a = encode_absolute(tile_a, -500.0, 9000.0)
    enc_b = encode_absolute(tile_b, -500.0, 9000.0)
    np.testing.assert_array_equal(enc_a[:3], enc_b[:3])


def test_encode_clamps_out_of_range():
    arr = np.array([[-1000.0, 99999.0]])
    enc = encode_absolute(arr, -500.0, 9000.0)
    assert enc[0, 0] == 0
    assert enc[0, 1] == U16_MAX


def test_fill_nodata_removes_holes():
    a = np.array([
        [10.0, 11.0, 12.0],
        [13.0, np.nan, 15.0],
        [16.0, 17.0, 18.0],
    ])
    filled = fill_nodata(a)
    assert np.isfinite(filled).all()
    # The hole should be near its neighbours' average.
    assert 11.0 <= filled[1, 1] <= 17.0


def test_fill_nodata_with_sentinel_value():
    a = np.array([[1.0, -9999.0], [2.0, 3.0]])
    filled = fill_nodata(a, nodata=-9999.0)
    assert np.isfinite(filled).all()
    assert filled[0, 1] != -9999.0


def test_fill_nodata_all_void():
    a = np.full((4, 4), np.nan)
    filled = fill_nodata(a)
    assert np.isfinite(filled).all()

"""Contract smoke test — exercises a terrain service exactly like the Unreal
client does, so you can validate the *server* end of the contract before (and
independently of) the in-engine compile.

Checks, against a live service:
  1. GET /project returns a valid grid config.
  2. A block of tiles fetches, with correct .r16 sizes.
  3. Adjacent tiles are seamless (shared edge byte-identical).
  4. An edit applies, changes the tile, and the result is still seamless.
  5. Undo reverts it.

Usable two ways:
  * CLI against a running server:   python -m tools.contract_smoke --url http://127.0.0.1:8000
  * In tests, pass any object with .get()/.post() returning objects exposing
    .status_code, .json(), .content (requests.Session or FastAPI TestClient).
"""

from __future__ import annotations

import argparse
import sys

import numpy as np


class SmokeFailure(AssertionError):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SmokeFailure(msg)


def run(session, base: str = "") -> dict:
    """Run the smoke checks using ``session`` (requests-like). Returns a summary
    dict; raises SmokeFailure on the first failed invariant."""
    results: dict[str, object] = {}

    # 1. project config
    r = session.get(f"{base}/project")
    _require(r.status_code == 200, f"/project returned {r.status_code}")
    cfg = r.json()
    n = int(cfg["derived"]["samples_per_edge"])
    results["samples_per_edge"] = n
    results["project_id"] = cfg["config"]["project_id"]

    def fetch(x: int, y: int) -> np.ndarray:
        resp = session.get(f"{base}/tile/0/{x}/{y}/heightmap.r16")
        _require(resp.status_code == 200, f"tile {x},{y} -> {resp.status_code}")
        arr = np.frombuffer(resp.content, dtype="<u2")
        _require(arr.size == n * n,
                 f"tile {x},{y} wrong size {arr.size}, expected {n*n}")
        return arr.reshape(n, n)

    # 2 + 3. fetch a 2x2 block and check seams
    a = fetch(0, 0)
    east = fetch(1, 0)
    north = fetch(0, 1)
    _require(np.array_equal(a[:, -1], east[:, 0]),
             "horizontal seam mismatch between (0,0) and (1,0)")
    _require(np.array_equal(a[0, :], north[-1, :]),
             "vertical seam mismatch between (0,0) and (0,1)")
    results["seam_check"] = "ok"

    # 4. edit on the shared edge, then re-verify change + seam
    tile_cm = cfg["config"]["tile_size_m"] * 100.0
    center_x = tile_cm          # shared edge between (0,0) and (1,0)
    center_y = tile_cm * 0.5
    before_center = int(a[n // 2, -1])
    e = session.post(f"{base}/edit", json={
        "type": "raise_lower", "center_x_cm": center_x, "center_y_cm": center_y,
        "radius_m": cfg["config"]["tile_size_m"] * 0.5, "strength_m": 80.0,
    })
    _require(e.status_code == 200, f"/edit returned {e.status_code}")
    a2 = fetch(0, 0)
    east2 = fetch(1, 0)
    _require(np.array_equal(a2[:, -1], east2[:, 0]),
             "seam broken after cross-boundary edit")
    _require(int(a2[n // 2, -1]) > before_center,
             "edit did not raise the shared-edge sample")
    results["edit_check"] = "ok"

    # 5. undo
    u = session.post(f"{base}/edit/undo", json={})
    _require(u.status_code == 200, f"/edit/undo returned {u.status_code}")
    a3 = fetch(0, 0)
    _require(abs(int(a3[n // 2, -1]) - before_center) <= 2,
             "undo did not restore the shared-edge sample")
    results["undo_check"] = "ok"

    results["status"] = "PASS"
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Terrain service contract smoke test.")
    p.add_argument("--url", default="http://127.0.0.1:8000",
                   help="Base URL of a running terrain service.")
    args = p.parse_args(argv)

    try:
        import requests
    except ImportError:
        print("requests is required: pip install requests", file=sys.stderr)
        return 2

    session = requests.Session()
    try:
        summary = run(session, args.url.rstrip("/"))
    except SmokeFailure as e:
        print(f"SMOKE FAIL: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # connection errors etc.
        print(f"ERROR contacting {args.url}: {e}", file=sys.stderr)
        return 2

    print("Contract smoke test PASSED")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

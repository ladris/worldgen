"""Command-line entry point for the terrain service.

Examples
--------
Create a project config::

    python -m terrain_service.cli init --project-id denver \\
        --lat 39.7392 --lon -104.9903 --provider synthetic -o denver.json

Generate a block of tiles to disk::

    python -m terrain_service.cli generate -c denver.json --center 0 0 --radius 2

Run the HTTP service::

    python -m terrain_service.cli serve -c denver.json --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import ProjectConfig
from .cache import TileCache
from .tile_grid import WorldGrid, TileIndex
from .providers import available_providers


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("-c", "--config", required=True, help="Project config JSON.")
    p.add_argument("--cache-root", default=".worldgen_cache",
                   help="Cache directory root.")


def cmd_init(args: argparse.Namespace) -> int:
    cfg = ProjectConfig(
        project_id=args.project_id,
        origin_lat=args.lat, origin_lon=args.lon,
        tile_size_m=args.tile_size_m, meters_per_pixel=args.mpp,
        elevation_min_m=args.elev_min, elevation_max_m=args.elev_max,
        dem_type=args.dem_type, provider=args.provider, crs=args.crs,
    )
    cfg.save(args.output)
    grid = WorldGrid(cfg)
    print(f"Wrote {args.output}")
    print(f"  CRS: {grid.crs_string}  ({grid.crs.name})")
    print(f"  tile: {cfg.cells_per_tile} cells / {cfg.samples_per_edge} samples "
          f"per edge @ {cfg.meters_per_pixel} m/px")
    print(f"  world Z-scale (constant): {cfg.ue_scale_z:.4f}  "
          f"(vertical precision {cfg.vertical_precision_m:.3f} m)")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    cfg = ProjectConfig.load(args.config)
    cache = TileCache(cfg, cache_root=args.cache_root)
    grid = cache.pipeline.grid
    cx, cy = args.center
    tiles = grid.tiles_in_radius(TileIndex(cx, cy, args.level), args.radius)
    result = cache.prestage(tiles)
    print(f"Generated {result['generated']}, cached {result['cached']}, "
          f"total {result['total']} tiles into {cache.project_dir}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    cfg = ProjectConfig.load(args.config)
    cache = TileCache(cfg, cache_root=args.cache_root)
    from .service import create_app
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required to serve: pip install uvicorn", file=sys.stderr)
        return 1
    app = create_app(cache)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"WARNING: binding to {args.host} exposes the service beyond this "
            "machine. It has no built-in auth unless WORLDGEN_API_TOKEN is set; "
            "put it behind an authenticating, rate-limiting proxy (see SECURITY.md)."
        )
    print(f"Serving project '{cfg.project_id}' on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="terrain_service",
                                description="Dynamic World Streaming terrain service.")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("init", help="Create a project config.")
    pi.add_argument("--project-id", required=True)
    pi.add_argument("--lat", type=float, required=True)
    pi.add_argument("--lon", type=float, required=True)
    pi.add_argument("--tile-size-m", type=float, default=1008.0)
    pi.add_argument("--mpp", type=float, default=1.0, help="Metres per pixel.")
    pi.add_argument("--elev-min", type=float, default=-500.0)
    pi.add_argument("--elev-max", type=float, default=9000.0)
    pi.add_argument("--dem-type", default="SRTMGL1")
    pi.add_argument("--provider", default="opentopography",
                    choices=available_providers())
    pi.add_argument("--crs", default=None, help="Override CRS (default auto-UTM).")
    pi.add_argument("-o", "--output", required=True)
    pi.set_defaults(func=cmd_init)

    pg = sub.add_parser("generate", help="Generate a block of tiles to disk.")
    _add_config_arg(pg)
    pg.add_argument("--center", type=int, nargs=2, metavar=("X", "Y"),
                    default=[0, 0])
    pg.add_argument("--radius", type=int, default=1)
    pg.add_argument("--level", type=int, default=0)
    pg.set_defaults(func=cmd_generate)

    ps = sub.add_parser("serve", help="Run the HTTP terrain service.")
    _add_config_arg(ps)
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8000)
    ps.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

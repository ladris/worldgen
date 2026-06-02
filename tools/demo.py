"""One-command demo backend: create a synthetic project and serve it.

    python -m tools.demo                      # synthetic Denver, port 8000
    python -m tools.demo --provider opentopography --dem-type SRTMGL1
        (set OPENTOPOGRAPHY_API_KEY for real Earth)

This is the backend the Unreal example map points at. It needs no API key when
using the default 'synthetic' provider, so you can compile + run the engine side
end-to-end offline.
"""

from __future__ import annotations

import argparse

from terrain_service.config import ProjectConfig
from terrain_service.cache import TileCache
from terrain_service.providers import get_provider, available_providers


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the demo terrain service.")
    p.add_argument("--project-id", default="demo")
    p.add_argument("--lat", type=float, default=39.7392)
    p.add_argument("--lon", type=float, default=-104.9903)
    p.add_argument("--tile-size-m", type=float, default=1008.0)
    p.add_argument("--mpp", type=float, default=2.0)
    p.add_argument("--provider", default="synthetic", choices=available_providers())
    p.add_argument("--dem-type", default="SRTMGL1")
    p.add_argument("--cache-root", default=".worldgen_cache")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)

    cfg = ProjectConfig(
        project_id=args.project_id, origin_lat=args.lat, origin_lon=args.lon,
        tile_size_m=args.tile_size_m, meters_per_pixel=args.mpp,
        provider=args.provider, dem_type=args.dem_type,
    )
    provider = get_provider(args.provider, dem_type=args.dem_type)
    cache = TileCache(cfg, cache_root=args.cache_root, provider=provider)

    from terrain_service.service import create_app
    import uvicorn

    app = create_app(cache)
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: binding beyond localhost; the service has no built-in "
              "auth unless WORLDGEN_API_TOKEN is set. See SECURITY.md.")
    print("=" * 64)
    print(f" Dynamic World Streaming — demo service")
    print(f"   project   : {cfg.project_id}  ({args.provider})")
    print(f"   origin    : {args.lat}, {args.lon}  -> {cache.pipeline.grid.crs_string}")
    print(f"   tile      : {cfg.cells_per_tile} cells @ {cfg.meters_per_pixel} m/px")
    print(f"   serving   : http://{args.host}:{args.port}")
    print(f"   point Unreal's Service Base Url here.")
    print("=" * 64)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

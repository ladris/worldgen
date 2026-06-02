# The Python ↔ Unreal Contract (v1.1)

> v1.1 adds the editable-terrain layer (§7). v1.0 streaming is unchanged.


This is the **single source of truth** shared by the Python terrain service and
the Unreal C++ plugin. Both sides implement the same WorldGrid math and the same
heightmap/manifest formats. If this file changes, both sides change together and
`schema_version` is bumped.

---

## 1. WorldGrid coordinate system

A **project** is defined by a small config:

| Field | Meaning | Example |
|-------|---------|---------|
| `origin_lat`, `origin_lon` | WGS84 anchor point of the world | `39.7392, -104.9903` |
| `crs` | Projected, metric CRS (auto = UTM zone of origin) | `EPSG:32613` |
| `tile_size_m` | Side length of one tile, in metres | `1008.0` |
| `meters_per_pixel` | Ground sample distance | `1.0` |
| `elevation_min_m`, `elevation_max_m` | **Project-wide** elevation range for encoding | `-500.0, 9000.0` |
| `dem_type` | Provider DEM product | `SRTMGL1` |

Derived constants:

```
cells_per_tile    = round(tile_size_m / meters_per_pixel)      # e.g. 1008
samples_per_edge  = cells_per_tile + 1                          # e.g. 1009  (shared edges!)
```

### 1.1 Tile → projected bounds

Let `(E0, N0)` be the origin's easting/northing in the project CRS (the grid
origin). For integer tile indices `(x, y)` (signed; grow in any direction):

```
min_x = E0 + x * tile_size_m
min_y = N0 + y * tile_size_m
max_x = min_x + tile_size_m
max_y = min_y + tile_size_m
```

`x` increases east, `y` increases north. This mapping is **total and
deterministic**: every integer `(x, y)` names exactly one patch of Earth, and
adjacent tiles share an edge line exactly (`tile x`'s `max_x` == `tile x+1`'s
`min_x`).

### 1.2 Sampling grid (why edges weld)

Tile `(x, y)` is sampled at `samples_per_edge²` points. Sample `(col, row)`,
`col, row ∈ [0, cells_per_tile]`, has projected coordinates:

```
px = min_x + col * meters_per_pixel
py = max_y - row * meters_per_pixel        # row 0 = north edge (image top)
```

The east column (`col = cells_per_tile`) of tile `(x, y)` lands on `max_x`,
which equals the west column (`col = 0`) of tile `(x+1, y)` at `min_x`. Same
world coordinate → same sampled elevation → **weldable vertices with zero gap**.

> Heightmap images therefore *overlap by one sample row/column* with each
> neighbour. This is intentional and is the standard terrain-tiling convention.

---

## 2. Elevation encoding (absolute, project-wide)

Every tile encodes elevation to uint16 with the **same** linear map:

```
u16 = clamp( round( (elev_m - elevation_min_m)
                    / (elevation_max_m - elevation_min_m) * 65535 ), 0, 65535 )
```

NoData samples are filled (interpolated/clamped) before encoding — a streaming
world cannot contain holes. The decode is exact and identical everywhere:

```
elev_m = elevation_min_m + (u16 / 65535) * (elevation_max_m - elevation_min_m)
```

Because the map is project-constant, the **Unreal Z-scale is one constant for the
whole world** (see §4), which is what makes vertical continuity automatic.

Vertical precision = `(elevation_max_m - elevation_min_m) / 65535`. For
`-500..9000 m` that is ≈ **0.145 m / level** — fine for terrain. Projects needing
finer detail set a tighter range.

---

## 3. Wire formats

### 3.1 Heightmap

- **Format:** headerless raw `uint16`, little-endian, row-major, top row = north.
  File suffix `.r16`. (Unreal-native; also emit 16-bit PNG for inspection.)
- **Dimensions:** `samples_per_edge × samples_per_edge`.

### 3.2 Manifest (JSON sidecar, also the HTTP JSON body)

```jsonc
{
  "schema_version": "1.0",
  "project_id": "denver-front-range",
  "tile": { "level": 0, "x": 12, "y": -3 },
  "grid": {
    "crs": "EPSG:32613",
    "origin_easting_m": 500000.0,
    "origin_northing_m": 4399999.99,
    "tile_size_m": 1008.0,
    "meters_per_pixel": 1.0,
    "cells_per_tile": 1008,
    "samples_per_edge": 1009
  },
  "bounds_projected_m": { "min_x": 512096.0, "min_y": 4396975.99,
                          "max_x": 513104.0, "max_y": 4397983.99 },
  "bounds_wgs84": { "west": -104.0, "south": 39.0, "east": -103.98, "north": 39.02 },
  "elevation": {
    "project_min_m": -500.0, "project_max_m": 9000.0,
    "tile_min_m": 1604.2, "tile_max_m": 1789.7,
    "encoding": "uint16_linear_absolute"
  },
  "heightmap": { "format": "r16", "width": 1009, "height": 1009,
                 "bbp": 16, "byte_order": "little", "row_order": "north_to_south" },
  "unreal": {
    "vertex_spacing_cm": 100.0,
    "tile_location_cm": { "x": 1209600.0, "y": -302400.0, "z": 0.0 },
    "scale": { "x": 100.0, "y": 100.0, "z": 1855.47 }
  },
  "neighbors": {
    "north": { "level": 0, "x": 12, "y": -2 },
    "south": { "level": 0, "x": 12, "y": -4 },
    "east":  { "level": 0, "x": 13, "y": -3 },
    "west":  { "level": 0, "x": 11, "y": -3 }
  },
  "content_hash": "sha256:…"   // hash of the .r16; for cache validation
}
```

---

## 4. Unreal placement math

The Unreal world is the project CRS scaled to centimetres, with the project
origin at Unreal world `(0,0)`.

```
vertex_spacing_cm = meters_per_pixel * 100
tile_location_cm.x = x * tile_size_m * 100
tile_location_cm.y = y * tile_size_m * 100        // +Y = north (left-handed: see note)
tile_location_cm.z = 0
```

Constant world Z-scale (Unreal's internal height span is 512 units):

```
scale.z = (elevation_max_m - elevation_min_m) * 100 / 512
```

A decoded sample `u16` becomes a vertex Z, in cm, of:

```
z_cm = (elevation_min_m * 100) + (u16 / 65535) * (elevation_max_m - elevation_min_m) * 100
```

> **Axis note:** Unreal is left-handed, +X forward, +Y right, +Z up. The grid's
> +Y (north) maps to Unreal +Y; row 0 of the heightmap (north) is placed at the
> tile's max-Y edge. The plugin centralises this in one transform so it is
> defined in exactly one place.

---

## 5. HTTP API

Base URL e.g. `http://127.0.0.1:8000`.

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/health` | `{"status":"ok","project_id":…}` |
| `GET` | `/project` | full project config + derived grid constants |
| `GET` | `/tile/{level}/{x}/{y}/manifest` | manifest JSON (generates if needed) |
| `GET` | `/tile/{level}/{x}/{y}/heightmap.r16` | raw uint16 body, `X-Tile-Manifest` header carries manifest URL |
| `GET` | `/tile/{level}/{x}/{y}` | multipart: manifest + heightmap (one round-trip) |
| `POST` | `/prestage` | body `{tiles:[{level,x,y},…]}` → warms cache async, returns job status |

Errors use standard HTTP codes; body `{"error": "...", "tile": {...}}`.

`level` is reserved for future LOD/zoom pyramids; `level 0` = native resolution.

---

## 7. Editable terrain layer (v1.1)

The world is **persistently editable**. The op log (server-side) is the source
of truth; tiles served by `/tile/...` are the composited result of base terrain
+ all edits. Persistence is therefore automatic: re-fetching a tile yields the
edited terrain. Edits crossing tile boundaries are applied on a shared mosaic so
shared edges stay byte-identical (no seams).

### 7.1 Edit operations

A brush stroke, expressed in **Unreal world centimetres** (what the UE client
has). The service converts to projected metres for evaluation.

| Field | Meaning |
|-------|---------|
| `type` | `raise_lower` \| `flatten` \| `smooth` |
| `center_x_cm`, `center_y_cm` | brush centre, Unreal world cm |
| `radius_m` | brush radius, metres |
| `strength_m` | raise_lower: +up / −down, metres |
| `target_height_m` | flatten target, metres |
| `falloff` | `smooth` \| `linear` \| `constant` |
| `iterations` | smooth passes |

Surface-only for now; the op record is extensible so a future **volumetric**
layer (caves/overhangs via voxel/SDF) can add op types without changing the
transport.

### 7.2 Endpoints

| Method | Path | Body / Returns |
|--------|------|----------------|
| `POST` | `/edit` | EditOp → `{op_id, affected:[tile…], manifests:[…]}` |
| `POST` | `/edit/undo` | → `{undone:op_id, affected:[tile…]}` |
| `GET`  | `/tile/{l}/{x}/{y}/edits` | ops affecting that tile (for replay/inspection) |

After an edit, affected tiles' `content_hash` changes; a client may compare
hashes to detect tiles it should refetch. The UE client applies the brush to the
live mesh immediately for instant feedback, and the next stream-in reconciles to
the authoritative composited tile.

## 6. Versioning

`schema_version` is `MAJOR.MINOR`. Breaking changes to grid math, encoding, or
formats bump MAJOR and require both halves to update in lockstep. Additive,
backward-compatible fields bump MINOR.

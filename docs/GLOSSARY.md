# Glossary

Domain terms used across the project, for newcomers from either a game-dev or a
GIS background (this project sits at the intersection of both).

### DEM (Digital Elevation Model)
A raster where each pixel stores a ground elevation. Our real-world data source
(OpenTopography) serves DEMs as GeoTIFFs. Products include SRTMGL1 (~30 m),
NASADEM, COP30, etc.

### Heightmap
A grayscale image where pixel brightness = terrain height. Unreal imports 16-bit
heightmaps (values 0–65535). We emit them as raw `.r16` (and `.png` previews).

### `.r16`
A headerless raw file of little-endian `uint16` samples, row-major, north row
first. Unreal-native heightmap format. Each tile is `samples_per_edge²` values.

### WorldGrid
The deterministic mapping between an integer tile index `(x, y)` and a patch of
the real Earth, in a projected metric CRS anchored at the project origin. The
keystone of the system: it makes every tile reproducible and makes neighbouring
tiles share edges exactly. (Python: `terrain_service/tile_grid.py`; Unreal:
`WorldGrid.h`.)

### Tile
One square chunk of terrain, addressed by `(level, x, y)`. Footprint =
`tile_size_m` metres on a side; sampled at `samples_per_edge × samples_per_edge`
points. `level 0` is native resolution (levels reserved for a future LOD
pyramid).

### Shared edge / welding
Tile `(x, y)` is sampled at `cells + 1` points per edge, so its east column lands
on the *same world coordinate* as tile `(x+1, y)`'s west column. Same coordinate
→ same elevation → vertices "weld" with zero gap. This is why there are no
cracks between tiles. (Heightmaps therefore overlap their neighbours by one
sample row/column — intentional.)

### CRS (Coordinate Reference System) / UTM / EPSG
A CRS defines how coordinates map to the Earth. **WGS84** (EPSG:4326) is
lat/lon. **UTM** zones are *projected* CRSs measured in metres, ideal for 1:1
game scale. Each is identified by an **EPSG** code (e.g. `EPSG:32613` = UTM
zone 13N). We auto-pick the UTM zone of the project origin.

### Projected vs geographic coordinates
*Geographic* = lat/lon (degrees, WGS84). *Projected* = metres in a flat plane
(UTM). The service reprojects DEM data into the project's UTM CRS so 1 pixel = a
fixed number of metres everywhere.

### Absolute elevation encoding
Every tile maps metres → uint16 using **one project-wide** range
(`elevation_min_m … elevation_max_m`), not per-tile min/max. Consequence: the
Unreal vertical (Z) scale is a single constant for the whole world, so heights
are continuous across every boundary. (`terrain_service/elevation.py`.)

### Manifest
The JSON emitted with each tile: its grid placement, Unreal location/scale,
elevation range, heightmap dimensions, neighbours, and a content hash. The
contract both halves agree on. (`docs/CONTRACT.md` §3.2.)

### Provider
A pluggable source of elevation. `synthetic` = deterministic analytic terrain
(offline, no key). `opentopography` = real Earth via the OpenTopography API.
(`terrain_service/providers/`.)

### Edit op / edit layer
A persistent terrain modification (brush stroke): `raise_lower`, `flatten`, or
`smooth`. The authoritative **op log** lives in the service; tiles served are the
**composited** result of base terrain + ops. (`terrain_service/edits.py`,
`edit_store.py`.)

### Composite / base
**Base** = pristine terrain straight from the provider. **Composite** = base with
all edits applied. The service stores base snapshots and rebuilds composited
tiles by replaying the op log over a mosaic of the affected tiles.

### Streaming / prediction / buffer zone
**Streaming** = loading/unloading tiles as the player moves. **Prediction** =
extrapolating the player's velocity to pre-load tiles *ahead* of travel.
**Buffer zone** = the margin around the player kept loaded so they never see an
edge. (Unreal: `PlayerPredictionComponent`, `RegionStreamingManager`.)

### UDynamicMeshComponent
Unreal's modern runtime mesh component (Geometry Scripting / `FDynamicMesh3`),
with emerging Lumen support in 5.5. Each terrain tile builds one. The design
report's recommended choice over the older `UProceduralMeshComponent`.

### World Partition
Unreal's built-in large-world streaming framework. Our dynamic tiles are
currently streamed by our own manager (a custom layer) that coexists with World
Partition; deeper WP integration is a roadmap item.

### Large World Coordinates (LWC)
UE5's double-precision world coordinates, needed so positions far from the
origin don't lose float precision. Relevant to the "enter anywhere on Earth"
goal (roadmap Phase 4).

### Volumetric / voxel / SDF
Representations that can express caves and overhangs (a point in space is
solid/empty), unlike a heightfield (one height per location). Planned as a
future second terrain layer (roadmap Phase 7).

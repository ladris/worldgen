# Good First Issues — Starter Tasks

A curated list of well-scoped tasks to get started, grouped by area and rough
difficulty. New here? Do the [Quickstart](QUICKSTART.md) first, skim the
[Architecture](ARCHITECTURE.md), and read [CONTRIBUTING](../CONTRIBUTING.md).

> Maintainers: these are good candidates to file as GitHub issues with the
> `good first issue` / `help wanted` labels.

## 🟢 Easy — get familiar

- **Compile the Unreal plugin in UE 5.5 and report build fixes.** The single
  most valuable starter task right now. Follow
  [`unreal/.../SETUP.md`](../unreal/DynamicWorldStreaming/SETUP.md) and
  [`EXAMPLE.md`](../unreal/DynamicWorldStreaming/EXAMPLE.md); open a PR/issue
  with any API nits you had to fix.
- **Stitched-mosaic preview tool.** Add `tools/preview_mosaic.py` that loads a
  block of cached `.png` tiles and writes one stitched image (handling the
  1-sample shared edge) so people can *see* seamlessness. (Logic already
  sketched in `docs/QUICKSTART.md` Stage 3.)
- **Improve error messages** when the OpenTopography key is missing or the API
  returns an error TIFF (point users to `--provider synthetic`).
- **Docs polish**: typos, clearer diagrams, a screenshots/GIF section in the
  README once the engine side runs.

## 🟡 Medium — extend the service

- **Add a DEM provider.** Subclass `DEMProvider` for USGS 3DEP, Copernicus DEM,
  or a **local GeoTIFF folder** provider (great for offline real data). See
  `providers/opentopography.py`. Add a test.
- **Cloud-Optimized GeoTIFF (COG) input** for OpenTopography to speed up
  fetches (read only the needed window).
- **`material/paint` edit op** (texture/biome layer, not height) — design the
  data model alongside the existing height edit layer.
- **Async prestage worker** + a `/prestage` status endpoint so clients can warm
  a region and poll progress.
- **Dockerfile + compose** for the terrain service (one-command deploy).

## 🟠 Larger — needs a design discussion first

- **Smooth-across-region-boundary refinement** (documented limitation in
  `edit_store.py`): make `smooth` identical at the seam between separately-edited
  regions (e.g. halo sampling).
- **Runtime LOD pyramid** (`level > 0`): the grid already supports it; implement
  mesh LOD generation/swapping in the UE plugin.
- **Roadmap Phases 4–7** (enter-anywhere + precision, VR tools, object
  placement, volumetric terrain). Open a Discussion before large work — see
  [`ROADMAP.md`](ROADMAP.md).

## How to claim one

Comment on the issue (or open one referencing this list) saying you're picking
it up, ask any clarifying questions, then open a draft PR early so feedback comes
before the work is "done."

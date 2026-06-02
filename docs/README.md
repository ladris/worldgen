# Documentation Index

Start here, then follow the path that fits you.

## Get going
- **[QUICKSTART](QUICKSTART.md)** — from clone to streaming + editing terrain in
  stages (Python-only path works today, no UE/API key/GPU).
- **[GLOSSARY](GLOSSARY.md)** — the vocabulary (DEM, WorldGrid, tile, manifest,
  CRS, edit op, …) for newcomers from game-dev *or* GIS backgrounds.

## Understand the system
- **[ARCHITECTURE](ARCHITECTURE.md)** — the master blueprint: the two halves,
  the module map, the runtime flow, and *why seams are impossible by design*.
- **[CONTRACT](CONTRACT.md)** — the exact Python↔Unreal contract: WorldGrid
  math, absolute elevation encoding, heightmap/manifest formats, HTTP API, and
  the editable-terrain endpoints (v1.1).
- **[ROADMAP](ROADMAP.md)** — phased status and the path to the full vision
  (enter-anywhere, VR, objects, volumetric).

## Build / run the engine side
- **[Unreal SETUP](../unreal/DynamicWorldStreaming/SETUP.md)** — install the
  plugin, dependencies, and first-build fixes.
- **[Unreal EXAMPLE](../unreal/DynamicWorldStreaming/EXAMPLE.md)** — no-Blueprint,
  no-VR first-compile walkthrough (fly + sculpt on desktop).

## Contribute
- **[CONTRIBUTING](../CONTRIBUTING.md)** — dev setup, the contract discipline,
  branching/PR conventions, extension points (add a provider / edit-op).
- **[GOOD_FIRST_ISSUES](GOOD_FIRST_ISSUES.md)** — curated starter tasks.
- **[CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md)** — community expectations.
- **[SECURITY](../SECURITY.md)** — threat model and how to report vulnerabilities.
- **[CHANGELOG](../CHANGELOG.md)** — what's landed.

## Legacy
- **[LEGACY_IMPORTER](LEGACY_IMPORTER.md)** — the original single-shot CLI tool
  the project grew from.

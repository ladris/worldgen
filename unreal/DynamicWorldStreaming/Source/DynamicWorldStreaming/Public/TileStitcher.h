// Copyright worldgen. Dynamic World Streaming plugin.
//
// FTileStitcher: reconciles shared-edge vertex normals between adjacent tiles
// so lighting is continuous across boundaries (design report §5.3.2).
//
// Geometric welding is already guaranteed by the data: neighbouring tiles share
// identical edge sample positions (CONTRACT §1.2), so there are never gaps or
// cracks. The only remaining discontinuity is shading — each tile computes edge
// normals from its own faces only. This pass averages the two sides' edge
// normals and assigns the result to both, removing the lighting seam.
//
// NOTE: This operates on the runtime UDynamicMeshComponent meshes and must be
// validated in-engine. A halo-based alternative (sample one extra ring of
// neighbour data at generation time so boundary normals already match) is
// documented in the .cpp and is the recommended long-term optimisation.

#pragma once

#include "CoreMinimal.h"
#include "TerrainStreamingTypes.h"

class ATerrainTileActor;

class DYNAMICWORLDSTREAMING_API FTileStitcher
{
public:
	/** Which shared edge of A meets B. */
	enum class EEdge { North, South, East, West };

	/** Average and reconcile the shared-edge vertex normals of two adjacent,
	 *  already-built tiles. EdgeOfA names A's edge that touches B. */
	static void StitchPair(ATerrainTileActor* A, ATerrainTileActor* B, EEdge EdgeOfA);
};

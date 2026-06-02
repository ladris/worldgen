// Copyright worldgen. Dynamic World Streaming plugin.
//
// ATerrainTileActor: one streamed terrain tile. Converts a decoded heightmap
// into a UDynamicMeshComponent mesh on a worker thread, then publishes to the
// game thread. Holds the data needed by the stitcher to reconcile shared-edge
// normals with neighbours. See docs/CONTRACT.md §4 and ARCHITECTURE §5.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TerrainStreamingTypes.h"
#include "TerrainDataClient.h"
#include "TerrainTileActor.generated.h"

class UDynamicMeshComponent;

UCLASS()
class DYNAMICWORLDSTREAMING_API ATerrainTileActor : public AActor
{
	GENERATED_BODY()

public:
	ATerrainTileActor();

	/** Build the tile geometry from a fetched heightmap. Mesh generation runs
	 *  on a worker thread; OnBuilt fires on the game thread when visible. */
	void BuildFromHeightmap(const FTileHeightmap& Heightmap,
							 const FProjectGridConfig& GridConfig);

	UFUNCTION(BlueprintCallable, Category = "WorldStreaming")
	FTileKey GetTileKey() const { return TileKey; }

	ETileState GetState() const { return State; }

	/** Cooks collision asynchronously once the mesh is present. */
	void EnableCollisionAsync();

	/** Immediately deform this tile's mesh under a brush, for instant VR
	 *  feedback. The authoritative result is reconciled on the next stream-in
	 *  from the service. BrushCenterWorldCm is in Unreal world space.
	 *  Returns true if any vertex was affected. */
	bool ApplyBrushLocal(const FVector& BrushCenterWorldCm, float RadiusM,
						 EBrushType Type, float StrengthM, float TargetHeightM);

	UPROPERTY(VisibleAnywhere, Category = "WorldStreaming")
	TObjectPtr<UDynamicMeshComponent> MeshComponent;

	/** World-space vertex Z (cm) on each edge, kept for the stitcher. Indexed
	 *  along the edge in ascending col/row order. */
	TArray<double> EdgeNorth, EdgeSouth, EdgeEast, EdgeWest;

	DECLARE_MULTICAST_DELEGATE_OneParam(FOnTileBuilt, ATerrainTileActor*);
	FOnTileBuilt OnBuilt;

protected:
	UPROPERTY()
	FTileKey TileKey;

	ETileState State = ETileState::None;

	int32 Width = 0;
	int32 Height = 0;
};

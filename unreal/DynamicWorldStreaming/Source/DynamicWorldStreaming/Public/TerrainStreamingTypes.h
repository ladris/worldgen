// Copyright worldgen. Dynamic World Streaming plugin.
//
// Shared types mirroring docs/CONTRACT.md. The Python terrain service performs
// all geodesy (CRS, reprojection, encoding); Unreal consumes the pre-computed
// manifest and works purely in Unreal world space + grid indices.

#pragma once

#include "CoreMinimal.h"
#include "TerrainStreamingTypes.generated.h"

/** Address of a tile in the world grid. Mirrors CONTRACT §1. */
USTRUCT(BlueprintType)
struct FTileKey
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "WorldGrid")
	int32 X = 0;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "WorldGrid")
	int32 Y = 0;

	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "WorldGrid")
	int32 Level = 0;

	FTileKey() = default;
	FTileKey(int32 InX, int32 InY, int32 InLevel = 0) : X(InX), Y(InY), Level(InLevel) {}

	bool operator==(const FTileKey& Other) const
	{
		return X == Other.X && Y == Other.Y && Level == Other.Level;
	}

	FString ToString() const { return FString::Printf(TEXT("L%d/%d/%d"), Level, X, Y); }

	friend uint32 GetTypeHash(const FTileKey& Key)
	{
		return HashCombine(HashCombine(GetTypeHash(Key.X), GetTypeHash(Key.Y)),
						   GetTypeHash(Key.Level));
	}
};

/** Project + grid configuration, from the service's /project endpoint. */
USTRUCT(BlueprintType)
struct FProjectGridConfig
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	FString ProjectId;

	/** Tile footprint, metres. */
	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double TileSizeM = 1008.0;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double MetersPerPixel = 1.0;

	/** Samples (vertices) per tile edge = cells + 1 (shared edges). */
	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	int32 SamplesPerEdge = 1009;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double ElevationMinM = -500.0;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double ElevationMaxM = 9000.0;

	/** Constant world Z-scale (CONTRACT §4): (span_m * 100) / 512. */
	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double UEScaleZ = 1855.46875;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double VertexSpacingCm = 100.0;

	bool IsValid() const { return SamplesPerEdge > 1 && TileSizeM > 0.0; }
};

/** Per-tile placement + decode info, from a tile manifest. */
USTRUCT(BlueprintType)
struct FTileManifest
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	FTileKey Tile;

	/** Grid-origin corner of the tile in Unreal world space (cm). */
	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	FVector TileLocationCm = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	int32 Width = 0;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	int32 Height = 0;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double ElevationMinM = -500.0;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double ElevationMaxM = 9000.0;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	double VertexSpacingCm = 100.0;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	FString HeightmapUrl;

	UPROPERTY(BlueprintReadOnly, Category = "WorldGrid")
	FString ContentHash;

	bool bValid = false;
};

/** Lifecycle state of a streamed tile. */
UENUM(BlueprintType)
enum class ETileState : uint8
{
	None,
	Requested,    // manifest/heightmap fetch in flight
	Building,     // mesh generation on a worker thread
	Active,       // visible, collision present
	Stitched,     // edge normals reconciled with neighbours
	Unloading
};

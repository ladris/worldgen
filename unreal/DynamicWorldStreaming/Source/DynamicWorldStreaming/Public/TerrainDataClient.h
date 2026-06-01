// Copyright worldgen. Dynamic World Streaming plugin.
//
// UTerrainDataClient: async HTTP access to the worldgen terrain service. Fetches
// the project/grid config, per-tile manifests, and raw .r16 heightmaps, parsing
// them into the plugin's structs. All requests are non-blocking; results arrive
// on the game thread via TFunction callbacks.

#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "Interfaces/IHttpRequest.h"
#include "TerrainStreamingTypes.h"
#include "TerrainDataClient.generated.h"

/** Decoded heightmap payload for one tile: manifest + raw uint16 samples. */
struct FTileHeightmap
{
	FTileManifest Manifest;
	TArray<uint16> Samples;   // row-major, north row first; size = Width*Height
	bool bValid = false;
};

DECLARE_DELEGATE_OneParam(FOnProjectConfig, const FProjectGridConfig& /*Config*/);
DECLARE_DELEGATE_OneParam(FOnTileFetched, const FTileHeightmap& /*Tile*/);

UCLASS()
class DYNAMICWORLDSTREAMING_API UTerrainDataClient : public UObject
{
	GENERATED_BODY()

public:
	/** Set the service base URL, e.g. http://127.0.0.1:8000 (no trailing slash). */
	void Initialize(const FString& InBaseUrl);

	/** GET /project → grid config. */
	void FetchProjectConfig(FOnProjectConfig OnComplete);

	/** GET manifest then heightmap.r16 for a tile; callback once both arrive. */
	void FetchTile(const FTileKey& Tile, FOnTileFetched OnComplete);

private:
	FString BaseUrl;

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> MakeGet(const FString& Path);

	static bool ParseProjectConfig(const FString& Json, FProjectGridConfig& Out);
	static bool ParseManifest(const FString& Json, FTileManifest& Out);

	void FetchHeightmap(const FTileManifest& Manifest, FOnTileFetched OnComplete);
};

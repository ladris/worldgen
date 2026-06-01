// Copyright worldgen. Dynamic World Streaming plugin.
//
// URegionStreamingManager: the runtime orchestrator (design report §9.1 modules
// 3 + 10). A world subsystem that, every update, asks the predictor which tiles
// the player needs, fetches the missing ones from the terrain service (bounded
// concurrency), spawns ATerrainTileActors for them, stitches new tiles to their
// active neighbours, and unloads tiles the player has left behind.
//
// These dynamic tiles are streamed by THIS manager (a custom streaming layer);
// it coexists with World Partition rather than injecting into WP's runtime hash
// (which the report flags as advanced/non-trivial — see SETUP.md for notes).

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "TerrainStreamingTypes.h"
#include "WorldGrid.h"
#include "RegionStreamingManager.generated.h"

class UTerrainDataClient;
class ATerrainTileActor;
class UPlayerPredictionComponent;

UCLASS()
class DYNAMICWORLDSTREAMING_API URegionStreamingManager : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	// USubsystem
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// FTickableGameObject (via UTickableWorldSubsystem)
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

	/** Begin streaming using project-settings values. Fetches /project first. */
	UFUNCTION(BlueprintCallable, Category = "WorldStreaming")
	void StartStreaming();

	UFUNCTION(BlueprintCallable, Category = "WorldStreaming")
	void StopStreaming();

	UFUNCTION(BlueprintCallable, Category = "WorldStreaming")
	int32 GetActiveTileCount() const { return ActiveTiles.Num(); }

private:
	UPROPERTY()
	TObjectPtr<UTerrainDataClient> Client;

	UPROPERTY()
	TMap<FTileKey, TObjectPtr<ATerrainTileActor>> ActiveTiles;

	TSet<FTileKey> InFlight;

	FWorldGrid Grid;
	bool bConfigReady = false;
	bool bStreaming = false;
	float TimeSinceUpdate = 0.0f;

	// settings snapshot
	FString BaseUrl;
	int32 LoadRadius = 2;
	int32 UnloadRadius = 4;
	int32 MaxConcurrentFetches = 6;
	float UpdateInterval = 0.25f;
	bool bEnableStitching = true;

	void UpdateStreaming();
	void RequestTile(const FTileKey& Tile);
	void OnTileBuilt(ATerrainTileActor* Tile);
	void StitchWithNeighbors(ATerrainTileActor* Tile);
	void UnloadFarTiles(const FTileKey& Center);

	UPlayerPredictionComponent* FindPredictor() const;
	bool GetPlayerTile(FTileKey& OutTile) const;
};

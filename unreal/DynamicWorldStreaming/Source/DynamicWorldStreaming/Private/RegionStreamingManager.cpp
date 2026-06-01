// Copyright worldgen. Dynamic World Streaming plugin.

#include "RegionStreamingManager.h"
#include "DynamicWorldStreaming.h"
#include "DynamicWorldStreamingSettings.h"
#include "TerrainDataClient.h"
#include "TerrainTileActor.h"
#include "TileStitcher.h"
#include "PlayerPredictionComponent.h"

#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"

void URegionStreamingManager::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	Client = NewObject<UTerrainDataClient>(this);

	const UDynamicWorldStreamingSettings* Settings = GetDefault<UDynamicWorldStreamingSettings>();
	BaseUrl = Settings->ServiceBaseUrl;
	LoadRadius = Settings->LoadRadius;
	UnloadRadius = FMath::Max(Settings->UnloadRadius, Settings->LoadRadius + 1);
	MaxConcurrentFetches = Settings->MaxConcurrentFetches;
	UpdateInterval = Settings->UpdateIntervalSeconds;
	bEnableStitching = Settings->bEnableStitching;

	if (Settings->bAutoStart)
	{
		StartStreaming();
	}
}

void URegionStreamingManager::Deinitialize()
{
	StopStreaming();
	Super::Deinitialize();
}

bool URegionStreamingManager::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId URegionStreamingManager::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(URegionStreamingManager, STATGROUP_Tickables);
}

void URegionStreamingManager::StartStreaming()
{
	if (bStreaming)
	{
		return;
	}
	bStreaming = true;
	Client->Initialize(BaseUrl);

	UE_LOG(LogDynamicWorldStreaming, Log, TEXT("Streaming start; fetching project config from %s"), *BaseUrl);

	TWeakObjectPtr<URegionStreamingManager> WeakThis(this);
	Client->FetchProjectConfig(FOnProjectConfig::CreateLambda(
		[WeakThis](const FProjectGridConfig& Config)
		{
			URegionStreamingManager* Self = WeakThis.Get();
			if (!Self) { return; }
			if (!Config.IsValid())
			{
				UE_LOG(LogDynamicWorldStreaming, Error,
					TEXT("Project config invalid; streaming disabled. Is the service running?"));
				Self->bStreaming = false;
				return;
			}
			Self->Grid.SetConfig(Config);
			Self->bConfigReady = true;
			// Propagate the grid to any predictor on the player pawn.
			if (UPlayerPredictionComponent* Pred = Self->FindPredictor())
			{
				Pred->SetGrid(Self->Grid);
				Pred->LoadRadius = Self->LoadRadius;
			}
			UE_LOG(LogDynamicWorldStreaming, Log,
				TEXT("Project '%s' ready: %d samples/edge, tile %.0f m, Zscale %.2f"),
				*Config.ProjectId, Config.SamplesPerEdge, Config.TileSizeM, Config.UEScaleZ);
		}));
}

void URegionStreamingManager::StopStreaming()
{
	bStreaming = false;
	for (auto& Pair : ActiveTiles)
	{
		if (IsValid(Pair.Value))
		{
			Pair.Value->Destroy();
		}
	}
	ActiveTiles.Empty();
	InFlight.Empty();
}

void URegionStreamingManager::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	if (!bStreaming || !bConfigReady)
	{
		return;
	}
	TimeSinceUpdate += DeltaTime;
	if (TimeSinceUpdate < UpdateInterval)
	{
		return;
	}
	TimeSinceUpdate = 0.0f;
	UpdateStreaming();
}

UPlayerPredictionComponent* URegionStreamingManager::FindPredictor() const
{
	if (const UWorld* World = GetWorld())
	{
		if (const APlayerController* PC = World->GetFirstPlayerController())
		{
			if (const APawn* Pawn = PC->GetPawn())
			{
				return Pawn->FindComponentByClass<UPlayerPredictionComponent>();
			}
		}
	}
	return nullptr;
}

bool URegionStreamingManager::GetPlayerTile(FTileKey& OutTile) const
{
	if (const UWorld* World = GetWorld())
	{
		if (const APlayerController* PC = World->GetFirstPlayerController())
		{
			if (const APawn* Pawn = PC->GetPawn())
			{
				OutTile = Grid.TileForWorldLocation(Pawn->GetActorLocation());
				return true;
			}
		}
	}
	return false;
}

void URegionStreamingManager::UpdateStreaming()
{
	// Desired set: from the predictor if present, else a plain radius block.
	TArray<FTileKey> Desired;
	FTileKey PlayerTile;
	if (UPlayerPredictionComponent* Pred = FindPredictor())
	{
		Pred->SetGrid(Grid);
		Desired = Pred->ComputeDesiredTiles();
		PlayerTile = Pred->CurrentTile();
	}
	else if (GetPlayerTile(PlayerTile))
	{
		Desired = Grid.TilesInRadius(PlayerTile, LoadRadius);
	}
	else
	{
		return; // no player yet
	}

	// Request missing tiles, respecting the concurrency budget. Desired is
	// priority-ordered (nearest/most-imminent first).
	int32 Budget = MaxConcurrentFetches - InFlight.Num();
	for (const FTileKey& Tile : Desired)
	{
		if (Budget <= 0)
		{
			break;
		}
		if (ActiveTiles.Contains(Tile) || InFlight.Contains(Tile))
		{
			continue;
		}
		RequestTile(Tile);
		--Budget;
	}

	UnloadFarTiles(PlayerTile);
}

void URegionStreamingManager::RequestTile(const FTileKey& Tile)
{
	InFlight.Add(Tile);
	TWeakObjectPtr<URegionStreamingManager> WeakThis(this);

	Client->FetchTile(Tile, FOnTileFetched::CreateLambda(
		[WeakThis, Tile](const FTileHeightmap& Heightmap)
		{
			URegionStreamingManager* Self = WeakThis.Get();
			if (!Self) { return; }
			Self->InFlight.Remove(Tile);

			if (!Heightmap.bValid)
			{
				UE_LOG(LogDynamicWorldStreaming, Warning,
					TEXT("Tile %s fetch invalid; will retry on a later update."),
					*Tile.ToString());
				return;
			}
			if (Self->ActiveTiles.Contains(Tile))
			{
				return; // raced; already have it
			}

			UWorld* World = Self->GetWorld();
			if (!World) { return; }

			FActorSpawnParameters Params;
			Params.Name = MakeUniqueObjectName(
				World, ATerrainTileActor::StaticClass(),
				*FString::Printf(TEXT("Tile_%d_%d_%d"), Tile.Level, Tile.X, Tile.Y));
			ATerrainTileActor* Actor = World->SpawnActor<ATerrainTileActor>(
				ATerrainTileActor::StaticClass(), FTransform::Identity, Params);
			if (!Actor) { return; }

			Actor->OnBuilt.AddUObject(Self, &URegionStreamingManager::OnTileBuilt);
			Self->ActiveTiles.Add(Tile, Actor);
			Actor->BuildFromHeightmap(Heightmap, Self->Grid.GetConfig());
		}));
}

void URegionStreamingManager::OnTileBuilt(ATerrainTileActor* Tile)
{
	if (!Tile || !bEnableStitching)
	{
		return;
	}
	StitchWithNeighbors(Tile);
}

void URegionStreamingManager::StitchWithNeighbors(ATerrainTileActor* Tile)
{
	const FTileKey Key = Tile->GetTileKey();
	FTileKey N, S, E, W;
	Grid.Neighbors(Key, N, S, E, W);

	auto TryStitch = [this, Tile](const FTileKey& NeighborKey, FTileStitcher::EEdge EdgeOfThis)
	{
		if (TObjectPtr<ATerrainTileActor>* Found = ActiveTiles.Find(NeighborKey))
		{
			ATerrainTileActor* Neighbor = *Found;
			if (IsValid(Neighbor) && Neighbor->GetState() == ETileState::Active)
			{
				FTileStitcher::StitchPair(Tile, Neighbor, EdgeOfThis);
			}
		}
	};

	TryStitch(N, FTileStitcher::EEdge::North);
	TryStitch(S, FTileStitcher::EEdge::South);
	TryStitch(E, FTileStitcher::EEdge::East);
	TryStitch(W, FTileStitcher::EEdge::West);
}

void URegionStreamingManager::UnloadFarTiles(const FTileKey& Center)
{
	TArray<FTileKey> ToRemove;
	for (const auto& Pair : ActiveTiles)
	{
		const FTileKey& K = Pair.Key;
		const int32 Cheb = FMath::Max(FMath::Abs(K.X - Center.X),
									  FMath::Abs(K.Y - Center.Y));
		if (Cheb > UnloadRadius)
		{
			ToRemove.Add(K);
		}
	}
	for (const FTileKey& K : ToRemove)
	{
		if (TObjectPtr<ATerrainTileActor>* Found = ActiveTiles.Find(K))
		{
			if (IsValid(*Found))
			{
				(*Found)->Destroy();
			}
		}
		ActiveTiles.Remove(K);
	}
}

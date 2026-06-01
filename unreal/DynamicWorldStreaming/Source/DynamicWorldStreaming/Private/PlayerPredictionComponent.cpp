// Copyright worldgen. Dynamic World Streaming plugin.

#include "PlayerPredictionComponent.h"
#include "DynamicWorldStreaming.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/Actor.h"

UPlayerPredictionComponent::UPlayerPredictionComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UPlayerPredictionComponent::BeginPlay()
{
	Super::BeginPlay();
}

FVector UPlayerPredictionComponent::GetPawnLocation() const
{
	if (const AActor* Owner = GetOwner())
	{
		return Owner->GetActorLocation();
	}
	return FVector::ZeroVector;
}

FVector UPlayerPredictionComponent::GetPawnVelocity() const
{
	if (const AActor* Owner = GetOwner())
	{
		return Owner->GetVelocity();
	}
	return FVector::ZeroVector;
}

FTileKey UPlayerPredictionComponent::CurrentTile() const
{
	return Grid.TileForWorldLocation(GetPawnLocation());
}

TArray<FTileKey> UPlayerPredictionComponent::ComputeDesiredTiles() const
{
	TArray<FTileKey> Desired;
	TSet<FTileKey> Seen;

	const FVector Location = GetPawnLocation();
	const FTileKey Center = Grid.TileForWorldLocation(Location);

	// 1. Always keep a solid block loaded around the player, ordered from the
	//    centre outward so the nearest tiles are fetched first.
	for (int32 Ring = 0; Ring <= LoadRadius; ++Ring)
	{
		for (const FTileKey& T : Grid.TilesInRadius(Center, Ring))
		{
			if (!Seen.Contains(T))
			{
				// Only the outermost ring is new each iteration; cheap dedup.
				const int32 Cheb = FMath::Max(FMath::Abs(T.X - Center.X),
											  FMath::Abs(T.Y - Center.Y));
				if (Cheb == Ring)
				{
					Seen.Add(T);
					Desired.Add(T);
				}
			}
		}
	}

	// 2. Predictive fan: extrapolate velocity forward and pre-load tiles along
	//    the travel direction so they arrive before the player does (§3.2).
	const FVector Velocity = GetPawnVelocity();
	const double Speed = Velocity.Size2D();
	if (Speed >= MinSpeedForPrediction && PredictiveLookaheadTiles > 0)
	{
		const FVector Predicted = Location + Velocity * PredictionHorizonSeconds;
		const FTileKey PredictedTile = Grid.TileForWorldLocation(Predicted);

		// Step along the line from the predicted tile, loading a small block at
		// the leading edge so turns are tolerated.
		const FVector2D Dir = FVector2D(Velocity.X, Velocity.Y).GetSafeNormal();
		for (int32 Step = 1; Step <= PredictiveLookaheadTiles; ++Step)
		{
			const FVector Probe = Predicted + FVector(Dir.X, Dir.Y, 0.0)
				* (Step * Grid.TileSizeCm());
			const FTileKey LeadTile = Grid.TileForWorldLocation(Probe);
			for (const FTileKey& T : Grid.TilesInRadius(LeadTile, 1))
			{
				if (!Seen.Contains(T))
				{
					Seen.Add(T);
					Desired.Add(T);
				}
			}
		}
		(void)PredictedTile;
	}

	return Desired;
}

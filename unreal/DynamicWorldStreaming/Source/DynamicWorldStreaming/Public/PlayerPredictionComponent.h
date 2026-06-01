// Copyright worldgen. Dynamic World Streaming plugin.
//
// UPlayerPredictionComponent: analyses the owning pawn's movement and predicts
// the set of grid tiles to pre-load. Implements the buffer-zone + trajectory
// extrapolation strategy from the design report §3. Deliberately simple and
// robust (the report warns against over-engineered prediction).

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TerrainStreamingTypes.h"
#include "WorldGrid.h"
#include "PlayerPredictionComponent.generated.h"

UCLASS(ClassGroup = (WorldStreaming), meta = (BlueprintSpawnableComponent))
class DYNAMICWORLDSTREAMING_API UPlayerPredictionComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPlayerPredictionComponent();

	/** How many rings of tiles to keep loaded around the player at all times. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldStreaming")
	int32 LoadRadius = 2;

	/** How far ahead (seconds) to extrapolate velocity for predictive loading. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldStreaming")
	float PredictionHorizonSeconds = 4.0f;

	/** Extra rings loaded in the predicted travel direction. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldStreaming")
	int32 PredictiveLookaheadTiles = 2;

	/** Speed (cm/s) below which prediction is disabled (player ~stationary). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "WorldStreaming")
	float MinSpeedForPrediction = 150.0f;

	void SetGrid(const FWorldGrid& InGrid) { Grid = InGrid; }

	/** Compute the desired tile set this frame: the load-radius block around the
	 *  player plus a predictive fan in the travel direction. Ordered by priority
	 *  (nearest / most-imminent first). */
	TArray<FTileKey> ComputeDesiredTiles() const;

	/** Tile the player currently occupies. */
	FTileKey CurrentTile() const;

protected:
	virtual void BeginPlay() override;

private:
	FWorldGrid Grid;

	FVector GetPawnLocation() const;
	FVector GetPawnVelocity() const;
};

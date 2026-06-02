// Copyright worldgen. Dynamic World Streaming plugin.
//
// UTerrainSculptComponent: the VR/interaction hook for editing terrain. Attach
// to a motion controller (or pawn) and bind your input to SculptTrace on the
// trigger. It line-traces to the streamed terrain and applies the active brush
// via URegionStreamingManager (instant local deform + persistent service edit).

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TerrainStreamingTypes.h"
#include "TerrainSculptComponent.generated.h"

UCLASS(ClassGroup = (WorldStreaming), meta = (BlueprintSpawnableComponent))
class DYNAMICWORLDSTREAMING_API UTerrainSculptComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UTerrainSculptComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sculpt")
	EBrushType BrushType = EBrushType::RaiseLower;

	/** Brush radius in metres. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sculpt", meta = (ClampMin = "1.0"))
	float RadiusM = 25.0f;

	/** Per-application strength in metres (raise_lower). Negative lowers. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sculpt")
	float StrengthM = 2.0f;

	/** Target height (metres) for the Flatten brush. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sculpt")
	float TargetHeightM = 0.0f;

	/** Max trace distance (cm) when sculpting via a ray (e.g. controller aim). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sculpt")
	float TraceDistanceCm = 100000.0f;

	/** Sculpt directly at a world location (e.g. the hand/controller position
	 *  when touching the ground). */
	UFUNCTION(BlueprintCallable, Category = "Sculpt")
	void SculptAtLocation(const FVector& WorldLocationCm);

	/** Line-trace from an origin along a direction and sculpt at the hit. Bind
	 *  this to the trigger using the motion controller's transform. Returns true
	 *  if terrain was hit. */
	UFUNCTION(BlueprintCallable, Category = "Sculpt")
	bool SculptTrace(const FVector& Origin, const FVector& Direction);

	/** Undo the most recent edit (whole world). */
	UFUNCTION(BlueprintCallable, Category = "Sculpt")
	void UndoLastEdit();

private:
	class URegionStreamingManager* GetManager() const;
};

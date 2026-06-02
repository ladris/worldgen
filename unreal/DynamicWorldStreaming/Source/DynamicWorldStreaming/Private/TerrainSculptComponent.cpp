// Copyright worldgen. Dynamic World Streaming plugin.

#include "TerrainSculptComponent.h"
#include "RegionStreamingManager.h"
#include "DynamicWorldStreaming.h"

#include "Engine/World.h"
#include "CollisionQueryParams.h"

UTerrainSculptComponent::UTerrainSculptComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

URegionStreamingManager* UTerrainSculptComponent::GetManager() const
{
	if (const UWorld* World = GetWorld())
	{
		return World->GetSubsystem<URegionStreamingManager>();
	}
	return nullptr;
}

void UTerrainSculptComponent::SculptAtLocation(const FVector& WorldLocationCm)
{
	if (URegionStreamingManager* Mgr = GetManager())
	{
		Mgr->ApplySculpt(WorldLocationCm, BrushType, RadiusM, StrengthM, TargetHeightM);
	}
}

bool UTerrainSculptComponent::SculptTrace(const FVector& Origin, const FVector& Direction)
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}

	const FVector End = Origin + Direction.GetSafeNormal() * TraceDistanceCm;
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(TerrainSculptTrace), /*bTraceComplex=*/true);
	if (const AActor* Owner = GetOwner())
	{
		Params.AddIgnoredActor(Owner);
	}

	if (World->LineTraceSingleByChannel(Hit, Origin, End, ECC_Visibility, Params))
	{
		SculptAtLocation(Hit.ImpactPoint);
		return true;
	}
	return false;
}

void UTerrainSculptComponent::UndoLastEdit()
{
	if (URegionStreamingManager* Mgr = GetManager())
	{
		Mgr->UndoLastEdit();
	}
}

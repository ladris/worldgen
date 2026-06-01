// Copyright worldgen. Dynamic World Streaming plugin.
//
// Project Settings → Plugins → Dynamic World Streaming.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "DynamicWorldStreamingSettings.generated.h"

UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "Dynamic World Streaming"))
class DYNAMICWORLDSTREAMING_API UDynamicWorldStreamingSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	/** Base URL of the worldgen terrain service (no trailing slash). */
	UPROPERTY(Config, EditAnywhere, Category = "Service")
	FString ServiceBaseUrl = TEXT("http://127.0.0.1:8000");

	/** Start streaming automatically when a world begins play. */
	UPROPERTY(Config, EditAnywhere, Category = "Streaming")
	bool bAutoStart = true;

	/** Rings of tiles kept loaded around the player. */
	UPROPERTY(Config, EditAnywhere, Category = "Streaming", meta = (ClampMin = "1"))
	int32 LoadRadius = 2;

	/** Tiles beyond this Chebyshev distance from the player are unloaded.
	 *  Should be >= LoadRadius (+1 for hysteresis). */
	UPROPERTY(Config, EditAnywhere, Category = "Streaming", meta = (ClampMin = "1"))
	int32 UnloadRadius = 4;

	/** Maximum simultaneous tile fetches in flight. */
	UPROPERTY(Config, EditAnywhere, Category = "Streaming", meta = (ClampMin = "1"))
	int32 MaxConcurrentFetches = 6;

	/** Seconds between streaming updates (re-evaluate desired tiles). */
	UPROPERTY(Config, EditAnywhere, Category = "Streaming", meta = (ClampMin = "0.05"))
	float UpdateIntervalSeconds = 0.25f;

	/** Run cross-tile normal stitching when neighbours become available. */
	UPROPERTY(Config, EditAnywhere, Category = "Streaming")
	bool bEnableStitching = true;
};

// Copyright worldgen. Dynamic World Streaming plugin — example content.
//
// AExampleGameMode: spawns AExampleExplorerPawn so the streaming + sculpting
// demo runs with zero Blueprint wiring. Set this as the map's GameMode Override
// (or the project default) and press Play.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "ExampleGameMode.generated.h"

UCLASS()
class DYNAMICWORLDSTREAMING_API AExampleGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AExampleGameMode();
};

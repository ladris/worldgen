// Copyright worldgen. Dynamic World Streaming plugin — example content.

#include "Examples/ExampleGameMode.h"
#include "Examples/ExampleExplorerPawn.h"

AExampleGameMode::AExampleGameMode()
{
	DefaultPawnClass = AExampleExplorerPawn::StaticClass();
}

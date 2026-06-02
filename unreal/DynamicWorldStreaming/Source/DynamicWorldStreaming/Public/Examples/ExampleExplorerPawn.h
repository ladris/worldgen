// Copyright worldgen. Dynamic World Streaming plugin — example content.
//
// AExampleExplorerPawn: a no-VR, no-asset way to validate the whole system on
// desktop. A free-flying pawn (inherits DefaultPawn movement) with a camera, a
// TerrainSculptComponent, and mouse/keyboard sculpt controls. Set this as the
// default pawn (see ExampleGameMode) and press Play: fly with WASD, look with
// the mouse, hold LMB to raise terrain / RMB to lower, F=flatten, G=smooth,
// scroll to size the brush, Z to undo.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/DefaultPawn.h"
#include "ExampleExplorerPawn.generated.h"

class UCameraComponent;
class UTerrainSculptComponent;

UCLASS()
class DYNAMICWORLDSTREAMING_API AExampleExplorerPawn : public ADefaultPawn
{
	GENERATED_BODY()

public:
	AExampleExplorerPawn();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* InputComponent) override;

	/** Starting height (cm) above the world origin if spawned at/near (0,0,0). */
	UPROPERTY(EditAnywhere, Category = "Explorer")
	float StartHeightCm = 25000.0f;

	UPROPERTY(VisibleAnywhere, Category = "Explorer")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, Category = "Explorer")
	TObjectPtr<UTerrainSculptComponent> Sculpt;

private:
	bool bRaising = false;
	bool bLowering = false;

	void OnRaisePressed() { bRaising = true; }
	void OnRaiseReleased() { bRaising = false; }
	void OnLowerPressed() { bLowering = true; }
	void OnLowerReleased() { bLowering = false; }
	void OnFlatten();
	void OnSmooth();
	void OnRaiseLowerMode();
	void OnBrushBigger();
	void OnBrushSmaller();
	void OnUndo();

	void DoSculpt(float SignedStrength);
};

// Copyright worldgen. Dynamic World Streaming plugin — example content.

#include "Examples/ExampleExplorerPawn.h"
#include "TerrainSculptComponent.h"
#include "DynamicWorldStreaming.h"

#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/PlayerController.h"

AExampleExplorerPawn::AExampleExplorerPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(GetRootComponent());
	Camera->bUsePawnControlRotation = true;

	Sculpt = CreateDefaultSubobject<UTerrainSculptComponent>(TEXT("Sculpt"));
	Sculpt->RadiusM = 40.0f;
	Sculpt->StrengthM = 4.0f;

	// Faster default flight so large terrain feels navigable.
	BaseTurnRate = 45.0f;
	BaseLookUpRate = 45.0f;
}

void AExampleExplorerPawn::BeginPlay()
{
	Super::BeginPlay();

	// If spawned at/near the origin, lift up and look down so terrain is in view.
	const FVector Loc = GetActorLocation();
	if (Loc.SizeSquared2D() < FMath::Square(1000.0f))
	{
		SetActorLocation(FVector(Loc.X, Loc.Y, StartHeightCm));
	}
	if (AController* C = GetController())
	{
		FRotator R = C->GetControlRotation();
		R.Pitch = -35.0f;
		C->SetControlRotation(R);
	}

	UE_LOG(LogDynamicWorldStreaming, Log,
		TEXT("ExampleExplorerPawn ready. LMB=raise RMB=lower F=flatten G=smooth "
			 "scroll=brush size Z=undo. Ensure the terrain service is running."));
}

void AExampleExplorerPawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bRaising)
	{
		DoSculpt(+FMath::Abs(Sculpt->StrengthM));
	}
	else if (bLowering)
	{
		DoSculpt(-FMath::Abs(Sculpt->StrengthM));
	}
}

void AExampleExplorerPawn::DoSculpt(float SignedStrength)
{
	if (!Sculpt || !Camera)
	{
		return;
	}
	// RaiseLower uses the signed strength; other brushes ignore the sign.
	if (Sculpt->BrushType == EBrushType::RaiseLower)
	{
		Sculpt->StrengthM = SignedStrength;
	}
	const FVector Origin = Camera->GetComponentLocation();
	const FVector Dir = Camera->GetForwardVector();
	Sculpt->SculptTrace(Origin, Dir);
}

void AExampleExplorerPawn::OnFlatten()
{
	if (Sculpt)
	{
		Sculpt->BrushType = EBrushType::Flatten;
		// Flatten toward whatever we are currently looking at: leave TargetHeightM
		// as configured; users can set it in the details panel.
		UE_LOG(LogDynamicWorldStreaming, Log, TEXT("Brush: Flatten (target %.1f m)"),
			Sculpt->TargetHeightM);
	}
}

void AExampleExplorerPawn::OnSmooth()
{
	if (Sculpt)
	{
		Sculpt->BrushType = EBrushType::Smooth;
		UE_LOG(LogDynamicWorldStreaming, Log, TEXT("Brush: Smooth"));
	}
}

void AExampleExplorerPawn::OnRaiseLowerMode()
{
	if (Sculpt)
	{
		Sculpt->BrushType = EBrushType::RaiseLower;
		UE_LOG(LogDynamicWorldStreaming, Log, TEXT("Brush: Raise/Lower"));
	}
}

void AExampleExplorerPawn::OnBrushBigger()
{
	if (Sculpt) { Sculpt->RadiusM = FMath::Clamp(Sculpt->RadiusM * 1.25f, 1.0f, 5000.0f); }
}

void AExampleExplorerPawn::OnBrushSmaller()
{
	if (Sculpt) { Sculpt->RadiusM = FMath::Clamp(Sculpt->RadiusM * 0.8f, 1.0f, 5000.0f); }
}

void AExampleExplorerPawn::OnUndo()
{
	if (Sculpt) { Sculpt->UndoLastEdit(); }
}

void AExampleExplorerPawn::SetupPlayerInputComponent(UInputComponent* InputComponent)
{
	Super::SetupPlayerInputComponent(InputComponent); // DefaultPawn movement axes

	// Legacy action mappings (see EXAMPLE.md for the DefaultInput.ini snippet).
	InputComponent->BindAction("Sculpt_Raise", IE_Pressed, this, &AExampleExplorerPawn::OnRaisePressed);
	InputComponent->BindAction("Sculpt_Raise", IE_Released, this, &AExampleExplorerPawn::OnRaiseReleased);
	InputComponent->BindAction("Sculpt_Lower", IE_Pressed, this, &AExampleExplorerPawn::OnLowerPressed);
	InputComponent->BindAction("Sculpt_Lower", IE_Released, this, &AExampleExplorerPawn::OnLowerReleased);
	InputComponent->BindAction("Brush_Flatten", IE_Pressed, this, &AExampleExplorerPawn::OnFlatten);
	InputComponent->BindAction("Brush_Smooth", IE_Pressed, this, &AExampleExplorerPawn::OnSmooth);
	InputComponent->BindAction("Brush_RaiseLower", IE_Pressed, this, &AExampleExplorerPawn::OnRaiseLowerMode);
	InputComponent->BindAction("Brush_Bigger", IE_Pressed, this, &AExampleExplorerPawn::OnBrushBigger);
	InputComponent->BindAction("Brush_Smaller", IE_Pressed, this, &AExampleExplorerPawn::OnBrushSmaller);
	InputComponent->BindAction("Sculpt_Undo", IE_Pressed, this, &AExampleExplorerPawn::OnUndo);
}

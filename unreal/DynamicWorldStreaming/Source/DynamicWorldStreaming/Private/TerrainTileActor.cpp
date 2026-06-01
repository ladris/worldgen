// Copyright worldgen. Dynamic World Streaming plugin.

#include "TerrainTileActor.h"
#include "DynamicWorldStreaming.h"

#include "Components/DynamicMeshComponent.h"
#include "UDynamicMesh.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/MeshNormals.h"
#include "Async/Async.h"

using namespace UE::Geometry;

namespace
{
	constexpr double U16_MAX = 65535.0;

	/** Decode an absolute-encoded uint16 sample to a world Z in cm (CONTRACT §4). */
	FORCEINLINE double DecodeZCm(uint16 Sample, double ElevMinM, double ElevMaxM)
	{
		const double Norm = (double)Sample / U16_MAX;
		const double ElevM = ElevMinM + Norm * (ElevMaxM - ElevMinM);
		return ElevM * 100.0;
	}
}

ATerrainTileActor::ATerrainTileActor()
{
	PrimaryActorTick.bCanEverTick = false;

	MeshComponent = CreateDefaultSubobject<UDynamicMeshComponent>(TEXT("TerrainMesh"));
	SetRootComponent(MeshComponent);
	MeshComponent->SetMobility(EComponentMobility::Movable);
	// Tiles are static once built; collision cooked async after the mesh lands.
	MeshComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void ATerrainTileActor::BuildFromHeightmap(const FTileHeightmap& Heightmap,
										   const FProjectGridConfig& GridConfig)
{
	if (!Heightmap.bValid)
	{
		UE_LOG(LogDynamicWorldStreaming, Error, TEXT("BuildFromHeightmap: invalid heightmap."));
		return;
	}

	TileKey = Heightmap.Manifest.Tile;
	Width = Heightmap.Manifest.Width;
	Height = Heightmap.Manifest.Height;
	State = ETileState::Building;

	// Place the actor at the tile's grid-origin corner (min X/Y) so local vertex
	// coordinates are simply (col, row)->(+X east, +Y north).
	SetActorLocation(Heightmap.Manifest.TileLocationCm);

	const double Spacing = Heightmap.Manifest.VertexSpacingCm > 0.0
		? Heightmap.Manifest.VertexSpacingCm : GridConfig.VertexSpacingCm;
	const double ElevMinM = Heightmap.Manifest.ElevationMinM;
	const double ElevMaxM = Heightmap.Manifest.ElevationMaxM;

	const int32 W = Width;
	const int32 H = Height;
	// Copy samples for the worker thread (decouples from the response buffer).
	TArray<uint16> Samples = Heightmap.Samples;

	TWeakObjectPtr<ATerrainTileActor> WeakThis(this);

	// --- Worker thread: build the mesh (no UObject access here) -----------
	Async(EAsyncExecution::ThreadPool,
		[WeakThis, Samples = MoveTemp(Samples), W, H, Spacing, ElevMinM, ElevMaxM]()
		{
			TUniquePtr<FDynamicMesh3> Mesh = MakeUnique<FDynamicMesh3>();
			Mesh->EnableAttributes();

			// Vertices: index = row*W + col. Row 0 is north (image top) → +Y max.
			for (int32 Row = 0; Row < H; ++Row)
			{
				const double LocalY = (double)(H - 1 - Row) * Spacing;
				for (int32 Col = 0; Col < W; ++Col)
				{
					const uint16 S = Samples[Row * W + Col];
					const double Z = DecodeZCm(S, ElevMinM, ElevMaxM);
					Mesh->AppendVertex(FVector3d((double)Col * Spacing, LocalY, Z));
				}
			}

			// Triangles: two per quad. If the surface renders inverted in-engine,
			// swap the vertex order within each AppendTriangle call (winding).
			for (int32 Row = 0; Row < H - 1; ++Row)
			{
				for (int32 Col = 0; Col < W - 1; ++Col)
				{
					const int32 V00 = Row * W + Col;
					const int32 V01 = Row * W + (Col + 1);
					const int32 V10 = (Row + 1) * W + Col;
					const int32 V11 = (Row + 1) * W + (Col + 1);
					Mesh->AppendTriangle(V00, V10, V11);
					Mesh->AppendTriangle(V00, V11, V01);
				}
			}

			// Locally-correct vertex normals (the stitcher fixes shared edges).
			FMeshNormals::QuickComputeVertexNormals(*Mesh);

			// --- Game thread: publish into the component ------------------
			AsyncTask(ENamedThreads::GameThread,
				[WeakThis, MeshPtr = MoveTemp(Mesh)]() mutable
				{
					ATerrainTileActor* Self = WeakThis.Get();
					if (!Self || !IsValid(Self) || !Self->MeshComponent)
					{
						return;
					}
					Self->MeshComponent->GetDynamicMesh()->SetMesh(MoveTemp(*MeshPtr));
					Self->MeshComponent->NotifyMeshUpdated();
					Self->State = ETileState::Active;
					Self->EnableCollisionAsync();
					Self->OnBuilt.Broadcast(Self);
				});
		});

	// Cache edge heights (world Z, cm) for stitching while we still hold samples.
	EdgeNorth.SetNumUninitialized(W);
	EdgeSouth.SetNumUninitialized(W);
	for (int32 Col = 0; Col < W; ++Col)
	{
		EdgeNorth[Col] = DecodeZCm(Heightmap.Samples[0 * W + Col], ElevMinM, ElevMaxM);
		EdgeSouth[Col] = DecodeZCm(Heightmap.Samples[(H - 1) * W + Col], ElevMinM, ElevMaxM);
	}
	EdgeEast.SetNumUninitialized(H);
	EdgeWest.SetNumUninitialized(H);
	for (int32 Row = 0; Row < H; ++Row)
	{
		EdgeWest[Row] = DecodeZCm(Heightmap.Samples[Row * W + 0], ElevMinM, ElevMaxM);
		EdgeEast[Row] = DecodeZCm(Heightmap.Samples[Row * W + (W - 1)], ElevMinM, ElevMaxM);
	}
}

void ATerrainTileActor::EnableCollisionAsync()
{
	if (!MeshComponent)
	{
		return;
	}
	// UDynamicMeshComponent supports complex-as-simple collision cooked off the
	// game thread; this avoids a hitch when the tile appears.
	MeshComponent->SetComplexAsSimpleCollisionEnabled(true);
	MeshComponent->bDeferCollisionUpdates = false;
	MeshComponent->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	MeshComponent->UpdateCollision(/*bAsyncCook=*/true);
}

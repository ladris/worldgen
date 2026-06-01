// Copyright worldgen. Dynamic World Streaming plugin.

#include "TileStitcher.h"
#include "TerrainTileActor.h"
#include "DynamicWorldStreaming.h"

#include "Components/DynamicMeshComponent.h"
#include "UDynamicMesh.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/MeshNormals.h"

using namespace UE::Geometry;

// Recommended optimisation (not yet implemented): instead of post-hoc averaging,
// generate each tile's mesh with a one-sample halo of its neighbours' heights
// and compute normals including that halo, then drop the halo verts from the
// rendered mesh. Because neighbours share the underlying field exactly, both
// tiles then compute identical boundary normals and no stitching pass is needed.
// That requires the service to emit haloed heightmaps (a CONTRACT addition).

namespace
{
	/** Vertex indices along a tile edge, in ascending col/row order, for a
	 *  W*H row-major grid (index = row*W + col, row 0 = north). */
	void EdgeVertexIndices(FTileStitcher::EEdge Edge, int32 W, int32 H,
						   TArray<int32>& Out)
	{
		Out.Reset();
		switch (Edge)
		{
		case FTileStitcher::EEdge::North: // row 0
			for (int32 Col = 0; Col < W; ++Col) Out.Add(0 * W + Col);
			break;
		case FTileStitcher::EEdge::South: // row H-1
			for (int32 Col = 0; Col < W; ++Col) Out.Add((H - 1) * W + Col);
			break;
		case FTileStitcher::EEdge::West:  // col 0
			for (int32 Row = 0; Row < H; ++Row) Out.Add(Row * W + 0);
			break;
		case FTileStitcher::EEdge::East:  // col W-1
			for (int32 Row = 0; Row < H; ++Row) Out.Add(Row * W + (W - 1));
			break;
		}
	}

	FTileStitcher::EEdge Opposite(FTileStitcher::EEdge E)
	{
		switch (E)
		{
		case FTileStitcher::EEdge::North: return FTileStitcher::EEdge::South;
		case FTileStitcher::EEdge::South: return FTileStitcher::EEdge::North;
		case FTileStitcher::EEdge::East:  return FTileStitcher::EEdge::West;
		default:                          return FTileStitcher::EEdge::East;
		}
	}

	/** Compute an averaged per-vertex normal for the listed vertices by area-
	 *  weighting their incident triangle face normals, returning one normal per
	 *  listed vertex. */
	void GatherVertexNormals(const FDynamicMesh3& Mesh, const TArray<int32>& Verts,
							 TArray<FVector3d>& Out)
	{
		Out.SetNumZeroed(Verts.Num());
		for (int32 i = 0; i < Verts.Num(); ++i)
		{
			const int32 Vid = Verts[i];
			FVector3d Accum = FVector3d::ZeroVector;
			if (Mesh.IsVertex(Vid))
			{
				for (int32 Tid : Mesh.VtxTrianglesItr(Vid))
				{
					FVector3d N, C; double A;
					Mesh.GetTriInfo(Tid, N, A, C);
					Accum += N * A; // area-weighted
				}
			}
			Out[i] = Accum.GetSafeNormal();
		}
	}

	/** Overwrite the normal-overlay elements at the listed vertices with the
	 *  provided per-vertex normals. */
	void AssignVertexNormals(FDynamicMesh3& Mesh, const TArray<int32>& Verts,
							 const TArray<FVector3d>& Normals)
	{
		if (!Mesh.HasAttributes() || Mesh.Attributes()->PrimaryNormals() == nullptr)
		{
			return;
		}
		FDynamicMeshNormalOverlay* Overlay = Mesh.Attributes()->PrimaryNormals();
		for (int32 i = 0; i < Verts.Num(); ++i)
		{
			const int32 Vid = Verts[i];
			const FVector3f N((float)Normals[i].X, (float)Normals[i].Y, (float)Normals[i].Z);
			// Set every overlay element associated with this vertex.
			for (int32 Tid : Mesh.VtxTrianglesItr(Vid))
			{
				FIndex3i Tri = Overlay->GetTriangle(Tid);
				FIndex3i VtxTri = Mesh.GetTriangle(Tid);
				for (int32 c = 0; c < 3; ++c)
				{
					if (VtxTri[c] == Vid && Tri[c] != FDynamicMesh3::InvalidID)
					{
						Overlay->SetElement(Tri[c], N);
					}
				}
			}
		}
	}
}

void FTileStitcher::StitchPair(ATerrainTileActor* A, ATerrainTileActor* B, EEdge EdgeOfA)
{
	if (!A || !B || !A->MeshComponent || !B->MeshComponent)
	{
		return;
	}

	UDynamicMesh* DynA = A->MeshComponent->GetDynamicMesh();
	UDynamicMesh* DynB = B->MeshComponent->GetDynamicMesh();
	if (!DynA || !DynB)
	{
		return;
	}

	const EEdge EdgeOfB = Opposite(EdgeOfA);
	TArray<FVector3d> NormsA, NormsB, Averaged;
	TArray<int32> VertsA, VertsB;

	// Tiles are square (N*N vertices); derive the edge index list from the
	// vertex count. (Edge ordering matches between opposite edges by row/col.)
	auto EdgeVerts = [](UDynamicMesh* Dyn, EEdge Edge, TArray<int32>& Verts)
	{
		Dyn->ProcessMesh([&](const FDynamicMesh3& Mesh)
		{
			const int32 N = FMath::RoundToInt(FMath::Sqrt((double)Mesh.VertexCount()));
			EdgeVertexIndices(Edge, N, N, Verts);
		});
	};

	EdgeVerts(DynA, EdgeOfA, VertsA);
	EdgeVerts(DynB, EdgeOfB, VertsB);
	if (VertsA.Num() != VertsB.Num() || VertsA.Num() == 0)
	{
		UE_LOG(LogDynamicWorldStreaming, Warning,
			TEXT("StitchPair: edge length mismatch (%d vs %d)."),
			VertsA.Num(), VertsB.Num());
		return;
	}

	DynA->ProcessMesh([&](const FDynamicMesh3& Mesh) { GatherVertexNormals(Mesh, VertsA, NormsA); });
	DynB->ProcessMesh([&](const FDynamicMesh3& Mesh) { GatherVertexNormals(Mesh, VertsB, NormsB); });

	Averaged.SetNumUninitialized(NormsA.Num());
	for (int32 i = 0; i < NormsA.Num(); ++i)
	{
		Averaged[i] = (NormsA[i] + NormsB[i]).GetSafeNormal();
	}

	DynA->EditMesh([&](FDynamicMesh3& Mesh) { AssignVertexNormals(Mesh, VertsA, Averaged); });
	DynB->EditMesh([&](FDynamicMesh3& Mesh) { AssignVertexNormals(Mesh, VertsB, Averaged); });

	A->MeshComponent->NotifyMeshUpdated();
	B->MeshComponent->NotifyMeshUpdated();
}

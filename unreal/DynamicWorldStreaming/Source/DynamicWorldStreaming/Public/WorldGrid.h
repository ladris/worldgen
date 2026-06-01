// Copyright worldgen. Dynamic World Streaming plugin.
//
// FWorldGrid: the Unreal-side mirror of the Python WorldGrid. It performs ONLY
// the metric grid arithmetic in Unreal world space (cm). All geodesy lives in
// the Python service. Must stay consistent with docs/CONTRACT.md §1 & §4.

#pragma once

#include "CoreMinimal.h"
#include "TerrainStreamingTypes.h"

class DYNAMICWORLDSTREAMING_API FWorldGrid
{
public:
	FWorldGrid() = default;
	explicit FWorldGrid(const FProjectGridConfig& InConfig) : Config(InConfig) {}

	void SetConfig(const FProjectGridConfig& InConfig) { Config = InConfig; }
	const FProjectGridConfig& GetConfig() const { return Config; }

	/** Side length of one tile in Unreal cm. */
	double TileSizeCm() const { return Config.TileSizeM * 100.0; }

	/** Grid-origin corner (min X/Y) of a tile, in Unreal world space (cm). */
	FVector TileToWorldLocationCm(const FTileKey& Tile) const
	{
		return FVector(Tile.X * TileSizeCm(), Tile.Y * TileSizeCm(), 0.0);
	}

	/** Centre of a tile in Unreal world space (cm). */
	FVector TileCenterCm(const FTileKey& Tile) const
	{
		const double Half = 0.5 * TileSizeCm();
		const FVector Corner = TileToWorldLocationCm(Tile);
		return FVector(Corner.X + Half, Corner.Y + Half, 0.0);
	}

	/** Which tile contains a world-space location. Floor division so the grid
	 *  tiles the plane with no gaps or overlaps. */
	FTileKey TileForWorldLocation(const FVector& WorldLocationCm, int32 Level = 0) const
	{
		const double Size = TileSizeCm();
		const int32 TX = FMath::FloorToInt(WorldLocationCm.X / Size);
		const int32 TY = FMath::FloorToInt(WorldLocationCm.Y / Size);
		return FTileKey(TX, TY, Level);
	}

	/** The four edge neighbours of a tile. */
	void Neighbors(const FTileKey& Tile, FTileKey& OutNorth, FTileKey& OutSouth,
				   FTileKey& OutEast, FTileKey& OutWest) const
	{
		OutNorth = FTileKey(Tile.X, Tile.Y + 1, Tile.Level);
		OutSouth = FTileKey(Tile.X, Tile.Y - 1, Tile.Level);
		OutEast  = FTileKey(Tile.X + 1, Tile.Y, Tile.Level);
		OutWest  = FTileKey(Tile.X - 1, Tile.Y, Tile.Level);
	}

	/** All tiles within a Chebyshev (square) radius of a centre tile. */
	TArray<FTileKey> TilesInRadius(const FTileKey& Center, int32 Radius) const
	{
		TArray<FTileKey> Out;
		Out.Reserve((2 * Radius + 1) * (2 * Radius + 1));
		for (int32 DY = -Radius; DY <= Radius; ++DY)
		{
			for (int32 DX = -Radius; DX <= Radius; ++DX)
			{
				Out.Emplace(Center.X + DX, Center.Y + DY, Center.Level);
			}
		}
		return Out;
	}

	/** Vertex spacing in cm (= metres-per-pixel * 100). */
	double VertexSpacingCm() const { return Config.MetersPerPixel * 100.0; }

private:
	FProjectGridConfig Config;
};

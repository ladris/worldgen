// Copyright worldgen. Dynamic World Streaming plugin.

#include "TerrainDataClient.h"
#include "DynamicWorldStreaming.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

void UTerrainDataClient::Initialize(const FString& InBaseUrl)
{
	BaseUrl = InBaseUrl;
	while (BaseUrl.EndsWith(TEXT("/")))
	{
		BaseUrl.LeftChopInline(1);
	}
}

TSharedRef<IHttpRequest, ESPMode::ThreadSafe> UTerrainDataClient::MakeGet(const FString& Path)
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetVerb(TEXT("GET"));
	Req->SetURL(BaseUrl + Path);
	return Req;
}

// ---- /project ----------------------------------------------------------

void UTerrainDataClient::FetchProjectConfig(FOnProjectConfig OnComplete)
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = MakeGet(TEXT("/project"));
	Req->OnProcessRequestComplete().BindLambda(
		[OnComplete](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
		{
			FProjectGridConfig Config;
			if (bOk && Response.IsValid() && Response->GetResponseCode() == 200
				&& ParseProjectConfig(Response->GetContentAsString(), Config))
			{
				OnComplete.ExecuteIfBound(Config);
			}
			else
			{
				UE_LOG(LogDynamicWorldStreaming, Error,
					TEXT("FetchProjectConfig failed (code %d)."),
					Response.IsValid() ? Response->GetResponseCode() : -1);
				OnComplete.ExecuteIfBound(Config); // invalid config; caller checks IsValid()
			}
		});
	Req->ProcessRequest();
}

bool UTerrainDataClient::ParseProjectConfig(const FString& Json, FProjectGridConfig& Out)
{
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return false;
	}
	const TSharedPtr<FJsonObject>* ConfigObj = nullptr;
	const TSharedPtr<FJsonObject>* DerivedObj = nullptr;
	if (!Root->TryGetObjectField(TEXT("config"), ConfigObj)
		|| !Root->TryGetObjectField(TEXT("derived"), DerivedObj))
	{
		return false;
	}
	const TSharedPtr<FJsonObject>& C = *ConfigObj;
	const TSharedPtr<FJsonObject>& D = *DerivedObj;

	C->TryGetStringField(TEXT("project_id"), Out.ProjectId);
	Out.TileSizeM = C->GetNumberField(TEXT("tile_size_m"));
	Out.MetersPerPixel = C->GetNumberField(TEXT("meters_per_pixel"));
	Out.ElevationMinM = C->GetNumberField(TEXT("elevation_min_m"));
	Out.ElevationMaxM = C->GetNumberField(TEXT("elevation_max_m"));

	Out.SamplesPerEdge = (int32)D->GetNumberField(TEXT("samples_per_edge"));
	Out.UEScaleZ = D->GetNumberField(TEXT("ue_scale_z"));
	Out.VertexSpacingCm = D->GetNumberField(TEXT("vertex_spacing_cm"));
	return Out.IsValid();
}

// ---- tile manifest + heightmap ----------------------------------------

void UTerrainDataClient::FetchTile(const FTileKey& Tile, FOnTileFetched OnComplete)
{
	const FString Path = FString::Printf(TEXT("/tile/%d/%d/%d/manifest"),
										 Tile.Level, Tile.X, Tile.Y);
	TWeakObjectPtr<UTerrainDataClient> WeakThis(this);
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = MakeGet(Path);
	Req->OnProcessRequestComplete().BindLambda(
		[WeakThis, Tile, OnComplete](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
		{
			UTerrainDataClient* Self = WeakThis.Get();
			FTileManifest Manifest;
			if (Self && bOk && Response.IsValid() && Response->GetResponseCode() == 200
				&& ParseManifest(Response->GetContentAsString(), Manifest))
			{
				Self->FetchHeightmap(Manifest, OnComplete);
			}
			else
			{
				UE_LOG(LogDynamicWorldStreaming, Error,
					TEXT("Manifest fetch failed for %s (code %d)."), *Tile.ToString(),
					Response.IsValid() ? Response->GetResponseCode() : -1);
				FTileHeightmap Empty;
				OnComplete.ExecuteIfBound(Empty);
			}
		});
	Req->ProcessRequest();
}

bool UTerrainDataClient::ParseManifest(const FString& Json, FTileManifest& Out)
{
	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* TileObj = nullptr;
	if (Root->TryGetObjectField(TEXT("tile"), TileObj))
	{
		Out.Tile.Level = (int32)(*TileObj)->GetNumberField(TEXT("level"));
		Out.Tile.X = (int32)(*TileObj)->GetNumberField(TEXT("x"));
		Out.Tile.Y = (int32)(*TileObj)->GetNumberField(TEXT("y"));
	}

	const TSharedPtr<FJsonObject>* HeightObj = nullptr;
	if (Root->TryGetObjectField(TEXT("heightmap"), HeightObj))
	{
		Out.Width = (int32)(*HeightObj)->GetNumberField(TEXT("width"));
		Out.Height = (int32)(*HeightObj)->GetNumberField(TEXT("height"));
	}

	const TSharedPtr<FJsonObject>* ElevObj = nullptr;
	if (Root->TryGetObjectField(TEXT("elevation"), ElevObj))
	{
		Out.ElevationMinM = (*ElevObj)->GetNumberField(TEXT("project_min_m"));
		Out.ElevationMaxM = (*ElevObj)->GetNumberField(TEXT("project_max_m"));
	}

	const TSharedPtr<FJsonObject>* UnrealObj = nullptr;
	if (Root->TryGetObjectField(TEXT("unreal"), UnrealObj))
	{
		Out.VertexSpacingCm = (*UnrealObj)->GetNumberField(TEXT("vertex_spacing_cm"));
		const TSharedPtr<FJsonObject>* LocObj = nullptr;
		if ((*UnrealObj)->TryGetObjectField(TEXT("tile_location_cm"), LocObj))
		{
			Out.TileLocationCm.X = (*LocObj)->GetNumberField(TEXT("x"));
			Out.TileLocationCm.Y = (*LocObj)->GetNumberField(TEXT("y"));
			Out.TileLocationCm.Z = (*LocObj)->GetNumberField(TEXT("z"));
		}
	}

	Root->TryGetStringField(TEXT("heightmap_url"), Out.HeightmapUrl);
	Root->TryGetStringField(TEXT("content_hash"), Out.ContentHash);

	Out.bValid = Out.Width > 1 && Out.Height > 1;
	return Out.bValid;
}

void UTerrainDataClient::PostEdit(EBrushType Type, const FVector& CenterWorldCm,
	float RadiusM, float StrengthM, float TargetHeightM)
{
	const TCHAR* TypeStr =
		Type == EBrushType::RaiseLower ? TEXT("raise_lower") :
		Type == EBrushType::Flatten    ? TEXT("flatten") : TEXT("smooth");

	const TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("type"), TypeStr);
	Body->SetNumberField(TEXT("center_x_cm"), CenterWorldCm.X);
	Body->SetNumberField(TEXT("center_y_cm"), CenterWorldCm.Y);
	Body->SetNumberField(TEXT("radius_m"), RadiusM);
	Body->SetNumberField(TEXT("strength_m"), StrengthM);
	Body->SetNumberField(TEXT("target_height_m"), TargetHeightM);
	Body->SetStringField(TEXT("falloff"), TEXT("smooth"));
	Body->SetNumberField(TEXT("iterations"), 1);

	FString Payload;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
	FJsonSerializer::Serialize(Body, Writer);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetVerb(TEXT("POST"));
	Req->SetURL(BaseUrl + TEXT("/edit"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	Req->SetContentAsString(Payload);
	Req->OnProcessRequestComplete().BindLambda(
		[](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
		{
			if (!bOk || !Response.IsValid() || Response->GetResponseCode() != 200)
			{
				UE_LOG(LogDynamicWorldStreaming, Warning,
					TEXT("PostEdit failed (code %d)."),
					Response.IsValid() ? Response->GetResponseCode() : -1);
			}
		});
	Req->ProcessRequest();
}

void UTerrainDataClient::PostUndo(FSimpleDelegate OnDone)
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = FHttpModule::Get().CreateRequest();
	Req->SetVerb(TEXT("POST"));
	Req->SetURL(BaseUrl + TEXT("/edit/undo"));
	Req->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
	Req->SetContentAsString(TEXT("{}"));
	Req->OnProcessRequestComplete().BindLambda(
		[OnDone](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
		{
			OnDone.ExecuteIfBound();
		});
	Req->ProcessRequest();
}

void UTerrainDataClient::FetchHeightmap(const FTileManifest& Manifest, FOnTileFetched OnComplete)
{
	// Prefer the manifest's heightmap_url; fall back to the conventional path.
	FString Path = Manifest.HeightmapUrl;
	if (Path.IsEmpty())
	{
		Path = FString::Printf(TEXT("/tile/%d/%d/%d/heightmap.r16"),
							   Manifest.Tile.Level, Manifest.Tile.X, Manifest.Tile.Y);
	}

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Req = MakeGet(Path);
	Req->OnProcessRequestComplete().BindLambda(
		[Manifest, OnComplete](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
		{
			FTileHeightmap Result;
			Result.Manifest = Manifest;
			const int32 Expected = Manifest.Width * Manifest.Height;

			if (bOk && Response.IsValid() && Response->GetResponseCode() == 200)
			{
				const TArray<uint8>& Bytes = Response->GetContent();
				if (Bytes.Num() == Expected * (int32)sizeof(uint16))
				{
					// .r16 is little-endian uint16, row-major, north row first.
					Result.Samples.SetNumUninitialized(Expected);
					FMemory::Memcpy(Result.Samples.GetData(), Bytes.GetData(),
									Bytes.Num());
					// Byte-swap on big-endian platforms (UE targets are LE, but
					// be explicit per the contract).
#if PLATFORM_BIG_ENDIAN
					for (uint16& S : Result.Samples) { S = BYTESWAP_ORDER16(S); }
#endif
					Result.bValid = true;
				}
				else
				{
					UE_LOG(LogDynamicWorldStreaming, Error,
						TEXT("Heightmap size mismatch for %s: got %d bytes, expected %d."),
						*Manifest.Tile.ToString(), Bytes.Num(),
						Expected * (int32)sizeof(uint16));
				}
			}
			OnComplete.ExecuteIfBound(Result);
		});
	Req->ProcessRequest();
}

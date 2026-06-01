// Copyright worldgen. Dynamic World Streaming plugin.

#include "DynamicWorldStreaming.h"

#define LOCTEXT_NAMESPACE "FDynamicWorldStreamingModule"

DEFINE_LOG_CATEGORY(LogDynamicWorldStreaming);

void FDynamicWorldStreamingModule::StartupModule()
{
	UE_LOG(LogDynamicWorldStreaming, Log, TEXT("DynamicWorldStreaming module started."));
}

void FDynamicWorldStreamingModule::ShutdownModule()
{
	UE_LOG(LogDynamicWorldStreaming, Log, TEXT("DynamicWorldStreaming module shut down."));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FDynamicWorldStreamingModule, DynamicWorldStreaming)

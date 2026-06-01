// Copyright worldgen. Dynamic World Streaming plugin.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(LogDynamicWorldStreaming, Log, All);

class FDynamicWorldStreamingModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};

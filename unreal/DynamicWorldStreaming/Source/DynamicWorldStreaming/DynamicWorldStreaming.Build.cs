// Copyright worldgen. Dynamic World Streaming plugin.

using UnrealBuildTool;

public class DynamicWorldStreaming : ModuleRules
{
	public DynamicWorldStreaming(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			// Procedural / dynamic geometry.
			"GeometryFramework",   // UDynamicMeshComponent, ADynamicMeshActor
			"GeometryCore",        // FDynamicMesh3, mesh ops
			"GeometryScriptingCore",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// Networking + parsing for the terrain service contract.
			"HTTP",
			"Json",
			"JsonUtilities",
			// Procedural mesh fallback path (alternative to UDynamicMeshComponent).
			"ProceduralMeshComponent",
		});

		// World Partition lives in Engine in UE 5.5; no extra module needed, but
		// keep this explicit comment so the dependency is discoverable.
	}
}

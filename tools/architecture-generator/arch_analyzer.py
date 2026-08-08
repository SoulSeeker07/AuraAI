"""
Architecture Analyzer
=====================

Analyzes parsed code structure to:
- Assign modules to 7 architectural layers with path pattern resolution
- Classify component roles (Orchestrators, Managers, Engines, Adapters, Pipelines)
- Build dependency graphs between modules and layers
- Validate architectural boundary guardrails
"""

from dataclasses import dataclass, field
from pathlib import Path

from ast_parser import ModuleInfo

from config import ArchitectureConfig


@dataclass
class ModuleDependency:
    """Represents a dependency between two modules."""

    from_module: str
    to_module: str
    import_type: str  # 'import' or 'from ... import'
    line_number: int


@dataclass
class LayerModule:
    """Represents a module within a layer."""

    name: str
    path: str
    layer_name: str
    role: str  # 'ORCHESTRATOR', 'MANAGER', 'ENGINE', 'ADAPTER', 'PIPELINE', 'ENTRY_POINT', 'UTILITY'
    classes: list[str]
    functions: list[str]
    imports: list[str]
    complexity: int = 0


@dataclass
class ArchitectureGraph:
    """Represents the complete architecture graph."""

    modules: dict[str, LayerModule] = field(
        default_factory=dict
    )  # module_name -> LayerModule
    layers: dict[str, list[LayerModule]] = field(
        default_factory=dict
    )  # layer_name -> list of LayerModules
    dependencies: list[ModuleDependency] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)
    module_map: dict[str, str] = field(
        default_factory=dict
    )  # module_name -> layer_name


class ArchitectureAnalyzer:
    """Analyzes code structure and maps it to architecture layers."""

    def __init__(self, parser, root_path: str):
        """
        Initialize the analyzer.

        Args:
            parser: ASTParser instance
            root_path: Root path of the project
        """
        self.parser = parser
        self.root_path = Path(root_path)
        self.graph = ArchitectureGraph()

    def analyze(self) -> ArchitectureGraph:
        """
        Perform complete architecture analysis.

        Returns:
            ArchitectureGraph with all analysis results
        """
        # 1. Assign modules to layers & classify roles
        self._assign_layers()

        # 2. Analyze dependencies
        self._analyze_dependencies()

        # 3. Detect guardrail violations
        self._detect_violations()

        return self.graph

    def _classify_role(self, module_name: str, module_info: ModuleInfo) -> str:
        """Classify module role based on module name, class names, and location."""
        name_lower = module_name.lower()
        class_names = [c.lower() for c in module_info.classes.keys()]

        # Check Entry Points
        if name_lower in ["main", "cli", "aura", "run_aura", "app"]:
            return "ENTRY_POINT"

        # Check Orchestrator
        if (
            "orchestrator" in name_lower
            or any("orchestrator" in c for c in class_names)
            or "auracore" in name_lower
            or "executive" in name_lower
        ):
            return "ORCHESTRATOR"

        # Check Blackboard / CognitiveState
        if (
            "blackboard" in name_lower
            or "cognitivestate" in name_lower
            or "decisioncontext" in name_lower
        ):
            return "BLACKBOARD"

        # Check Manager
        if "manager" in name_lower or any("manager" in c for c in class_names):
            return "MANAGER"

        # Check Adapter
        if "adapter" in name_lower or any("adapter" in c for c in class_names):
            return "ADAPTER"

        # Check Engine / Planner
        if (
            "engine" in name_lower
            or "planner" in name_lower
            or any("engine" in c or "planner" in c for c in class_names)
        ):
            return "ENGINE"

        # Check Pipeline / Loop
        if "loop" in name_lower or "pipeline" in name_lower:
            return "PIPELINE"

        # Check Event Bus
        if "event" in name_lower or "bus" in name_lower:
            return "EVENT_BUS"

        return "UTILITY"

    def _assign_layers(self):
        """Assign each module to its architecture layer and collect layer modules."""
        module_map = self.parser.get_all_modules()

        # Initialize layer lists
        for layer in ArchitectureConfig.ALL_LAYERS:
            self.graph.layers[layer.name] = []

        for module_name, module_info in module_map.items():
            module_path = Path(module_info.path)

            # Find matching layer
            layer = ArchitectureConfig.get_layer_by_path(str(module_path))

            # Classify component role
            role = self._classify_role(module_name, module_info)

            # Store in module_map
            self.graph.module_map[module_name] = layer.name

            # Get imports from this module
            imports = [imp.module for imp in module_info.imports]

            # Create LayerModule
            layer_module = LayerModule(
                name=module_name,
                path=str(module_path),
                layer_name=layer.name,
                role=role,
                classes=[cls.name for cls in module_info.classes.values()],
                functions=[func.name for func in module_info.functions.values()],
                imports=imports,
                complexity=self._calculate_complexity(module_info),
            )

            self.graph.modules[module_name] = layer_module
            if layer.name not in self.graph.layers:
                self.graph.layers[layer.name] = []
            self.graph.layers[layer.name].append(layer_module)

    def _calculate_complexity(self, module_info: ModuleInfo) -> int:
        """Calculate module complexity score."""
        score = 0
        score += len(module_info.classes) * 3
        score += len(module_info.functions)
        score += len(module_info.imports)
        score += sum(1 for func in module_info.functions.values() if func.decorators)
        score += sum(1 for cls in module_info.classes.values() if cls.decorators)
        return score

    def _analyze_dependencies(self):
        """Analyze dependencies between modules and layers."""
        module_map = self.parser.get_all_modules()

        for module_name, module_info in module_map.items():
            for imp in module_info.imports:
                imported_module = self._resolve_module(imp.module, module_name)

                if imported_module and imported_module in self.graph.module_map:
                    dep = ModuleDependency(
                        from_module=module_name,
                        to_module=imported_module,
                        import_type="from ... import" if imp.alias else "import",
                        line_number=imp.line_number,
                    )
                    self.graph.dependencies.append(dep)

    def _resolve_module(self, import_module: str, current_module: str) -> str | None:
        """Resolve a dotted import to a concrete module name."""
        if not import_module:
            return None

        # Handle relative imports
        if import_module.startswith("."):
            current_layer_name = self.graph.module_map.get(current_module)
            if not current_layer_name or current_module not in self.graph.modules:
                return None

            current_path = self.graph.modules[current_module].path
            current_module_path = Path(current_path).parent

            level = import_module.count(".")
            path_parts = (
                list(current_module_path.parts[:-level])
                if level > 0
                else list(current_module_path.parts)
            )
            target_parts = path_parts + import_module.lstrip(".").split(".")

            target_path = Path(*target_parts)

            for module_name, module_info in self.parser.get_all_modules().items():
                if Path(module_info.path).stem == target_path.stem:
                    return module_name
            return None

        # Handle absolute imports
        else:
            parts = import_module.split(".")
            last_part = parts[-1]
            first_part = parts[0]

            # Match exact or suffix
            all_mods = self.parser.get_all_modules()
            if import_module in all_mods:
                return import_module

            if last_part in all_mods:
                return last_part

            for m_name in all_mods.keys():
                if (
                    m_name == first_part
                    or m_name == last_part
                    or m_name.endswith(f".{last_part}")
                ):
                    return m_name

            return None

    def _detect_violations(self):
        """Detect Guardrail 1 and architecture layer violations."""
        violations = []

        for dep in self.graph.dependencies:
            from_layer = self.graph.module_map.get(dep.from_module, "")
            to_layer = self.graph.module_map.get(dep.to_module, "")

            if from_layer and to_layer and from_layer != to_layer:
                layer_from = ArchitectureConfig.get_layer_by_name(from_layer)

                # Check forbidden imports
                if to_layer in layer_from.forbidden_imports:
                    violations.append(
                        {
                            "type": "forbidden_import",
                            "from_module": dep.from_module,
                            "to_module": dep.to_module,
                            "from_layer": from_layer,
                            "to_layer": to_layer,
                            "line": dep.line_number,
                        }
                    )

        self.graph.violations = violations

    def get_layer_summary(self) -> dict[str, dict]:
        """Get accurate layer statistics for all 7 layers."""
        summary = {}

        for layer_config in ArchitectureConfig.ALL_LAYERS:
            layer_name = layer_config.name
            modules_in_layer = self.graph.layers.get(layer_name, [])

            total_classes = sum(len(m.classes) for m in modules_in_layer)
            total_functions = sum(len(m.functions) for m in modules_in_layer)
            total_complexity = sum(m.complexity for m in modules_in_layer)

            summary[layer_name] = {
                "name": layer_config.name,
                "level": layer_config.level,
                "description": layer_config.description,
                "module_count": len(modules_in_layer),
                "class_count": total_classes,
                "function_count": total_functions,
                "complexity": total_complexity,
                "icon": layer_config.icon,
                "color": layer_config.color,
                "border_color": layer_config.border_color,
            }

        return summary

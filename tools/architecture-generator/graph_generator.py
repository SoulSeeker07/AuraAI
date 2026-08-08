"""
Graph Generator
===============

Generates visual and structural architecture representations:
- High-Level Cognitive & Systems Architecture (Mermaid, Graphviz, Draw.io)
- Module Dependency Diagrams (grouped by 7 layers with colors and icons)
- Draw.io XML format export (.drawio)
- Markdown Architecture Documentation (ARCHITECTURE.md)
"""

from config import ArchitectureConfig


class DotGraph:
    """Helper for generating Graphviz DOT format."""

    def __init__(self, title: str = "AuraAI Cognitive Architecture"):
        self.title = title
        self.nodes = {}
        self.edges = []
        self.clusters = {}

    def add_node(
        self,
        node_id: str,
        label: str,
        layer: str,
        shape: str = "box",
        role: str = "UTILITY",
        color: str = "#4B8BBE",
    ):
        self.nodes[node_id] = {
            "label": label,
            "layer": layer,
            "shape": shape,
            "role": role,
            "color": color,
        }

    def add_edge(
        self, from_node: str, to_node: str, label: str = "", style: str = "solid"
    ):
        self.edges.append(
            {"from": from_node, "to": to_node, "label": label, "style": style}
        )

    def add_cluster(self, layer_name: str, nodes: list[str], title: str, color: str):
        self.clusters[layer_name] = {"nodes": nodes, "title": title, "color": color}

    def generate(self) -> str:
        lines = [
            "digraph AuraArchitecture {",
            "  compound=true;",
            "  rankdir=TB;",
            '  fontname="Helvetica,Arial,sans-serif";',
            '  node [fontname="Helvetica,Arial,sans-serif", fontsize=10, style="filled,rounded", penwidth=1.5];',
            '  edge [fontname="Helvetica,Arial,sans-serif", fontsize=8, color="#64748B", penwidth=1.2];',
            '  bgcolor="#FFFFFF";',
            f'  label="{self.title}\\n ";',
            '  labelloc="t";',
            "  fontsize=16;",
            "",
        ]

        # Add clusters
        for cluster_id, cluster in self.clusters.items():
            safe_id = "".join(c if c.isalnum() else "_" for c in cluster_id)
            lines.append(f"  subgraph cluster_{safe_id} {{")
            lines.append(f'    label="{cluster["title"]}";')
            lines.append('    style="filled,rounded";')
            lines.append(f'    color="{cluster["color"]}";')
            lines.append(f'    fillcolor="{cluster["color"]}22";')
            lines.append("    fontsize=12;")
            lines.append('    fontcolor="#1E293B";')

            for node_id in cluster["nodes"]:
                node = self.nodes.get(node_id)
                if node:
                    safe_node = "".join(c if c.isalnum() else "_" for c in node_id)
                    lines.append(
                        f'    "{safe_node}" [label="{node["label"]}", shape="{node["shape"]}", fillcolor="{node["color"]}", color="{node["color"]}", fontcolor="#0F172A"];'
                    )

            lines.append("  }")
            lines.append("")

        # Add edges (limit top dependencies to prevent visual clutter)
        seen_edges = set()
        for edge in self.edges[:150]:
            safe_from = "".join(c if c.isalnum() else "_" for c in edge["from"])
            safe_to = "".join(c if c.isalnum() else "_" for c in edge["to"])
            edge_key = (safe_from, safe_to)
            if (
                edge_key not in seen_edges
                and safe_from in self.nodes
                and safe_to in self.nodes
            ):
                seen_edges.add(edge_key)
                label_attr = f' [label="{edge["label"]}"]' if edge["label"] else ""
                lines.append(f'  "{safe_from}" -> "{safe_to}"{label_attr};')

        lines.append("}")
        return "\n".join(lines)


class MermaidGraph:
    """Helper for generating Mermaid diagram format."""

    def __init__(self, title: str = "Aura Architecture Flow"):
        self.title = title
        self.clusters = {}
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id: str, label: str, layer: str, icon: str = ""):
        self.nodes[node_id] = {"label": label, "layer": layer, "icon": icon}

    def add_edge(self, from_node: str, to_node: str, label: str = ""):
        self.edges.append({"from": from_node, "to": to_node, "label": label})

    def add_cluster(self, layer_name: str, title: str, color: str):
        self.clusters[layer_name] = {"title": title, "color": color, "nodes": []}

    def generate(self) -> str:
        lines = [
            "```mermaid",
            "graph TD",
            "  %% Aura Cognitive Architecture Flow",
            "  classDef default font-family:sans-serif,font-size:12px;",
        ]

        # Add subgraphs
        for layer_config in ArchitectureConfig.ALL_LAYERS:
            layer_name = layer_config.name
            safe_cluster = "".join(c if c.isalnum() else "_" for c in layer_name)
            lines.append(
                f'  subgraph {safe_cluster} ["{layer_config.icon} {layer_name}"]'
            )

            # Nodes in layer
            for n_id, n_info in self.nodes.items():
                if n_info["layer"] == layer_name:
                    safe_n = "".join(c if c.isalnum() else "_" for c in n_id)
                    lines.append(f"    {safe_n}[\"{n_info['label']}\"]")
            lines.append("  end")
            lines.append("")

            # Style subgraph
            lines.append(
                f"  style {safe_cluster} fill:{layer_config.color}33,stroke:{layer_config.border_color},stroke-width:2px;"
            )

        # Add edges
        seen = set()
        for edge in self.edges[:120]:
            sf = "".join(c if c.isalnum() else "_" for c in edge["from"])
            st = "".join(c if c.isalnum() else "_" for c in edge["to"])
            if (
                (sf, st) not in seen
                and sf in self.nodes
                and st in self.nodes
                and sf != st
            ):
                seen.add((sf, st))
                lines.append(f"  {sf} --> {st}")

        lines.append("```")
        return "\n".join(lines)


class GraphGenerator:
    """Generates graphs and reports from ArchitectureGraph."""

    def __init__(self, graph):
        self.graph = graph

    def generate_dot(self, format: str = "dot") -> str:
        dot = DotGraph(title="AuraAI Architectural Layer & Dependency Graph")

        for layer_config in ArchitectureConfig.ALL_LAYERS:
            layer_name = layer_config.name
            modules_in_layer = self.graph.layers.get(layer_name, [])

            node_ids = []
            for mod in modules_in_layer:
                shape = (
                    "box"
                    if mod.role in ["ORCHESTRATOR", "ENGINE", "MANAGER"]
                    else "ellipse"
                )
                dot.add_node(
                    node_id=mod.name,
                    label=mod.name.replace("_", " ").title(),
                    layer=layer_name,
                    shape=shape,
                    role=mod.role,
                    color=layer_config.color,
                )
                node_ids.append(mod.name)

            if node_ids:
                dot.add_cluster(
                    layer_name=layer_name,
                    nodes=node_ids,
                    title=f"{layer_config.icon} {layer_name} ({len(node_ids)} modules)",
                    color=layer_config.border_color,
                )

        for dep in self.graph.dependencies:
            dot.add_edge(
                from_node=dep.from_module, to_node=dep.to_module, label=dep.import_type
            )

        return dot.generate()

    def generate_mermaid(self, format: str = "mermaid") -> str:
        mermaid = MermaidGraph(title="Aura Architecture Layer Breakdown")

        for mod_name, mod in self.graph.modules.items():
            layer_config = ArchitectureConfig.get_layer_by_name(mod.layer_name)
            mermaid.add_node(
                node_id=mod_name,
                label=f"{mod_name.replace('_', ' ').title()}",
                layer=mod.layer_name,
                icon=layer_config.icon,
            )

        for dep in self.graph.dependencies:
            mermaid.add_edge(from_node=dep.from_module, to_node=dep.to_module)

        return mermaid.generate()

    def generate_cognitive_flow_mermaid(self) -> str:
        """Generates high-level professional cognitive execution flow Mermaid diagram."""
        return """```mermaid
graph TD
  subgraph USER_LAYER ["🚀 1. USER & APPLICATION INTERFACES"]
    USER(("👤 User Input"))
    CLI["💻 CLI Client (cli.py)"]
    GUI["🎨 Desktop GUI Client"]
    VOICE["🎙️ Voice Interface"]
  end

  subgraph CORE_LAYER ["👑 2. AURA OS KERNEL & RUNTIME CORE"]
    CORE["⚙️ AuraCore (aura_core.py)"]
    SESSION["📋 RuntimeSession"]
    EVENTBUS["⚡ EventBus (Broadcaster)"]
  end

  subgraph ACA_LAYER ["🧠 3. AURA COGNITIVE ARCHITECTURE (ACA)"]
    BLACKBOARD["📝 Blackboard (CognitiveState)"]
    DMM["🔍 Decision Manager (DMM)"]
    STRATEGY["🎯 StrategyEngine (Stage 1.5)"]
    POLICY["🛡️ PolicyEngine (Governance)"]
    PLANNER["📐 ACAPlanner (ExecutionGraph)"]
    COORDINATOR["⚡ ExecutionCoordinator (Stage 3)"]
    REFLECTION["🔄 ReflectionEngine (Stage 4)"]
    LEARNING["💡 LearningEngine (Stage 4)"]
  end

  subgraph SUBSYSTEMS_LAYER ["🎯 4. DOMAIN ENGINE ADAPTERS & SUBSYSTEMS"]
    REGISTRY["🏥 EngineRegistry (Health & Capabilities)"]
    DESKTOP_ENG["🖥️ DesktopEngineAdapter → Windows OS"]
    BROWSER_ENG["🌐 BrowserEngineAdapter → Playwright"]
    RESEARCH_ENG["🔬 ResearchEngineAdapter → Deep Search"]
    ENGINEERING_ENG["🛠️ EngineeringManager → AST & Refactor"]
    VISION_ENG["👁️ VisionManager → OCR & Element Detect"]
    VOICE_ENG["🔊 VoiceManager → STT / TTS"]
  end

  subgraph MEMORY_LAYER ["📚 5. KNOWLEDGE & PERSISTENCE"]
    MEMORY["💾 Memory 2.0 (Fact & Vector Store)"]
    GOALS["🎯 GoalManager (Long-term Goals)"]
    ARTIFACTS["📦 ArtifactManager"]
  end

  %% Flow Connections
  USER --> CLI & GUI & VOICE
  CLI & GUI & VOICE --> CORE
  CORE --> SESSION & BLACKBOARD
  BLACKBOARD --> DMM
  DMM --> STRATEGY
  STRATEGY --> POLICY
  POLICY --> PLANNER
  PLANNER --> COORDINATOR
  COORDINATOR --> REGISTRY
  REGISTRY --> DESKTOP_ENG & BROWSER_ENG & RESEARCH_ENG & ENGINEERING_ENG & VISION_ENG & VOICE_ENG
  DESKTOP_ENG & BROWSER_ENG & RESEARCH_ENG & ENGINEERING_ENG --> REFLECTION
  REFLECTION --> LEARNING
  LEARNING --> MEMORY
  COORDINATOR --> ARTIFACTS
  EVENTBUS -.-> BLACKBOARD & REFLECTION

  %% Styling
  style USER_LAYER fill:#FEF08A33,stroke:#CA8A04,stroke-width:2px
  style CORE_LAYER fill:#E9D5FF33,stroke:#9333EA,stroke-width:2px
  style ACA_LAYER fill:#FFEDD533,stroke:#EA580C,stroke-width:2px
  style SUBSYSTEMS_LAYER fill:#CCFBF133,stroke:#0D9488,stroke-width:2px
  style MEMORY_LAYER fill:#FED7AA33,stroke:#D97706,stroke-width:2px
```"""

    def generate_drawio_xml(self) -> str:
        """Generates native Draw.io XML format for visual editing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="2026-08-07T00:00:00.000Z" agent="AuraAI Architecture Generator" version="21.0.0" type="device">
  <diagram id="aura_arch" name="Aura Architecture">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827" background="#ffffff">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        
        <!-- User Layer -->
        <mxCell id="layer_user" value="🚀 Applications &amp; Clients" style="swimlane;whiteSpace=wrap;html=1;fillColor=#FEF08A;strokeColor=#CA8A04;startSize=30;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="1080" height="90" as="geometry" />
        </mxCell>
        <mxCell id="cli" value="💻 CLI Client" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#CA8A04;" vertex="1" parent="layer_user">
          <mxGeometry x="20" y="35" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="gui" value="🎨 Desktop GUI Client" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#CA8A04;" vertex="1" parent="layer_user">
          <mxGeometry x="200" y="35" width="160" height="40" as="geometry" />
        </mxCell>
        
        <!-- Core Kernel -->
        <mxCell id="layer_core" value="👑 OS Kernel &amp; Runtime Core" style="swimlane;whiteSpace=wrap;html=1;fillColor=#E9D5FF;strokeColor=#9333EA;startSize=30;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="40" y="160" width="1080" height="90" as="geometry" />
        </mxCell>
        <mxCell id="auracore" value="⚙️ AuraCore (Kernel)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9333EA;fontStyle=1;" vertex="1" parent="layer_core">
          <mxGeometry x="20" y="35" width="180" height="40" as="geometry" />
        </mxCell>
        <mxCell id="eventbus" value="⚡ EventBus" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9333EA;" vertex="1" parent="layer_core">
          <mxGeometry x="230" y="35" width="140" height="40" as="geometry" />
        </mxCell>
        
        <!-- ACA Layer -->
        <mxCell id="layer_aca" value="🧠 Cognitive Architecture (ACA)" style="swimlane;whiteSpace=wrap;html=1;fillColor=#FFEDD5;strokeColor=#EA580C;startSize=30;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="40" y="280" width="1080" height="150" as="geometry" />
        </mxCell>
        <mxCell id="blackboard" value="📝 Blackboard (CognitiveState)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#EA580C;" vertex="1" parent="layer_aca">
          <mxGeometry x="20" y="40" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="acabrain" value="🧠 ACABrain (Stages 0-4)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#EA580C;fontStyle=1;" vertex="1" parent="layer_aca">
          <mxGeometry x="240" y="40" width="180" height="40" as="geometry" />
        </mxCell>
        <mxCell id="coordinator" value="⚡ ExecutionCoordinator" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#EA580C;fontStyle=1;" vertex="1" parent="layer_aca">
          <mxGeometry x="450" y="40" width="180" height="40" as="geometry" />
        </mxCell>
        
        <!-- Domain Subsystems -->
        <mxCell id="layer_domain" value="🎯 Domain Subsystems &amp; Engine Adapters" style="swimlane;whiteSpace=wrap;html=1;fillColor=#CCFBF1;strokeColor=#0D9488;startSize=30;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="40" y="460" width="1080" height="120" as="geometry" />
        </mxCell>
        <mxCell id="desktop_eng" value="🖥️ Desktop Engine" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0D9488;" vertex="1" parent="layer_domain">
          <mxGeometry x="20" y="45" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="browser_eng" value="🌐 Browser Engine" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0D9488;" vertex="1" parent="layer_domain">
          <mxGeometry x="190" y="45" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="research_eng" value="🔬 Research Engine" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0D9488;" vertex="1" parent="layer_domain">
          <mxGeometry x="360" y="45" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="engineering_eng" value="🛠️ Engineering Manager" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#0D9488;" vertex="1" parent="layer_domain">
          <mxGeometry x="530" y="45" width="170" height="40" as="geometry" />
        </mxCell>
        
      </root>
    </mxGraphModel>
  </mxfile>
"""

    def generate_statistics(self) -> dict:
        """Calculates accurate layer statistics across all 520+ modules."""
        stats = {
            "total_modules": len(self.graph.modules),
            "total_dependencies": len(self.graph.dependencies),
            "total_violations": len(self.graph.violations),
            "layers": {},
            "layer_dependencies": ArchitectureConfig.get_layer_dependencies(),
        }

        for layer_config in ArchitectureConfig.ALL_LAYERS:
            layer_name = layer_config.name
            modules_in_layer = self.graph.layers.get(layer_name, [])

            stats["layers"][layer_name] = {
                "module_count": len(modules_in_layer),
                "class_count": sum(len(m.classes) for m in modules_in_layer),
                "function_count": sum(len(m.functions) for m in modules_in_layer),
                "complexity": sum(m.complexity for m in modules_in_layer),
            }

        return stats

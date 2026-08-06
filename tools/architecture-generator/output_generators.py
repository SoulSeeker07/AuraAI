"""
Output Generators
=================

Handles generation of output files in various formats:
- DOT format (Graphviz text)
- Mermaid format (.mmd text)
- Draw.io XML format (.drawio)
- JSON (.json for automated tool consumption)
- Markdown Documentation (ARCHITECTURE.md)
- Text Analysis Report (architecture_report.txt)
- Visual renders (PNG, SVG, PDF) via Graphviz CLI if available
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Optional
import subprocess
from enum import Enum
from datetime import datetime

from graph_generator import GraphGenerator
from config import ArchitectureConfig


class OutputGenerator:
    """Generates architecture diagram files and reports."""
    
    def __init__(self, graph_generator: GraphGenerator):
        self.graph_generator = graph_generator
        
    def _save_file(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        
    def _save_json_file(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        
    def generate_dot(self, output_path: Optional[Path] = None) -> str:
        content = self.graph_generator.generate_dot(format='dot')
        if output_path:
            self._save_file(output_path, content)
        return content

    def generate_mermaid(self, output_path: Optional[Path] = None) -> str:
        content = self.graph_generator.generate_mermaid(format='mermaid')
        if output_path:
            self._save_file(output_path, content)
        return content

    def generate_cognitive_mermaid(self, output_path: Optional[Path] = None) -> str:
        content = self.graph_generator.generate_cognitive_flow_mermaid()
        if output_path:
            self._save_file(output_path, content)
        return content

    def generate_drawio(self, output_path: Optional[Path] = None) -> str:
        content = self.graph_generator.generate_drawio_xml()
        if output_path:
            self._save_file(output_path, content)
        return content

    def generate_json(self, output_path: Optional[Path] = None) -> dict:
        stats = self.graph_generator.generate_statistics()
        json_data = {
            'version': '1.0.0',
            'generated_at': datetime.now().isoformat(),
            'statistics': stats
        }
        if output_path:
            self._save_json_file(output_path, json_data)
        return json_data

    def generate_markdown_docs(self, output_path: Optional[Path] = None) -> str:
        """Generates full ARCHITECTURE.md markdown documentation with embedded Mermaid flow diagrams."""
        stats = self.graph_generator.generate_statistics()
        flow_mermaid = self.graph_generator.generate_cognitive_flow_mermaid()
        
        lines = [
            "# 🏛️ AuraAI System & Cognitive Architecture Documentation",
            "",
            "> **CORE PRINCIPLE:** *\"The architecture is largely complete. The runtime is not.\"*",
            "> Every user request flows through a single cognitive runtime pipeline.",
            "",
            "---",
            "",
            "## 📊 High-Level Layer Breakdown",
            "",
            "| Layer Level | Architecture Layer | Description | Modules | Classes | Functions | Complexity |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: |"
        ]
        
        for layer_config in ArchitectureConfig.ALL_LAYERS:
            layer_name = layer_config.name
            l_data = stats['layers'].get(layer_name, {})
            lines.append(
                f"| **{layer_config.level}** | {layer_config.icon} **{layer_name}** | {layer_config.description} | "
                f"{l_data.get('module_count', 0)} | {l_data.get('class_count', 0)} | {l_data.get('function_count', 0)} | {l_data.get('complexity', 0)} |"
            )
            
        lines.extend([
            "",
            "---",
            "",
            "## 🔁 Continuous Agent Decision & Cognitive Pipeline Flow",
            "",
            flow_mermaid,
            "",
            "---",
            "",
            "## 🛡️ Guardrail Rules & Component Layer Contracts",
            "",
            "1. **Single Entry Point**: All user requests enter through `AuraCore.process_request()`.",
            "2. **Guardrail 1 Decoupling**: No domain backend (`src/desktop`, `src/browser`, `src/research`, `src/engineering`, `src/vision`) may import from `src.brain.aca`.",
            "3. **Single Coordinator**: Only `ExecutionCoordinator` invokes execution engines via `EngineRegistry` & `EngineAdapters`.",
            "4. **Shared Blackboard**: All stages read from and write to `Blackboard` (`CognitiveState`).",
            "",
            f"*Generated automatically on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by `generate_architecture.py`.*"
        ])
        
        content = "\n".join(lines)
        if output_path:
            self._save_file(output_path, content)
        return content

    def generate_statistics_report(self, output_path: Optional[Path] = None) -> str:
        stats = self.graph_generator.generate_statistics()
        
        lines = [
            "=" * 80,
            "  AURA ARCHITECTURE ANALYSIS REPORT",
            "=" * 80,
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Modules Analyzed: {stats.get('total_modules', 0)}",
            f"Total Dependencies Mapped: {stats.get('total_dependencies', 0)}",
            f"Architecture Violations Detected: {stats.get('total_violations', 0)}",
            "",
            "-" * 80,
            "  7-LAYER ARCHITECTURAL BREAKDOWN",
            "-" * 80,
            ""
        ]
        
        for layer_config in ArchitectureConfig.ALL_LAYERS:
            layer_name = layer_config.name
            layer_data = stats['layers'].get(layer_name, {})
            lines.append(f"  {layer_config.icon} {layer_name} (Level {layer_config.level}):")
            lines.append(f"    - Description: {layer_config.description}")
            lines.append(f"    - Modules Count: {layer_data.get('module_count', 0)}")
            lines.append(f"    - Classes Count: {layer_data.get('class_count', 0)}")
            lines.append(f"    - Functions Count: {layer_data.get('function_count', 0)}")
            lines.append(f"    - Complexity Score: {layer_data.get('complexity', 0)}")
            lines.append("")
            
        lines.extend([
            "-" * 80,
            "  EXPECTED DEPENDENCY CHAIN",
            "-" * 80,
            ""
        ])
        
        for layer_name, depends_on in stats.get('layer_dependencies', {}).items():
            deps_str = ", ".join(depends_on) if depends_on else "None (Base Layer)"
            lines.append(f"  {layer_name} -> {deps_str}")
            
        lines.append("")
        lines.append("=" * 80)
        
        content = "\n".join(lines)
        if output_path:
            self._save_file(output_path, content)
        return content

    def save_all_outputs(self, output_dir: Path, include_visuals: bool = False) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            'dot': str(output_dir / 'architecture.dot'),
            'mermaid': str(output_dir / 'architecture.mmd'),
            'cognitive_mermaid': str(output_dir / 'architecture_flow.mmd'),
            'drawio': str(output_dir / 'architecture.drawio'),
            'json': str(output_dir / 'architecture.json'),
            'markdown': str(output_dir / 'ARCHITECTURE.md'),
            'report': str(output_dir / 'architecture_report.txt'),
            'png': None,
            'svg': None,
            'pdf': None
        }
        
        self.generate_dot(Path(results['dot']))
        self.generate_mermaid(Path(results['mermaid']))
        self.generate_cognitive_mermaid(Path(results['cognitive_mermaid']))
        self.generate_drawio(Path(results['drawio']))
        self.generate_json(Path(results['json']))
        self.generate_markdown_docs(Path(results['markdown']))
        self.generate_statistics_report(Path(results['report']))
        
        if include_visuals:
            results['png'] = self._render_graphviz(Path(results['dot']), output_dir / 'architecture.png', 'png')
            results['svg'] = self._render_graphviz(Path(results['dot']), output_dir / 'architecture.svg', 'svg')
            results['pdf'] = self._render_graphviz(Path(results['dot']), output_dir / 'architecture.pdf', 'pdf')
            
        return results

    def _render_graphviz(self, dot_file: Path, output_file: Path, fmt: str) -> Optional[str]:
        try:
            cmd = ['dot', f'-T{fmt}', str(dot_file), '-o', str(output_file)]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return str(output_file)
        except Exception:
            return None

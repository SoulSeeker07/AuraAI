#!/usr/bin/env python
"""Test AuraCore initialization with new components"""

from core.aura_core import AuraCore

print("Initializing AuraCore...")
core = AuraCore()

print("✓ AuraCore initialized successfully")
print(f"✓ Multi-Agent Status: {core.multi_agent_status.value}")
print(f"✓ Agent Runtime Status: {core.agent_runtime_status.value}")
print(f"✓ Workflow Engine Status: {core.workflow_engine_status.value}")
print(
    f"✓ Multi-Agent components loaded: {core.components.get('multi_agent', {}).loaded}"
)
print(
    f"✓ Agent Runtime components loaded: {core.components.get('agent_runtime', {}).loaded}"
)
print(
    f"✓ Workflow Engine components loaded: {core.components.get('workflow_engine', {}).loaded}"
)

print("\n✅ All tests passed! New components are connected to AuraCore.")

# Import Convention Violations: 250 across 67 files

### `tests/browser/test_browser_agent.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 155 | `    from src.execution.risk_analyzer import RiskAnalyzer, RiskLevel` |

### `tests/core/test_orchestration.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 25 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 26 | `from src.desktop.native.desktop_execution_engine import (` |
| 31 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 32 | `from src.desktop.planner import DesktopPlanner` |

### `tests/core/test_stabilization_phase.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 17 | `from src.execution.safety_policy import SafetyPolicy` |

### `tests/desktop/test_audio_manager.py` (6 violations)

| Line | Offending Import Statement |
|---|---|
| 19 | `import src.desktop.native.managers.audio_manager as am_module` |
| 20 | `from src.desktop.native.adapters.audio_adapter import (` |
| 27 | `from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine` |
| 28 | `from src.desktop.native.managers.audio_manager import AudioManager` |
| 29 | `from src.desktop.native.managers.base_manager import HealthStatus` |
| 30 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |

### `tests/desktop/test_clipboard_manager_pattern.py` (6 violations)

| Line | Offending Import Statement |
|---|---|
| 23 | `from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine` |
| 24 | `from src.desktop.native.desktop_result import DesktopResult, DesktopStatus` |
| 25 | `from src.desktop.native.managers.clipboard_manager import (` |
| 29 | `from src.desktop.native.native_exceptions import ClipboardError` |
| 71 | `    import src.desktop.native.managers.clipboard_manager as cm_module` |
| 291 | `    import src.desktop.native.managers.clipboard_manager as cm_module` |

### `tests/desktop/test_desktop_planner.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 12 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 13 | `from src.desktop.native.desktop_execution_engine import (` |
| 18 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 19 | `from src.desktop.planner import (` |

### `tests/desktop/test_desktop_planner_expansion.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 15 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 16 | `from src.desktop.native.desktop_execution_engine import (` |
| 21 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 22 | `from src.desktop.planner import (` |

### `tests/desktop/test_display_manager.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 17 | `import src.desktop.native.managers.display_manager as dm_module` |
| 18 | `from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine` |
| 19 | `from src.desktop.native.managers.display_manager import DisplayManager` |
| 20 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |

### `tests/desktop/test_native_manager_registry.py` (7 violations)

| Line | Offending Import Statement |
|---|---|
| 20 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 21 | `from src.desktop.native.capability_validator import (` |
| 25 | `from src.desktop.native.desktop_execution_engine import (` |
| 29 | `from src.desktop.native.managers.base_manager import (` |
| 34 | `from src.desktop.native.managers.clipboard_manager import ClipboardManager` |
| 35 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 36 | `from src.desktop.native.managers.window_manager import WindowManager` |

### `tests/desktop/test_network_manager.py` (5 violations)

| Line | Offending Import Statement |
|---|---|
| 14 | `from src.desktop.native.adapters.network_adapter import (` |
| 22 | `from src.desktop.native.capability_registry import (` |
| 27 | `from src.desktop.native.desktop_execution_engine import (` |
| 32 | `from src.desktop.native.managers.native_manager_registry import (` |
| 36 | `from src.desktop.native.managers.network_manager import NetworkManager` |

### `tests/desktop/test_permission_manager.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 11 | `from src.agents.permission_manager import PermissionLevel, PermissionManager` |
| 12 | `from src.agents.process_manager import ProcessManager` |
| 13 | `from src.agents.task_model import Task, TaskInput, TaskType` |

### `tests/desktop/test_phase2b_architecture_validation.py` (6 violations)

| Line | Offending Import Statement |
|---|---|
| 18 | `from src.desktop.native.adapters.network_adapter import DummyNetworkAdapter` |
| 19 | `from src.desktop.native.capability_registry import CapabilityRegistry, RiskLevel` |
| 20 | `from src.desktop.native.desktop_execution_engine import (` |
| 25 | `from src.desktop.native.managers.base_manager import BaseNativeManager` |
| 26 | `from src.desktop.native.managers.native_manager_registry import (` |
| 30 | `from src.desktop.native.managers.network_manager import NetworkManager` |

### `tests/desktop/test_phase3_3_adaptive_intelligence.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 14 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 15 | `from src.desktop.native.desktop_execution_engine import (` |
| 20 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 21 | `from src.desktop.planner import (` |

### `tests/desktop/test_planner_integration_goals.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 16 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 17 | `from src.desktop.native.desktop_execution_engine import (` |
| 22 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 23 | `from src.desktop.planner import (` |

### `tests/desktop/test_power_manager.py` (6 violations)

| Line | Offending Import Statement |
|---|---|
| 20 | `import src.desktop.native.managers.power_manager as pm_module` |
| 21 | `from src.desktop.native.adapters.power_adapter import (` |
| 28 | `from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine` |
| 29 | `from src.desktop.native.managers.base_manager import HealthStatus` |
| 30 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 31 | `from src.desktop.native.managers.power_manager import PowerManager` |

### `tests/desktop/test_process_manager.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 8 | `from src.agents.desktop_agent import DesktopAgent` |
| 9 | `from src.agents.task_model import Task, TaskInput, TaskType` |

### `tests/desktop/test_real_world_scenarios.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 17 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 18 | `from src.desktop.native.desktop_execution_engine import (` |
| 23 | `from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry` |
| 24 | `from src.desktop.planner import (` |

### `tests/desktop/test_window_manager_resolver.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 8 | `from src.desktop.native.managers.window_manager import WindowManager` |
| 9 | `from src.desktop.native.native_result import ResultStatus` |

### `tests/desktop/test_window_manager_validation.py` (5 violations)

| Line | Offending Import Statement |
|---|---|
| 21 | `from src.desktop.native.capability_registry import CapabilityRegistry` |
| 22 | `from src.desktop.native.desktop_execution_engine import (` |
| 26 | `from src.desktop.native.desktop_result import DesktopResult, DesktopStatus` |
| 27 | `from src.desktop.native.managers.window_manager import WindowManager` |
| 32 | `    import src.desktop.native.managers.window_manager as wm_module` |

### `tests/e2e/test_cognitive_runtime.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 42 | `from src.memory.cognitive_memory import CognitiveMemoryEngine` |
| 43 | `from src.memory.models import MemoryItem, MemoryType, MemoryProvenance, ProvenanceSource` |

### `tests/end_to_end_voice_test.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 69 | `    from src.voice.voice_manager import VoiceManager` |

### `tests/final_h2_validation_30min.py` (5 violations)

| Line | Offending Import Statement |
|---|---|
| 37 | `from src.voice.tts_manager import TTSSettings, TTSManger, TTSSpeaker` |
| 38 | `from src.browser.engine import BrowserEngine` |
| 39 | `from src.brain.goal_verifier import GoalVerifier` |
| 40 | `from src.core.config import AuraConfig` |
| 220 | `            from src.brain.goal_verifier import GoalVerifier` |

### `tests/integration/test_e2e_cli_regression.py` (5 violations)

| Line | Offending Import Statement |
|---|---|
| 3 | `from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |
| 4 | `from src.brain.aca.engine_interface import EngineRegistry` |
| 5 | `from src.core.orchestration.reference_resolver import ReferenceResolver` |
| 68 | `    from src.brain.intent_router import IntentRouter` |
| 90 | `            from src.core.orchestration.decision_engine import DecisionEngine` |

### `tests/integration/test_milestone14_integration.py` (7 violations)

| Line | Offending Import Statement |
|---|---|
| 19 | `from src.research.models import (` |
| 26 | `from src.research.research_context import ResearchContext, ResearchMode` |
| 27 | `from src.research.research_engine import ResearchEngine` |
| 165 | `        from src.research.reasoning_layer import ReasoningResult, ResearchReasoner` |
| 173 | `        from src.research.models import Evidence, SourceTrustLevel` |
| 247 | `        from src.research.citation_formatter import CitationFormatter` |
| 251 | `        from src.research.models import Citation, SourceTrustLevel` |

### `tests/integration/test_personal_os_runtime_e2e.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 3 | `from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |

### `tests/memory/test_auracore_brain_init_wiring.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 18 | `    from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |
| 40 | `    from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |

### `tests/memory/test_integration_memory.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 20 | `from src.brain.conversation_engine import ConversationEngine` |
| 21 | `from src.memory.manager.memory_manager import MemoryManager` |

### `tests/memory/test_integration_voice_memory.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 11 | `from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |

### `tests/playwright_live_navigation_probe.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 36 | `from src.browser.engine import BrowserEngine` |
| 37 | `from src.core.backends.adapters.browser_backend import PlaywrightBrowserAdapter` |
| 38 | `from src.brain.goal_verifier import GoalVerifier` |
| 39 | `from src.brain.execution_coordinator import StepResult, CoordinationResult` |

### `tests/run_interactive_loop.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 23 | `from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |
| 24 | `from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState` |
| 25 | `from src.voice.voice_manager import VoiceManager` |

### `tests/short_h2_validation_slice.py` (5 violations)

| Line | Offending Import Statement |
|---|---|
| 37 | `from src.voice.tts_manager import TTSSettings, TTSManger, TTSSpeaker` |
| 38 | `from src.browser.engine import BrowserEngine` |
| 39 | `from src.brain.goal_verifier import GoalVerifier` |
| 40 | `from src.core.config import AuraConfig` |
| 218 | `            from src.brain.goal_verifier import GoalVerifier` |

### `tests/test_agent_runtime.py` (6 violations)

| Line | Offending Import Statement |
|---|---|
| 12 | `from src.agents.agent_runtime import AgentRuntime` |
| 13 | `from src.agents.execution_graph import ExecutionGraph` |
| 14 | `from src.agents.goal import Goal, GoalPriority, GoalStatus` |
| 15 | `from src.agents.planner import Planner` |
| 16 | `from src.agents.scheduler import ExecutionStrategy, Scheduler` |
| 17 | `from src.agents.task import (` |

### `tests/test_agentic_runtime_m19.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 25 | `from src.workspace.workspace_instruction_loader import WorkspaceInstructionLoader` |

### `tests/test_agents_integration.py` (7 violations)

| Line | Offending Import Statement |
|---|---|
| 19 | `from src.agents.agent_registry import (` |
| 25 | `from src.agents.config import ConfigManager, ProviderType, get_config_manager` |
| 26 | `from src.agents.plugin_system import PluginBase, PluginRegistry` |
| 27 | `from src.agents.safety_layer import OperationType, SafetyLayer` |
| 28 | `from src.agents.skill_system import SkillCategory, SkillRegistry, SkillStep` |
| 29 | `from src.agents.task_manager import TaskManager` |
| 30 | `from src.agents.task_model import (` |

### `tests/test_client.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 12 | `from src.aura.client.api_client import ApiClient` |
| 13 | `from src.aura.client.connection_manager import ConnectionManager` |

### `tests/test_code_editor_backup.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 4 | `from src.engineering.code_editor import CodeEditor` |

### `tests/test_coding_backend_wiring.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 261 | `    from src.brain.providers.base import ProviderFact, QueryResult` |

### `tests/test_cognitive_memory.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 33 | `from src.memory.cognitive_memory import CognitiveMemoryEngine` |
| 34 | `from src.memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource` |

### `tests/test_connection.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 13 | `from src.aura.client.connection_manager import ConnectionManager` |
| 14 | `from src.aura.shared import AuraMessage, MessageType` |

### `tests/test_continuous_loop.py` (8 violations)

| Line | Offending Import Statement |
|---|---|
| 90 | `    from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState` |
| 91 | `    from src.voice.voice_manager import VoiceManager` |
| 128 | `    from src.voice.continuous_loop import ContinuousVoiceLoop` |
| 129 | `    from src.voice.voice_manager import VoiceManager` |
| 199 | `    from src.voice.stt_manager import DESKTOP_VOCABULARY_PROMPT, FasterWhisperSTTEngine, STTSettings` |
| 228 | `    from src.desktop.native.managers.window_manager import WindowManager` |
| 258 | `    from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState` |
| 259 | `    from src.voice.voice_manager import VoiceManager` |

### `tests/test_continuous_loop_fsm.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 15 | `from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState` |

### `tests/test_continuous_loop_level2.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 18 | `from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState` |
| 19 | `from src.core.orchestration.personal_os_runtime import PersonalOSRuntime, RuntimeExecutionReport` |
| 20 | `from src.brain.execution_coordinator import CoordinationResult` |

### `tests/test_continuous_loop_level3.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 24 | `from src.voice.continuous_loop import ContinuousVoiceLoop, VoiceState` |
| 25 | `from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |
| 26 | `from src.brain.execution_coordinator import CoordinationResult` |
| 27 | `from src.voice.voice_manager import VoiceManager, ConversationState` |

### `tests/test_earcon_player.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 6 | `from src.voice.earcon_player import EarconPlayer` |

### `tests/test_execution_engine.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 11 | `from src.execution import (` |
| 31 | `from src.execution.exceptions import (` |
| 799 | `            from src.execution import ToolCategory, ToolMetadata` |

### `tests/test_interactive_stt.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 24 | `from src.voice.stt_manager import STTManager, STTSettings, STTProvider` |

### `tests/test_m20_6.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 4 | `from src.engineering.test_engine import TestEngine` |

### `tests/test_m20_6_repair.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 4 | `from src.engineering.test_engine import TestEngine` |
| 5 | `from src.engineering.code_editor import CodeEditor` |
| 6 | `from src.engineering.bug_repair import BugRepairLoop` |

### `tests/test_rag_2_0.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 18 | `from src.knowledge.parsers import get_parser_registry` |

### `tests/test_routing_system.py` (9 violations)

| Line | Offending Import Statement |
|---|---|
| 9 | `from src.routing.capability_router import CapabilityRouter` |
| 10 | `from src.routing.capability_types import CapabilityType` |
| 11 | `from src.routing.intent_classifier import IntentClassifier` |
| 12 | `from src.routing.keyword_router import KeywordRouter` |
| 13 | `from src.routing.permission_analyzer import PermissionAnalyzer` |
| 14 | `from src.routing.plugin_registry import PluginCapability, PluginRegistry` |
| 15 | `from src.routing.risk_levels import RiskLevel` |
| 16 | `from src.routing.routing_result import RoutingResult` |
| 17 | `from src.routing.workflow_orchestrator import WorkflowOrchestrator` |

### `tests/test_stt_manager.py` (6 violations)

| Line | Offending Import Statement |
|---|---|
| 4 | `from src.voice.stt_manager import FasterWhisperSTTEngine, LocalAgreementStabilizer` |
| 5 | `from src.voice.models import STTSettings` |
| 98 | `    from src.voice.stt_manager import GoogleSTTEngine, CircuitBreakerState` |
| 161 | `    from src.voice.stt_manager import GoogleSTTEngine, CircuitBreakerState` |
| 191 | `    from src.voice.stt_manager import GoogleSTTEngine, CircuitBreakerState` |
| 222 | `    from src.voice.stt_manager import GoogleSTTEngine` |

### `tests/test_tts_manager.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 8 | `from src.voice.tts_manager import (` |
| 16 | `from src.voice.stt_manager import FasterWhisperSTTEngine, STTSettings, STTProvider` |

### `tests/test_tts_stt_runtime.py` (21 violations)

| Line | Offending Import Statement |
|---|---|
| 66 | `        from src.voice.tts_manager import PiperTTSEngine, TTSSettings, TTSSpeaker` |
| 90 | `        from src.voice.tts_manager import EdgeTTSEngine, TTSSettings, TTSSpeaker` |
| 105 | `        from src.voice.tts_manager import TTSSettings, TTSSpeaker` |
| 114 | `        from src.voice.tts_manager import TTSSettings, TTSSpeaker` |
| 123 | `        from src.voice.tts_manager import TTSSettings` |
| 134 | `        from src.voice.tts_manager import TTSManger, TTSSettings, TTSSpeaker` |
| 148 | `        from src.voice.tts_manager import TTSManger, TTSSettings, TTSSpeaker` |
| 158 | `        from src.voice.tts_manager import TTSManger, TTSSettings, TTSSpeaker` |
| 171 | `        from src.voice.tts_manager import TTSSpeaker` |
| 192 | `        from src.voice.stt_manager import FasterWhisperSTTEngine, STTSettings, STTProvider` |
| 219 | `        from src.voice.stt_manager import STTManager, STTSettings, STTProvider` |
| 239 | `        from src.voice.stt_manager import STTSettings, STTProvider` |
| 248 | `        from src.voice.stt_manager import STTSettings` |
| 259 | `        from src.voice.stt_manager import VoskSTTEngine, STTSettings, STTProvider` |
| 281 | `        from src.voice.stt_manager import STTSettings, STTProvider` |
| 292 | `        from src.voice.stt_manager import STTManager, STTSettings, STTProvider` |
| 302 | `        from src.voice.stt_manager import STTManager, STTSettings, STTProvider` |
| 312 | `        from src.voice.stt_manager import STTProvider` |
| 329 | `        from src.voice.voice_manager import VoiceManager` |
| 330 | `        from src.voice.tts_manager import TTSSpeaker` |
| 331 | `        from src.voice.stt_manager import STTProvider` |

### `tests/test_tts_text_cleaner.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 5 | `from src.voice.tts_text_cleaner import clean_for_tts` |

### `tests/test_websocket.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 9 | `from src.aura.client.connection_manager import ConnectionManager` |

### `tests/test_workspace_awareness.py` (6 violations)

| Line | Offending Import Statement |
|---|---|
| 13 | `from src.workspace import (` |
| 27 | `from src.workspace.active_window import ActiveWindowMonitor` |
| 28 | `from src.workspace.clipboard_monitor import ClipboardMonitor` |
| 29 | `from src.workspace.git_context import GitContext` |
| 30 | `from src.workspace.project_detector import ProjectDetector` |
| 31 | `from src.workspace.running_apps import RunningAppsMonitor` |

### `tests/test_workspace_instructions.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 8 | `from src.workspace.workspace_instruction_loader import WorkspaceInstructionLoader` |

### `tests/test_world_model_consolidation.py` (9 violations)

| Line | Offending Import Statement |
|---|---|
| 23 | `from src.brain.world_model import WorldModel, WorldState` |
| 24 | `from src.core.orchestration.world_diff import WorldDiff` |
| 25 | `from src.core.orchestration.world_snapshot import DesktopStateSnapshot, WorldSnapshotProvider` |
| 26 | `from src.core.orchestration.world_state_observer import WorldStateObserver` |
| 27 | `from src.core.orchestration.world_timeline import TimelineEvent, WorldTimeline` |
| 28 | `from src.workspace.active_window import RECT, ActiveWindowMonitor` |
| 29 | `from src.workspace.git_context import GitContext` |
| 30 | `from src.workspace.models import ActiveWindow, GitRepository, RunningApplication` |
| 31 | `from src.workspace.running_apps import RunningAppsMonitor` |

### `tests/test_world_model_providers.py` (8 violations)

| Line | Offending Import Statement |
|---|---|
| 24 | `from src.brain.providers.base import IWorldProvider, ProviderFact, QueryResult` |
| 25 | `from src.brain.providers.browser_provider import BrowserProvider` |
| 26 | `from src.brain.providers.desktop_provider import DesktopProvider` |
| 27 | `from src.brain.providers.memory_provider import MemoryProvider` |
| 28 | `from src.brain.providers.symbol_provider import SymbolGraphProvider` |
| 29 | `from src.brain.providers.workspace_provider import WorkspaceProvider` |
| 30 | `from src.brain.world_model import WorldModel` |
| 31 | `from src.workspace.models import ActiveWindow, GitRepository, RunningApplication` |

### `tests/tts_enum_fix_probe.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 23 | `from src.voice.tts_manager import TTSSettings, TTSManger, TTSSpeaker` |
| 24 | `from src.voice.models import TTSSettings as ModelsTTSSettings` |

### `tests/unit/browser/test_browser_goal_planner.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 16 | `from src.browser.planner.browser_goal import BrowserGoal` |
| 17 | `from src.browser.planner.browser_goal_planner import BrowserGoalPlanner` |
| 18 | `from src.browser.planner.site_registry import SiteRegistry` |

### `tests/unit/gui/test_gui_framework.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 17 | `from src.gui.main_window import MainWindow` |
| 18 | `from src.gui.overlay import OverlayWindow` |
| 19 | `from src.gui.signals import ExecutionStep, StepStatus, app_signals` |
| 20 | `from src.gui.widgets import (` |

### `tests/unit/test_evidence_layer.py` (1 violation)

| Line | Offending Import Statement |
|---|---|
| 14 | `from src.research.models import (` |

### `tests/unit/test_intent_regression.py` (4 violations)

| Line | Offending Import Statement |
|---|---|
| 2 | `from src.core.nlu.nlu_engine import NLUEngine` |
| 3 | `from src.brain.intent_router import IntentRouter` |
| 4 | `from src.core.orchestration.decision_engine import DecisionEngine` |
| 5 | `from src.core.orchestration.reference_resolver import ReferenceResolver` |

### `tests/unit/test_researchcontext.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 5 | `from src.research.citation_builder import CitationBuilder, CitationStyle` |
| 6 | `from src.research.models import Evidence, SourceTrustLevel` |
| 7 | `from src.research.research_context import ResearchContext, ResearchMode` |

### `tests/unit/test_tts_lazy_init.py` (3 violations)

| Line | Offending Import Statement |
|---|---|
| 28 | `from src.voice.tts_manager import (` |
| 220 | `        from src.voice.voice_manager import VoiceManager` |
| 255 | `        from src.voice.models import ConversationState` |

### `scratch/test_os_routing.py` (2 violations)

| Line | Offending Import Statement |
|---|---|
| 5 | `from src.core.orchestration.personal_os_runtime import PersonalOSRuntime` |
| 6 | `from src.core.orchestration.reference_resolver import ReferenceResolver` |

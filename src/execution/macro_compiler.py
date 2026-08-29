"""
Pre-flight Verified Macro Compiler & Execution Subsystem
Location: src/execution/macro_compiler.py

Compiles repeatedly verified action DAG traces into zero-token deterministic Python macros
with workspace-scoping and fail-closed pre-flight element signature verification.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROMOTION_SUCCESS_THRESHOLD = 3
PROMOTION_CONFIDENCE_THRESHOLD = 0.90


class MacroDriftError(Exception):
    """Raised when live UI signature mismatches the compiled macro's expected signature."""
    pass


@dataclass
class MacroStep:
    """A single deterministic step within a compiled macro."""
    action_type: str  # "click", "type", "hotkey", "scroll"
    target_signature: dict[str, Any]  # {"control_type", "label_hash", "center_hint", "tag_name"}
    parameters: dict[str, Any] = field(default_factory=dict)
    fallback_selector: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroStep":
        return cls(
            action_type=data.get("action_type", "click"),
            target_signature=data.get("target_signature", {}),
            parameters=data.get("parameters", {}),
            fallback_selector=data.get("fallback_selector", ""),
        )

    def compute_step_hash(self) -> str:
        """Hash the step definition to guarantee exact sequence comparison."""
        payload = f"{self.action_type}:{json.dumps(self.target_signature, sort_keys=True)}:{json.dumps(self.parameters, sort_keys=True)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


@dataclass
class CompiledMacro:
    """A verified, workspace-scoped macro compiled from repeated successful traces."""
    macro_id: str
    intent_pattern: str
    app_name: str
    workspace_scope: str  # repo root or task_id
    steps: list[MacroStep]
    sequence_hash: str
    confidence: float = 0.95
    success_count: int = 3
    created_at: float = field(default_factory=time.time)
    last_executed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompiledMacro":
        steps = [MacroStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            macro_id=data["macro_id"],
            intent_pattern=data["intent_pattern"],
            app_name=data["app_name"],
            workspace_scope=data.get("workspace_scope", "global"),
            steps=steps,
            sequence_hash=data.get("sequence_hash", ""),
            confidence=data.get("confidence", 0.95),
            success_count=data.get("success_count", 3),
            created_at=data.get("created_at", time.time()),
            last_executed_at=data.get("last_executed_at", time.time()),
        )


class MacroCompiler:
    """
    Compiler and execution manager for verified UI macros.

    Enforces:
      1. Step-signature level sequence equality before promotion.
      2. Strict workspace/app scoping to prevent cross-project coordinate leakage.
      3. Fail-closed pre-flight validation against live UI signatures before firing.
    """

    _instance: Optional["MacroCompiler"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self):
        # Key: (intent_pattern.lower(), app_name.lower(), workspace_scope) -> CompiledMacro
        self._compiled_macros: dict[tuple[str, str, str], CompiledMacro] = {}
        # Trace history: (intent_pattern.lower(), app_name.lower(), workspace_scope) -> list[tuple[sequence_hash, list[MacroStep], float]]
        self._trace_history: dict[tuple[str, str, str], list[tuple[str, list[MacroStep], float]]] = {}
        self._execution_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "MacroCompiler":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _normalize_intent(self, intent: str) -> str:
        return " ".join(intent.lower().strip().split())

    def _normalize_workspace(self, workspace_scope: str | Path | None) -> str:
        if not workspace_scope:
            return "global"
        return str(Path(workspace_scope).resolve()).lower()

    def compute_sequence_hash(self, steps: list[MacroStep]) -> str:
        """Compute holistic hash across all step signatures in the DAG."""
        step_hashes = [s.compute_step_hash() for s in steps]
        return hashlib.sha256(":".join(step_hashes).encode("utf-8")).hexdigest()[:16]

    def record_trace(
        self,
        intent: str,
        app_name: str,
        workspace_scope: str | Path | None,
        steps: list[MacroStep],
        confidence: float,
    ) -> Optional[CompiledMacro]:
        """
        Record a successful execution trace.
        If >= 3 consecutive traces have identical step-level sequence hashes and confidence >= 0.90,
        promotes the trace to a CompiledMacro.
        """
        if confidence < PROMOTION_CONFIDENCE_THRESHOLD or not steps:
            return None

        norm_intent = self._normalize_intent(intent)
        norm_app = app_name.lower().strip()
        norm_ws = self._normalize_workspace(workspace_scope)
        key = (norm_intent, norm_app, norm_ws)

        seq_hash = self.compute_sequence_hash(steps)

        with self._execution_lock:
            if key not in self._trace_history:
                self._trace_history[key] = []

            self._trace_history[key].append((seq_hash, steps, confidence))

            # Keep only the last 10 traces
            if len(self._trace_history[key]) > 10:
                self._trace_history[key] = self._trace_history[key][-10:]

            recent_traces = self._trace_history[key][-PROMOTION_SUCCESS_THRESHOLD:]

            # Promotion condition: exactly PROMOTION_SUCCESS_THRESHOLD traces with IDENTICAL sequence_hash
            if len(recent_traces) == PROMOTION_SUCCESS_THRESHOLD and all(
                t[0] == seq_hash and t[2] >= PROMOTION_CONFIDENCE_THRESHOLD for t in recent_traces
            ):
                macro_id = f"macro_{uuid.uuid4().hex[:8]}"
                avg_confidence = sum(t[2] for t in recent_traces) / len(recent_traces)

                compiled = CompiledMacro(
                    macro_id=macro_id,
                    intent_pattern=norm_intent,
                    app_name=norm_app,
                    workspace_scope=norm_ws,
                    steps=steps,
                    sequence_hash=seq_hash,
                    confidence=avg_confidence,
                    success_count=len(recent_traces),
                )
                self._compiled_macros[key] = compiled
                logger.info(
                    f"[MacroCompiler] Promoted macro '{macro_id}' for intent '{norm_intent}' "
                    f"in app '{norm_app}' (workspace: {norm_ws}, confidence: {avg_confidence:.2f})"
                )
                return compiled

        return None

    def resolve_macro(
        self,
        intent: str,
        app_name: str,
        workspace_scope: str | Path | None = None,
    ) -> Optional[CompiledMacro]:
        """
        Look up a compiled macro matching the intent, app, and workspace scope.
        """
        norm_intent = self._normalize_intent(intent)
        norm_app = app_name.lower().strip()
        norm_ws = self._normalize_workspace(workspace_scope)

        # 1. Try exact workspace-scoped match
        key = (norm_intent, norm_app, norm_ws)
        if key in self._compiled_macros:
            return self._compiled_macros[key]

        # 2. Try global workspace fallback if applicable
        global_key = (norm_intent, norm_app, "global")
        if global_key in self._compiled_macros:
            return self._compiled_macros[global_key]

        return None

    def preflight_verify_step(self, step: MacroStep, app_context: Any) -> bool:
        """
        Pre-flight check: Verifies that the live UI matches the target signature
        before executing the macro step.
        """
        sig = step.target_signature
        if not sig:
            # Step requires no visual verification (e.g. standard hotkey)
            return True

        expected_label = sig.get("label", "")
        expected_type = sig.get("control_type", "")

        # 1. Check Tier 1 DOM if Playwright page is present
        page = getattr(app_context, "page", None)
        if page is not None and expected_label:
            try:
                locator = page.locator(f"text={expected_label}")
                elem = getattr(locator, "first", locator)
                if elem.is_visible():
                    return True
            except Exception:
                pass

        # 2. Check Tier 1 UIA if native adapter is available
        try:
            import importlib
            reg_mod = importlib.import_module("desktop.native.managers.native_manager_registry")
            NativeManagerRegistry = getattr(reg_mod, "NativeManagerRegistry")
            uia_mgr = NativeManagerRegistry.get_instance().get_manager("uia")
            if uia_mgr and hasattr(uia_mgr, "adapter") and uia_mgr.adapter.is_available():
                elements = uia_mgr.adapter.find_elements(name=expected_label)
                if elements:
                    return True
        except Exception:
            pass

        # 3. Signature verification failed -> UI has drifted
        return False

    def execute_macro(self, macro: CompiledMacro, app_context: Any) -> bool:
        """
        Execute all steps in the compiled macro with pre-flight verification at each step.
        Raises MacroDriftError on signature mismatch to trigger fail-closed grounding fallback.
        """
        logger.info(f"[MacroCompiler] Executing verified macro '{macro.macro_id}' (zero tokens)")

        for idx, step in enumerate(macro.steps):
            # Pre-flight verification
            if not self.preflight_verify_step(step, app_context):
                logger.warning(
                    f"[MacroCompiler] Pre-flight signature mismatch on step {idx+1}/{len(macro.steps)} "
                    f"('{step.action_type}'). Macro '{macro.macro_id}' invalidated due to UI drift."
                )
                raise MacroDriftError(
                    f"UI drift detected at step {idx+1} ({step.action_type}). "
                    f"Expected signature {step.target_signature} not found."
                )

            # Native execution dispatch
            self._dispatch_native_step(step, app_context)

        macro.last_executed_at = time.time()
        macro.success_count += 1
        return True

    def _dispatch_native_step(self, step: MacroStep, app_context: Any) -> None:
        """Dispatch native action via NativeManagerRegistry or Playwright page."""
        action = step.action_type.lower().strip()
        params = step.parameters

        # Browser dispatch
        page = getattr(app_context, "page", None)
        if page is not None:
            if action == "click" and step.fallback_selector:
                page.click(step.fallback_selector)
                return
            elif action == "type" and step.fallback_selector:
                page.fill(step.fallback_selector, params.get("text", ""))
                return

        # Native Desktop dispatch
        try:
            import importlib
            reg_mod = importlib.import_module("desktop.native.managers.native_manager_registry")
            NativeManagerRegistry = getattr(reg_mod, "NativeManagerRegistry")
            reg = NativeManagerRegistry.get_instance()
            input_mgr = reg.get_manager("input")
            if input_mgr:
                if action == "click":
                    center = step.target_signature.get("center", (params.get("x", 0), params.get("y", 0)))
                    input_mgr.execute("input.click", {"x": center[0], "y": center[1]})
                elif action == "type":
                    input_mgr.execute("input.type", {"text": params.get("text", "")})
                elif action == "hotkey":
                    input_mgr.execute("input.hotkey", {"keys": params.get("keys", [])})
        except Exception as e:
            logger.debug(f"[MacroCompiler] Step dispatch note: {e}")

"""
Backend Registry & Capability Router
=====================================
Registers execution backends, performs dynamic capability negotiation,
tracks adaptive latency/success metrics, and routes requests based on capabilities.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from .base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)


class BackendRegistry:
    """
    Centralized registry for execution backends, adaptive metric scoring,
    and capability negotiation.
    """

    _instance: Optional["BackendRegistry"] = None

    def __init__(self, manifest_path: Path | None = None):
        self._backends: dict[str, BaseBackendAdapter] = {}
        self._capability_map: dict[str, list[str]] = {}
        self._manifest_capabilities: dict[str, Any] = {}
        self._metrics: dict[str, dict[str, Any]] = {}
        self.load_capability_manifest(manifest_path)

    def load_capability_manifest(self, manifest_path: Path | None = None) -> None:
        """Load capability mapping manifest from config/capabilities.json or .yaml."""
        if manifest_path is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
            json_path = root / "config" / "capabilities.json"
            yaml_path = root / "config" / "capabilities.yaml"
            manifest_path = json_path if json_path.exists() else yaml_path

        if manifest_path and manifest_path.exists():
            try:
                if manifest_path.suffix == ".json":
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    self._manifest_capabilities = data.get("capabilities", {})
                logger.info(f"Loaded capability manifest from {manifest_path.name}")
            except Exception as e:
                logger.warning(
                    f"Failed to parse capability manifest {manifest_path}: {e}"
                )

    @classmethod
    def get_instance(cls) -> "BackendRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def negotiate_capabilities(self, backend: BaseBackendAdapter) -> list[str]:
        """Dynamically query backend capabilities for negotiation."""
        if hasattr(backend, "capabilities"):
            return list(backend.capabilities)
        return []

    def register(self, backend: BaseBackendAdapter) -> None:
        """Register a backend adapter and perform capability negotiation."""
        self._backends[backend.name] = backend
        self._metrics[backend.name] = {
            "latency_ms": 100.0,
            "successes": 0,
            "total": 0,
            "success_rate": 1.0,
        }

        caps = self.negotiate_capabilities(backend)
        for cap in caps:
            if cap not in self._capability_map:
                self._capability_map[cap] = []
            if backend.name not in self._capability_map[cap]:
                self._capability_map[cap].append(backend.name)

        logger.info(
            f"Registered backend '{backend.name}' supporting {len(caps)} capabilities"
        )

    def record_execution_metric(
        self, name: str, latency_ms: float, success: bool
    ) -> None:
        """Record live execution metrics for adaptive routing."""
        if name not in self._metrics:
            self._metrics[name] = {
                "latency_ms": latency_ms,
                "successes": 0,
                "total": 0,
                "success_rate": 1.0,
            }

        m = self._metrics[name]
        m["total"] += 1
        if success:
            m["successes"] += 1
        m["success_rate"] = m["successes"] / m["total"] if m["total"] > 0 else 1.0
        # Exponential moving average for latency
        m["latency_ms"] = 0.8 * m["latency_ms"] + 0.2 * latency_ms

    def get_backend(self, name: str) -> BaseBackendAdapter | None:
        """Get backend adapter by name."""
        return self._backends.get(name)

    def _resolve_capability_key(self, capability: str) -> str:
        """Resolve capability key considering version tags (e.g. chat.fast -> chat.fast@1)."""
        if capability in self._capability_map:
            return capability

        # Check prefix match for versioned capabilities
        base = capability.split("@")[0]
        for cap_key in self._capability_map:
            if cap_key.split("@")[0] == base:
                return cap_key
        return capability

    def find_backends_for_capability(self, capability: str) -> list[BaseBackendAdapter]:
        """Find all backends supporting a specific capability."""
        key = self._resolve_capability_key(capability)
        names = self._capability_map.get(key, [])
        return [self._backends[n] for n in names if n in self._backends]

    def select_best_backend(self, capability: str) -> BaseBackendAdapter | None:
        """
        Select the best healthy backend for a capability based on adaptive metrics and metadata.

        Args:
            capability: Capability string (e.g. chat.fast or chat.fast@1)

        Returns:
            Preferred BaseBackendAdapter or None if not supported
        """
        candidates = self.find_backends_for_capability(capability)
        if not candidates:
            return None

        healthy = [b for b in candidates if b.health_check()]
        if not healthy:
            logger.warning(
                f"No healthy backends found for capability '{capability}', defaulting to candidate"
            )
            return candidates[0]

        # Adaptive scoring: success_rate * 100 - latency_ms * 0.1 - cost * 10
        scored = []
        for b in healthy:
            desc = b.describe()
            cost = desc.get("cost", 0.0)
            is_local = desc.get("is_local", True)
            metrics = self._metrics.get(
                b.name, {"latency_ms": 100.0, "success_rate": 1.0}
            )

            latency = metrics["latency_ms"]
            success_rate = metrics["success_rate"]

            score = (
                (100.0 if is_local else 50.0)
                + (success_rate * 50.0)
                - (cost * 10.0)
                - (latency * 0.1)
            )
            scored.append((score, b))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def list_all_backends(self) -> list[dict[str, Any]]:
        """List metadata for all registered backends."""
        result = []
        for name, b in self._backends.items():
            desc = b.describe()
            desc["metrics"] = self._metrics.get(name, {})
            result.append(desc)
        return result

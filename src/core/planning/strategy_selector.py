"""
Strategy Selector
Learns and prefers top-performing backend adapters per capability on the local machine.
"""


class StrategySelector:
    """
    Learns and selects optimal backend strategies per capability.
    """

    def __init__(self):
        # Maps capability -> list of (adapter_name, success_count, total_count, total_duration_ms)
        self._stats: dict[str, dict[str, dict[str, float]]] = {}

    def record_execution(
        self, capability: str, adapter_name: str, success: bool, duration_ms: float
    ) -> None:
        """Record adapter execution performance."""
        if capability not in self._stats:
            self._stats[capability] = {}

        if adapter_name not in self._stats[capability]:
            self._stats[capability][adapter_name] = {
                "successes": 0,
                "total": 0,
                "duration": 0.0,
            }

        st = self._stats[capability][adapter_name]
        st["total"] += 1
        if success:
            st["successes"] += 1
        st["duration"] += duration_ms

    def select_best_adapter(
        self, capability: str, available_adapters: list[str]
    ) -> str | None:
        """
        Select best adapter based on historical success rate and speed.

        Args:
            capability: Capability name
            available_adapters: Available adapter candidates

        Returns:
            Preferred adapter name or None if no data
        """
        if capability not in self._stats or not available_adapters:
            return available_adapters[0] if available_adapters else None

        cap_stats = self._stats[capability]
        best_adapter = None
        best_score = -1.0

        for adapter in available_adapters:
            if adapter in cap_stats:
                st = cap_stats[adapter]
                success_rate = (
                    (st["successes"] / st["total"]) if st["total"] > 0 else 0.0
                )
                avg_speed = (
                    (st["duration"] / st["total"]) if st["total"] > 0 else 1000.0
                )
                speed_score = max(0.0, 100.0 - (avg_speed / 10.0))
                score = (success_rate * 80.0) + (speed_score * 0.2)

                if score > best_score:
                    best_score = score
                    best_adapter = adapter

        return best_adapter or (available_adapters[0] if available_adapters else None)

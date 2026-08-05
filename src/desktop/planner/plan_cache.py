"""
Plan Cache
Caches and retrieves successful DesktopPlan templates for repeated goals.
"""

from .desktop_plan import DesktopPlan


class PlanCache:
    """
    In-memory cache for DesktopPlan instances.
    """

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: dict[str, DesktopPlan] = {}

    def get(self, goal_text: str) -> DesktopPlan | None:
        """Get cached plan for goal text."""
        return self._cache.get(goal_text.strip().lower())

    def put(self, goal_text: str, plan: DesktopPlan) -> None:
        """Cache a successful plan."""
        if len(self._cache) >= self.max_size:
            # Drop oldest entry
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[goal_text.strip().lower()] = plan

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()

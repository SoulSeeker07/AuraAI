"""
Capability Discovery
Search for capabilities based on goals instead of hardcoded names.

Planner → Capability Search → Best Capability
"""

from typing import List, Dict, Any, Optional
from enum import Enum

from .capability_registry import CapabilityRegistry, CapabilityDescriptor, PermissionRequired
from .native_manager import NativeManager
from .native_exceptions import CapabilityNotFoundError


class GoalIntent(Enum):
    """Intent of the user's goal"""
    OPEN_APPLICATION = "open_application"
    CLOSE_APPLICATION = "close_application"
    MINIMIZE_APPLICATION = "minimize_application"
    MAXIMIZE_APPLICATION = "maximize_application"
    RESTORE_APPLICATION = "restore_application"
    ACTIVATE_WINDOW = "activate_window"
    MOVE_WINDOW = "move_window"
    RESIZE_WINDOW = "resize_window"
    READ_CLIPBOARD = "read_clipboard"
    WRITE_CLIPBOARD = "write_clipboard"
    CLEAR_CLIPBOARD = "clear_clipboard"
    LIST_WINDOWS = "list_windows"
    LIST_APPS = "list_apps"
    LIST_DISPLAYS = "list_displays"
    SHUTDOWN = "shutdown"
    RESTART = "restart"
    SLEEP = "sleep"
    LOCK = "lock"
    LOGOFF = "logoff"
    SET_VOLUME = "set_volume"
    TOGGLE_MUTE = "toggle_mute"
    LIST_AUDIO_DEVICES = "list_audio_devices"
    LIST_NETWORK = "list_network_interfaces"
    READ_REGISTRY = "read_registry"
    WRITE_REGISTRY = "write_registry"
    LIST_SERVICES = "list_services"
    START_SERVICE = "start_service"
    STOP_SERVICE = "stop_service"
    RESTART_SERVICE = "restart_service"


class CapabilityMatchScore(Enum):
    """Score of capability match"""
    NO_MATCH = 0
    WEAK_MATCH = 1
    MODERATE_MATCH = 2
    STRONG_MATCH = 3
    EXACT_MATCH = 4


class CapabilityDiscovery:
    """
    Capability discovery system.

    Maps user goals to capabilities without hardcoding names.
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None):
        """
        Initialize discovery system.

        Args:
            registry: CapabilityRegistry instance (defaults to singleton)
        """
        self.registry = registry or get_capability_registry()
        self.native_manager = NativeManager()

    # ==================== Goal Matching ====================

    def discover_capabilities_for_goal(self, goal: str) -> List[Dict[str, Any]]:
        """
        Discover capabilities for a given goal.

        Args:
            goal: User's goal in natural language

        Returns:
            List of matching capabilities with scores and reasons
        """
        if not goal or not goal.strip():
            return []

        goal_lower = goal.lower()
        matches = []

        # Try exact intent matching first
        for intent in GoalIntent:
            if intent.value in goal_lower:
                capabilities = self._get_capabilities_for_intent(intent)
                for cap in capabilities:
                    score = self._calculate_score(goal, cap, intent)
                    if score > CapabilityMatchScore.WEAK_MATCH:
                        matches.append({
                            "capability": cap,
                            "intent": intent,
                            "score": score,
                            "reason": self._get_match_reason(goal, intent)
                        })

        # If no matches from intents, do semantic matching
        if not matches:
            matches = self._semantic_match(goal)

        # Sort by score
        matches.sort(key=lambda x: x["score"], reverse=True)

        return matches

    def _get_capabilities_for_intent(self, intent: GoalIntent) -> List[str]:
        """
        Get capabilities for a specific intent.

        Args:
            intent: Goal intent

        Returns:
            List of capability names
        """
        # Map intents to capabilities
        intent_to_capability: Dict[GoalIntent, List[str]] = {
            GoalIntent.OPEN_APPLICATION: ["launch_application"],
            GoalIntent.CLOSE_APPLICATION: ["close_window"],
            GoalIntent.MINIMIZE_APPLICATION: ["minimize_window"],
            GoalIntent.MAXIMIZE_APPLICATION: ["maximize_window"],
            GoalIntent.RESTORE_APPLICATION: ["restore_window"],
            GoalIntent.ACTIVATE_WINDOW: ["activate_window", "set_foreground_window"],
            GoalIntent.MOVE_WINDOW: ["move_window"],
            GoalIntent.RESIZE_WINDOW: ["resize_window"],
            GoalIntent.READ_CLIPBOARD: ["read_clipboard"],
            GoalIntent.WRITE_CLIPBOARD: ["write_clipboard"],
            GoalIntent.CLEAR_CLIPBOARD: ["clear_clipboard"],
            GoalIntent.LIST_WINDOWS: ["list_windows"],
            GoalIntent.LIST_APPS: ["list_windows"],
            GoalIntent.LIST_DISPLAYS: ["list_displays"],
            GoalIntent.SHUTDOWN: ["shutdown"],
            GoalIntent.RESTART: ["restart"],
            GoalIntent.SLEEP: ["sleep"],
            GoalIntent.LOCK: ["lock"],
            GoalIntent.LOGOFF: ["logoff"],
            GoalIntent.SET_VOLUME: ["set_volume"],
            GoalIntent.TOGGLE_MUTE: ["toggle_mute"],
            GoalIntent.LIST_AUDIO_DEVICES: ["list_audio_devices"],
            GoalIntent.LIST_NETWORK: ["list_network_interfaces"],
            GoalIntent.READ_REGISTRY: ["read_registry_key"],
            GoalIntent.WRITE_REGISTRY: ["write_registry_key"],
            GoalIntent.LIST_SERVICES: ["list_services"],
            GoalIntent.START_SERVICE: ["start_service"],
            GoalIntent.STOP_SERVICE: ["stop_service"],
            GoalIntent.RESTART_SERVICE: ["restart_service"],
        }

        return intent_to_capability.get(intent, [])

    def _calculate_score(
        self,
        goal: str,
        capability: str,
        intent: GoalIntent
    ) -> CapabilityMatchScore:
        """
        Calculate match score between goal and capability.

        Args:
            goal: User's goal
            capability: Capability name
            intent: Goal intent

        Returns:
            Match score
        """
        score = CapabilityMatchScore.NO_MATCH

        # Check if capability name appears in goal
        if capability.lower() in goal.lower():
            score = CapabilityMatchScore.STRONG_MATCH

        # Check if intent matches well
        if intent.value in goal.lower():
            score = max(score, CapabilityMatchScore.EXACT_MATCH)

        # Check if manager name appears
        capability_name_lower = capability.lower()
        manager_name = capability_name_lower.split("_")[0]
        if manager_name in goal.lower():
            score = max(score, CapabilityMatchScore.MODERATE_MATCH)

        # Check for specific keywords
        keywords = self._get_keywords_for_capability(capability)
        for keyword in keywords:
            if keyword in goal.lower():
                score = max(score, CapabilityMatchScore.MODERATE_MATCH)

        return score

    def _get_match_reason(self, goal: str, intent: GoalIntent) -> str:
        """
        Get explanation for why a capability matches the goal.

        Args:
            goal: User's goal
            intent: Goal intent

        Returns:
            Match reason
        """
        return f"Matches {intent.value} intent"

    def _get_keywords_for_capability(self, capability: str) -> List[str]:
        """
        Get keywords for a capability.

        Args:
            capability: Capability name

        Returns:
            List of keywords
        """
        keywords: Dict[str, List[str]] = {
            "list_windows": ["list", "show", "display", "open", "running"],
            "list_displays": ["list", "screen", "monitor", "display"],
            "list_audio_devices": ["list", "audio", "sound", "speaker", "microphone"],
            "list_network_interfaces": ["list", "network", "interface", "wifi", "ethernet"],
            "read_clipboard": ["clipboard", "copy", "paste"],
            "write_clipboard": ["clipboard", "copy", "paste"],
            "set_volume": ["volume", "loud", "quiet", "mute", "sound"],
            "shutdown": ["shutdown", "turn off", "power off", "exit"],
            "restart": ["restart", "reboot", "refresh", "reset"],
            "sleep": ["sleep", "hibernate", "standby", "pause"],
            "lock": ["lock", "screen", "secure"],
            "logoff": ["logoff", "switch user", "logout", "exit"],
            "activate_window": ["activate", "focus", "bring to front", "select", "open"],
            "move_window": ["move", "position", "location", "drag"],
            "resize_window": ["resize", "size", "dimensions", "maximize", "minimize"],
            "close_window": ["close", "exit", "quit", "end", "stop"],
        }

        return keywords.get(capability.lower(), [])

    def _semantic_match(self, goal: str) -> List[Dict[str, Any]]:
        """
        Perform semantic matching based on capability categories.

        Args:
            goal: User's goal

        Returns:
            List of matching capabilities with scores
        """
        matches = []
        goal_lower = goal.lower()

        # Analyze goal for keywords
        found_categories = self._analyze_goal_categories(goal_lower)

        # Match capabilities by category
        for category, capabilities in self.registry.list_by_category().items():
            category_score = self._calculate_category_score(goal_lower, category)

            if category_score > CapabilityMatchScore.WEAK_MATCH:
                for cap in capabilities:
                    # Get metadata
                    descriptor = self.registry.get(cap.name)
                    if descriptor:
                        score = category_score
                        if score >= CapabilityMatchScore.STRONG_MATCH:
                            score = CapabilityMatchScore.EXACT_MATCH

                        matches.append({
                            "capability": cap.name,
                            "intent": None,
                            "score": score,
                            "reason": f"Related to {category}"
                        })

        return matches

    def _analyze_goal_categories(self, goal: str) -> List[str]:
        """
        Analyze goal and return relevant categories.

        Args:
            goal: User's goal (lowercase)

        Returns:
            List of relevant category names
        """
        categories: List[str] = []

        # Window-related keywords
        if any(kw in goal for kw in ["window", "app", "program", "browser", "chrome", "edge"]):
            categories.append("window")

        # Display-related keywords
        if any(kw in goal for kw in ["display", "screen", "monitor", "resolution", "fullscreen"]):
            categories.append("display")

        # Clipboard-related keywords
        if any(kw in goal for kw in ["clipboard", "copy", "paste"]):
            categories.append("clipboard")

        # Audio-related keywords
        if any(kw in goal for kw in ["audio", "sound", "volume", "mute", "speaker", "microphone"]):
            categories.append("audio")

        # Network-related keywords
        if any(kw in goal for kw in ["network", "internet", "wifi", "ethernet", "connection"]):
            categories.append("network")

        # Power-related keywords
        if any(kw in goal for kw in ["power", "shutdown", "restart", "sleep", "lock", "logoff"]):
            categories.append("power")

        # Registry-related keywords
        if any(kw in goal for kw in ["registry", "system", "config", "setting"]):
            categories.append("registry")

        # Service-related keywords
        if any(kw in goal for kw in ["service", "server", "background", "daemon", "process"]):
            categories.append("service")

        return categories

    def _calculate_category_score(self, goal: str, category: str) -> CapabilityMatchScore:
        """
        Calculate score based on category relevance.

        Args:
            goal: User's goal
            category: Category name

        Returns:
            Match score
        """
        score = CapabilityMatchScore.NO_MATCH

        # Window category
        if category == "window" and any(kw in goal for kw in ["window", "app", "browser", "chrome", "edge"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        # Display category
        if category == "display" and any(kw in goal for kw in ["display", "screen", "monitor", "resolution"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        # Clipboard category
        if category == "clipboard" and any(kw in goal for kw in ["clipboard", "copy", "paste"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        # Audio category
        if category == "audio" and any(kw in goal for kw in ["audio", "sound", "volume", "mute"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        # Network category
        if category == "network" and any(kw in goal for kw in ["network", "internet", "wifi", "ethernet"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        # Power category
        if category == "power" and any(kw in goal for kw in ["power", "shutdown", "restart", "sleep", "lock", "logoff"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        # Registry category
        if category == "registry" and any(kw in goal for kw in ["registry", "system", "config", "setting"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        # Service category
        if category == "service" and any(kw in goal for kw in ["service", "server", "background", "daemon"]):
            score = CapabilityMatchScore.MODERATE_MATCH

        return score

    # ==================== Capability Selection ====================

    def select_best_capability(self, goal: str) -> Optional[Dict[str, Any]]:
        """
        Select the best capability for a given goal.

        Args:
            goal: User's goal in natural language

        Returns:
            Best capability with metadata or None
        """
        matches = self.discover_capabilities_for_goal(goal)

        if not matches:
            return None

        # Return best match
        best_match = matches[0]
        return {
            "capability": best_match["capability"],
            "metadata": self.registry.get(best_match["capability"]),
            "reason": best_match["reason"],
            "score": best_match["score"]
        }

    def list_capable_capabilities(self, goal: str) -> List[Dict[str, Any]]:
        """
        List all capabilities that could potentially fulfill the goal.

        Args:
            goal: User's goal in natural language

        Returns:
            List of capabilities with match scores
        """
        matches = self.discover_capabilities_for_goal(goal)
        return matches

    def verify_capability_available(self, capability: str) -> bool:
        """
        Verify that a capability is available and can be executed.

        Args:
            capability: Capability name

        Returns:
            True if capability is available
        """
        return self.registry.get(capability) is not None


# Singleton instance
_discovery: Optional[CapabilityDiscovery] = None


def get_capability_discovery(registry: Optional[CapabilityRegistry] = None) -> CapabilityDiscovery:
    """
    Get or create the global capability discovery singleton.

    Args:
        registry: Optional CapabilityRegistry instance

    Returns:
        CapabilityDiscovery instance
    """
    global _discovery
    if _discovery is None:
        _discovery = CapabilityDiscovery(registry)
    return _discovery


def reset_capability_discovery() -> None:
    """Reset the global capability discovery"""
    global _discovery
    _discovery = None


def get_capability_registry() -> CapabilityRegistry:
    """Get CapabilityRegistry singleton (for internal use)"""
    from .capability_registry import CapabilityRegistry
    return CapabilityRegistry()

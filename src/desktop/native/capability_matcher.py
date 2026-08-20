"""
Capability Discovery Matcher Subsystem
Tokenized N-Gram Capability Matching with Two-Tier Precedence and Deterministic Tie-Breaking.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Sequence

logger = logging.getLogger(__name__)


def tokenize(text: str) -> list[str]:
    """Tokenize a string into lowercase alphanumeric words."""
    if not text:
        return []
    # Replace non-alphanumeric characters and underscores with space
    cleaned = re.sub(r"[^\w\s]|_", " ", text.lower())
    return [token for token in cleaned.split() if token]


@dataclass
class MatchCandidate:
    """Represents an evaluated candidate capability match."""

    capability: str
    token_count: int
    keyword_len: int
    keyword_coverage: float
    namespace_in_goal: bool
    is_curated: bool


class CapabilityDiscoveryMatcher:
    """
    High-precision tokenized capability discovery matcher.

    Replaces fragile substring containment with token n-gram matching,
    word boundary enforcement, two-tier source hierarchy (Curated > Dynamic Registry),
    and 4-level deterministic tie-breaking.
    """

    DEFAULT_CURATED_KEYWORDS: dict[str, list[str]] = {
        "uia.click": [
            "click button",
            "press button",
            "tap button",
            "invoke button",
            "click on",
            "click the",
            "click",
        ],
        "uia.type_text": [
            "type text into",
            "type into",
            "write into",
            "fill text",
            "enter text into",
            "input text",
            "type in",
        ],
        "uia.toggle": [
            "toggle checkbox",
            "toggle switch",
            "check box",
            "uncheck",
            "toggle",
        ],
        "uia.get_tree": [
            "inspect tree",
            "inspect ui tree",
            "ui tree",
            "element tree",
            "dump tree",
            "dump ui",
        ],
        "uia.find_element": [
            "find element",
            "locate element",
            "search element",
            "find button",
            "locate button",
        ],
        "uia.get_value": [
            "get value of",
            "read value",
            "read text from",
            "get value",
            "get text",
        ],
        "uia.select_item": [
            "select option",
            "select item",
            "choose option",
            "choose item",
        ],
        "activate_window": [
            "activate window",
            "bring window to foreground",
            "foreground window",
            "focus window",
            "bring to front",
            "switch to",
            "activate",
            "focus",
        ],
        "close_window": [
            "close window",
            "kill window",
            "terminate window",
            "dismiss window",
            "close",
            "exit",
            "quit",
            "end",
        ],
        "list_windows": [
            "show all open windows",
            "list windows",
            "open windows",
            "show windows",
            "what windows",
            "running apps",
            "get windows",
            "all windows",
        ],
        "minimize_window": [
            "minimize window",
            "hide window",
            "minimize",
        ],
        "maximize_window": [
            "maximize window",
            "fullscreen window",
            "full screen",
            "maximize",
            "fullscreen",
        ],
        "restore_window": [
            "restore active window",
            "restore window",
            "unminimize window",
            "unminimize",
            "restore",
        ],
        "move_window": ["move window", "reposition window"],
        "resize_window": ["resize window", "change window size"],
        "clipboard.read_text": [
            "read text from clipboard",
            "read clipboard text",
            "get clipboard text",
            "paste from clipboard",
            "read clipboard",
            "view clipboard",
        ],
        "clipboard.write_text": [
            "write text to clipboard",
            "copy text to clipboard",
            "set clipboard text",
            "write clipboard",
            "copy to clipboard",
        ],
        "clipboard.clear": ["clear clipboard", "empty clipboard"],
        "clipboard.read_image": ["read clipboard image", "get clipboard image"],
        "clipboard.write_image": [
            "write clipboard image",
            "copy image to clipboard",
        ],
        "clipboard.read_files": ["read clipboard files", "get copied files"],
        "clipboard.write_files": [
            "write clipboard files",
            "copy files to clipboard",
        ],
        "clipboard.read_html": ["read clipboard html", "get clipboard html"],
        "clipboard.write_html": ["write clipboard html", "copy html to clipboard"],
        "clipboard.get_formats": [
            "clipboard formats",
            "what is in clipboard",
            "list clipboard formats",
        ],
        "clipboard.has_text": ["clipboard has text", "does clipboard have text"],
        "clipboard.has_image": ["clipboard has image", "does clipboard have image"],
        "clipboard.has_files": ["clipboard has files", "does clipboard have files"],
        "list_displays": [
            "list displays",
            "show displays",
            "monitors",
            "connected monitors",
        ],
        "get_primary_display": ["primary display", "main monitor", "main display"],
        "get_volume": [
            "get volume",
            "read volume",
            "master volume",
            "current volume",
            "check volume",
        ],
        "set_volume": [
            "set volume",
            "change volume",
            "turn up",
            "turn down",
            "adjust volume",
            "lower volume",
            "increase volume",
        ],
        "toggle_mute": ["toggle mute", "mute system sound", "mute", "unmute"],
        "is_muted": ["is muted", "are speakers muted", "check if muted", "muted"],
        "list_microphones": [
            "microphones",
            "list microphones",
            "connected microphones",
        ],
        "list_audio_devices": ["list audio", "audio devices", "sound devices"],
        "list_network_interfaces": [
            "list network",
            "network interfaces",
            "show network adapters",
        ],
        "network.interfaces": ["get network interfaces", "all network adapters"],
        "network.default_interface": [
            "default interface",
            "active adapter",
            "main network",
        ],
        "network.public_ip": [
            "public ip",
            "external ip",
            "my public ip",
            "what is my ip",
            "public ip address",
        ],
        "network.local_ip": [
            "local ip",
            "internal ip",
            "ip address",
            "my ip",
            "internal ip address",
        ],
        "network.gateway": ["default gateway", "gateway address", "router ip"],
        "network.dns": ["dns servers", "dns configuration", "what is my dns"],
        "network.mac": ["mac address", "physical address", "hardware address"],
        "network.hostname": ["hostname", "computer name"],
        "network.connection_type": ["connection type", "am i on wifi"],
        "network.wifi_name": ["wifi name", "ssid", "connected wifi"],
        "network.signal_strength": ["signal strength", "wifi strength"],
        "network.ping": ["ping", "ping google", "ping host"],
        "network.traceroute": ["traceroute", "tracert", "trace route"],
        "network.lookup": ["dns lookup", "nslookup", "domain lookup"],
        "network.port_check": ["port check", "check port", "is port open"],
        "network.internet": [
            "internet connection",
            "check internet",
            "is internet working",
            "internet is slow",
        ],
        "network.speed": ["speed test", "test speed", "internet speed"],
        "network.latency": ["measure latency", "check latency", "ping latency"],
        "network.packet_loss": ["packet loss", "check loss"],
        "network.enable_adapter": ["enable adapter", "enable wifi"],
        "network.disable_adapter": ["disable adapter", "disable wifi"],
        "network.release_ip": ["release ip", "release dhcp"],
        "network.renew_ip": ["renew ip", "renew dhcp"],
        "network.flush_dns": ["flush dns", "clear dns cache"],
        "network.disconnect_wifi": ["disconnect wifi", "disconnect wireless"],
        "network.connect_wifi": ["connect wifi", "connect to wifi"],
        "power.battery": [
            "battery",
            "battery level",
            "battery status",
            "get battery",
            "charge level",
        ],
        "power.ac_status": [
            "ac status",
            "ac power",
            "plugged in",
            "charger status",
        ],
        "power.power_plan": ["power plan", "power scheme", "active power plan"],
        "shutdown": ["shutdown", "turn off", "power off"],
        "restart": ["restart", "reboot"],
        "sleep": ["sleep", "hibernate", "standby"],
        "lock": ["lock screen", "lock computer", "lock"],
        "list_services": ["list services", "show services", "windows services"],
        "start_service": ["start service"],
        "stop_service": ["stop service", "kill service"],
    }

    def __init__(
        self,
        curated_keywords: dict[str, list[str]] | None = None,
        registry: Any | None = None,
    ):
        """
        Initialize matcher with curated keywords and optional CapabilityRegistry.
        """
        self.curated_dict = (
            curated_keywords
            if curated_keywords is not None
            else self.DEFAULT_CURATED_KEYWORDS
        )
        self.registry = registry

        # Pre-tokenize curated patterns
        self._curated_patterns: list[tuple[str, list[str], str]] = []
        for cap, phrases in self.curated_dict.items():
            namespace = cap.split(".")[0] if "." in cap else cap.split("_")[0]
            for phrase in phrases:
                tokens = tokenize(phrase)
                if tokens:
                    self._curated_patterns.append((cap, tokens, namespace))

    def match(self, goal: str) -> str | None:
        """
        Discover the single best matching capability for an atomic goal phrase.

        Evaluates Tier 1 (Curated Dictionary) first; only falls back to Tier 2
        (Registry Descriptors) if zero curated matches occur.
        """
        if not goal or not isinstance(goal, str):
            return None

        goal_tokens = tokenize(goal)
        if not goal_tokens:
            return None

        # ── TIER 1: Curated Keyword Dictionary ──
        tier1_candidates = self._evaluate_patterns(
            goal_tokens, self._curated_patterns, is_curated=True
        )
        if tier1_candidates:
            winner = self._resolve_winner(tier1_candidates, goal)
            return winner.capability

        # ── TIER 2: Dynamic Capability Registry Fallback ──
        if self.registry:
            registry_patterns = self._build_registry_patterns()
            tier2_candidates = self._evaluate_patterns(
                goal_tokens, registry_patterns, is_curated=False
            )
            if tier2_candidates:
                winner = self._resolve_winner(tier2_candidates, goal)
                return winner.capability

        return None

    def _evaluate_patterns(
        self,
        goal_tokens: list[str],
        patterns: Sequence[tuple[str, list[str], str]],
        is_curated: bool,
    ) -> list[MatchCandidate]:
        """
        Match goal tokens against registered patterns using exact token sequence containment.
        """
        candidates: list[MatchCandidate] = []
        goal_len = len(goal_tokens)
        goal_set = set(goal_tokens)

        for cap, pat_tokens, namespace in patterns:
            pat_len = len(pat_tokens)
            if pat_len == 0 or pat_len > goal_len:
                continue

            # Check for contiguous token sequence match
            matched = False
            for i in range(goal_len - pat_len + 1):
                if goal_tokens[i : i + pat_len] == pat_tokens:
                    matched = True
                    break

            if matched:
                coverage = 1.0  # Entire keyword pattern was matched
                ns_in_goal = namespace in goal_set or cap in goal_set
                candidates.append(
                    MatchCandidate(
                        capability=cap,
                        token_count=pat_len,
                        keyword_len=pat_len,
                        keyword_coverage=coverage,
                        namespace_in_goal=ns_in_goal,
                        is_curated=is_curated,
                    )
                )

        return candidates

    def _build_registry_patterns(self) -> list[tuple[str, list[str], str]]:
        """Build tokenized patterns from dynamic CapabilityRegistry descriptors."""
        patterns: list[tuple[str, list[str], str]] = []
        if not self.registry:
            return patterns

        descriptors = (
            self.registry.list_all()
            if hasattr(self.registry, "list_all")
            else []
        )
        for desc in descriptors:
            name = desc.name
            namespace = getattr(desc, "category", None) or (
                name.split(".")[0] if "." in name else name.split("_")[0]
            )

            # Descriptor name
            name_tokens = tokenize(name)
            if name_tokens:
                patterns.append((name, name_tokens, namespace))

            # Usage examples if present
            for example in getattr(desc, "usage_examples", []):
                ex_tokens = tokenize(example)
                if ex_tokens:
                    patterns.append((name, ex_tokens, namespace))

        return patterns

    def _resolve_winner(
        self, candidates: list[MatchCandidate], goal: str
    ) -> MatchCandidate:
        """
        Select the winning candidate using the 4-level deterministic rule chain:
        1. Max token sequence length (N-gram specificity)
        2. Keyword completeness / coverage
        3. Target token / namespace affinity in goal
        4. Deterministic alphabetical sorting + trace logging
        """
        # Sort key implements the 4-level rule hierarchy
        # 1. token_count (descending)
        # 2. keyword_coverage (descending)
        # 3. namespace_in_goal (descending: True > False)
        # 4. capability name (ascending alphabetical)
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                -c.token_count,
                -c.keyword_coverage,
                -int(c.namespace_in_goal),
                c.capability.lower().strip(),
            ),
        )

        winner = sorted_candidates[0]

        # If there were multiple candidates with identical top scores, log the tie-break
        if len(sorted_candidates) > 1:
            second = sorted_candidates[1]
            if (
                winner.token_count == second.token_count
                and winner.keyword_coverage == second.keyword_coverage
                and winner.namespace_in_goal == second.namespace_in_goal
                and winner.capability != second.capability
            ):
                logger.debug(
                    f"[CapabilityDiscoveryMatcher] Deterministic tie-break: '{winner.capability}' "
                    f"selected over '{second.capability}' for goal '{goal}' "
                    f"(matched token_len={winner.token_count})"
                )

        return winner

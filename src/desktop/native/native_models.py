"""
Native Windows Layer Models
Strongly typed dataclasses for Windows desktop operations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import win32con


class WindowStyle(Enum):
    """Window styles"""

    NORMAL = 0
    MINIMIZED = win32con.WS_MINIMIZE
    MAXIMIZED = win32con.WS_MAXIMIZE
    HIDDEN = 0  # No WS_VISIBLE flag (Windows has no WS_HIDDEN constant)


class WindowState(Enum):
    """Window states"""

    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    HIDDEN = "hidden"
    CLOSED = "closed"


@dataclass
class Rect:
    """Window rectangle coordinates"""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class WindowInfo:
    """Window information"""

    hwnd: int
    title: str
    process_id: int
    executable: str
    is_active: bool
    is_visible: bool
    is_minimized: bool
    is_maximized: bool
    rect: Rect
    style: WindowStyle
    class_name: str
    thread_id: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "process_id": self.process_id,
            "executable": self.executable,
            "is_active": self.is_active,
            "is_visible": self.is_visible,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized,
            "rect": {
                "left": self.rect.left,
                "top": self.rect.top,
                "right": self.rect.right,
                "bottom": self.rect.bottom,
            },
            "style": self.style.name,
            "class_name": self.class_name,
            "thread_id": self.thread_id,
        }


@dataclass
class ProcessInfo:
    """Process information"""

    process_id: int
    name: str
    executable_path: str
    command_line: str
    working_set_size: int
    cpu_time: float
    threads: list[int]
    parent_pid: int | None
    user: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "process_id": self.process_id,
            "name": self.name,
            "executable_path": self.executable_path,
            "command_line": self.command_line,
            "working_set_size": self.working_set_size,
            "cpu_time": self.cpu_time,
            "threads": self.threads,
            "parent_pid": self.parent_pid,
            "user": self.user,
        }


@dataclass
class ClipboardData:
    """Clipboard data"""

    text: str
    html: str | None
    image: Any | None
    files: list[str]
    format: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "text": self.text,
            "html": self.html,
            "image": self.image is not None,
            "files": self.files,
            "format": self.format,
        }


@dataclass
class DisplayInfo:
    """Display information"""

    index: int
    name: str
    width: int
    height: int
    bits_per_pixel: int
    primary: bool
    rect: Rect
    refresh_rate: int
    orientation: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "index": self.index,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "bits_per_pixel": self.bits_per_pixel,
            "primary": self.primary,
            "rect": {
                "left": self.rect.left,
                "top": self.rect.top,
                "right": self.rect.right,
                "bottom": self.rect.bottom,
            },
            "refresh_rate": self.refresh_rate,
            "orientation": self.orientation,
        }


@dataclass
class AudioDevice:
    """Audio device information"""

    index: int
    name: str
    type: str  # 'output' or 'input'
    volume: float  # 0.0 to 1.0
    muted: bool
    is_default: bool
    device_id: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "index": self.index,
            "name": self.name,
            "type": self.type,
            "volume": self.volume,
            "muted": self.muted,
            "is_default": self.is_default,
            "device_id": self.device_id,
        }


@dataclass
class NetworkInterface:
    """Network interface information"""

    name: str
    index: int
    description: str
    is_up: bool
    is_connected: bool
    ip_address: str | None
    subnet_mask: str | None
    gateway: str | None
    mac_address: str
    dns_servers: list[str]
    speed: int  # in Mbps

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "index": self.index,
            "description": self.description,
            "is_up": self.is_up,
            "is_connected": self.is_connected,
            "ip_address": self.ip_address,
            "subnet_mask": self.subnet_mask,
            "gateway": self.gateway,
            "mac_address": self.mac_address,
            "dns_servers": self.dns_servers,
            "speed": self.speed,
        }


@dataclass
class RegistryKey:
    """Registry key information"""

    key_path: str
    key_name: str
    value_type: str
    value: Any
    is_string: bool
    is_integer: bool
    is_binary: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "key_path": self.key_path,
            "key_name": self.key_name,
            "value_type": self.value_type,
            "value": self.value,
            "is_string": self.is_string,
            "is_integer": self.is_integer,
            "is_binary": self.is_binary,
        }


@dataclass
class ServiceInfo:
    """Service information"""

    service_name: str
    display_name: str
    status: str
    start_type: str
    description: str | None
    process_id: int | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "service_name": self.service_name,
            "display_name": self.display_name,
            "status": self.status,
            "start_type": self.start_type,
            "description": self.description,
            "process_id": self.process_id,
        }

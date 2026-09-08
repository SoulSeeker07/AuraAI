"""
Webcam Manager — Camera Device Listing, Photo Capture, and Status
Location: src/desktop/native/managers/webcam_manager.py

Manages camera and webcam hardware on Windows via OpenCV (cv2) and PowerShell PnP device querying.
Supports device enumeration, photo capture to disk, and hardware status diagnostics.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# Graceful import of OpenCV (cv2)
try:
    import cv2  # type: ignore

    if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    CV2_AVAILABLE = False


class WebcamManager(BaseNativeManager):
    """
    Native manager for camera and webcam devices.

    Capabilities:
    - webcam.list: List available camera devices via PowerShell PnP query and cv2 index probing.
    - webcam.capture: Capture a photo from a webcam and save to output_path.
    - webcam.status: Check if a camera device index is available or currently in use.
    """

    NAME = "webcam"
    VERSION = "1.0"
    PRIORITY = 30
    DEPENDENCIES: list[str] = []

    def __init__(self):
        super().__init__()
        self._initialized = False
        self._cv2_available = CV2_AVAILABLE

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        return [
            "webcam.list",
            "webcam.capture",
            "webcam.status",
        ]

    def initialize(self) -> bool:
        """Initialize the webcam manager, re-verifying cv2 availability."""
        global cv2, CV2_AVAILABLE
        if not self._cv2_available:
            try:
                import cv2  # type: ignore

                if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
                    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
                self._cv2_available = True
                CV2_AVAILABLE = True
            except ImportError:
                self._cv2_available = False
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        """Perform health check on WebcamManager and its OpenCV backend."""
        status = HealthStatus.HEALTHY if self._cv2_available else HealthStatus.DEGRADED
        missing = [] if self._cv2_available else ["opencv-python"]
        available_fallbacks = ["powershell_pnp"] if not self._cv2_available else []

        return HealthCheckResult(
            manager_name=self.name,
            status=status,
            missing_dependencies=missing,
            available_fallbacks=available_fallbacks,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities) if self._cv2_available else 1,
            details={
                "initialized": self._initialized,
                "cv2_available": self._cv2_available,
            },
        )

    def shutdown(self) -> None:
        """Shutdown manager and clean up state."""
        self._initialized = False

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        """
        Execute native webcam operation for the given capability.

        Returns:
            DesktopResult with execution data or failure message.
        """
        args = arguments or {}
        args.update(kwargs)
        cap = capability.lower()

        try:
            if cap in ("webcam.list", "webcam.devices", "list", "devices"):
                return self._handle_list(goal=goal, capability=capability, arguments=args)
            elif cap in ("webcam.capture", "capture"):
                return self._handle_capture(goal=goal, capability=capability, arguments=args)
            elif cap in ("webcam.status", "status"):
                return self._handle_status(goal=goal, capability=capability, arguments=args)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported capability: {capability}",
                )
        except Exception as exc:
            logger.error(f"WebcamManager.{cap} failed: {exc}", exc_info=True)
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Operation failed: {exc}",
            )

    # -------------------------------------------------------------------------
    # Capability Handlers
    # -------------------------------------------------------------------------

    def _handle_list(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        List available camera devices.
        Uses PowerShell PnP query: Get-PnpDevice -Class Camera -Status OK | Select FriendlyName, InstanceId, Status.
        If cv2 is available, also probes device indices 0-4 with cv2.VideoCapture(i).isOpened().
        """
        pnp_devices = self._query_pnp_cameras()
        probed_indices = self._probe_cv2_indices(max_indices=5) if self._cv2_available else []
        available_indices = [item["index"] for item in probed_indices if item.get("available")]

        data = {
            "devices": pnp_devices,
            "pnp_devices": pnp_devices,
            "probed_indices": probed_indices,
            "available_indices": available_indices,
            "device_count": max(len(pnp_devices), len(available_indices)),
            "cv2_available": self._cv2_available,
        }

        return DesktopResult.create_success(
            goal=goal,
            capability=capability,
            manager=self.name,
            data=data,
            events=["webcam.listed"],
        )

    def _handle_capture(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        Capture a still photo from a webcam.
        Args:
            device_index (int, default 0): Camera hardware index.
            output_path (str, required): File path where photo will be saved.
            warmup_frames (int, default 2): Number of initial frames to discard for auto-exposure.
        """
        if not self._cv2_available or cv2 is None:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=(
                    "OpenCV (cv2) is not installed. Please install opencv-python "
                    "('pip install opencv-python') to capture webcam photos."
                ),
                data={"cv2_available": False},
            )

        output_path_raw = arguments.get("output_path") or arguments.get("path") or arguments.get("file_path")
        if not output_path_raw:
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error="Missing required argument 'output_path'.",
                data={"arguments": arguments},
            )

        try:
            device_index = int(arguments.get("device_index", 0))
        except (ValueError, TypeError):
            device_index = 0

        try:
            warmup_frames = int(arguments.get("warmup_frames", 2))
        except (ValueError, TypeError):
            warmup_frames = 2

        output_file = Path(output_path_raw).resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        cap = None
        try:
            cap = cv2.VideoCapture(device_index)
            if not cap.isOpened() and hasattr(cv2, "CAP_DSHOW"):
                cap.release()
                cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)

            if not cap.isOpened():
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=(
                        f"Could not open camera at device_index={device_index}. "
                        "The device may be disconnected, unavailable, or in use by another application."
                    ),
                    data={"device_index": device_index, "output_path": str(output_file)},
                )

            # Optional warmup frames to allow exposure and white balance to calibrate
            for _ in range(max(0, warmup_frames)):
                cap.read()

            ret, frame = cap.read()
            if not ret or frame is None:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Failed to read video frame from camera at device_index={device_index}.",
                    data={"device_index": device_index, "output_path": str(output_file)},
                )

            # Save frame to disk
            save_success = cv2.imwrite(str(output_file), frame)
            if not save_success:
                # Fallback for paths with special characters on Windows
                ext = output_file.suffix if output_file.suffix else ".jpg"
                encoded_ret, buffer = cv2.imencode(ext, frame)
                if encoded_ret:
                    with open(output_file, "wb") as f:
                        f.write(buffer)
                    save_success = True

            if not save_success or not output_file.exists():
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Failed to save captured frame to '{output_file}'. Ensure path and extension are valid.",
                    data={"device_index": device_index, "output_path": str(output_file)},
                )

            height, width = frame.shape[:2]
            channels = frame.shape[2] if len(frame.shape) > 2 else 1
            file_size = output_file.stat().st_size

            data = {
                "output_path": str(output_file),
                "device_index": device_index,
                "width": width,
                "height": height,
                "channels": channels,
                "file_size_bytes": file_size,
            }
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data=data,
                events=["webcam.captured"],
            )
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    def _handle_status(
        self, goal: str, capability: str, arguments: dict[str, Any]
    ) -> DesktopResult:
        """
        Check if a camera is available or currently in use.
        Args:
            device_index (int, default 0): Camera hardware index.
        """
        try:
            device_index = int(arguments.get("device_index", 0))
        except (ValueError, TypeError):
            device_index = 0

        if not self._cv2_available or cv2 is None:
            pnp_devices = self._query_pnp_cameras()
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=(
                    "OpenCV (cv2) is not installed to query direct camera hardware status. "
                    "Please install opencv-python."
                ),
                data={
                    "device_index": device_index,
                    "pnp_devices": pnp_devices,
                    "cv2_available": False,
                },
            )

        cap = None
        try:
            cap = cv2.VideoCapture(device_index)
            is_opened = cap.isOpened()
            can_read = False
            width = 0
            height = 0
            fps = 0.0
            backend = ""

            if is_opened:
                try:
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = float(cap.get(cv2.CAP_PROP_FPS))
                    if hasattr(cap, "getBackendName"):
                        backend = cap.getBackendName()
                except Exception:
                    pass

                ret, frame = cap.read()
                can_read = ret and (frame is not None)

            status_str = "available" if is_opened else "unavailable_or_in_use"
            data = {
                "device_index": device_index,
                "available": is_opened,
                "can_read_frame": can_read,
                "status": status_str,
                "resolution": f"{width}x{height}" if (width and height) else None,
                "width": width,
                "height": height,
                "fps": fps,
                "backend": backend,
                "cv2_available": True,
            }
            return DesktopResult.create_success(
                goal=goal,
                capability=capability,
                manager=self.name,
                data=data,
                events=["webcam.status_checked"],
            )
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _query_pnp_cameras(self) -> list[dict[str, str]]:
        """Query Windows PnP camera devices via PowerShell."""
        ps_cmd = (
            "@(Get-PnpDevice -Class Camera -Status OK -ErrorAction SilentlyContinue "
            "| Select-Object FriendlyName, InstanceId, Status) | ConvertTo-Json -Compress"
        )
        devices = self._run_powershell_pnp(ps_cmd)
        if not devices:
            # Fallback query also checking Image class (some webcams register as Image devices)
            ps_fallback = (
                "@(Get-PnpDevice -Class Image -Status OK -ErrorAction SilentlyContinue "
                "| Select-Object FriendlyName, InstanceId, Status) | ConvertTo-Json -Compress"
            )
            devices = self._run_powershell_pnp(ps_fallback)
        return devices

    def _run_powershell_pnp(self, ps_cmd: str) -> list[dict[str, str]]:
        """Run PowerShell command and parse JSON output into camera device list."""
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=6.0,
            )
            stdout = proc.stdout.strip()
            if not stdout:
                return []

            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                raw_devices = [parsed]
            elif isinstance(parsed, list):
                raw_devices = parsed
            else:
                raw_devices = []

            devices: list[dict[str, str]] = []
            for d in raw_devices:
                if isinstance(d, dict):
                    name = d.get("FriendlyName") or "Camera Device"
                    devices.append(
                        {
                            "name": name,
                            "friendly_name": name,
                            "instance_id": d.get("InstanceId") or "",
                            "status": d.get("Status") or "OK",
                        }
                    )
            return devices
        except Exception as exc:
            logger.warning(f"PowerShell PnpDevice camera query failed: {exc}")
            return []

    def _probe_cv2_indices(self, max_indices: int = 5) -> list[dict[str, Any]]:
        """Probe camera indices 0 through max_indices-1 using cv2.VideoCapture."""
        if not self._cv2_available or cv2 is None:
            return []

        probed: list[dict[str, Any]] = []
        for i in range(max_indices):
            opened = False
            cap = None
            try:
                cap = cv2.VideoCapture(i)
                opened = cap.isOpened()
            except Exception as exc:
                logger.debug(f"Error probing cv2 index {i}: {exc}")
                opened = False
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
            probed.append({"index": i, "available": opened})
        return probed

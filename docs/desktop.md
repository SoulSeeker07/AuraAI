# Desktop Native Engine Architecture

The Desktop Native Engine (`src/desktop/native/`) provides safe, high-reliability control over Windows operating system APIs.

---

## 1. Native Manager Contract (`BaseNativeManager`)

All desktop managers inherit from `BaseNativeManager` (`src/desktop/native/managers/base_manager.py`):

```python
class BaseNativeManager(ABC):
    NAME: str
    VERSION: str
    PRIORITY: int
    DEPENDENCIES: list[str]

    @abstractmethod
    def execute(self, capability: str, context: NativeExecutionContext) -> NativeResult: ...
    def health_check(self) -> HealthCheckResult: ...
    def is_available(self) -> bool: ...
    def get_status(self) -> str: ...
    def verify(self, result: NativeResult) -> bool: ...
    def rollback(self, result: NativeResult, context: NativeExecutionContext) -> bool: ...
```

---

## 2. Core Native Managers

- **`WindowManager`**: Win32 window enum, focus activation, layout resizing, process ID mapping.
- **`ClipboardManager`**: Win32 clipboard monitoring, history caching, format conversion.
- **`DisplayManager`**: Screen Resolution, multi-monitor geometry, DPI scaling.
- **`AudioManager`**: Peak meter volume monitoring, audio device enumeration, mute toggling.
- **`PowerManager`**: Battery percentage, AC line status, power scheme queries.
- **`NetworkManager`**: Interface enumeration, IP address resolution, ping latency tests.

---

## 3. Pipeline Safety Guarantees

Every native manager call executes through the `NativePipeline`, which automatically handles:
1. **Permission Check**: Verifies security clearance prior to execution.
2. **Context Logging**: Records operation start and parameter context.
3. **Execution & Timing**: Measures exact millisecond duration.
4. **Verification**: Invokes automated post-action state verification.
5. **Rollback**: Triggers inverse operation if verification fails.

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.aura_core import AuraCore, AuraCoreStatus
from core.config import AuraConfig
from core.logger import logger


class AuraMonitor:
    '''Continuously monitors all AuraAI features and shows real-time status.'''

    def __init__(self, aura_core: Optional[AuraCore] = None, refresh_interval: int = 2):
        '''Initialize the monitor.

        Args:
            aura_core: Existing AuraCore instance to monitor (reused, never rebuilt).
                       Pass the app's singleton here so the monitor doesn't spin up
                       a second, independent AuraCore in the background.
                       If None, the monitor builds and owns its own instance
                       (standalone mode, e.g. running this file directly).
            refresh_interval: Refresh interval in seconds
        '''
        self.refresh_interval = refresh_interval
        self.running = True
        self.config = AuraConfig()
        self.log_file = self.config.project_root / "Data" / "aura_monitor.log"
        self.core = aura_core
        self._owns_core = aura_core is None  # only standalone mode is allowed to (re)build
        self.start_time = datetime.now()
        self._stop_event = asyncio.Event()

    def _init_log_file(self):
        '''Initialize log file.'''
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write('AURA AI LIVE MONITOR\n')
            f.write('=' * 80 + '\n')
            f.write(f'Start Time: {self.start_time.strftime("%Y-%m-%d %H:%M:%S")}\n')
            f.write('\n')

    def _write_log(self, content: str):
        '''Write content to log file.'''
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f'[{timestamp}] {content}\n'
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    def _format_status(self, status: AuraCoreStatus) -> str:
        '''Format AuraCoreStatus to string.'''
        if status == AuraCoreStatus.READY:
            return 'READY'
        elif status == AuraCoreStatus.ERROR:
            return 'ERROR'
        return 'UNKNOWN'

    def _format_bool(self, value: bool) -> str:
        '''Format boolean to yes/no.'''
        return 'YES' if value else 'NO'

    def _write_component_status(self):
        '''Write component status to log.'''
        self._write_log('\n--- COMPONENT STATUS ---')
        self._write_log(f'  Memory: {self._format_status(AuraCoreStatus.READY if self.core.memory_enabled else AuraCoreStatus.ERROR)}')
        self._write_log(f'  Knowledge: {self._format_status(AuraCoreStatus.READY if self.core.knowledge_enabled else AuraCoreStatus.ERROR)}')
        self._write_log(f'  Workspace: {self._format_status(AuraCoreStatus.READY if self.core.workspace_aware else AuraCoreStatus.ERROR)}')
        self._write_log(f'  Plugins: {self._format_status(AuraCoreStatus.READY)} - {self.core.plugin_count} loaded')
        self._write_log(f'  Agent Runtime: {self._format_status(self.core.agent_runtime_status)}')
        self._write_log(f'  Workflow Engine: {self._format_status(self.core.workflow_engine_status)}')
        self._write_log(f'  Vision: {self._format_status(AuraCoreStatus.ERROR if not self.core.vision_enabled else AuraCoreStatus.READY)}')
        self._write_log(f'  Voice: {self._format_status(AuraCoreStatus.ERROR if not self.core.voice_enabled else AuraCoreStatus.READY)}')

    def _write_system_stats(self):
        '''Write system statistics to log.'''
        self._write_log('\n--- SYSTEM STATISTICS ---')

        if hasattr(self.core, 'memory_stats') and self.core.memory_stats:
            for key, value in self.core.memory_stats.items():
                self._write_log(f'  {key}: {value}')
        else:
            self._write_log('  Memory: Not available')

        if hasattr(self.core, 'knowledge_stats') and self.core.knowledge_stats:
            for key, value in self.core.knowledge_stats.items():
                if isinstance(value, bool):
                    self._write_log(f'  {key}: {self._format_bool(value)}')
                else:
                    self._write_log(f'  {key}: {value}')
        else:
            self._write_log('  Knowledge: Not available')

        if hasattr(self.core, 'workspace_info') and self.core.workspace_info:
            for key, value in self.core.workspace_info.items():
                if isinstance(value, bool):
                    self._write_log(f'  {key}: {self._format_bool(value)}')
                else:
                    self._write_log(f'  {key}: {value}')
        else:
            self._write_log('  Workspace: Not available')

        conv_count = len(self.core.conversation_history)
        self._write_log(f'  Conversation History: {conv_count} turns')

        llm_status = 'Ready' if self.core.llm_enabled else 'Not Configured'
        groq_model = self.core.groq_model if self.core.groq_client else 'Not Available'
        self._write_log(f'  LLM: {llm_status} - {groq_model}')

    def _write_plugins_list(self):
        '''Write plugins list to log.'''
        self._write_log('\n--- PLUGINS ---')
        self._write_log(f'{self.core.plugin_count} loaded:')
        for plugin in self.core.plugins:
            self._write_log(f'  - {plugin}')

    def _write_summary(self):
        '''Write monitoring summary to log.'''
        self._write_log('\n--- MONITORING SUMMARY ---')
        self._write_log(f'Project: {self.core.project_root}')
        self._write_log(f'Workspace: {self.core.workspace}')
        self._write_log(f'Vision System: {self._format_bool(self.core.vision_enabled)}')
        self._write_log(f'Voice System: {self._format_bool(self.core.voice_enabled)}')
        self._write_log(f'Uptime: {self.get_uptime()}')
        self._write_log('-' * 80 + '\n')

    def get_uptime(self) -> str:
        '''Calculate uptime since monitor started.'''
        delta = datetime.now() - self.start_time
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{delta.days}d {hours}h {minutes}m {seconds}s"

    def load_core(self) -> bool:
        '''Load a fresh AuraCore. Only valid in standalone mode.

        If this monitor was created with an existing aura_core instance
        (the normal in-app case), this is a no-op that just confirms we
        still have that instance — it will NEVER construct a second,
        independent AuraCore behind the app's back.
        '''
        if not self._owns_core:
            logger.warning("load_core() called on a monitor bound to an external AuraCore — ignoring rebuild")
            return self.core is not None

        try:
            project_root = self.config.project_root
            data_path = self.config.project_root / "Data" / "ChatLog.json"

            self.core = AuraCore(config={
                'project_root': project_root,
                'data_path': data_path
            })
            return True
        except Exception as e:
            logger.error(f"Error loading AuraCore: {e}")
            return False

    async def _load_core_async(self) -> bool:
        '''Async wrapper around load_core (kept for API compatibility).'''
        return self.load_core()

    def _ensure_core(self) -> bool:
        '''Make sure we have a core to report on, without ever rebuilding
        an externally-provided instance out from under the app.'''
        if self.core is not None:
            return True
        if self._owns_core:
            return self.load_core()
        # Bound to an external core that hasn't been created yet — nothing to do.
        return False

    async def monitor_async(self):
        '''Main monitoring loop (async version).'''
        self._init_log_file()

        while not self._stop_event.is_set():
            try:
                if not self._ensure_core():
                    await asyncio.sleep(self.refresh_interval)
                    continue

                self._write_component_status()
                self._write_system_stats()

                if hasattr(self.core, 'plugins') and self.core.plugins:
                    self._write_plugins_list()

                self._write_summary()

                await asyncio.sleep(self.refresh_interval)

            except Exception as e:
                logger.error(f'Monitor error: {e}', exc_info=True)
                await asyncio.sleep(self.refresh_interval)

    def monitor(self):
        '''Main monitoring loop (sync version).'''
        self._init_log_file()

        while self.running:
            try:
                if not self._ensure_core():
                    time.sleep(self.refresh_interval)
                    continue

                self._write_component_status()
                self._write_system_stats()

                if hasattr(self.core, 'plugins') and self.core.plugins:
                    self._write_plugins_list()

                self._write_summary()

                time.sleep(self.refresh_interval)

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                logger.error(f'Monitor error: {e}', exc_info=True)
                time.sleep(self.refresh_interval)

        print('\nMonitor stopped.')

    def print_component_status(self, component_name: str, status: str, message: str):
        '''Print component status with color coding.'''
        icon = '✓' if status == 'Ready' else '✗' if status == 'Error' else '•'
        print(f'{icon} {component_name:<20} {status:<12} {message}')

    def print_plugin_status(self, plugin_name: str, status: str):
        '''Print plugin status.'''
        color = '\033[32m' if status == 'loaded' else '\033[31m'
        print(f'{color} {plugin_name:<25} {status}\033[0m')

    def print_memory_status(self, stats: Dict[str, Any]):
        '''Print memory status.'''
        print('\nMemory Statistics:')
        for key, value in stats.items():
            print(f'  {key:<20} {value}')

    def print_knowledge_status(self, stats: Dict[str, Any]):
        '''Print knowledge status.'''
        print('\nKnowledge Statistics:')
        for key, value in stats.items():
            if isinstance(value, bool):
                print(f'  {key:<20} {"Enabled" if value else "Disabled"}')
            else:
                print(f'  {key:<20} {value}')

    def print_workspace_status(self, info: Dict[str, Any]):
        '''Print workspace status.'''
        print('\nWorkspace Statistics:')
        for key, value in info.items():
            if isinstance(value, bool):
                print(f'  {key:<20} {"Yes" if value else "No"}')
            else:
                print(f'  {key:<20} {value}')

    def print_plugin_list(self, plugins: List[str], plugin_count: int):
        '''Print list of all plugins.'''
        print(f'\nPlugins: {plugin_count} loaded')
        for plugin in plugins:
            print(f'  - {plugin}')


def main():
    '''Standalone entry point — builds its own AuraCore since there's no
    running app to share an instance with.'''
    import argparse

    parser = argparse.ArgumentParser(description='AuraAI Live Monitor')
    parser.add_argument('--interval', '-i', type=int, default=2,
                        help='Refresh interval in seconds (default: 2)')

    args = parser.parse_args()

    monitor = AuraMonitor(aura_core=None, refresh_interval=args.interval)
    monitor.monitor()


if __name__ == '__main__':
    main()
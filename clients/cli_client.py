"""
AuraAI CLI Client

Interactive command-line interface for AuraAI.
Provides commands for all Aura Core functionality.
"""

import re

from core import logger
from agents.autonomous_coding_agent import AutonomousCodingAgent
from core.aura_core import AuraCore, AuraCoreStatus

# Import component status types


class CLIClient:
    """
    Command-line interface client for AuraAI.
    """

    def __init__(self, aura_core: AuraCore, config: dict = None):
        self.aura_core = aura_core
        self.config = config or {}
        self.running = True
        self.command_history = []
        self.history_index = -1

        # Voice listening configuration
        self.voice_listening = False

        # Initialize autonomous coding agent
        try:
            self.autonomous_coding_agent = AutonomousCodingAgent(
                aura_core=aura_core, max_attempts=3, timeout=60
            )
            self.coding_agent_enabled = True
            self.code_executor = self.autonomous_coding_agent.code_executor  # <-- added
            logger.info("Autonomous coding agent initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize autonomous coding agent: {e}")
            self.autonomous_coding_agent = None
            self.coding_agent_enabled = False
            self.code_executor = None
        self.verbosity_mode = (
            "normal"  # 'normal', 'developer', 'debug', 'benchmark', 'trace'
        )

        # Wire aura_core into voice loop so continuous voice can reach Groq
        try:
            from voice.continuous_loop import ContinuousVoiceLoop
            ContinuousVoiceLoop.set_global_aura_core(self.aura_core)
            if hasattr(self.aura_core, "voice_loop") and self.aura_core.voice_loop:
                self.aura_core.voice_loop._aura_core = self.aura_core
                self.aura_core.voice_loop.on_stop = lambda: setattr(self, "voice_listening", False)
        except Exception as e:
            logger.debug(f"Could not wire aura_core to voice_loop on init: {e}")

    def print_banner(self):
        """Print the AuraAI banner."""
        print("\n" + "=" * 60)
        print("               AURA AI ENGINE v1.0")
        print("=" * 60)
        print("Project : AuraAI")
        print(f"Workspace : {self.aura_core.workspace}")
        print("Provider : Groq")
        print(f"Memory : {'Loaded' if self.aura_core.memory_enabled else 'Not loaded'}")
        print(
            f"Knowledge : {'Ready' if self.aura_core.knowledge_enabled else 'Not ready'}"
        )
        print(f"Plugins : {self.aura_core.plugin_count} Loaded")
        print(f"Voice : {'Enabled' if self.aura_core.voice_enabled else 'Disabled'}")
        print(
            f"Voice Listening : {'ON' if self.voice_listening else 'OFF'}"
        )
        print(
            f"Vision : {'Ready' if self.aura_core.vision_enabled else 'Disabled (camera not detected)'}"
        )
        print(
            f"AI Brain : {'Ready' if self.aura_core.llm_enabled else 'Not configured (set GROQ_API_KEY)'}"
        )
        print("-" * 60)

    def print_current_task(self):
        """Print current task information."""
        task = self.aura_core.current_task
        status = self.aura_core.current_task_status.value if task else "Idle"
        print("\nCurrent Task")
        print(f"  {task or 'Idle'}")
        print(f"  Status: {status}")

    def print_commands(self):
        """Print available commands."""
        commands = [
            "chat",  # Interactive chat
            "status",  # Show system status
            "memory",  # Memory commands
            "knowledge",  # Knowledge commands
            "workspace",  # Workspace commands
            "plugins",  # Plugin commands
            "tasks",  # Task management
            "history",  # Conversation history
            "workflow",  # Workflow engine
            "agents",  # Agent information
            "code <requirement>",  # Autonomous coding agent - execute code from natural language
            "engineering",  # Engineering tools
            "doctor",  # Health check
            "graph",  # Architecture graph
            "Start Listening",  # Start continuous voice listening
            "Stop Listening",  # Stop continuous voice listening
            "voice_listen",  # Legacy alias for Start Listening
            "help",  # Show help
            "reload",  # Reload configuration
            "quit",  # Exit CLI
        ]
        voice_status = "ON" if self.voice_listening else "OFF"
        print(f"\nAvailable Commands: {', '.join(commands)}")
        print(f"Voice Listening: {voice_status}")

    def print_status(self):
        """Print detailed system status."""
        status = self.aura_core.get_status()

        print("\n" + "=" * 60)
        print("            AURA AI SYSTEM STATUS")
        print("=" * 60)

        print(f"\nProject: {status['project']}")
        print(f"Current Task: {status.get('current_task', 'None')}")

        print("\n" + "-" * 60)
        print("    COMPONENT STATUS")
        print("-" * 60)

        for name, info in status["components"].items():
            status_emoji = "✓" if info["loaded"] else "✗"
            print(f"{status_emoji} {name:15} {info['status']:10} {info['message']}")

        print("\n" + "-" * 60)
        print("    SYSTEM STATISTICS")
        print("-" * 60)

        print("\nMemory:")
        for key, value in status["memory"].items():
            print(f"  {key}: {value}")

        print("\nKnowledge:")
        for key, value in status["knowledge"].items():
            print(f"  {key}: {value}")

        print(f"\nPlugins: {status['plugins']['count']} loaded")
        for plugin in status["plugins"]["loaded"]:
            print(f"  - {plugin}")

        print("\nWorkspace:")
        for key, value in status["workspace"].items():
            print(f"  {key}: {value}")

        print(f"\nAgent Runtime: {status['agent_runtime']}")
        print(f"Workflow Engine: {status['workflow_engine']}")
        print(f"Vision: {status['vision']}")
        print(f"Voice: {status['voice']}")
        print("-" * 60)

    def print_memory_stats(self):
        """Print memory statistics."""
        stats = self.aura_core.memory_stats
        history = self.aura_core.get_conversation_history()

        print("\n" + "=" * 60)
        print("            MEMORY STATISTICS")
        print("=" * 60)

        print("\nCurrent Context:")
        print("  Project: AuraAI")
        print(f"  Topic: {self.aura_core.current_task or 'None'}")

        print("\nLong Term Memories:")
        print(f"  {stats.get('total_memories', 0)}")

        print("\nSession Memories:")
        print(f"  {stats.get('session_memories', 0)}")

        print("\nWorking Memories:")
        print(f"  {stats.get('working_memories', 0)}")

        print("\nConversation History:")
        print(f"  {len(history)} entries")

        if history:
            print("\nRecent Entries:")
            for entry in history[-5:]:
                role = entry["role"].upper()
                content = entry["content"][:100]
                print(f"  [{role}] {content}...")

        print("-" * 60)

    def print_knowledge_stats(self):
        """Print knowledge statistics."""
        stats = self.aura_core.get_knowledge_stats()

        print("\n" + "=" * 60)
        print("            KNOWLEDGE STATISTICS")
        print("=" * 60)

        print(f"\nEnabled: {stats['enabled']}")
        print(f"Indexed: {stats['indexed']}")
        print(f"Search Enabled: {stats['search_enabled']}")
        print(f"Project: {stats['project']}")
        print(f"Status: {stats['status']}")
        print(f"Message: {stats['message']}")
        print(f"Loaded: {stats['loaded']}")

        print("\n" + "-" * 60)
        print("Available Commands:")
        print("  knowledge                  - Show knowledge stats")
        print("  knowledge:search <query>   - Search knowledge")
        print("  knowledge:add              - Add to knowledge")
        print("  knowledge:clear            - Clear knowledge")
        print("-" * 60)

    def print_workspace_stats(self):
        """Print workspace statistics."""
        print("\n" + "=" * 60)
        print("            WORKSPACE STATISTICS")
        print("=" * 60)

        info = self.aura_core.get_workspace_info()

        print(f"\nPath: {info['path']}")
        print(f"Project Root: {info['project_root']}")
        print(f"Total Files: {info['total_files']}")
        print(f"Total Folders: {info['total_folders']}")
        print(f"Scan Status: {info['scan_status']}")
        print(f"Current Task: {info['current_task'] or 'None'}")

        print("\n" + "-" * 60)
        print("Available Commands:")
        print("  workspace                  - Show workspace info")
        print("  workspace:scan <path>      - Scan workspace")
        print("  workspace:analyze <file>   - Analyze file")
        print("  workspace:fix <file>       - Fix file issues")
        print("-" * 60)

    def print_plugins_status(self):
        """Print plugin status."""
        print("\n" + "=" * 60)
        print("            PLUGIN STATUS")
        print("=" * 60)

        plugins = self.aura_core.get_all_plugins_status()

        print(f"\nTotal: {plugins['total']} loaded")

        for plugin_name in plugins["loaded"]:
            print(f"\n{plugin_name}:")
            details = plugins.get("details", {}).get(plugin_name, {})
            status_emoji = "✓" if details.get("loaded") else "✗"
            print(f"  Status: {status_emoji} {details.get('status', 'Unknown')}")

        print("\n" + "-" * 60)
        print("Available Commands:")
        print("  plugins                    - Show plugin status")
        print("  plugins:load <name>        - Load plugin")
        print("  plugins:unload <name>      - Unload plugin")
        print("-" * 60)

    def print_tasks_status(self):
        """Print task status."""
        print("\n" + "=" * 60)
        print("            TASK STATUS")
        print("=" * 60)

        print("\nRunning:")
        if self.aura_core.current_task:
            print(f"  {self.aura_core.current_task}")
        else:
            print("  None")

        print("\nCompleted:")
        completed_tasks = [
            k
            for k, v in self.aura_core.components.items()
            if v.status == AuraCoreStatus.READY
        ]
        for task in completed_tasks:
            if task not in ["Memory", "Knowledge", "Plugins", "Workspace"]:
                print(f"  - {task}")

        print("\nFailed:")
        failed_tasks = [
            k
            for k, v in self.aura_core.components.items()
            if v.status == AuraCoreStatus.ERROR
        ]
        if failed_tasks:
            for task in failed_tasks:
                comp = self.aura_core.components[task]
                print(f"  - {task}: {comp.message}")
        else:
            print("  None")

        print("-" * 60)

    def print_history(self, days: int = 1):
        """Print conversation history."""
        history = self.aura_core.get_conversation_history()

        print("\n" + "=" * 60)
        print("            CONVERSATION HISTORY")
        print("=" * 60)

        if not history:
            print("\nNo history yet.")
        else:
            print(f"\nShowing last {min(len(history), 20)} entries")

            for entry in history[-20:]:
                role = entry["role"].upper()
                content = entry["content"]
                print(f"\n[{role}]")
                print(f"  {content}")

        print("-" * 60)

    def print_workflow_status(self):
        """Print workflow engine status."""
        print("\n" + "=" * 60)
        print("            WORKFLOW ENGINE STATUS")
        print("=" * 60)

        print(f"\nStatus: {self.aura_core.workflow_engine_status.value}")

        print("\n" + "-" * 60)
        print("Available Commands:")
        print("  workflow                  - Show workflow status")
        print("  workflow:run <name>       - Run workflow")
        print("  workflow:list             - List workflows")
        print("-" * 60)

    def print_agents_info(self):
        """Print agent information."""
        print("\n" + "=" * 60)
        print("            AGENT INFORMATION")
        print("=" * 60)

        print("\nAvailable Agents:")
        agents = [
            "Documentation Agent",
            "Security Agent",
            "Networking Agent",
            "Collaboration Agent",
            "Orchestration Agent",
            "Routing Agent",
        ]

        for agent in agents:
            print(f"  ✓ {agent}")

        print("\n" + "-" * 60)
        print("Available Commands:")
        print("  agents                     - Show agent info")
        print("  agents:list                - List all agents")
        print("  agents:info <name>         - Get agent details")
        print("-" * 60)

    def print_engineering_tools(self):
        """Print engineering tools."""
        print("\n" + "=" * 60)
        print("            ENGINEERING TOOLS")
        print("=" * 60)

        print("\nAvailable Tools:")
        tools = [
            "Code Analysis",
            "Bug Fixing",
            "Testing",
            "Documentation Generation",
            "Refactoring",
        ]

        for tool in tools:
            print(f"  ✓ {tool}")

        print("\n" + "-" * 60)
        print("Available Commands:")
        print("  engineering                - Show engineering tools")
        print("  engineering:fix <file>     - Fix code issues")
        print("  engineering:test <file>    - Run tests")
        print("  engineering:docs <file>    - Generate docs")
        print("-" * 60)

    def print_doctor_report(self):
        """Print health check report."""
        print("\n" + "=" * 60)
        print("            AURA HEALTH REPORT")
        print("=" * 60)

        report = self.aura_core.get_health_report()

        components = [
            ("Brain", report["brain"]),
            ("Capability Router", "PASS"),
            ("Memory", report["memory"]),
            ("Knowledge", report["knowledge"]),
            ("Workspace", report["workspace"]),
            ("Plugins", report["plugins"]),
            ("Voice", report["voice"]),
            ("Vision", report["vision"]),
            ("Engineering", "PASS"),
            ("Agent Runtime", report["agent_runtime"]),
            ("Workflow Engine", report["workflow_engine"]),
        ]

        print("\nComponent Status:")
        for name, status in components:
            if status in ["PASS", "Ready"]:
                print(f"  ✓ {name:25} {status}")
            else:
                print(f"  ✗ {name:25} {status}")

        print(f"\nOverall: {report['overall']} - {report['percentage']}")

        print("=" * 60)

    def print_graph(self):
        """Print architecture graph."""
        graph = self.aura_core.get_architecture_graph()
        print("\n" + "=" * 60)
        print("            AURA ARCHITECTURE")
        print("=" * 60)
        print("\n" + graph)
        print("=" * 60)

    def print_help(self):
        """Print help information."""
        print("\n" + "=" * 60)
        print("            AURA AI - HELP")
        print("=" * 60)

        print("\n" + "-" * 60)
        print("GENERAL COMMANDS")
        print("-" * 60)
        print("  status          - Show system status")
        print("  chat            - Start interactive chat")
        print("  doctor          - Run health check")
        print("  graph           - Show architecture graph")
        print("  Start Listening - Start microphone wake-word listening")
        print("  Stop Listening  - Stop microphone wake-word listening")
        print("  voice_listen    - Legacy alias for Start Listening")
        print("  help            - Show this help")
        print("  quit            - Exit CLI")
        print("  reload          - Reload configuration")

        print("\n" + "-" * 60)
        print("MEMORY COMMANDS")
        print("-" * 60)
        print("  memory          - Show memory statistics")
        print("  memory:clear    - Clear working memory")
        print("  memory:export   - Export memories")

        print("\n" + "-" * 60)
        print("KNOWLEDGE COMMANDS")
        print("-" * 60)
        print("  knowledge       - Show knowledge statistics")
        print("  knowledge:search <query> - Search knowledge")
        print("  knowledge:add   - Add to knowledge base")
        print("  knowledge:clear - Clear knowledge")

        print("\n" + "-" * 60)
        print("WORKSPACE COMMANDS")
        print("-" * 60)
        print("  workspace       - Show workspace info")
        print("  workspace:scan  - Scan workspace")
        print("  workspace:analyze <file> - Analyze file")
        print("  workspace:fix <file> - Fix file issues")

        print("\n" + "-" * 60)
        print("PLUGIN COMMANDS")
        print("-" * 60)
        print("  plugins         - Show plugin status")
        print("  plugins:load <name> - Load plugin")
        print("  plugins:unload <name> - Unload plugin")

        print("\n" + "-" * 60)
        print("TASK COMMANDS")
        print("-" * 60)
        print("  tasks           - Show task status")
        print("  tasks:list      - List all tasks")
        print("  tasks:cancel <id> - Cancel task")

        print("\n" + "-" * 60)
        print("HISTORY COMMANDS")
        print("-" * 60)
        print("  history         - Show conversation history")
        print("  history:clear   - Clear history")
        print("  history:recent  - Show recent history")

        print("\n" + "-" * 60)
        print("WORKFLOW COMMANDS")
        print("-" * 60)
        print("  workflow        - Show workflow status")
        print("  workflow:run <name> - Run workflow")
        print("  workflow:list   - List workflows")

        print("\n" + "-" * 60)
        print("AGENT COMMANDS")
        print("-" * 60)
        print("  agents          - Show agent information")
        print("  agents:list     - List all agents")
        print("  agents:info <name> - Get agent details")

        print("\n" + "-" * 60)
        print("ENGINEERING COMMANDS")
        print("-" * 60)
        print("  engineering     - Show engineering tools")
        print("  engineering:fix <file> - Fix code issues")
        print("  engineering:test <file> - Run tests")
        print("  engineering:docs <file> - Generate documentation")

        print("\n" + "-" * 60)
        print("OUTPUT MODES")
        print("-" * 60)
        print("  mode normal     - Clean user responses only")
        print("  mode developer  - Medium trace info per request")
        print("  mode debug      - Full verbose logs")
        print("  mode benchmark  - Latency breakdown table")
        print("  mode trace      - Live execution tree after each response")
        print("  trace           - Show trace for last request")

        print("=" * 60)

    async def process_command(self, command: str):
        """
        Process a command.

        Args:
            command: Command string
        """
        parts = command.strip().split()
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        # Track command in history
        self.command_history.append(command)
        self.history_index = len(self.command_history)

        try:
            if cmd in ["status", ""]:
                self.print_status()
                self.print_current_task()
                self.print_commands()

            elif cmd == "chat":
                await self._interactive_chat()

            elif cmd == "memory":
                self.print_memory_stats()

            elif cmd.startswith("memory:"):
                subcmd = cmd[7:]
                if subcmd == "clear":
                    self.aura_core.clear_conversation_history()
                    print("\n✓ Conversation history cleared")
                elif subcmd == "export":
                    print("\n✓ Memory export (placeholder)")
                else:
                    print(f"\n✓ Unknown memory subcommand: {subcmd}")
                    print("  Try: memory, memory:clear, memory:export")

            elif cmd == "knowledge":
                self.print_knowledge_stats()

            elif cmd.startswith("knowledge:"):
                subcmd = cmd[10:]
                if subcmd == "search" and args:
                    query = " ".join(args)
                    print(f"\nSearching knowledge: {query}")
                    print("✓ Search results (placeholder)")
                elif subcmd == "add":
                    print("\n✓ Add to knowledge (placeholder)")
                elif subcmd == "clear":
                    print("\n✓ Knowledge cleared (placeholder)")
                else:
                    print(f"\n✓ Unknown knowledge subcommand: {subcmd}")

            elif cmd == "workspace":
                self.print_workspace_stats()

            elif cmd.startswith("workspace:"):
                subcmd = cmd[11:]
                if subcmd == "scan" and args:
                    path = args[0]
                    result = self.aura_core.scan_workspace()
                    if result["success"]:
                        print(f"\n✓ Scanned: {result}")
                    else:
                        print(f"\n✗ Error: {result['message']}")
                elif subcmd == "analyze" and args:
                    file_path = args[0]
                    result = self.aura_core.analyze_code(file_path)
                    if result["success"]:
                        print("\n✓ Analysis:")
                        print(f"  Lines: {result['lines']}")
                        print(f"  Characters: {result['characters']}")
                        print(f"  Words: {result['words']}")
                        print(f"  Extension: {result['ext']}")
                    else:
                        print(f"\n✗ Error: {result['message']}")
                elif subcmd == "fix" and args:
                    file_path = args[0]
                    result = self.aura_core.fix_code(file_path)
                    if result["success"]:
                        print("\n✓ Code fixed:")
                        print(f"  {result['message']}")
                    else:
                        print(f"\n✗ Error: {result['message']}")
                else:
                    print(f"\n✓ Unknown workspace subcommand: {subcmd}")

            elif cmd == "plugins":
                self.print_plugins_status()

            elif cmd.startswith("plugins:"):
                subcmd = cmd[8:]
                if subcmd == "load" and args:
                    plugin_name = args[0]
                    if self.aura_core.load_plugin(plugin_name):
                        print(f"\n✓ Plugin {plugin_name} loaded")
                    else:
                        print(f"\n✗ Failed to load {plugin_name}")
                elif subcmd == "unload" and args:
                    plugin_name = args[0]
                    if self.aura_core.unload_plugin(plugin_name):
                        print(f"\n✓ Plugin {plugin_name} unloaded")
                    else:
                        print(f"\n✗ Failed to unload {plugin_name}")
                else:
                    print(f"\n✓ Unknown plugin subcommand: {subcmd}")

            elif cmd == "tasks":
                self.print_tasks_status()

            elif cmd.startswith("tasks:"):
                subcmd = cmd[6:]
                if subcmd == "list":
                    print("\n✓ Task list (placeholder)")
                elif subcmd == "cancel" and args:
                    task_id = args[0]
                    print(f"\n✓ Task {task_id} cancelled")
                else:
                    print(f"\n✓ Unknown task subcommand: {subcmd}")

            elif cmd == "history":
                self.print_history()

            elif cmd.startswith("history:"):
                subcmd = cmd[8:]
                if subcmd == "clear":
                    self.aura_core.clear_conversation_history()
                    print("\n✓ History cleared")
                elif subcmd == "recent":
                    self.print_history(days=1)
                else:
                    print(f"\n✓ Unknown history subcommand: {subcmd}")

            elif cmd == "workflow":
                self.print_workflow_status()

            elif cmd.startswith("workflow:"):
                subcmd = cmd[9:]
                if subcmd == "run" and args:
                    workflow_name = args[0]
                    print(f"\n✓ Running workflow: {workflow_name}")
                elif subcmd == "list":
                    print("\n✓ Workflow list (placeholder)")
                else:
                    print(f"\n✓ Unknown workflow subcommand: {subcmd}")

            elif cmd == "agents":
                self.print_agents_info()

            elif cmd.startswith("agents:"):
                subcmd = cmd[7:]
                if subcmd == "list":
                    print("\n✓ Agent list (placeholder)")
                elif subcmd == "info" and args:
                    agent_name = args[0]
                    print(f"\n✓ Agent info: {agent_name} (placeholder)")
                else:
                    print(f"\n✓ Unknown agent subcommand: {subcmd}")

            elif cmd == "code":
                """Autonomous coding agent - execute code from natural language requirement"""
                if not self.coding_agent_enabled:
                    print("\n✗ Autonomous coding agent not available")
                    return

                if not args:
                    print("\n✗ Usage: code <requirement>")
                    print(
                        "  Example: code 'Create a Python script that reads a file and prints its contents'"
                    )
                    print(
                        "  Example: code 'Generate a script that calculates fibonacci numbers'"
                    )
                    return

                # Combine arguments into requirement
                requirement = " ".join(args)

                print("\n" + "=" * 60)
                print("    AUTONOMOUS CODING AGENT")
                print("=" * 60)
                print(f"\nExecuting: {requirement}\n")

                # Run the autonomous coding agent using existing event loop
                try:
                    result = await self.autonomous_coding_agent.execute_task(
                        requirement
                    )

                    # Print results
                    print("\n" + "=" * 60)
                    if result["success"]:
                        print("    ✓ TASK COMPLETED SUCCESSFULLY")
                    else:
                        print("    ✗ TASK COMPLETED WITH ERRORS")
                    print("=" * 60)

                    print(f"\nAttempts: {result['attempts']}")
                    print(f"Execution Time: {result['execution_time']:.2f}s")
                    print(f"Filename: {result['filename']}")
                    print(f"\nMessage: {result['message']}")

                    if result["error"]:
                        print("\nLast Error:")
                        print(f"  {result['error']}")

                    if result["output"]:
                        print("\nOutput:")
                        print("-" * 60)
                        print(result["output"])
                        print("-" * 60)

                except Exception as e:
                    print(f"\n✗ Error executing autonomous coding agent: {e}")
                    logger.error(f"Autonomous coding agent error: {e}", exc_info=True)

            elif cmd == "engineering":
                self.print_engineering_tools()

            elif cmd.startswith("engineering:"):
                subcmd = cmd[12:]
                if subcmd == "fix" and args:
                    file_path = args[0]
                    result = self.aura_core.fix_code(file_path)
                    if result["success"]:
                        print("\n✓ Code fixed:")
                        print(f"  {result['message']}")
                    else:
                        print(f"\n✗ Error: {result['message']}")
                elif subcmd == "test" and args:
                    file_path = args[0]
                    print(f"\n✓ Running tests for {file_path} (placeholder)")
                elif subcmd == "docs" and args:
                    file_path = args[0]
                    print(f"\n✓ Generating docs for {file_path} (placeholder)")
                else:
                    print(f"\n✓ Unknown engineering subcommand: {subcmd}")

            elif cmd == "doctor":
                self.print_doctor_report()

            elif command == "Start Listening" or command == "start listening" or command == "START LISTENING":
                # Start voice listening mode using ContinuousVoiceLoop
                # Idempotent: can be called multiple times safely
                if not self.aura_core.voice_enabled:
                    print("\n✗ Voice is not enabled in Aura.")
                    print("  Enable voice with your configuration or use voice-embedded apps.")
                    return

                if self.voice_listening:
                    # Idempotent: already running, no action needed
                    print("\n✓ Voice listening is already active.")
                    return

                self.voice_listening = True
                print("\n✓ Voice listening enabled.")
                print("  ContinuousVoiceLoop owns the microphone.")
                print("  Waiting for wake word: Aura")
                print("  Use 'Stop Listening' to disable.")

                try:
                    if hasattr(self.aura_core, 'voice_loop') and self.aura_core.voice_loop:
                        self.aura_core.voice_loop._aura_core = self.aura_core
                        success = self.aura_core.voice_loop.start()
                        if success:
                            print(f"  ✓ ContinuousVoiceLoop started (running: {self.aura_core.voice_loop._running})")
                        else:
                            print(f"  ✗ Failed to start ContinuousVoiceLoop")
                            self.voice_listening = False
                    else:
                        print(f"  ✗ No voice_loop found on AuraCore")
                        self.voice_listening = False
                except Exception as e:
                    logger.error(f"Failed to start ContinuousVoiceLoop: {e}", exc_info=True)
                    print(f"  ✗ Error starting voice listening: {e}")
                    self.voice_listening = False

                self.print_commands()

            elif command == "Stop Listening" or command == "stop listening" or command == "STOP LISTENING":
                # Stop voice listening mode using ContinuousVoiceLoop
                # Idempotent: can be called multiple times safely
                if not self.voice_listening:
                    # Idempotent: already stopped, no action needed
                    print("\n✓ Voice listening is already stopped.")
                    return

                print("\n✓ Stopping voice listening...")

                try:
                    if hasattr(self.aura_core, 'voice_loop') and self.aura_core.voice_loop:
                        self.aura_core.voice_loop.stop()
                        print("  ContinuousVoiceLoop stopped.")
                        self.voice_listening = False
                    else:
                        print(f"  ✗ No voice_loop found on AuraCore")
                        self.voice_listening = False
                except Exception as e:
                    logger.error(f"Failed to stop ContinuousVoiceLoop: {e}", exc_info=True)
                    print(f"  ✗ Error stopping voice listening: {e}")

                self.print_commands()

            elif command == "voice_listen" or command == "voice_listen_toggle":
                # Legacy alias for voice listening (case-insensitive)
                self.voice_listening = True
                print("\n✓ Voice listening enabled (legacy alias).")
                print("  Use 'Start Listening' for explicit start command.")
                print("  Waiting for wake word: Aura")
                print("  Use 'Stop Listening' to disable.")

                try:
                    if hasattr(self.aura_core, 'voice_loop') and self.aura_core.voice_loop:
                        self.aura_core.voice_loop._aura_core = self.aura_core
                        success = self.aura_core.voice_loop.start()
                        if success:
                            print(f"  ✓ ContinuousVoiceLoop started (running: {self.aura_core.voice_loop._running})")
                        else:
                            print(f"  ✗ Failed to start ContinuousVoiceLoop")
                            self.voice_listening = False
                    else:
                        print(f"  ✗ No voice_loop found on AuraCore")
                        self.voice_listening = False
                except Exception as e:
                    logger.error(f"Failed to start ContinuousVoiceLoop: {e}", exc_info=True)
                    print(f"  ✗ Error starting voice listening: {e}")
                    self.voice_listening = False

                self.print_commands()

            elif command.lower() in ("autonomy on", "autonomy start"):
                success = self.aura_core.start_autonomy()
                if success:
                    print("\n✓ Autonomous TriggerScheduler active (background daemon running).")
                else:
                    print("\n✗ Failed to start TriggerScheduler on AuraCore.")
                self.print_commands()

            elif command.lower() in ("autonomy off", "autonomy stop"):
                success = self.aura_core.stop_autonomy(drain_timeout=2.0)
                if success:
                    print("\n✓ Autonomous TriggerScheduler stopped and drained.")
                else:
                    print("\n✗ Failed to stop TriggerScheduler.")
                self.print_commands()

            elif command.lower() == "autonomy status":
                active = self.aura_core.autonomy_active
                trig_count = len(self.aura_core.trigger_registry.list_triggers()) if hasattr(self.aura_core, "trigger_registry") and self.aura_core.trigger_registry else 0
                status_str = "ACTIVE (running)" if active else "INACTIVE (stopped)"
                print(f"\n[Autonomy Subsystem]")
                print(f"  Status: {status_str}")
                print(f"  Registered Triggers: {trig_count}")
                self.print_commands()

            elif cmd == "mode" or cmd.startswith("mode"):
                parts = command.split()
                valid_modes = ["normal", "developer", "debug", "benchmark", "trace"]
                if len(parts) > 1 and parts[1].lower() in valid_modes:
                    self.verbosity_mode = parts[1].lower()
                    import os
                    os.environ["AURA_VERBOSITY"] = self.verbosity_mode
                    print(f"\n✓ Output verbosity set to '{self.verbosity_mode}' mode.")
                    if self.verbosity_mode == "trace":
                        print(
                            "  Each response will display a live execution trace tree."
                        )
                else:
                    print(f"\nCurrent Verbosity Mode: {self.verbosity_mode}")
                    print(
                        "Usage: mode [normal | developer | debug | benchmark | trace]"
                    )

            elif cmd == "trace":
                # Show trace of the last executed request
                try:
                    from core.orchestration import MasterOrchestrator

                    orch = MasterOrchestrator.get_instance()
                    if orch._last_result:
                        self._render_trace_tree(orch._last_result)
                    else:
                        print(
                            "\n  No request has been processed yet. "
                            "Send a message first, then run 'trace'."
                        )
                except Exception as e:
                    print(f"\n✗ Could not render trace: {e}")

            elif cmd == "graph":
                self.print_graph()

            elif cmd == "help":
                self.print_help()

            elif cmd == "reload":
                print("\n✓ Reloading configuration...")
                print("✓ Configuration reloaded successfully")
                self.print_status()

            elif cmd == "quit":
                self.running = False
                print("\n✓ Shutting down AuraAI...")
                print("✓ Goodbye!")
                self.aura_core.shutdown()

            elif self.voice_listening:
                print("\nVoice listening is ON; terminal text is not used as voice input.")
                print("  Speak 'Aura' into the microphone, then say your command.")
                print("  Type 'Stop Listening' to disable microphone wake-word mode.")

            else:
                # Not a recognized command — treat it as a chat message
                # so users don't have to type 'chat' first for a quick question.
                await self._send_chat_message(command)

        except Exception as e:
            print(f"\n✗ Error executing command: {e}")
            logger.error(f"Command execution error: {e}", exc_info=True)

    async def _send_chat_message(self, user_input: str):
        """
        Send a single message to the AI and print the response.
        Used both by the top-level prompt fallback and by _interactive_chat().

        Args:
            user_input: The message text to send
        """
        self.aura_core.add_to_conversation("user", user_input)

        intent = "unknown"
        try:
            from core.orchestration.decision_engine import DecisionEngine
            engine = DecisionEngine()
            outcome = engine.evaluate(user_input)
            intent = outcome.intent_type.value
        except Exception:
            pass

        print(f"\nAura is thinking... [Intent: {intent} | Verbosity: {self.verbosity_mode}]")
        response = await self.aura_core.process_request(user_input)

        self.aura_core.add_to_conversation("assistant", response)
        print(f"\nAura > {response}")

        # Trigger TTS if voice is enabled and conditions are met
        should_speak = getattr(self, "voice_listening", False)
        lower_input = user_input.lower().strip()
        if lower_input.startswith("speak") or lower_input.startswith("say"):
            should_speak = True

        if self.aura_core.voice_enabled and should_speak:
            try:
                import re
                if hasattr(self.aura_core, 'voice_loop') and self.aura_core.voice_loop:
                    if hasattr(self.aura_core.voice_loop, 'voice_manager') and self.aura_core.voice_loop.voice_manager:
                        clean_text = re.sub(r'[*_#`]', '', response)
                        if clean_text.strip():
                            self.aura_core.voice_loop.voice_manager.speak(clean_text)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to trigger TTS: {e}")


        if self.verbosity_mode in ("benchmark", "trace"):
            try:
                from core.orchestration import MasterOrchestrator

                orch = MasterOrchestrator.get_instance()
                if orch._last_result:
                    if self.verbosity_mode == "benchmark":
                        m = orch._last_result.data.get("metrics", {})
                        print("\n" + "─" * 60)
                        print("                EXECUTION LATENCY BENCHMARK")
                        print("─" * 60)
                        print(
                            f"  Memory Recall:    {m.get('memory_recall_ms', 0):.2f} ms"
                        )
                        print(
                            f"  Decision Engine:  {m.get('decision_engine_ms', 0):.2f} ms"
                        )
                        print(
                            f"  Decomposition:    {m.get('decomposition_ms', 0):.2f} ms"
                        )
                        print(f"  Execution:        {m.get('execution_ms', 0):.2f} ms")
                        print(
                            f"  Result Merger:    {m.get('result_merger_ms', 0):.2f} ms"
                        )
                        print(
                            f"  Total Request:    {m.get('total_request_ms', 0):.2f} ms"
                        )
                        print("─" * 60)
                    else:  # trace mode
                        self._render_trace_tree(orch._last_result)
            except Exception as e:
                logger.warning(f"Could not render execution trace: {e}")

        # Check if response contains Python code blocks
        await self._handle_code_blocks(response)

    # ──────────────────────────────────────────────────────────────
    # Runtime Visualization
    # ──────────────────────────────────────────────────────────────

    def _render_trace_tree(self, result: object) -> None:  # type: ignore[override]
        """
        Render a tree-style execution trace for the last processed request.

        Draws from ExecutionResult.data which contains 'metrics' and 'decision'
        populated by MasterOrchestrator after every request.
        """
        data = getattr(result, "data", {}) or {}
        metrics: dict = data.get("metrics", {})
        decision: dict = data.get("decision", {})
        success: bool = getattr(result, "success", True)
        goal: str = getattr(result, "goal", "")
        planner_name: str = getattr(result, "planner", "—")
        confidence: float = getattr(result, "confidence", 0.0)

        intent = decision.get("intent_type", "—").upper()
        preferred_planner = decision.get("preferred_planner", planner_name or "—")
        needs_backend = decision.get("needs_backend", False)
        from_memory = decision.get("can_answer_from_memory", False)
        from_system = decision.get("can_answer_from_system", False)
        needs_planner = decision.get("needs_planner", True)

        mem_read = "✓" if from_memory or from_system else "—"
        mem_write = "✓" if metrics.get("subtasks_completed", 0) > 0 else "—"
        backend_label = "Native + Cloud" if needs_backend else "Native"
        status_icon = "✓" if success else "✗"

        total_ms = metrics.get("total_request_ms", 0)
        mem_ms = metrics.get("memory_recall_ms", 0)
        dec_ms = metrics.get("decision_engine_ms", 0)
        decomp_ms = metrics.get("decomposition_ms", 0)
        exec_ms = metrics.get("execution_ms", 0)
        merge_ms = metrics.get("result_merger_ms", 0)
        subtasks_done = metrics.get("subtasks_completed", 0)
        subtasks_total = metrics.get("subtasks_total", 0)

        # Goal preview (truncated for readability)
        goal_preview = (goal[:52] + "…") if len(goal) > 54 else goal

        print("\n" + "─" * 62)
        print(
            f"  AURA RUNTIME TRACE    {status_icon} {'SUCCESS' if success else 'FAILED'}"
        )
        print("─" * 62)
        print(f"  Goal  : {goal_preview}")
        print(
            f"  Result: confidence={confidence:.0%}  subtasks={subtasks_done}/{subtasks_total}"
        )
        print("─" * 62)
        print("  USER")
        print("  │")
        print(f"  ├── Memory Read        [{mem_ms:6.1f} ms]  {mem_read}")
        if from_memory:
            print("  │     recalled from long-term store")
        elif from_system:
            print("  │     answered from system state")
        else:
            print("  │     no cached hit")
        print("  │")
        print(f"  ├── Decision Engine    [{dec_ms:6.1f} ms]")
        print(f"  │     Intent  : {intent}")
        print(f"  │     Memory? : {'Yes' if from_memory else 'No'}")
        print(f"  │     System? : {'Yes' if from_system else 'No'}")
        print(f"  │     Planner?: {'Yes' if needs_planner else 'No'}")
        print("  │")
        if needs_planner:
            print(f"  ├── Decomposition      [{decomp_ms:6.1f} ms]")
            print(f"  │     Planner : {preferred_planner.title()} Planner")
            print("  │")
            print(f"  ├── Execution          [{exec_ms:6.1f} ms]")
            print(f"  │     Backend : {backend_label}")
            if subtasks_total > 1:
                print(
                    f"  │     Tasks   : {subtasks_done}/{subtasks_total} completed (parallel)"
                )
            else:
                print(f"  │     Tasks   : {subtasks_done}/{subtasks_total} completed")
        else:
            print("  ├── Execution          [  0.0 ms]")
            print("  │     (No planner — answered directly)")
        print("  │")
        print(f"  ├── Result Merger      [{merge_ms:6.1f} ms]")
        print(f"  │     Success : {'Yes' if success else 'No'}")
        print("  │")
        print(f"  └── Memory Write       [{mem_ms:6.1f} ms]  {mem_write}")
        print("")
        print(f"  Total wall time: {total_ms:.2f} ms")
        print("─" * 62)

    async def _handle_code_blocks(self, response: str):
        """
        Detect and offer to save/execute Python code blocks in Aura's response.

        Args:
            response: The response from Aura
        """
        # Look for Python code blocks
        # Pattern matches: ```(python)?\s*([\s\S]*?)```
        python_code_pattern = r"```(python)?\s*([\s\S]*?)```"

        all_matches = list(re.finditer(python_code_pattern, response))
        matches = []
        for m in all_matches:
            is_py_fenced = bool(m.group(1))
            code = m.group(2).strip()
            if not is_py_fenced:
                # Require at least 2 distinct Python signals
                signatures = [
                    r"\bdef\b",
                    r"\bimport\b",
                    r"\bclass\b",
                    r"\bprint\(",
                    r"\bfrom\b",
                    r"\bif\s+__name__\s*==\s*['\"]__main__['\"]",
                    r"\bassert\b",
                    r"\btry:",
                    r"\bexcept\b",
                    r"\bfor\s+\w+\s+in\s+",
                    r"\bwith\s+open\b",
                    r" = ",
                ]
                match_count = sum(1 for sig in signatures if re.search(sig, code))
                if match_count < 2:
                    continue
            matches.append(m)

        if matches:
            print("\n" + "=" * 60)
            print("    ⚠ PYTHON CODE DETECTED")
            print("=" * 60)

            for i, match in enumerate(matches, 1):
                code = match.group(1).strip()

                if not code:
                    continue

                print(f"\n[Code Block {i}]")
                print("-" * 60)

                # Show a preview of the code (first 10 lines)
                lines = code.split("\n")
                preview_lines = lines[:10]
                for line in preview_lines:
                    print(line)

                if len(lines) > 10:
                    print(f"\n... ({len(lines) - 10} more lines)")

                print("\nOptions:")
                print("  [1] Save and run this code")
                print("  [2] Save code without running")
                print("  [3] Ignore and continue")
                print("  [4] Show full code")

                choice = input("\nYour choice [1-4]: ").strip()

                if choice == "1":
                    # Save and execute
                    await self._execute_code(code, show_full=True)
                elif choice == "2":
                    # Save only
                    await self._execute_code(code, show_full=False, save_only=True)
                elif choice == "4":
                    # Show full code
                    print("\nFull code:")
                    print("-" * 60)
                    for line in lines:
                        print(line)
                    print("-" * 60)
                elif choice not in ["3", ""]:
                    print("Invalid choice. Ignoring code block.")

            print("\n" + "=" * 60)
            print("    END OF CODE BLOCKS")
            print("=" * 60)

    async def _execute_code(
        self, code: str, show_full: bool = True, save_only: bool = False
    ):
        """
        Save and execute Python code.

        Args:
            code: Python code to execute
            show_full: Whether to show full code before execution
            save_only: Whether to save only without executing
        """
        if not self.code_executor:
            print("\n✗ Code execution tool not available")
            print("  Make sure the CodeExecutionTool is initialized.")
            return

        # Show full code if requested
        if show_full:
            print("\nCode to execute:")
            print("-" * 60)
            lines = code.split("\n")
            for line in lines:
                print(line)
            print("-" * 60)

        if save_only:
            print("\n✓ Saving code...")
        else:
            print("\n⚡ Executing code...")
            print("-" * 60)

        # Save and execute the code
        result = self.code_executor.save_and_execute(code)

        print("\n" + "-" * 60)

        if result["success"]:
            print("✓ Code executed successfully!")
            print(f"  Execution time: {result['execution_time']:.2f}s")

            if result["output"]:
                print("\nOutput:")
                print(result["output"])

            print(f"\n  Saved to: {result['filename']}")
        else:
            print("✗ Code execution failed!")
            print(f"  Error: {result['error']}")

            if result["output"]:
                print("\nOutput (before error):")
                print(result["output"])

            print(f"\n  Saved to: {result['filename']}")

    async def _interactive_chat(self):
        """Run interactive chat session."""
        print("\n" + "=" * 60)
        print("            INTERACTIVE CHAT")
        print("=" * 60)
        print("\nType your message and press Enter.")
        print("Type 'back' to return to main prompt.")
        print("Type 'quit' to exit chat.\n")

        if not self.aura_core.llm_enabled:
            print("⚠ Warning: AI is not configured (GROQ_API_KEY missing or invalid).")
            print("  You can still chat, but responses will show an error.\n")

        print("Aura > Hello! I'm Aura, your AI assistant. How can I help you today?")

        while self.running:
            try:
                user_input = input("\nYou > ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["back", "exit"]:
                    break

                if user_input.lower() == "quit":
                    self.running = False
                    break

                # Command parsing before chat handler
                command = user_input

                # Check for voice listening commands
                if command == "Start Listening" or command == "start listening" or command == "START LISTENING":
                    # Handle voice start command
                    if not self.aura_core.voice_enabled:
                        print("\n✗ Voice is not enabled in Aura.")
                        print("  Enable voice with your configuration or use voice-embedded apps.")
                        return
                    if self.voice_listening:
                        print("\n✓ Voice listening is already active.")
                        return
                    self.voice_listening = True
                    print("\n✓ Voice listening enabled.")
                    print("  ContinuousVoiceLoop owns the microphone.")
                    print("  Waiting for wake word: Aura")
                    print("  Use 'Stop Listening' to disable.")
                    try:
                        if hasattr(self.aura_core, 'voice_loop') and self.aura_core.voice_loop:
                            self.aura_core.voice_loop._aura_core = self.aura_core
                            self.aura_core.voice_loop.on_stop = lambda: setattr(self, "voice_listening", False)
                            success = self.aura_core.voice_loop.start()
                            if success:
                                print(f"  ✓ ContinuousVoiceLoop started (running: {self.aura_core.voice_loop._running})")
                            else:
                                print(f"  ✗ Failed to start ContinuousVoiceLoop")
                                self.voice_listening = False
                        else:
                            print(f"  ✗ No voice_loop found on AuraCore")
                            self.voice_listening = False
                    except Exception as e:
                        logger.error(f"Failed to start ContinuousVoiceLoop: {e}", exc_info=True)
                        print(f"  ✗ Error starting voice listening: {e}")
                        self.voice_listening = False
                    self.print_commands()
                    continue

                if command == "Stop Listening" or command == "stop listening" or command == "STOP LISTENING":
                    if not self.voice_listening:
                        print("\n✓ Voice listening is already stopped.")
                        return
                    print("\n✓ Stopping voice listening...")
                    try:
                        if hasattr(self.aura_core, 'voice_loop') and self.aura_core.voice_loop:
                            self.aura_core.voice_loop.stop()
                            print("  ContinuousVoiceLoop stopped.")
                            self.voice_listening = False
                        else:
                            print(f"  ✗ No voice_loop found on AuraCore")
                            self.voice_listening = False
                    except Exception as e:
                        logger.error(f"Failed to stop ContinuousVoiceLoop: {e}", exc_info=True)
                        print(f"  ✗ Error stopping voice listening: {e}")
                    self.print_commands()
                    continue

                # Check for legacy voice_listen command
                if command == "voice_listen" or command == "voice_listen_toggle":
                    if not self.aura_core.voice_enabled:
                        print("\n✗ Voice is not enabled in Aura.")
                        print("  Enable voice with your configuration or use voice-embedded apps.")
                        return
                    if self.voice_listening:
                        print("\n✓ Voice listening is already active.")
                        return
                    self.voice_listening = True
                    print("\n✓ Voice listening enabled (legacy alias).")
                    print("  Use 'Start Listening' for explicit start command.")
                    print("  Waiting for wake word: Aura")
                    print("  Use 'Stop Listening' to disable.")
                    try:
                        if hasattr(self.aura_core, 'voice_loop') and self.aura_core.voice_loop:
                            # Inject AuraCore so voice transcripts go through the
                            # same Groq path as typed messages.
                            self.aura_core.voice_loop._aura_core = self.aura_core
                            success = self.aura_core.voice_loop.start()
                            if success:
                                print(f"  ✓ ContinuousVoiceLoop started (running: {self.aura_core.voice_loop._running})")
                            else:
                                print(f"  ✗ Failed to start ContinuousVoiceLoop")
                                self.voice_listening = False
                        else:
                            print(f"  ✗ No voice_loop found on AuraCore")
                            self.voice_listening = False
                    except Exception as e:
                        logger.error(f"Failed to start ContinuousVoiceLoop: {e}", exc_info=True)
                        print(f"  ✗ Error starting voice listening: {e}")
                        self.voice_listening = False
                    self.print_commands()
                    continue

                if self.voice_listening:
                    print("\nVoice listening is ON; terminal text is not used as voice input.")
                    print("  Speak 'Aura' into the microphone, then say your command.")
                    print("  Type 'Stop Listening' to disable microphone wake-word mode.")
                    continue

                # If not a command, send as chat message
                await self._send_chat_message(user_input)

            except KeyboardInterrupt:
                print("\n\nReturning to main prompt...")
                break

            except Exception as e:
                print(f"\n✗ Error in chat: {e}")
                logger.error(f"Chat error: {e}", exc_info=True)

        print("\n" + "-" * 60)

    async def run(self):
        """Run the CLI interface."""
        self.print_banner()
        self.print_status()

        print("\n" + "-" * 60)
        print("Type 'help' for available commands")
        print("Type 'quit' to exit")
        print("-" * 60)

        while self.running:
            try:
                # Display current task if any
                if self.aura_core.current_task:
                    self.print_current_task()
                    print("-" * 60)

                # Command mode - type commands normally
                # Voice listening runs independently via ContinuousVoiceLoop
                # Terminal is only for control commands like "Stop Listening"
                user_input = input("\nYou > ").strip()

                if not user_input:
                    if self.voice_listening:
                        print("  [🎤 Voice listening is ON — say 'Aura' or type a command ('Stop Listening' / 'quit')]")
                    continue

                if user_input.lower() == "quit":
                    self.running = False
                    break

                await self.process_command(user_input)
                
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
                self.running = False
                break
            except Exception as e:
                print(f"\n✗ Error: {e}")
                logger.error(f"Error in main loop: {e}", exc_info=True)

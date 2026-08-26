"""
Aura Application - Multi-Agent System Integration

This module integrates the AuraAI multi-agent system with the application.
"""

import sys
from pathlib import Path

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Python 3.7+
except Exception:
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


from core import logger


def create_app():
    """
    Create and configure the Aura Application with multi-agent system.

    This function initializes:
    - Event Bus for communication
    - Context Manager for agent context allocation
    - Agent Orchestration System (multi-agent coordination)
    - Agent Registry for agent management
    - Specialized agents (Networking, Security, Documentation)

    Returns:
        AuraApplication instance with full agent system integration
    """
    logger.info("Initializing AuraAI with Multi-Agent System...")

    # Step 1: Initialize Event Bus
    from core.event_bus import EventBus

    event_bus = EventBus()
    logger.info("✓ Event Bus initialized")

    # Step 2: Initialize Context Manager
    from agents.agent_context import AGENT_CONTEXT_REQUIREMENTS, ContextManager

    context_manager = ContextManager(event_bus)
    logger.info("✓ Context Manager initialized")
    logger.info(
        f"  - Predefined context requirements loaded: {len(AGENT_CONTEXT_REQUIREMENTS)} types"
    )

    # Step 3: Initialize Agent Registry
    from agents.base_agent import AgentRegistry

    agent_registry = AgentRegistry(event_bus)
    logger.info("✓ Agent Registry initialized")

    # Step 4: Initialize Agent Orchestration System
    from agents.orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator(
        agent_registry=agent_registry,
        context_manager=context_manager,
        mode="COLLABORATIVE",
    )
    logger.info("✓ Agent Orchestration System initialized")
    logger.info(f"  - Orchestration mode: {orchestrator.mode}")

    # Step 5: Register special agents
    logger.info("  - Registering specialized agents...")

    # Create security plugin (mock for demonstration)
    class SecurityPlugin:
        """Mock security plugin for demonstration."""

        pass

    # Register Security Agent
    security_plugin = SecurityPlugin()
    from agents.security.security_agent import SecurityAgent

    security_agent = SecurityAgent(config={"security_plugin": security_plugin})
    agent_registry.register_agent(security_agent)
    logger.info("    ✓ Security Agent registered")

    # Create networking plugin (mock)
    class NetworkingPlugin:
        """Mock networking plugin for demonstration."""

        pass

    # Register Networking Agent
    networking_plugin = NetworkingPlugin()
    from agents.networking.networking_agent import NetworkingAgent

    networking_agent = NetworkingAgent(config={"network_plugin": networking_plugin})
    agent_registry.register_agent(networking_agent)
    logger.info("    ✓ Networking Agent registered")

    # Create documentation plugin (mock)
    class DocumentationPlugin:
        """Mock documentation plugin for demonstration."""

        pass

    # Register Documentation Agent
    doc_plugin = DocumentationPlugin()
    from agents.documentation.documentation_agent import DocumentationAgent

    doc_agent = DocumentationAgent(config={"doc_plugin": doc_plugin})
    agent_registry.register_agent(doc_agent)
    logger.info("    ✓ Documentation Agent registered")

    # Step 6: Initialize Routing System
    from agents.routing import RoutingSystem

    routing_system = RoutingSystem(
        agent_registry=agent_registry, strategy="CAPABILITY_MATCH", mode="DIRECT"
    )
    logger.info("✓ Routing System initialized")
    logger.info(f"  - Routing strategy: {routing_system.strategy}")
    logger.info(f"  - Routing mode: {routing_system.mode}")

    # Step 7: Initialize Collaboration System
    from agents.collaboration import CollaborationSystem

    collaboration_system = CollaborationSystem(event_bus)
    logger.info("✓ Collaboration System initialized")

    # Step 8: Create Aura Application

    class AuraApplication:
        """
        Main AuraAI Application with integrated Multi-Agent System.

        This application coordinates specialized agents that work together
        to complete complex tasks. Each agent has a specialized domain
        and can collaborate with others to achieve comprehensive results.
        """

        def __init__(self):
            """Initialize AuraAI with all components."""
            self.event_bus = event_bus
            self.context_manager = context_manager
            self.agent_registry = agent_registry
            self.orchestrator = orchestrator
            self.routing_system = routing_system
            self.collaboration_system = collaboration_system

            logger.info("AuraAI Application initialized successfully!")

            # Log agent registry information
            logger.info(
                f"  - Total registered agents: {agent_registry.get_agent_count()}"
            )
            logger.info(
                f"  - Available agent types: {', '.join(agent_registry.get_available_agent_types())}"
            )

        async def coordinate_multi_agent_task(
            self, task: dict, options: dict = None
        ) -> dict:
            """
            Coordinate a task across multiple specialized agents.

            Args:
                task: Task dictionary with task_type and data
                options: Optional configuration for coordination

            Returns:
                Orchestration result with merged agent outputs

            Example:
                >>> result = await app.coordinate_multi_agent_task(
                ...     task={
                ...         "task_type": "assess_security_risk",
                ...         "data": {"context": {...}}
                ...     }
                ... )
            """
            if options is None:
                options = {}

            logger.info(f"Coordinating task: {task.get('task_type', 'unknown')}")

            # Route task to appropriate agent(s)
            routing_result = self.routing_system.route_task(task, options)

            if routing_result.success:
                logger.info(f"  - Task routed to: {routing_result.agent_type}")

                # Execute task through orchestrator
                orchestration_result = await self.orchestrator.coordinate_task(
                    task, options
                )

                # Combine with routing information
                result = {
                    "success": orchestration_result.success,
                    "summary": orchestration_result.summary,
                    "agent_type": routing_result.agent_type,
                    "result": orchestration_result.data,
                }

                logger.info(
                    f"  - Task completed with status: {orchestration_result.success}"
                )
                return result
            else:
                logger.warning(f"  - Task routing failed: {routing_result.error}")
                return {
                    "success": False,
                    "error": routing_result.error,
                    "agent_type": None,
                }

        async def generate_readme(self, project_data: dict) -> dict:
            """
            Generate README documentation using Documentation Agent.

            Args:
                project_data: Project information for README

            Returns:
                Generation result
            """
            task = {"task_type": "generate_readme", "data": project_data}
            return await self.coordinate_multi_agent_task(task)

        async def generate_api_docs(self, api_data: dict) -> dict:
            """
            Generate API documentation using Documentation Agent.

            Args:
                api_data: API information for documentation

            Returns:
                Generation result
            """
            task = {"task_type": "generate_api_docs", "data": api_data}
            return await self.coordinate_multi_agent_task(task)

        async def audit_security(self, security_data: dict) -> dict:
            """
            Perform security audit using Security Agent.

            Args:
                security_data: Security information for audit

            Returns:
                Audit result
            """
            task = {"task_type": "assess_security_risk", "data": security_data}
            return await self.coordinate_multi_agent_task(task)

        async def analyze_network(self, network_data: dict) -> dict:
            """
            Analyze network configuration using Networking Agent.

            Args:
                network_data: Network information for analysis

            Returns:
                Analysis result
            """
            task = {"task_type": "analyze_network_configuration", "data": network_data}
            return await self.coordinate_multi_agent_task(task)

        def get_agent_info(self) -> dict:
            """
            Get information about registered agents.

            Returns:
                Dictionary with agent information
            """
            return {
                "total_agents": self.agent_registry.get_agent_count(),
                "available_types": self.agent_registry.get_available_agent_types(),
                "context_types": list(AGENT_CONTEXT_REQUIREMENTS.keys()),
                "orchestrator_mode": self.orchestrator.mode,
                "routing_strategy": self.routing_system.strategy,
                "collaboration_mode": self.collaboration_system.mode,
            }

        async def run(self):
            """Run the AuraAI application."""
            logger.info("\n" + "=" * 60)
            logger.info("AuraAI Multi-Agent System Running")
            logger.info("=" * 60)

            # Display agent information
            agent_info = self.get_agent_info()
            logger.info(f"\nRegistered Agents: {agent_info['total_agents']}")
            logger.info(f"Available Types: {', '.join(agent_info['available_types'])}")
            logger.info(f"Context Types: {len(agent_info['context_types'])}")
            logger.info(f"Orchestration Mode: {agent_info['orchestrator_mode']}")
            logger.info(f"Routing Strategy: {agent_info['routing_strategy']}")
            logger.info(f"Collaboration Mode: {agent_info['collaboration_mode']}")

            logger.info("\n" + "-" * 60)
            logger.info("Multi-Agent System Ready")
            logger.info("-" * 60 + "\n")

            return True

    # Create and return the application
    app = AuraApplication()

    logger.info("\n" + "=" * 60)
    logger.info("AuraAI Multi-Agent System Initialized")
    logger.info("=" * 60)
    logger.info("\n✓ Event Bus: Ready")
    logger.info("✓ Context Manager: Ready")
    logger.info("✓ Agent Registry: Ready")
    logger.info("✓ Agent Orchestration: Ready")
    logger.info("✓ Routing System: Ready")
    logger.info("✓ Collaboration System: Ready")
    logger.info("✓ Specialized Agents: Ready")
    logger.info("\n" + "=" * 60 + "\n")

    return app


# Optional: Main execution entry point for testing
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("AuraAI Multi-Agent System - Entry Point")
    print("=" * 60 + "\n")

    # Create application
    app = create_app()

    # Run the application
    import asyncio

    async def main():
        result = await app.run()
        return result

    asyncio.run(main())

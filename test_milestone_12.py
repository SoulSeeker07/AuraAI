"""
Multi-Agent System Test Suite for Milestone 12

This test file validates the AuraAI Multi-Agent System implementation,
testing:
- Agent initialization and registration
- Context allocation and filtering
- Task routing strategies
- Agent orchestration and coordination
- Result merging and collaboration
- Specialized agent capabilities
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from core.event_bus import EventBus
from agents.base_agent import AgentRegistry, AgentState
from agents.agent_context import ContextManager, AGENT_CONTEXT_REQUIREMENTS
from agents.orchestrator import AgentOrchestrator, OrchestrationMode
from agents.routing import RoutingSystem, RoutingStrategy, RoutingMode
from agents.collaboration import CollaborationSystem
from agents.security.security_agent import SecurityAgent
from agents.networking.networking_agent import NetworkingAgent
from agents.documentation.documentation_agent import DocumentationAgent


class TestResults:
    """Track test results."""
    
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.errors = []
    
    def add_test(self, name: str, passed: bool, error: str = None):
        """Add a test result."""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"✓ {name}")
        else:
            self.failed_tests += 1
            error_msg = f"✗ {name}: {error}"
            self.errors.append(error_msg)
            print(error_msg)


# Initialize test results
results = TestResults()


async def test_agent_initialization():
    """Test 1: Agent initialization and registration."""
    print("\n=== Test 1: Agent Initialization ===")
    
    # Create event bus
    event_bus = EventBus()
    
    # Create security agent
    security_agent = SecurityAgent()
    await security_agent.initialize()
    
    # Register agent
    registry = AgentRegistry(event_bus)
    registry.register_agent(security_agent)
    
    # Verify registration
    agent_info = registry.get_agent_info()
    
    test1_1 = agent_info.get("security") is not None
    results.add_test(
        "Security agent registered successfully",
        test1_1
    )
    
    # Create networking agent
    networking_agent = NetworkingAgent()
    await networking_agent.initialize()
    registry.register_agent(networking_agent)
    
    test1_2 = registry.get_agent_count() == 2
    results.add_test(
        "Two agents registered successfully",
        test1_2
    )
    
    # Test cleanup
    await security_agent.cleanup()
    await networking_agent.cleanup()


async def test_context_allocation():
    """Test 2: Context allocation and filtering."""
    print("\n=== Test 2: Context Allocation ===")
    
    event_bus = EventBus()
    
    # Create context manager
    context_manager = ContextManager(event_bus)
    
    # Test context allocation for different agent types
    test2_1 = True
    
    for agent_type, requirements in AGENT_CONTEXT_REQUIREMENTS.items():
        context = context_manager.allocate_context(
            agent_type=agent_type,
            requirements=requirements
        )
        
        test_passed = context and len(context) > 0
        test2_1 = test2_1 and test_passed
        results.add_test(
            f"Context allocated for {agent_type}",
            test_passed
        )
    
    # Test context filtering
    agent_context = context_manager.allocate_context(
        agent_type="security",
        requirements=["permissions", "credentials"]
    )
    
    test2_2 = "permissions" in str(agent_context)
    results.add_test(
        "Context filtering works correctly",
        test2_2
    )


async def test_routing_system():
    """Test 3: Task routing system."""
    print("\n=== Test 3: Routing System ===")
    
    event_bus = EventBus()
    registry = AgentRegistry(event_bus)
    
    # Register agents
    security_agent = SecurityAgent()
    await security_agent.initialize()
    registry.register_agent(security_agent)
    
    networking_agent = NetworkingAgent()
    await networking_agent.initialize()
    registry.register_agent(networking_agent)
    
    # Create routing system
    routing_system = RoutingSystem(
        agent_registry=registry,
        strategy=RoutingStrategy.CAPABILITY_MATCH,
        mode=RoutingMode.DIRECT
    )
    
    # Test routing
    test3_1 = routing_system.strategy == RoutingStrategy.CAPABILITY_MATCH
    results.add_test(
        "Routing system initialized with CAPABILITY_MATCH",
        test3_1
    )
    
    # Route a security task
    security_task = {
        "task_type": "assess_security_risk",
        "data": {"context": {}}
    }
    
    routing_result = routing_system.route_task(security_task, {})
    
    test3_2 = routing_result.success
    results.add_test(
        "Security task routed successfully",
        test3_2
    )
    
    test3_3 = "security" in routing_result.agent_type.lower()
    results.add_test(
        "Correct agent type selected",
        test3_3
    )
    
    # Cleanup
    await security_agent.cleanup()
    await networking_agent.cleanup()


async def test_orchestration():
    """Test 4: Agent orchestration and coordination."""
    print("\n=== Test 4: Agent Orchestration ===")
    
    event_bus = EventBus()
    
    # Create registry and agents
    registry = AgentRegistry(event_bus)
    security_agent = SecurityAgent()
    await security_agent.initialize()
    registry.register_agent(security_agent)
    
    # Create orchestrator
    orchestrator = AgentOrchestrator(
        agent_registry=registry,
        context_manager=ContextManager(event_bus),
        mode=OrchestrationMode.COLLABORATIVE
    )
    
    test4_1 = orchestrator.mode == OrchestrationMode.COLLABORATIVE
    results.add_test(
        "Orchestrator initialized with COLLABORATIVE mode",
        test4_1
    )
    
    # Execute a security task
    security_task = {
        "task_type": "assess_security_risk",
        "data": {
            "context": {
                "vulnerabilities": [],
                "threats": []
            }
        }
    }
    
    orchestration_result = await orchestrator.coordinate_task(security_task, {})
    
    test4_2 = orchestration_result.success
    results.add_test(
        "Security task executed successfully",
        test4_2
    )
    
    test4_3 = orchestration_result.summary and len(orchestration_result.summary) > 0
    results.add_test(
        "Orchestration returned valid summary",
        test4_3
    )
    
    test4_4 = orchestration_result.data and "risk_score" in orchestration_result.data
    results.add_test(
        "Orchestration returned execution data",
        test4_4
    )
    
    # Cleanup
    await security_agent.cleanup()


async def test_result_merging():
    """Test 5: Result merging and collaboration."""
    print("\n=== Test 5: Result Merging ===")
    
    event_bus = EventBus()
    collaboration_system = CollaborationSystem(event_bus)
    
    # Create test results from different agents
    result1 = {
        "success": True,
        "summary": "Security assessment complete",
        "data": {"risk_score": 65, "vulnerabilities": 2}
    }
    
    result2 = {
        "success": True,
        "summary": "Network analysis complete",
        "data": {"network_status": "operational", "issues": 1}
    }
    
    result3 = {
        "success": True,
        "summary": "Documentation generation complete",
        "data": {"readme_length": 500, "sections": 8}
    }
    
    # Merge results
    merged = collaboration_system.merge_agent_results([result1, result2, result3])
    
    test5_1 = merged["success"]
    results.add_test(
        "Results merging successful",
        test5_1
    )
    
    test5_2 = merged["summary"] and len(merged["summary"]) > 0
    results.add_test(
        "Merged result has summary",
        test5_2
    )
    
    test5_3 = "combined" in merged["summary"].lower() or "consolidated" in merged["summary"].lower()
    results.add_test(
        "Merged result mentions combination",
        test5_3
    )
    
    test5_4 = len(merged["data"]) == 3
    results.add_test(
        "Merged result contains all agent outputs",
        test5_4
    )


async def test_specialized_agents():
    """Test 6: Specialized agent capabilities."""
    print("\n=== Test 6: Specialized Agent Capabilities ===")
    
    event_bus = EventBus()
    registry = AgentRegistry(event_bus)
    
    # Test Security Agent
    security_agent = SecurityAgent()
    await security_agent.initialize()
    registry.register_agent(security_agent)
    
    security_info = registry.get_agent_info()
    security_capabilities = security_agent.capabilities.tasks
    
    test6_1 = "assess_security_risk" in security_capabilities
    results.add_test(
        "Security Agent has risk assessment capability",
        test6_1
    )
    
    test6_2 = "review_user_permissions" in security_capabilities
    results.add_test(
        "Security Agent has permission review capability",
        test6_2
    )
    
    test6_3 = security_agent.capabilities.priority == 95
    results.add_test(
        "Security Agent has high priority",
        test6_3
    )
    
    # Test Networking Agent
    networking_agent = NetworkingAgent()
    await networking_agent.initialize()
    registry.register_agent(networking_agent)
    
    networking_capabilities = networking_agent.capabilities.tasks
    
    test6_4 = "analyze_network_configuration" in networking_capabilities
    results.add_test(
        "Networking Agent has configuration analysis capability",
        test6_4
    )
    
    test6_5 = "analyze_routing_protocols" in networking_capabilities
    results.add_test(
        "Networking Agent has routing protocol capability",
        test6_5
    )
    
    test6_6 = networking_agent.capabilities.priority == 90
    results.add_test(
        "Networking Agent has priority 90",
        test6_6
    )
    
    # Test Documentation Agent
    doc_agent = DocumentationAgent()
    await doc_agent.initialize()
    registry.register_agent(doc_agent)
    
    doc_capabilities = doc_agent.capabilities.tasks
    
    test6_7 = "generate_readme" in doc_capabilities
    results.add_test(
        "Documentation Agent has README generation capability",
        test6_7
    )
    
    test6_8 = "generate_api_docs" in doc_capabilities
    results.add_test(
        "Documentation Agent has API documentation capability",
        test6_8
    )
    
    test6_9 = doc_agent.capabilities.priority == 70
    results.add_test(
        "Documentation Agent has priority 70",
        test6_9
    )
    
    # Cleanup
    await security_agent.cleanup()
    await networking_agent.cleanup()
    await doc_agent.cleanup()


async def test_full_integration():
    """Test 7: Full multi-agent system integration."""
    print("\n=== Test 7: Full Integration ===")
    
    try:
        # Create all components
        event_bus = EventBus()
        registry = AgentRegistry(event_bus)
        
        security_agent = SecurityAgent()
        await security_agent.initialize()
        registry.register_agent(security_agent)
        
        networking_agent = NetworkingAgent()
        await networking_agent.initialize()
        registry.register_agent(networking_agent)
        
        doc_agent = DocumentationAgent()
        await doc_agent.initialize()
        registry.register_agent(doc_agent)
        
        context_manager = ContextManager(event_bus)
        orchestrator = AgentOrchestrator(
            agent_registry=registry,
            context_manager=context_manager,
            mode=OrchestrationMode.COLLABORATIVE
        )
        
        routing_system = RoutingSystem(
            agent_registry=registry,
            strategy=RoutingStrategy.CAPABILITY_MATCH,
            mode=RoutingMode.DIRECT
        )
        
        collaboration_system = CollaborationSystem(event_bus)
        
        # Test agent info
        agent_info = orchestrator.get_agent_info()
        test7_1 = agent_info and len(agent_info) > 0
        results.add_test(
            "Orchestrator has agent information",
            test7_1
        )
        
        # Test multiple routing attempts
        tasks = [
            {"task_type": "assess_security_risk", "data": {"context": {}}},
            {"task_type": "analyze_network_configuration", "data": {"configuration": ""}},
            {"task_type": "generate_readme", "data": {"project": {"name": "Test"}}}
        ]
        
        successful_routes = 0
        for task in tasks:
            result = routing_system.route_task(task, {})
            if result.success:
                successful_routes += 1
        
        test7_2 = successful_routes >= 2
        results.add_test(
            f"{successful_routes}/3 tasks routed successfully",
            test7_2
        )
        
        # Test security task execution
        security_task = {
            "task_type": "assess_security_risk",
            "data": {"context": {"vulnerabilities": [], "threats": []}}
        }
        
        orchestration_result = await orchestrator.coordinate_task(security_task, {})
        test7_3 = orchestration_result.success
        results.add_test(
            "Full orchestration cycle works",
            test7_3
        )
        
        # Cleanup
        await security_agent.cleanup()
        await networking_agent.cleanup()
        await doc_agent.cleanup()
        
    except Exception as e:
        results.add_test(
            "Full integration test",
            False,
            str(e)
        )


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AuraAI Multi-Agent System - Test Suite")
    print("Milestone 12 Validation")
    print("="*60)
    
    try:
        await test_agent_initialization()
        await test_context_allocation()
        await test_routing_system()
        await test_orchestration()
        await test_result_merging()
        await test_specialized_agents()
        await test_full_integration()
        
        # Print summary
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        print(f"Total Tests: {results.total_tests}")
        print(f"Passed: {results.passed_tests}")
        print(f"Failed: {results.failed_tests}")
        print(f"Success Rate: {(results.passed_results / results.total_results if results.total_results > 0 else 0):.1%}")
        
        if results.errors:
            print("\nFailed Tests:")
            for error in results.errors:
                print(f"  {error}")
        
        if results.failed_results == 0:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n⚠️  {results.failed_results} test(s) failed")
        
        print("="*60 + "\n")
        
        return 0 if results.failed_results == 0 else 1
        
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

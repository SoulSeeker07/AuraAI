"""
Integration Tests for Routing System

Tests the complete Capability Router system with all three routing levels.
"""

import pytest

from routing.capability_router import CapabilityRouter
from routing.capability_types import CapabilityType
from routing.intent_classifier import IntentClassifier
from routing.keyword_router import KeywordRouter
from routing.permission_analyzer import PermissionAnalyzer
from routing.plugin_registry import PluginCapability, PluginRegistry
from routing.risk_levels import RiskLevel
from routing.routing_result import RoutingResult
from routing.workflow_orchestrator import WorkflowOrchestrator


class TestKeywordRouter:
    """Tests for Level 1 Keyword Router."""

    def test_desktop_operations(self):
        """Test desktop-related keyword routing."""
        router = KeywordRouter()

        # Window management
        result = router.route("minimize all windows")
        assert result is not None
        assert result.capability == CapabilityType.DESKTOP
        assert result.confidence > 0.8

        result = router.route("close Chrome")
        assert result is not None
        assert result.capability == CapabilityType.DESKTOP
        assert result.confidence > 0.8

        # Application operations
        result = router.route("open VS Code")
        assert result is not None
        assert result.capability == CapabilityType.DESKTOP
        assert result.confidence > 0.8

    def test_filesystem_operations(self):
        """Test filesystem-related keyword routing."""
        router = KeywordRouter()

        # File operations
        result = router.route("create new file")
        assert result is not None
        assert result.capability == CapabilityType.FILESYSTEM
        assert result.confidence > 0.8

        result = router.route("delete test.txt")
        assert result is not None
        assert result.capability == CapabilityType.FILESYSTEM
        assert result.confidence > 0.8
        assert result.requires_permission

        result = router.route("rename report.docx")
        assert result is not None
        assert result.capability == CapabilityType.FILESYSTEM
        assert result.confidence > 0.8

        result = router.route("compress project.zip")
        assert result is not None
        assert result.capability == CapabilityType.FILESYSTEM
        assert result.confidence > 0.8

    def test_memory_operations(self):
        """Test memory-related keyword routing."""
        router = KeywordRouter()

        result = router.route("remember my WiFi password")
        assert result is not None
        assert result.capability == CapabilityType.MEMORY
        assert result.confidence > 0.8

        result = router.route("what did I tell you yesterday?")
        assert result is not None
        assert result.capability == CapabilityType.MEMORY
        assert result.confidence > 0.8

    def test_browser_operations(self):
        """Test browser-related keyword routing."""
        router = KeywordRouter()

        result = router.route("search Cisco SD-WAN")
        assert result is not None
        assert result.capability == CapabilityType.BROWSER
        assert result.confidence > 0.8

        result = router.route("open YouTube")
        assert result is not None
        assert result.capability == CapabilityType.BROWSER
        assert result.confidence > 0.8

    def test_general_request_no_match(self):
        """Test that general requests without keywords return None."""
        router = KeywordRouter()

        result = router.route("How would Internet routing change if BGP disappeared?")
        assert result is None


class TestIntentClassifier:
    """Tests for Level 2 Intent Classifier."""

    @pytest.mark.skipif(True, reason="Requires provider_manager")
    def test_vision_request(self):
        """Test vision request classification."""
        # This would require a mock provider_manager
        pass

    @pytest.mark.skipif(True, reason="Requires provider_manager")
    def test_knowledge_request(self):
        """Test knowledge request classification."""
        # This would require a mock provider_manager
        pass

    @pytest.mark.skipif(True, reason="Requires provider_manager")
    def test_llm_request(self):
        """Test LLM request classification."""
        # This would require a mock provider_manager
        pass


class TestWorkflowOrchestrator:
    """Tests for Workflow Orchestrator."""

    def test_multi_step_workflow_detection(self):
        """Test detection of multi-step workflows."""
        orchestrator = WorkflowOrchestrator()

        # Test with explicit connectors
        assert orchestrator.can_orchestrate("Find all Python files and summarize them")

        assert orchestrator.can_orchestrate("Open VS Code and then clone repository")

        # Test with comma separation
        assert orchestrator.can_orchestrate(
            "Find all Python files, summarize them, create README"
        )

    def test_extract_operations(self):
        """Test operation extraction from requests."""
        orchestrator = WorkflowOrchestrator()

        text = "Find all Python files, summarize them, and create a README"
        operations = orchestrator._extract_operations(text)

        assert len(operations) >= 2
        capabilities = [op["capability"] for op in operations]
        assert CapabilityType.FILESYSTEM in capabilities
        assert CapabilityType.KNOWLEDGE in capabilities
        assert CapabilityType.PROVIDER in capabilities

    def test_operation_ordering(self):
        """Test that operations are ordered correctly."""
        orchestrator = WorkflowOrchestrator()

        operations = [
            {
                "capability": CapabilityType.FILESYSTEM,
                "step_type": "execute",
                "description": "Find files",
            },
            {
                "capability": CapabilityType.PROVIDER,
                "step_type": "execute",
                "description": "Generate output",
            },
            {
                "capability": CapabilityType.FILESYSTEM,
                "step_type": "execute",
                "description": "Save output",
            },
        ]

        ordered = orchestrator._order_operations(operations)

        # Save operation should be last
        assert ordered[-1]["capability"] == CapabilityType.FILESYSTEM

    def test_workflow_planning(self):
        """Test workflow planning from multi-step request."""
        orchestrator = WorkflowOrchestrator()

        text = "Find all Python files and create a README"
        steps = orchestrator.plan_workflow(text)

        assert len(steps) > 0
        assert len(steps) <= 3  # Should have 2-3 steps

    def test_execute_workflow(self):
        """Test workflow execution."""
        orchestrator = WorkflowOrchestrator()

        text = "Open Chrome and open YouTube"
        steps = orchestrator.plan_workflow(text)

        if steps:
            orchestrator.execute_workflow()


class TestCapabilityRouter:
    """Tests for main Capability Router."""

    def test_level_1_keyword_routing(self):
        """Test that Level 1 (Keyword Router) works."""
        router = CapabilityRouter()

        result = router.route("open Chrome")
        assert result is not None
        assert result.capability == CapabilityType.DESKTOP
        assert result.priority == CapabilityPriority.HIGH  # From keyword router

    def test_level_2_intent_classification(self):
        """Test that Level 2 (Intent Classifier) works."""
        router = CapabilityRouter()

        # This would work with a provider_manager
        # result = router.route("summarize this PDF")
        # assert result is not None
        # assert result.capability == CapabilityType.KNOWLEDGE

        pass

    def test_level_3_llm_fallback(self):
        """Test that Level 3 (LLM Fallback) works."""
        router = CapabilityRouter()

        result = router.route("general question about AI")
        assert result is not None
        assert result.capability == CapabilityType.PROVIDER
        assert result.priority == CapabilityPriority.LOWEST

    def test_routing_with_permission_requirements(self):
        """Test that permission requirements are set correctly."""
        router = CapabilityRouter()

        result = router.route("delete C:\\Windows")
        assert result is not None
        assert result.requires_permission
        assert result.permission_level == "critical"

    def test_routing_without_permissions(self):
        """Test that safe operations don't require permissions."""
        router = CapabilityRouter()

        result = router.route("open Chrome")
        assert result is not None
        assert not result.requires_permission

        result = router.route("read file.txt")
        assert result is not None
        assert not result.requires_permission


class TestRoutingResult:
    """Tests for RoutingResult object."""

    def test_routing_result_creation(self):
        """Test creating a RoutingResult."""
        result = RoutingResult(
            capability=CapabilityType.DESKTOP,
            confidence=0.95,
            priority=CapabilityPriority.HIGH,
            requires_permission=False,
        )

        assert result.capability == CapabilityType.DESKTOP
        assert result.confidence == 0.95
        assert not result.requires_permission

    def test_add_step(self):
        """Test adding steps to routing result."""
        result = RoutingResult(capability=CapabilityType.FILESYSTEM, confidence=0.9)

        result.add_step("Find files")
        result.add_step("Analyze files")

        assert len(result.estimated_steps) == 2
        assert "Find files" in result.estimated_steps

    def test_add_plugin(self):
        """Test adding plugins to routing result."""
        result = RoutingResult(capability=CapabilityType.PROVIDER, confidence=0.8)

        result.add_plugin("summarizer_plugin")

        assert len(result.plugins) == 1
        assert "summarizer_plugin" in result.plugins

    def test_set_permission_required(self):
        """Test setting permission requirements."""
        result = RoutingResult(capability=CapabilityType.FILESYSTEM, confidence=0.9)

        result.set_permission_required("high")

        assert result.requires_permission
        assert result.permission_level == "high"
        assert result.risk_level == "high"

    def test_needs_confirmation(self):
        """Test confirmation requirements."""
        result = RoutingResult(capability=CapabilityType.DESKTOP, confidence=0.9)

        result.set_permission_required("confirmation")
        assert result.needs_confirmation()

        result.set_permission_required("low")
        assert not result.needs_confirmation()

    def test_is_safe(self):
        """Test safety checks."""
        result = RoutingResult(capability=CapabilityType.FILESYSTEM, confidence=0.9)

        result.set_permission_required("low")
        assert result.is_safe()

        result.set_permission_required("critical")
        assert not result.is_safe()

    def test_as_dict(self):
        """Test converting to dictionary."""
        result = RoutingResult(
            capability=CapabilityType.DESKTOP,
            confidence=0.95,
            priority=CapabilityPriority.HIGH,
        )
        result.add_step("Open Chrome")
        result.add_plugin("desktop_plugin")

        data = result.as_dict()

        assert data["capability"] == "desktop"
        assert data["confidence"] == 0.95
        assert data["priority"] == "high"
        assert len(data["estimated_steps"]) == 1
        assert len(data["plugins"]) == 1


class TestPermissionAnalyzer:
    """Tests for Permission Analyzer."""

    def test_permission_analysis(self):
        """Test basic permission analysis."""
        analyzer = PermissionAnalyzer()

        result = analyzer.analyze_request("shutdown computer", "desktop_operation")
        assert result["requires_permission"] is True
        assert result["permission_level"] in ["critical", "high", "medium"]

    def test_desktop_permission_levels(self):
        """Test desktop operation permission levels."""
        analyzer = PermissionAnalyzer()

        critical = analyzer.check_desktop_operation("shutdown computer")
        assert critical["permission_level"] == "critical"

        high = analyzer.check_desktop_operation("force quit Chrome")
        assert high["permission_level"] == "high"

        medium = analyzer.check_desktop_operation("open Chrome")
        assert medium["permission_level"] == "medium"


class TestRiskLevels:
    """Tests for Risk Levels."""

    def test_risk_level_mapping(self):
        """Test risk level mappings."""
        assert RiskLevel.NONE.value == "none"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_needs_confirmation(self):
        """Test confirmation requirements for different risk levels."""
        assert RiskLevel.NONE.needs_confirmation() is False
        assert RiskLevel.LOW.needs_confirmation() is True
        assert RiskLevel.MEDIUM.needs_confirmation() is True
        assert RiskLevel.HIGH.needs_confirmation() is True
        assert RiskLevel.CRITICAL.needs_confirmation() is True

    def test_get_risk_level(self):
        """Test getting risk levels for operations."""
        critical = get_risk_level("shutdown", {})
        assert critical == "critical"

        high = get_risk_level("delete_file", {"path": "/some/path"})
        assert high in ["high", "critical"]

        low = get_risk_level("open_file", {"path": "/tmp/test.txt"})
        assert low == "low"


class TestPluginRegistry:
    """Tests for Plugin Registry."""

    def test_plugin_registration(self):
        """Test registering a plugin."""
        registry = PluginRegistry()

        class MockPlugin:
            def get_capabilities(self):
                return [
                    {
                        "name": "test_capability",
                        "capability_type": "desktop",
                        "description": "Test capability",
                        "supported_operations": ["open", "close"],
                        "priority": "high",
                    }
                ]

        plugin = MockPlugin()
        registry.register_plugin("test_plugin", plugin)

        assert "test_plugin" in registry.plugins
        assert len(registry.capabilities) > 0

    def test_discover_capabilities(self):
        """Test discovering capabilities from plugin."""
        registry = PluginRegistry()

        class MockPlugin:
            def get_capabilities(self):
                return [
                    {
                        "name": "test_cap",
                        "capability_type": "filesystem",
                        "description": "Test",
                        "supported_operations": ["read", "write"],
                    }
                ]

        plugin = MockPlugin()
        discovered = registry.discover_capabilities(plugin)

        assert len(discovered) > 0
        assert discovered[0]["name"] == "test_cap"

    def test_get_capabilities_for_operation(self):
        """Test getting capabilities for a specific operation."""
        registry = PluginRegistry()

        class MockPlugin:
            def get_capabilities(self):
                return [
                    {
                        "name": "file_op",
                        "capability_type": "filesystem",
                        "description": "File operations",
                        "supported_operations": ["read", "write", "delete"],
                    }
                ]

        plugin = MockPlugin()
        registry.register_plugin("file_plugin", plugin)

        # Test finding capability for operation
        caps = registry.get_capabilities_for_operation("read")
        assert len(caps) > 0

        caps = registry.get_capabilities_for_operation("delete")
        assert len(caps) > 0

        caps = registry.get_capabilities_for_operation("move")
        assert len(caps) == 0

    def test_get_capabilities_by_type(self):
        """Test getting capabilities by type."""
        registry = PluginRegistry()

        class MockPlugin:
            def get_capabilities(self):
                return [
                    {
                        "name": "cap1",
                        "capability_type": "desktop",
                        "description": "Test",
                    },
                    {
                        "name": "cap2",
                        "capability_type": "filesystem",
                        "description": "Test",
                    },
                ]

        plugin = MockPlugin()
        registry.register_plugin("test_plugin", plugin)

        desktop_caps = registry.get_capabilities_by_type(CapabilityType.DESKTOP)
        assert len(desktop_caps) == 1

        filesystem_caps = registry.get_capabilities_by_type(CapabilityType.FILESYSTEM)
        assert len(filesystem_caps) == 1


class TestEndToEndRouting:
    """End-to-end tests for the complete routing flow."""

    def test_complete_routing_flow_desktop(self):
        """Test complete routing flow for desktop request."""
        router = CapabilityRouter()

        result = router.route("open VS Code")
        assert result is not None
        assert result.capability == CapabilityType.DESKTOP
        assert result.priority == CapabilityPriority.HIGH
        assert not result.requires_permission

    def test_complete_routing_flow_filesystem(self):
        """Test complete routing flow for filesystem request."""
        router = CapabilityRouter()

        result = router.route("delete test.txt")
        assert result is not None
        assert result.capability == CapabilityType.FILESYSTEM
        assert result.priority == CapabilityPriority.HIGH
        assert result.requires_permission

    def test_complete_routing_flow_browser(self):
        """Test complete routing flow for browser request."""
        router = CapabilityRouter()

        result = router.route("search Cisco SD-WAN")
        assert result is not None
        assert result.capability == CapabilityType.BROWSER
        assert result.priority == CapabilityPriority.MEDIUM

    def test_complete_routing_flow_memory(self):
        """Test complete routing flow for memory request."""
        router = CapabilityRouter()

        result = router.route("remember my Wi-Fi password")
        assert result is not None
        assert result.capability == CapabilityType.MEMORY
        assert result.priority == CapabilityPriority.MEDIUM

    def test_multi_step_workflow_routing(self):
        """Test complete routing flow for multi-step workflow."""
        router = CapabilityRouter()

        # This would trigger the workflow orchestrator
        text = "find all Python files, summarize them, and create README"
        result = router.route(text)

        # The result should have routing information
        assert result is not None
        assert result.capability in [CapabilityType.FILESYSTEM, CapabilityType.PROVIDER]
        assert len(result.estimated_steps) > 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

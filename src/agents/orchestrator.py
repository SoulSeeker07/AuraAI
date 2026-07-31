"""
Agent Orchestration System - Central coordinator for multi-agent collaboration.

The AgentOrchestrator is the "CEO" of Aura, managing all agent operations.
It coordinates specialized agents to work together on complex tasks.
"""

from typing import Dict, Any, List, Optional, Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import asyncio

from .base_agent import BaseAgent, AgentResult, AgentState, AgentCapabilities
from .agent_registry import AgentRegistry
from .agent_context import ContextManager, AGENT_CONTEXT_REQUIREMENTS

logger = logging.getLogger(__name__)


class CollaborationMode(Enum):
    """Collaboration modes for agent coordination."""
    SEQUENTIAL = "sequential"  # Agents work one after another
    PARALLEL = "parallel"  # Agents work simultaneously
    SELECTION = "selection"  # One agent handles the task
    COLLABORATION = "collaboration"  # Multiple agents work together
    HYBRID = "hybrid"  # Combination of strategies


@dataclass
class OrchestrationTask:
    """A task to be orchestrated by the AgentOrchestrator."""
    task_type: str  # Type of task
    description: str  # Human-readable description
    priority: int = 50  # Priority (1-100, higher is better)
    target_agents: Optional[List[str]] = None  # Specific agents to use
    collaboration_mode: CollaborationMode = CollaborationMode.SELECTION
    required_capabilities: Optional[List[str]] = None
    timeout: int = 300  # Timeout in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: Optional[List[str]] = None  # Task dependencies
    context_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    """Result of orchestrating agents."""
    success: bool
    tasks_completed: List[str]
    tasks_failed: List[str]
    primary_agent: Optional[str] = None
    output: AgentResult = None
    merged_output: Dict[str, Any] = field(default_factory=dict)
    conflicts_resolved: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """
    Central orchestrator for Aura's multi-agent system.
    
    Responsibilities:
    - Select appropriate agents for tasks
    - Spawn and manage agent instances
    - Coordinate agent collaboration
    - Merge outputs from multiple agents
    - Resolve conflicts between agents
    - Allocate context to agents
    - Track orchestration progress
    - Manage agent lifecycle
    
    Pattern: Agents never call each other directly.
    All communication goes through the Orchestrator.
    """
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        context_manager: Optional[ContextManager] = None
    ):
        """
        Initialize the AgentOrchestrator.
        
        Args:
            agent_registry: AgentRegistry for agent discovery
            context_manager: ContextManager for context allocation
        """
        self.agent_registry = agent_registry
        self.context_manager = context_manager or ContextManager()
        
        # Active agent instances
        self.active_agents: Dict[str, BaseAgent] = {}
        
        # Task tracking
        self.active_tasks: Dict[str, OrchestrationTask] = {}
        self.task_results: Dict[str, OrchestrationResult] = {}
        
        # Orchestration progress
        self.start_time: Optional[datetime] = None
        self.callbacks: List[Callable] = []
        
        logger.info("AgentOrchestrator initialized")
    
    def register_callback(self, callback: Callable) -> None:
        """Register a callback for orchestration events."""
        self.callbacks.append(callback)
    
    def _notify_callback(self, event_type: str, data: dict) -> None:
        """Notify all callbacks of an event."""
        for callback in self.callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in orchestration callback: {e}")
    
    def assign_context(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Allocate appropriate context to an agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent's context dictionary
        """
        # Update global context filters if specified
        if agent_name in self.active_tasks:
            task = self.active_tasks[agent_name]
            if task.context_filters:
                for key, value in task.context_filters.items():
                    self.context_manager.update_global_context(key, value)
        
        # Allocate context
        if agent_name in AGENT_CONTEXT_REQUIREMENTS:
            agent_context = self.context_manager.allocate_context(agent_name)
            return agent_context.filtered_data
        
        # Fallback to default workspace context
        agent_context = self.context_manager.allocate_context(agent_name)
        return agent_context.filtered_data
    
    def select_agent(self, task_type: str) -> Optional[str]:
        """
        Select the best agent for a task.
        
        Args:
            task_type: Type of task
            
        Returns:
            Agent name or None if no suitable agent found
        """
        # Use agent registry to find best agent
        best_agent = self.agent_registry.get_best_agent(task_type)
        
        if best_agent:
            return best_agent.agent_name
        
        return None
    
    def create_agent_instance(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Create an instance of the specified agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent instance or None if creation failed
        """
        registration = self.agent_registry.get_agent(agent_name)
        
        if not registration:
            logger.error(f"Agent {agent_name} not found in registry")
            return None
        
        # Get agent capabilities
        capabilities = registration.capabilities
        
        # Create agent instance
        # Note: This would typically use registration.agent_class
        # For now, we'll return None as we need the actual agent classes
        logger.debug(f"Agent instance would be created for: {agent_name}")
        return None
    
    async def coordinate_task(
        self,
        task: OrchestrationTask,
        user_input: str = ""
    ) -> OrchestrationResult:
        """
        Coordinate agents to complete a task.
        
        Args:
            task: The task to orchestrate
            user_input: User's original input/task description
            
        Returns:
            OrchestrationResult with outcomes
        """
        self.start_time = datetime.now()
        self._notify_callback("task_start", {
            "task_type": task.task_type,
            "description": task.description,
            "priority": task.priority
        })
        
        logger.info(f"Orchestrating task: {task.description}")
        
        # Step 1: Select agents
        selected_agents = await self._select_agents(task)
        
        if not selected_agents:
            logger.warning(f"No suitable agents found for task: {task.task_type}")
            return OrchestrationResult(
                success=False,
                tasks_completed=[],
                tasks_failed=[task.task_type],
                warnings=["No suitable agents found for task"]
            )
        
        # Step 2: Assign context to agents
        for agent_name in selected_agents:
            self.assign_context(agent_name)
        
        # Step 3: Execute agents based on collaboration mode
        result = await self._execute_agents(
            selected_agents,
            task,
            user_input
        )
        
        # Step 4: Merge results
        merged_output = self._merge_results(result)
        
        # Step 5: Update task results
        self.task_results[task.task_type] = OrchestrationResult(
            success=result.success,
            tasks_completed=selected_agents,
            tasks_failed=result.tasks_failed,
            output=result.output,
            merged_output=merged_output,
            execution_time=self._get_execution_time(),
            metadata={
                "agents_used": selected_agents,
                "collaboration_mode": task.collaboration_mode.value
            }
        )
        
        self._notify_callback("task_complete", {
            "task_type": task.task_type,
            "success": result.success,
            "agents_used": selected_agents,
            "execution_time": self._get_execution_time()
        })
        
        return self.task_results[task.task_type]
    
    async def _select_agents(self, task: OrchestrationTask) -> List[str]:
        """Select appropriate agents for the task."""
        selected_agents = []
        
        if task.target_agents:
            # Use specific agents if specified
            selected_agents = task.target_agents
        else:
            # Use best agent selection
            if task.collaboration_mode == CollaborationMode.SELECTION:
                # Single agent handles the task
                best_agent = self.select_agent(task.task_type)
                if best_agent:
                    selected_agents = [best_agent]
            else:
                # Multiple agents collaborate
                # Use all agents capable of the task
                capable_agents = self.agent_registry.get_agents_by_task(task.task_type)
                selected_agents = [agent.agent_name for agent in capable_agents]
        
        # Limit to active agents
        selected_agents = [
            name for name in selected_agents
            if name in self.agent_registry.get_all_agents()
        ]
        
        return selected_agents
    
    async def _execute_agents(
        self,
        agent_names: List[str],
        task: OrchestrationTask,
        user_input: str
    ) -> Dict[str, AgentResult]:
        """Execute selected agents based on collaboration mode."""
        
        if task.collaboration_mode == CollaborationMode.SELECTION:
            # Single agent handles everything
            agent_name = agent_names[0] if agent_names else None
            
            if agent_name:
                result = await self._execute_agent(agent_name, task, user_input)
                return {agent_name: result}
            else:
                return {}
        
        elif task.collaboration_mode == CollaborationMode.SEQUENTIAL:
            # Agents work one after another
            results = {}
            for agent_name in agent_names:
                result = await self._execute_agent(agent_name, task, user_input)
                results[agent_name] = result
            return results
        
        elif task.collaboration_mode == CollaborationMode.PARALLEL:
            # Agents work simultaneously
            tasks = [
                self._execute_agent(agent_name, task, user_input)
                for agent_name in agent_names
            ]
            results = {}
            
            try:
                completed = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(completed):
                    if isinstance(result, Exception):
                        results[agent_names[i]] = AgentResult(
                            agent_name=agent_names[i],
                            success=False,
                            error=str(result)
                        )
                    else:
                        results[agent_names[i]] = result
            except Exception as e:
                logger.error(f"Parallel execution error: {e}")
                for agent_name in agent_names:
                    results[agent_name] = AgentResult(
                        agent_name=agent_name,
                        success=False,
                        error=str(e)
                    )
            
            return results
        
        else:  # Collaboration or Hybrid
            return await self._execute_collaboration(agent_names, task, user_input)
    
    async def _execute_agent(
        self,
        agent_name: str,
        task: OrchestrationTask,
        user_input: str
    ) -> AgentResult:
        """
        Execute a single agent.
        
        Args:
            agent_name: Name of the agent
            task: The task to execute
            user_input: User's original input
            
        Returns:
            Agent result
        """
        try:
            # Get agent registration
            registration = self.agent_registry.get_agent(agent_name)
            if not registration:
                return AgentResult(
                    agent_name=agent_name,
                    success=False,
                    error=f"Agent {agent_name} not found"
                )
            
            # Prepare task data
            task_data = {
                "task_type": task.task_type,
                "description": task.description,
                "user_input": user_input,
                "metadata": task.metadata,
                "context": self.assign_context(agent_name)
            }
            
            # Note: In real implementation, we would instantiate and execute the agent here
            # For now, we'll create a mock result
            logger.debug(f"Executing agent: {agent_name}")
            
            # Mock execution (would be replaced with actual agent execution)
            result = AgentResult(
                agent_name=agent_name,
                success=True,
                summary=f"{agent_name} completed task: {task.description}",
                actions=[f"Executed {task.task_type} using {agent_name}"],
                confidence=0.85
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing agent {agent_name}: {e}")
            return AgentResult(
                agent_name=agent_name,
                success=False,
                error=str(e)
            )
    
    async def _execute_collaboration(
        self,
        agent_names: List[str],
        task: OrchestrationTask,
        user_input: str
    ) -> Dict[str, AgentResult]:
        """Execute agents in collaboration mode."""
        # For collaboration mode, agents work together on the task
        # This is a simplified implementation
        results = {}
        
        for agent_name in agent_names:
            result = await self._execute_agent(agent_name, task, user_input)
            results[agent_name] = result
        
        return results
    
    def _merge_results(self, agent_results: Dict[str, AgentResult]) -> Dict[str, Any]:
        """
        Merge results from multiple agents.
        
        Args:
            agent_results: Results from each agent
            
        Returns:
            Merged output dictionary
        """
        merged = {
            "summary": "Multi-agent task completed",
            "total_agents": len(agent_results),
            "successful_agents": 0,
            "failed_agents": 0,
            "results": {}
        }
        
        for agent_name, result in agent_results.items():
            if result.success:
                merged["successful_agents"] += 1
            else:
                merged["failed_agents"] += 1
            
            merged["results"][agent_name] = {
                "success": result.success,
                "summary": result.summary,
                "actions": result.actions,
                "confidence": result.confidence,
                "files_modified": result.files_modified,
                "warnings": result.warnings,
                "suggestions": result.suggestions,
                "error": result.error
            }
        
        # Generate overall summary
        if merged["successful_agents"] > 0:
            merged["success"] = merged["failed_agents"] == 0
        else:
            merged["success"] = False
        
        return merged
    
    def _get_execution_time(self) -> float:
        """Calculate and return execution time."""
        if not self.start_time:
            return 0.0
        
        end_time = datetime.now()
        return (end_time - self.start_time).total_seconds()
    
    def get_task_status(self, task_type: str) -> Optional[OrchestrationResult]:
        """Get status of a completed task."""
        return self.task_results.get(task_type)
    
    def clear_active_agents(self) -> None:
        """Clear all active agent instances."""
        self.active_agents.clear()
        logger.info("Cleared all active agents")


# Global orchestrator instance
_global_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator(
    agent_registry: Optional[AgentRegistry] = None,
    context_manager: Optional[ContextManager] = None
) -> AgentOrchestrator:
    """
    Get the global AgentOrchestrator instance.
    
    Args:
        agent_registry: Optional agent registry
        context_manager: Optional context manager
        
    Returns:
        Orchestrator instance
    """
    global _global_orchestrator
    
    if _global_orchestrator is None:
        if agent_registry is None:
            # Use global agent registry
            from .agent_registry import get_agent_registry
            agent_registry = get_agent_registry()
        
        if context_manager is None:
            context_manager = ContextManager()
        
        _global_orchestrator = AgentOrchestrator(agent_registry, context_manager)
    
    return _global_orchestrator

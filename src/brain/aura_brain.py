"""
AuraBrain - The Operating System of Aura

The only public API for Aura.
Nothing talks directly to Memory, Providers, or Plugins.
Everything goes through AuraBrain.
"""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Any, AsyncGenerator, Optional
from datetime import datetime
from uuid import uuid4

from brain.request import (
    AuraRequest,
    AuraResponse,
    ResponseStatus,
    ExecutionResult,
    ToolResult,
    ActionType,
)
from brain.execution_state import ExecutionState, StreamingStatus, TaskStatus
from brain.decision_engine import DecisionEngine
from brain.response_coordinator import ResponseCoordinator
from brain.context_builder import ContextBuilder

from core.memory.memory_manager import MemoryManager
from core.workspace.workspace_manager import WorkspaceManager
from core.tools.tool_router import ToolRouter
from core.plugins.plugin_registry import PluginRegistry
from ai.provider_manager import ProviderManager

from agents.agent_registry import AgentRegistry, AgentType, AgentCapability
from agents.task_model import Task, TaskType, TaskInput, TaskStatus, TaskPriority
from uuid import uuid4

from routing.capability_router import CapabilityRouter
from routing.workflow_orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


class AuraBrain:
    """
    The operating system of Aura.
    
    Everything flows through here. Nothing bypasses the brain.
    
    Architecture:
        1. User Input → AuraBrain.process()
        2. AuraBrain → Context Builder → Unified Context
        3. AuraBrain → Decision Engine → What to do?
        4. AuraBrain → Execute Decision → Get Result
        5. AuraBrain → Response Coordinator → Stream Output
    
    Responsibilities:
        - Single entry point for all requests
        - Orchestration (not business logic)
        - State management
        - Request routing
        - Response formatting
        - Error handling
    
    Attributes:
        memory: MemoryManager instance
        provider_manager: ProviderManager instance
        workspace: WorkspaceManager instance
        tool_router: ToolRouter instance
        planner: Optional[PlannerAgent] (optional)
        execution_state: ExecutionState instance
        response_coordinator: ResponseCoordinator instance
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        provider_manager: ProviderManager,
        workspace_manager: Optional[WorkspaceManager] = None,
        tool_router: Optional[ToolRouter] = None,
        plugin_registry: Optional[PluginRegistry] = None,
        agent_registry: Optional[AgentRegistry] = None,
        response_coordinator: Optional[ResponseCoordinator] = None,
        enable_events: bool = True,
        enable_routing: bool = True,
    ):
        """
        Initialize AuraBrain.

        Args:
            memory_manager: Memory manager for knowledge access
            provider_manager: Provider manager for AI responses
            workspace_manager: Workspace manager for file/app access
            tool_router: Tool router for plugin/tool execution
            plugin_registry: Plugin registry for discovering plugins
            agent_registry: Agent registry for agent delegation
            response_coordinator: Response coordinator for streaming
            enable_events: Whether to log internal events
            enable_routing: Whether to enable Capability Router system
        """
        self.memory_manager = memory_manager
        self.provider_manager = provider_manager
        self.workspace = workspace_manager
        self.tool_router = tool_router
        self.plugin_registry = plugin_registry
        self.agent_registry = agent_registry
        self.enable_events = enable_events
        self.enable_events = enable_events
        self.enable_routing = enable_routing

        # Execution state
        self.execution_state = ExecutionState()
        self.execution_state.metadata['enable_events'] = enable_events

        # Build internal components
        self.response_coordinator = response_coordinator or ResponseCoordinator()

        # Initialize capability router and workflow orchestrator
        self.capability_router = None
        self.workflow_orchestrator = None

        if enable_routing:
            self.capability_router = CapabilityRouter(provider_manager)
            self.workflow_orchestrator = WorkflowOrchestrator()
            logger.info("Capability Router and Workflow Orchestrator initialized")

        # Initialize tool router if not provided
        if tool_router is None:
            if plugin_registry is None:
                plugin_registry = PluginRegistry()
            if workspace_manager is None:
                workspace_manager = WorkspaceManager()

            self.tool_router = ToolRouter(
                plugin_registry=plugin_registry,
                desktop_agent=workspace_manager.desktop_agent,
                filesystem=workspace_manager.filesystem
            )

        # Initialize decision engine
        self.decision_engine = DecisionEngine(
            memory_manager=memory_manager,
            tool_router=self.tool_router,
            workspace_manager=workspace_manager,
            agent_registry=agent_registry
        )

        # Initialize context builder
        self.context_builder = ContextBuilder(
            memory_manager=memory_manager,
            workspace_manager=workspace_manager,
            response_coordinator=self.response_coordinator
        )

        logger.info("AuraBrain initialized")
    
    async def process(self, request: AuraRequest) -> AuraResponse:
        """
        Main entry point - all requests go through here.

        This is the only method that external code should call.
        Everything else (Vision, Voice, Desktop, Plugins) uses this.

        Processing Flow:
            1. Validate request
            2. Route using Capability Router (if enabled)
            3. Check for multi-step workflows
            4. Build context (memory + workspace + attachments)
            5. Plan (if complex)
            6. Decide what to do (memory/tool/provider)
            7. Execute decision
            8. Stream response with formatting

        Args:
            request: AuraRequest from any source (chat, voice, vision, etc.)

        Returns:
            AuraResponse with result and status

        Example:
            >>> brain = AuraBrain(memory, provider)
            >>> request = AuraRequest(text="Hello", source="voice")
            >>> async for chunk in brain.process(request):
            ...     print(chunk)  # Streaming output
        """
        # Start timer
        start_time = time.time()

        try:
            logger.info(f"AuraBrain processing request from {request.source}: {request.text[:50]}...")

            # Reset execution state for new request
            self.execution_state.reset()

            # 1. Validate request
            if not request.text or not request.text.strip():
                return AuraResponse(
                    text="Please provide a request.",
                    status=ResponseStatus.ERROR,
                    execution_time=time.time() - start_time,
                    conversation_id=request.conversation_id
                )

            # 2. Route using Capability Router (if enabled)
            routing_result = None
            if self.capability_router:
                logger.debug("Routing request through Capability Router")
                routing_result = self.capability_router.route(request.text)

                if routing_result:
                    logger.info(f"Routing result: {routing_result.capability.value} "
                              f"(confidence: {routing_result.confidence:.2f})")
                    self.execution_state.metadata['routing'] = routing_result.as_dict()
                else:
                    logger.debug("No routing match found")

            # 3. Check for multi-step workflows
            is_workflow = False
            workflow_steps = []
            if self.workflow_orchestrator and self.workflow_orchestrator.can_orchestrate(request.text):
                logger.info("Request identified as multi-step workflow")
                is_workflow = True
                workflow_steps = self.workflow_orchestrator.plan_workflow(request.text)

                if workflow_steps:
                    logger.info(f"Workflow planned with {len(workflow_steps)} steps")
                    self.execution_state.metadata['workflow_steps'] = workflow_steps

            # 4. Build unified context
            logger.info("Building context...")
            context = await self.build_context(request)
            self.execution_state.conversation_id = context.conversation_id

            # 5. Check if planning is needed
            needs_planning = self.needs_planning(request)
            if needs_planning:
                logger.info("Request needs planning")
                context = await self.plan(request, context)

            # 6. Decision engine - what should Aura do?
            logger.info("Making decision...")
            decision = self.decide_action(request, context)

            # 7. Execute the decision
            logger.info(f"Executing action: {decision.action_type}")

            # If it's a workflow, execute it instead of single decision
            if is_workflow and workflow_steps:
                result = await self.execute_workflow(workflow_steps, request, context)
            else:
                result = await self.execute_decision(decision, request, context)

            # 8. Format response
            self.execution_state.set_execution_time(time.time() - start_time)

            logger.info(f"AuraBrain completed request: {request.text[:50]}...")

            return AuraResponse(
                text=result.text,
                status=ResponseStatus.SUCCESS if result.success else ResponseStatus.ERROR,
                execution_time=time.time() - start_time,
                tool_results=result.tool_results,
                metadata=result.metadata,
                conversation_id=request.conversation_id
            )
        
        except asyncio.CancelledError:
            logger.warning("Request was cancelled")
            self.execution_state.cancel_streaming()
            return AuraResponse(
                text="Request was cancelled.",
                status=ResponseStatus.ERROR,
                execution_time=time.time() - start_time,
                conversation_id=request.conversation_id
            )
        
        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            self.execution_state.update_task_status(TaskStatus.FAILED, str(e))
            
            return AuraResponse(
                text=f"I encountered an error: {type(e).__name__}: {e}",
                status=ResponseStatus.ERROR,
                execution_time=time.time() - start_time,
                conversation_id=request.conversation_id
            )
    
    async def process_stream(self, request: AuraRequest) -> AsyncGenerator[str, None]:
        """
        Process request with streaming output.
        
        This is the main entry point for streaming responses.
        
        Args:
            request: AuraRequest from any source
        
        Yields:
            Streaming chunks for UI consumption
        """
        # Start timer
        start_time = time.time()
        
        # Process request
        response = await self.process(request)
        
        # Stream the response
        self.execution_state.start_streaming()
        
        try:
            async for chunk in self.response_coordinator.stream(response):
                yield chunk
        finally:
            self.execution_state.complete_streaming()
    
    async def build_context(self, request: AuraRequest) -> Any:
        """
        Build unified context object.
        
        Context includes:
        - Memory facts
        - Workspace information
        - User attachments
        - Recent conversation history
        - Provider settings
        
        Args:
            request: Incoming request
        
        Returns:
            Unified context object
        """
        return await self.context_builder.build_aura(
            user_input=request.text,
            attachments=request.attachments,
            workspace_info=request.context,
            conversation_id=request.conversation_id
        )
    
    def needs_planning(self, request: AuraRequest) -> bool:
        """
        Determine if request needs task planning.

        Checks if PLANNER agent is available, then uses heuristics.

        Args:
            request: Incoming request

        Returns:
            True if planning is needed
        """
        # Check if PLANNER agent is available
        if not self.agent_registry:
            return False

        # Try to find PLANNER agent
        planner_agents = self.agent_registry.get_agent_by_type(AgentType.PLANNER)
        if not planner_agents:
            return False

        # Complex requests need planning
        word_count = len(request.text.split())
        if word_count > 10:
            return True

        # Multi-step keywords
        multi_step_indicators = ["and", "then", "after that", "first", "next"]
        if any(word in request.text.lower() for word in multi_step_indicators):
            return True

        return False
    
    def decide_action(self, request: AuraRequest, context: Any) -> Any:
        """
        Decision Engine - what should Aura do?
        
        Returns one of:
        - MemoryAction (for memory queries)
        - ToolAction (for tool/plugin execution)
        - ProviderAction (for AI responses)
        - VisionAction (for image analysis)
        - VoiceAction (for voice processing)
        
        Args:
            request: Incoming request
            context: Built context object
        
        Returns:
            Action to execute
        """
        return self.decision_engine.decide(request, context)
    
    async def plan(self, request: AuraRequest, context: Any) -> Any:
        """
        Plan the request into executable tasks.

        Uses PLANNER agent from agent_registry to analyze and decompose requests.

        Args:
            request: Incoming request
            context: Built context object

        Returns:
            Context with plan/task list
        """
        if not self.agent_registry:
            return context

        # Try to find PLANNER agent
        planner_agents = self.agent_registry.get_agent_by_type(AgentType.PLANNER)
        if not planner_agents:
            logger.debug("PLANNER agent not available, skipping planning")
            return context

        # Instantiate PLANNER agent
        planner_agent = planner_agents[0].instantiate(
            dependencies={
                "memory_manager": self.memory_manager,
                "tool_router": self.tool_router,
                "workspace_manager": self.workspace,
                "response_coordinator": self.response_coordinator
            }
        )

        # Create task for planning
        task = Task(
            id=str(uuid4()),
            type=TaskType.PLANNING,
            title="Plan Request",
            input=TaskInput(data={"query": request.text, "context": context})
        )

        # Execute planning task
        planner_agent.execute_task(task)
        output = task.output

        # Extract tasks from output
        if output and output.data:
            tasks = output.data.get("tasks", [])
        else:
            # Fallback to simple planning if agent doesn't return structured tasks
            tasks = self._simple_plan(request.text)

        # Add tasks to context
        context.planned_tasks = tasks

        logger.info(f"Planned {len(tasks)} tasks for request")

        return context

    def _simple_plan(self, text: str) -> list:
        """
        Simple planning fallback when PLANNER agent is not available.

        Args:
            text: User request text

        Returns:
            List of planned tasks
        """
        # This is a simple heuristic-based planning fallback
        # In production, this would be more sophisticated
        words = text.lower().split()
        tasks = []

        if len(words) > 5:
            tasks.append({"type": "analyze", "description": "Analyze user request"})
            tasks.append({"type": "execute", "description": "Execute requested action"})

        return tasks
    
    async def execute_decision(self, decision: Any, request: AuraRequest, context: Any) -> ExecutionResult:
        """
        Execute the decision and return result.
        
        Args:
            decision: Decision from Decision Engine
            request: Incoming request
            context: Built context object
        
        Returns:
            ExecutionResult with text and tool results
        """
        result = ExecutionResult(
            text="",
            action_type=decision.action_type,
            metadata=request.metadata
        )
        
        try:
            if decision.action_type == ActionType.MEMORY:
                result = await self.handle_memory_decision(decision, context)
            elif decision.action_type == ActionType.TOOL:
                result = await self.handle_tool_decision(decision, context)
            elif decision.action_type == ActionType.PROVIDER:
                result = await self.handle_provider_decision(request, context)
            elif decision.action_type == ActionType.VISION:
                result = await self.handle_vision_decision(request, context)
            elif decision.action_type == ActionType.RESEARCH:
                result = await self.handle_research_decision(request, context)
            elif decision.action_type == ActionType.CODING:
                result = await self.handle_coding_decision(request, context)
            elif decision.action_type == ActionType.DESKTOP:
                result = await self.handle_desktop_decision(request, context)
            elif decision.action_type == ActionType.VOICE:
                result = await self.handle_voice_decision(request, context)
            elif decision.action_type == ActionType.AGENT:
                result = await self.handle_agent_decision(decision, context)
            elif decision.action_type == ActionType.LEARNING:
                result = await self.handle_learning_decision(request, context)
            else:
                # Default to provider
                result = await self.handle_provider_decision(request, context)
            
            return result
        
        except Exception as e:
            logger.error(f"Error executing decision: {e}", exc_info=True)
            result.errors.append(f"Execution failed: {type(e).__name__}: {e}")
            return result

    async def execute_workflow(self, steps: list, request: AuraRequest, context: Any) -> ExecutionResult:
        """
        Execute a multi-step workflow.

        This method handles complex requests that involve multiple capabilities
        (e.g., "Find all Python files and create a README").

        Args:
            steps: List of workflow steps from WorkflowOrchestrator
            request: Incoming request
            context: Built context object

        Returns:
            ExecutionResult with combined output from all steps
        """
        result = ExecutionResult(
            text="",
            action_type=ActionType.PROVIDER,  # Workflow execution as provider action
            metadata=request.metadata
        )

        try:
            logger.info(f"Starting workflow execution with {len(steps)} steps")

            # Execute each step sequentially
            for i, step in enumerate(steps):
                capability = step.get("capability", "")
                description = step.get("description", f"Step {i+1}")

                logger.info(f"Executing workflow step {i+1}/{len(steps)}: {description} ({capability})")

                try:
                    # Route the step through the capability router
                    if self.capability_router:
                        routing_result = self.capability_router.route(description)
                        if routing_result:
                            logger.debug(f"Step routing: {routing_result.capability.value}")

                    # Execute based on capability type
                    if capability == "filesystem":
                        # Handle filesystem operation
                        # This would integrate with workspace_manager.filesystem
                        step_output = f"[Filesystem] {description} completed"
                    elif capability == "knowledge":
                        # Handle knowledge operation
                        step_output = f"[Knowledge] {description} completed"
                    elif capability == "provider":
                        # Handle AI generation
                        step_output = f"[Provider] {description} completed"
                    elif capability == "desktop":
                        # Handle desktop operation
                        step_output = f"[Desktop] {description} completed"
                    elif capability == "browser":
                        # Handle browser operation
                        step_output = f"[Browser] {description} completed"
                    elif capability == "vision":
                        # Handle vision operation
                        step_output = f"[Vision] {description} completed"
                    elif capability == "memory":
                        # Handle memory operation
                        step_output = f"[Memory] {description} completed"
                    else:
                        # Default to provider for unknown capabilities
                        step_output = f"[Provider] {description} completed"

                    # Append to result
                    if i == 0:
                        result.text = step_output
                    else:
                        result.text += f" {step_output}"

                    logger.info(f"Step {i+1} completed successfully")

                except Exception as e:
                    error_msg = f"Step {i+1} failed: {type(e).__name__}: {e}"
                    logger.error(error_msg, exc_info=True)
                    result.errors.append(error_msg)

                    # Determine if workflow should continue or fail
                    # By default, stop on first failure for critical steps
                    if i < len(steps) - 1:
                        continue  # Continue with next step
                    else:
                        break  # Stop if it's the last step

            # Update metadata with workflow results
            result.metadata['workflow_completed'] = len(result.errors) == 0
            result.metadata['workflow_steps'] = len(steps)
            result.metadata['workflow_errors'] = len(result.errors)

            logger.info(f"Workflow execution completed: {len(result.errors)} errors")

            return result

        except Exception as e:
            logger.error(f"Error executing workflow: {e}", exc_info=True)
            result.errors.append(f"Workflow execution failed: {type(e).__name__}: {e}")
            return result

    async def handle_memory_decision(self, decision: Any, context: Any) -> ExecutionResult:
        """Handle memory-related decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.MEMORY,
            metadata=context.metadata
        )
        
        # Check for specific memory queries
        memory_keywords = ["remember", "what do you know", "my facts", "profile", "preferences", "summarize"]
        
        if any(keyword in context.user_input.lower() for keyword in memory_keywords):
            # Return memory summary
            summary = self.memory_manager.summarize()
            result.text = summary
        
        else:
            # Try to extract and remember facts
            facts = self.memory_manager.extract_facts(context.user_input)
            for fact in facts:
                self.memory_manager.remember(fact)
            
            if facts:
                result.text = f"I'll remember: {', '.join(f'{f.category}: {f.value}' for f in facts[:3])}"
            else:
                result.text = "I've processed that for future reference."
        
        return result
    
    async def handle_tool_decision(self, decision: Any, context: Any) -> ExecutionResult:
        """Handle tool/plugin execution decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.TOOL,
            metadata=context.metadata
        )
        
        if hasattr(decision, 'tool_name') and decision.tool_name:
            # Execute tool
            tool_result = self.tool_router.route(decision.tool_name, decision.params or {})
            
            if tool_result.success:
                result.text = f"Executed {decision.tool_name}: {tool_result.output}"
                result.add_tool_result(tool_result)
            else:
                result.text = f"Error executing {decision.tool_name}: {tool_result.error}"
                result.add_tool_result(tool_result)
        
        else:
            result.text = "No specific tool requested."
        
        return result
    
    async def handle_provider_decision(self, request: AuraRequest, context: Any) -> ExecutionResult:
        """Handle AI provider chat decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.PROVIDER,
            metadata=context.metadata
        )
        
        try:
            # Call provider manager
            response = self.provider_manager.chat(
                messages=context.messages,
                model=context.provider_settings.get('models', {}).get('default', 'llama3-8b-8192'),
                temperature=context.provider_settings.get('temperature', 0.7),
                max_tokens=context.provider_settings.get('max_tokens', 1024)
            )
            
            result.text = response.text
            result.metadata['provider'] = response.provider
            result.metadata['model'] = response.model
            
            # Update execution state
            self.execution_state.update_provider(response.provider)
        
        except Exception as e:
            result.errors.append(f"Provider error: {type(e).__name__}: {e}")
        
        return result
            
            result.text = response.text
            result.metadata['provider'] = response.provider
            result.metadata['model'] = response.model
            
            # Update execution state
            self.execution_state.update_provider(response.provider)
            
        except Exception as e:
            result.errors.append(f"Provider error: {type(e).__name__}: {e}")
        
        return result
    
    async def handle_vision_decision(self, request: AuraRequest, context: Any) -> ExecutionResult:
        """Handle vision/image analysis decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.VISION,
            metadata=context.metadata
        )
        
        if request.has_attachments:
            # Process first image
            image_path = request.attachments[0].path
            
            if image_path.exists():
                try:
                    from core.vision.image_analyzer import ImageAnalyzer
                    
                    analyzer = ImageAnalyzer()
                    analysis = analyzer.analyze_image(image_path)
                    
                    result.text = analysis
                    result.metadata['image_path'] = str(image_path)
                except Exception as e:
                    result.errors.append(f"Image analysis failed: {type(e).__name__}: {e}")
            else:
                result.errors.append(f"Image not found: {image_path}")
        else:
            result.text = "Please provide an image to analyze."
        
        return result
    
    async def handle_research_decision(self, request: AuraRequest, context: Any) -> ExecutionResult:
        """Handle research agent decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.PROVIDER,
            metadata=context.metadata
        )
        
        try:
            if self.agent_registry:
                research_agent = self.agent_registry.get_agent_by_type(AgentType.RESEARCH)
                if research_agent:
                    agent_instance = research_agent[0].instantiate(
                        memory_manager=self.memory_manager,
                        provider_manager=self.provider_manager
                    )
                    
                    task = Task(
                        id=str(uuid4()),
                        type=TaskType.DEEP_RESEARCH,
                        title="Research Task",
                        description=f"Research: {request.text[:100]}",
                        priority=TaskPriority.HIGH,
                        input=TaskInput(data={"query": request.text, "context": context.to_dict()})
                    )
                    
                    agent_instance.execute_task(task)
                    output = task.output
                    
                    if output.success:
                        result.text = output.data.get('text', 'Research completed.')
                        result.metadata.update(output.metadata or {})
                    else:
                        result.text = f"Research failed: {output.error}"
                else:
                    result = await self.handle_provider_decision(request, context)
            else:
                result = await self.handle_provider_decision(request, context)
        
        except Exception as e:
            logger.error(f"Research agent error: {e}", exc_info=True)
            result.errors.append(f"Research error: {type(e).__name__}: {e}")
            result = await self.handle_provider_decision(request, context)
        
        return result
    
    async def handle_coding_decision(self, request: AuraRequest, context: Any) -> ExecutionResult:
        """Handle coding agent decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.PROVIDER,
            metadata=context.metadata
        )
        
        try:
            if self.agent_registry:
                coding_agent = self.agent_registry.get_agent_by_type(AgentType.CODING)
                if coding_agent:
                    agent_instance = coding_agent[0].instantiate(
                        memory_manager=self.memory_manager,
                        provider_manager=self.provider_manager,
                        tool_router=self.tool_router
                    )
                    
                    task = Task(
                        id=str(uuid4()),
                        type=TaskType.CODE_GENERATE,
                        title="Coding Task",
                        description=f"Code: {request.text[:100]}",
                        priority=TaskPriority.HIGH,
                        input=TaskInput(data={"query": request.text, "context": context.to_dict()})
                    )
                    
                    agent_instance.execute_task(task)
                    output = task.output
                    
                    if output.success:
                        result.text = output.data.get('text', 'Code generation completed.')
                        result.metadata.update(output.metadata or {})
                    else:
                        result.text = f"Code generation failed: {output.error}"
                else:
                    result = await self.handle_provider_decision(request, context)
            else:
                result = await self.handle_provider_decision(request, context)
        
        except Exception as e:
            logger.error(f"Coding agent error: {e}", exc_info=True)
            result.errors.append(f"Coding error: {type(e).__name__}: {e}")
            result = await self.handle_provider_decision(request, context)
        
        return result
    
    async def handle_desktop_decision(self, request: AuraRequest, context: Any) -> ExecutionResult:
        """Handle desktop agent decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.TOOL,
            metadata=context.metadata
        )
        
        try:
            if self.agent_registry:
                desktop_agent = self.agent_registry.get_agent_by_type(AgentType.DESKTOP)
                if desktop_agent:
                    agent_instance = desktop_agent[0].instantiate(
                        workspace_manager=self.workspace,
                        tool_router=self.tool_router
                    )
                    
                    task = Task(
                        id=str(uuid4()),
                        type=TaskType.FILE_SEARCH,
                        title="Desktop Task",
                        description=f"Desktop: {request.text[:100]}",
                        priority=TaskPriority.MEDIUM,
                        input=TaskInput(data={"query": request.text, "context": context.to_dict()})
                    )
                    
                    agent_instance.execute_task(task)
                    output = task.output
                    
                    if output.success:
                        result.text = output.data.get('text', 'Desktop operation completed.')
                        result.metadata.update(output.metadata or {})
                    else:
                        result.text = f"Desktop operation failed: {output.error}"
                else:
                    result = await self.handle_tool_decision(
                        type('Decision', (), {'action_type': ActionType.TOOL, 'tool_name': 'execute_command', 'params': {'command': request.text}})(),
                        context
                    )
            else:
                result = await self.handle_tool_decision(
                    type('Decision', (), {'action_type': ActionType.TOOL, 'tool_name': 'execute_command', 'params': {'command': request.text}})(),
                    context
                )
        
        except Exception as e:
            logger.error(f"Desktop agent error: {e}", exc_info=True)
            result.errors.append(f"Desktop error: {type(e).__name__}: {e}")
            result = await self.handle_tool_decision(
                type('Decision', (), {'action_type': ActionType.TOOL, 'tool_name': 'execute_command', 'params': {'command': request.text}})(),
                context
            )
        
        return result
    
    async def handle_voice_decision(self, request: AuraRequest, context: Any) -> ExecutionResult:
        """Handle voice agent decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.PROVIDER,
            metadata=context.metadata
        )
        
        try:
            if self.agent_registry:
                voice_agent = self.agent_registry.get_agent_by_type(AgentType.VOICE)
                if voice_agent:
                    agent_instance = voice_agent[0].instantiate(
                        memory_manager=self.memory_manager,
                        provider_manager=self.provider_manager
                    )
                    
                    task = Task(
                        id=str(uuid4()),
                        type=TaskType.SPEECH_TO_TEXT,
                        title="Voice Task",
                        description=f"Voice: {request.text[:100]}",
                        priority=TaskPriority.MEDIUM,
                        input=TaskInput(data={"query": request.text, "context": context.to_dict()})
                    )
                    
                    agent_instance.execute_task(task)
                    output = task.output
                    
                    if output.success:
                        result.text = output.data.get('text', 'Voice processing completed.')
                        result.metadata.update(output.metadata or {})
                    else:
                        result.text = f"Voice processing failed: {output.error}"
                else:
                    result = await self.handle_provider_decision(request, context)
            else:
                result = await self.handle_provider_decision(request, context)
        
        except Exception as e:
            logger.error(f"Voice agent error: {e}", exc_info=True)
            result.errors.append(f"Voice error: {type(e).__name__}: {e}")
            result = await self.handle_provider_decision(request, context)
        
        return result

    async def handle_agent_decision(self, decision: Any, context: Any) -> ExecutionResult:
        """
        Handle agent-based decisions using AgentRegistry.

        This routes requests to the appropriate agent based on the decision.
        """
        result = ExecutionResult(
            text="",
            action_type=ActionType.AGENT,
            metadata=context.metadata
        )

        try:
            # Extract agent name from decision
            agent_name = decision.params.get("agent", "")

            if not agent_name:
                result.text = "No agent specified."
                return result

            # Get agent from registry
            if not self.agent_registry:
                result.text = "AgentRegistry not available."
                return result

            # Find agent by type name
            agent = self.agent_registry.find_agent_for_task(
                TaskInput(data={"text": "test", "agent": agent_name})
            )

            if not agent:
                result.text = f"Agent '{agent_name}' not found."
                logger.warning(f"Agent '{agent_name}' not found in registry")
                return result

            # Instantiate agent with dependencies
            agent_instance = agent.instantiate(
                dependencies={
                    "memory_manager": self.memory_manager,
                    "tool_router": self.tool_router,
                    "workspace_manager": self.workspace,
                    "response_coordinator": self.response_coordinator,
                    "provider_manager": getattr(self, 'provider_manager', None)
                }
            )

            # Determine task type based on agent type
            task_type_map = {
                AgentType.RESEARCH: TaskType.RESEARCH_WEB,
                AgentType.CODING: TaskType.CODE_GENERATE,
                AgentType.DESKTOP: TaskType.DESKTOP,
                AgentType.VOICE: TaskType.SPEECH_TO_TEXT,
                AgentType.LEARNING: TaskType.LEARN_SUCCESS,
            }

            # Use specific task type if available, otherwise default
            task_type = task_type_map.get(
                agent.agent_type,
                TaskType.GENERIC
            )

            # Create task
            task = Task(
                id=str(uuid4()),
                type=task_type,
                title=f"Agent Task: {agent_name}",
                input=TaskInput(data={"query": context.user_input or "general", "context": context})
            )

            # Execute task
            agent_instance.execute_task(task)
            output = task.output

            # Extract result from output
            if output.success:
                result.text = output.data.get('text', output.data.get('result', 'Agent task completed.'))
                result.metadata.update(output.metadata or {})
                result.metadata['agent_used'] = agent_name
                result.metadata['agent_type'] = agent.agent_type.value
            else:
                result.text = f"Agent task failed: {output.error}"

        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            result.errors.append(f"Agent execution failed: {type(e).__name__}: {e}")
            result.text = f"Error executing agent: {type(e).__name__}: {e}"

        return result

    async def handle_learning_decision(self, request: AuraRequest, context: Any) -> ExecutionResult:
        """Handle learning agent decisions."""
        result = ExecutionResult(
            text="",
            action_type=ActionType.PROVIDER,
            metadata=context.metadata
        )
        
        try:
            if self.agent_registry:
                learning_agent = self.agent_registry.get_agent_by_type(AgentType.LEARNING)
                if learning_agent:
                    agent_instance = learning_agent[0].instantiate(
                        memory_manager=self.memory_manager,
                        provider_manager=self.provider_manager
                    )
                    
                    task = Task(
                        id=str(uuid4()),
                        type=TaskType.LEARN_SUCCESS,
                        title="Learning Task",
                        description=f"Learning: {request.text[:100]}",
                        priority=TaskPriority.MEDIUM,
                        input=TaskInput(data={"query": request.text, "context": context.to_dict()})
                    )
                    
                    agent_instance.execute_task(task)
                    output = task.output
                    
                    if output.success:
                        result.text = output.data.get('text', 'Learning completed.')
                        result.metadata.update(output.metadata or {})
                    else:
                        result.text = f"Learning failed: {output.error}"
                else:
                    result = await self.handle_provider_decision(request, context)
            else:
                result = await self.handle_provider_decision(request, context)
        
        except Exception as e:
            logger.error(f"Learning agent error: {e}", exc_info=True)
            result.errors.append(f"Learning error: {type(e).__name__}: {e}")
            result = await self.handle_provider_decision(request, context)
        
        return result
    
    def get_execution_state(self) -> dict[str, Any]:
        """Get current execution state."""
        return self.execution_state.to_dict()
    
    def cancel_request(self):
        """Cancel the current request."""
        self.execution_state.cancel_streaming()
    
    def set_progress_step(self, step: str):
        """Add a progress step."""
        self.execution_state.add_progress_step(step)

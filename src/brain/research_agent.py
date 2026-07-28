from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ai.models import ChatRequest
from ai.provider_manager import ProviderManager


@dataclass
class ResearchStep:
    """A step in a research plan."""
    
    step_number: int
    description: str
    query: str
    substeps: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class ResearchPlan:
    """Complete research plan with steps."""
    
    main_query: str
    steps: list[ResearchStep]
    total_steps: int
    estimated_duration: str
    reasoning: str


class ResearchAgent:
    """
    Plans and executes multi-step research.
    This agent breaks down complex queries into subtasks and executes them.
    """

    RESEARCH_SYSTEM_PROMPT = """You are a research planner for Aura AI, an intelligent assistant.
Your job is to break down complex research queries into a structured research plan.

For a given research query, create a step-by-step research plan.
Each step should:
1. Have a clear, concise description
2. Define the specific search query to execute
3. Specify what sources to prioritize
4. Indicate what outcome is expected

For multi-source comparison queries (e.g., "Compare X vs Y"), break it into:
1. Research X first
2. Research Y next
3. Compare the findings
4. Draw conclusions

For educational/informational queries (e.g., "Explain how Y works"), break it into:
1. Find overview of Y
2. Find detailed explanations
3. Find examples and use cases
4. Summarize findings

Return JSON with:
- main_query: The original research query
- steps: List of research steps, each with:
  - step_number: 1, 2, 3...
  - description: What this step will do
  - query: Specific search query for this step
  - substeps: Optional list of subqueries for complex steps
  - sources: List of domains to prioritize
- total_steps: Total number of steps
- estimated_duration: Human-readable time estimate (e.g., "5-10 minutes")
- reasoning: Brief explanation of the plan

Make the plan comprehensive but efficient. Avoid redundant searches."""

    def __init__(self, provider_manager: ProviderManager, model: str = "llama3-70b-8192"):
        """
        Initialize the research agent.
        
        Args:
            provider_manager: AI provider manager
            model: Model to use for planning
        """
        self.provider_manager = provider_manager
        self.model = model

    def create_plan(self, query: str) -> ResearchPlan:
        """
        Create a research plan for a complex query.
        
        Args:
            query: Research query
            
        Returns:
            ResearchPlan object
        """
        try:
            system_prompt = self.RESEARCH_SYSTEM_PROMPT
            
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            request = ChatRequest(
                messages=messages,
                model=self.model,
                temperature=0.1,
                max_tokens=500
            )

            response = self.provider_manager.chat(request)
            result = json.loads(response.text)
            
            # Convert steps to ResearchStep objects
            steps = []
            for step_data in result.get("steps", []):
                step = ResearchStep(
                    step_number=step_data.get("step_number", 0),
                    description=step_data.get("description", ""),
                    query=step_data.get("query", ""),
                    substeps=step_data.get("substeps", []),
                    sources=step_data.get("sources", []),
                )
                steps.append(step)
            
            return ResearchPlan(
                main_query=query,
                steps=steps,
                total_steps=len(steps),
                estimated_duration=result.get("estimated_duration", "Unknown"),
                reasoning=result.get("reasoning", "Plan created"),
            )
        
        except json.JSONDecodeError:
            # Fallback: create a simple 2-step plan
            return self._create_simple_plan(query)
        except Exception:
            # Fallback: create a simple 2-step plan
            return self._create_simple_plan(query)

    def _create_simple_plan(self, query: str) -> ResearchPlan:
        """
        Create a simple 2-step research plan as fallback.
        
        Args:
            query: Research query
            
        Returns:
            Simple ResearchPlan
        """
        return ResearchPlan(
            main_query=query,
            steps=[
                ResearchStep(
                    step_number=1,
                    description=f"Find overview and basic information about {query}",
                    query=query,
                ),
                ResearchStep(
                    step_number=2,
                    description=f"Find detailed information, examples, and comparison data about {query}",
                    query=query + " details examples comparison",
                ),
            ],
            total_steps=2,
            estimated_duration="5-10 minutes",
            reasoning="Simple 2-step research plan created due to AI unavailability",
        )

    def execute_plan(
        self,
        plan: ResearchPlan,
        execute_steps: list[int] | None = None,
        on_progress: callable | None = None
    ) -> dict[str, Any]:
        """
        Execute a research plan step by step.
        
        Args:
            plan: Research plan to execute
            execute_steps: List of step numbers to execute (None = all)
            on_progress: Callback function for progress updates
            
        Returns:
            Dictionary with research results
        """
        if execute_steps is None:
            execute_steps = list(range(1, plan.total_steps + 1))
        
        # Filter steps to execute
        steps_to_execute = [step for step in plan.steps if step.step_number in execute_steps]
        
        results = {
            "query": plan.main_query,
            "steps_executed": [],
            "all_results": [],
            "conclusion": "",
            "sources_used": [],
        }
        
        for step in steps_to_execute:
            # Execute the step
            if on_progress:
                on_progress(f"🔍 {step.description}")
            
            # Note: This is a placeholder. In reality, you'd call the search engine here
            step_results = {
                "step_number": step.step_number,
                "description": step.description,
                "query": step.query,
                "results": [],  # To be filled by search engine
                "sources": step.sources,
            }
            
            results["steps_executed"].append(step_results)
            results["all_results"].extend(step_results["results"])
            results["sources_used"].extend(step_results["sources"])
        
        # Generate conclusion
        results["conclusion"] = self._generate_conclusion(results)
        
        return results

    def _generate_conclusion(self, results: dict[str, Any]) -> str:
        """
        Generate a conclusion based on research results.
        
        Args:
            results: Research results
            
        Returns:
            Conclusion text
        """
        # This would normally use AI to analyze the results
        # For now, return a placeholder
        return (
            f"Based on the research, I found {len(results['all_results'])} sources. "
            f"Please review the results in the steps above for details."
        )

    def is_complex_query(self, query: str) -> bool:
        """
        Determine if a query requires multi-step research.
        
        Args:
            query: Query to analyze
            
        Returns:
            True if complex query
        """
        # Check for comparison keywords
        comparison_keywords = ["compare", "vs", "versus", "differences", "similarities", "similar", "alternatives"]
        
        # Check for educational keywords
        educational_keywords = ["explain", "how", "why", "tutorial", "guide", "overview", "introduction"]
        
        # Check for multi-concept queries
        query_words = set(query.lower().split())
        
        # Check for multiple keywords
        comparison_count = sum(1 for kw in comparison_keywords if kw in query_words)
        education_count = sum(1 for kw in educational_keywords if kw in query_words)
        
        # Check for multiple distinct topics
        concepts = [w for w in query_words if len(w) > 3]
        
        # Consider complex if:
        # 1. Has comparison keywords
        # 2. Has educational keywords
        # 3. Has multiple distinct concepts
        return (comparison_count > 0 or education_count > 0 or len(concepts) > 3)

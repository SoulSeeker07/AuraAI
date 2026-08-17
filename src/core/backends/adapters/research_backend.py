"""
Research Engine Backend Adapter
Location: src/core/backends/adapters/research_backend.py

Integrates the deep ResearchEngine into the universal backend registry.
Provides structured capability dispatch for research.search, research.synthesize,
and research.deep_query with transparent offline/mock mode tagging and fail-closed guardrails.
"""

import logging
from datetime import datetime
from typing import Any

try:
    from ...planning.execution_result import ExecutionResult
    from ..base_backend import BaseBackendAdapter
except (ImportError, ValueError):
    from core.planning.execution_result import ExecutionResult
    from core.backends.base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)


class ResearchEngineBackend(BaseBackendAdapter):
    """
    Backend adapter connecting Aura's ResearchEngine to the Universal Capability Runtime.
    """

    def __init__(self, engine: Any | None = None) -> None:
        if engine is None:
            from research.research_engine import ResearchEngine
            self.engine = ResearchEngine()
        else:
            self.engine = engine

    @property
    def name(self) -> str:
        return "research_engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "research",
            "research.search",
            "research.synthesize",
            "research.deep_query",
            "web_search",
        ]

    def describe(self) -> dict[str, Any]:
        enabled_providers = (
            len(self.engine.search_manager.enabled_providers)
            if self.engine and hasattr(self.engine, "search_manager") and self.engine.search_manager
            else 0
        )
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 250.0,
            "cost": 0.0,
            "is_local": enabled_providers == 0,
            "version": "2.0.0",
            "active_providers": enabled_providers,
        }

    def health_check(self) -> bool:
        return self.engine is not None

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        start_t = datetime.now().timestamp()
        args = arguments or {}
        cap_clean = capability.lower().strip()

        logger.info(
            f"[ResearchEngineBackend] Executing capability '{cap_clean}' for goal: '{goal}'"
        )

        try:
            # ── 1. Search Query ───────────────────────────────────────────────
            if cap_clean in ("research.search", "web_search"):
                query = args.get("query") or args.get("topic") or goal
                max_results = int(args.get("max_results", 5))

                if not str(query).strip():
                    return ExecutionResult(
                        success=False,
                        planner="research",
                        goal=goal,
                        observations=["❌ Search failed: Empty query provided."],
                        data={"error": "Search query cannot be empty."},
                    )

                results, meta = self.engine.search(
                    query=query, max_results=max_results, allow_mock=True
                )

                if meta.get("error"):
                    return ExecutionResult(
                        success=False,
                        planner="research",
                        goal=goal,
                        observations=[f"❌ Search failed: {meta['error']}"],
                        data=meta,
                    )

                is_offline = meta.get("offline_mode", False)
                prefix = "[Offline / Mock Search] " if is_offline else ""

                if not results:
                    return ExecutionResult(
                        success=False,
                        planner="research",
                        goal=goal,
                        observations=[
                            f"❌ {prefix}Zero search results found for '{query}'. "
                            f"Try refining query keywords or specifying target domains."
                        ],
                        data=dict(meta, error=f"Zero search results for '{query}'."),
                    )

                # Format search result snippets
                snippets = []
                serialized_results = []
                for idx, r in enumerate(results, start=1):
                    snippets.append(f"{idx}. {r.title} ({r.url})\n   {r.snippet}")
                    serialized_results.append(
                        {
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "source": r.source,
                            "score": r.score,
                        }
                    )

                obs_text = (
                    f"✓ {prefix}Found {len(results)} relevant sources for '{query}':\n"
                    + "\n".join(snippets)
                )

                dur = datetime.now().timestamp() - start_t
                return ExecutionResult(
                    success=True,
                    planner="research",
                    goal=goal,
                    confidence=1.0 if not is_offline else 0.85,
                    execution_time_seconds=dur,
                    observations=[obs_text],
                    artifacts=[
                        {
                            "artifact_id": "art_search_results",
                            "artifact_type": "research",
                            "content": serialized_results,
                            "data": {"results": serialized_results, "query": query},
                        }
                    ],
                    data={
                        "backend": self.name,
                        "capability": cap_clean,
                        "query": query,
                        "results": serialized_results,
                        "count": len(results),
                        "offline_mode": is_offline,
                        "is_mock": meta.get("is_mock", False),
                        "provider": meta.get("provider", "unknown"),
                    },
                )

            # ── 2. Synthesize Evidence ────────────────────────────────────────
            elif cap_clean == "research.synthesize":
                topic = args.get("topic") or goal
                sources = args.get("sources") or args.get("results")

                if not sources and args.get("content"):
                    content_val = args.get("content")
                    if isinstance(content_val, list):
                        sources = content_val
                    elif isinstance(content_val, dict) and "results" in content_val:
                        sources = content_val["results"]
                    elif isinstance(content_val, str) and content_val.strip():
                        sources = [{"title": "Search Summary", "url": "https://research.internal", "snippet": content_val, "score": 85.0}]

                if not sources and args.get("artifact"):
                    art_obj = args.get("artifact")
                    art_cnt = getattr(art_obj, "content", None)
                    if isinstance(art_cnt, list):
                        sources = art_cnt
                    elif isinstance(art_cnt, str) and art_cnt.strip():
                        sources = [{"title": "Search Summary", "url": "https://research.internal", "snippet": art_cnt, "score": 85.0}]

                if not sources:
                    sources = []

                synth_result = self.engine.synthesize(topic=topic, sources=sources)

                if not synth_result.get("success", False):
                    err_msg = synth_result.get("error", "Synthesis failed.")
                    return ExecutionResult(
                        success=False,
                        planner="research",
                        goal=goal,
                        observations=[f"❌ Failed to synthesize research for '{topic}': {err_msg}"],
                        data=synth_result,
                    )

                summary = synth_result.get("summary", "")
                citations = synth_result.get("citations", [])
                conf_score = synth_result.get("confidence_score", 0.0)

                # Format citations block
                cit_lines = []
                for c in citations:
                    c_title = c.get("title") or c.get("source", "Source")
                    c_url = c.get("url", "")
                    cit_lines.append(f"- [{c_title}]({c_url})" if c_url else f"- {c_title}")

                cit_block = "\n" + "\n".join(cit_lines) if cit_lines else ""
                obs_text = (
                    f"✓ Synthesized findings for '{topic}' (Confidence: {conf_score:.0%}):\n\n"
                    f"{summary}\n\n"
                    f"Sources & Citations:{cit_block}"
                )

                dur = datetime.now().timestamp() - start_t
                return ExecutionResult(
                    success=True,
                    planner="research",
                    goal=goal,
                    confidence=conf_score,
                    execution_time_seconds=dur,
                    observations=[obs_text],
                    data={
                        "backend": self.name,
                        "capability": cap_clean,
                        "topic": topic,
                        "summary": summary,
                        "citations": citations,
                        "confidence_score": conf_score,
                    },
                )

            # ── 3. Deep Research Loop / Standard Research ─────────────────────
            elif cap_clean in ("research.deep_query", "research"):
                question = args.get("question") or args.get("query") or goal
                rounds = int(args.get("rounds", 3))

                report = self.engine.deep_query(question=question, rounds=rounds)
                summary = report.summary or "Deep research concluded."
                conf = (
                    report.key_stats.get("confidence_score", 85.0) / 100.0
                    if isinstance(report.key_stats, dict)
                    else 0.85
                )

                obs_text = (
                    f"✓ Deep Research Report on '{question}' (Duration: {report.duration:.1f}s):\n\n"
                    f"{summary}"
                )

                dur = datetime.now().timestamp() - start_t
                return ExecutionResult(
                    success=True,
                    planner="research",
                    goal=goal,
                    confidence=conf,
                    execution_time_seconds=dur,
                    observations=[obs_text],
                    data={
                        "backend": self.name,
                        "capability": cap_clean,
                        "question": question,
                        "report_summary": summary,
                        "duration": report.duration,
                        "sources_count": len(report.results),
                    },
                )

            else:
                return ExecutionResult(
                    success=False,
                    planner="research",
                    goal=goal,
                    observations=[f"❌ Unknown research capability: '{cap_clean}'"],
                    data={"error": f"Capability '{cap_clean}' not supported by ResearchEngineBackend."},
                )

        except Exception as exc:
            logger.exception(f"[ResearchEngineBackend] Error executing '{cap_clean}': {exc}")
            return ExecutionResult(
                success=False,
                planner="research",
                goal=goal,
                observations=[f"❌ Research backend error: {str(exc)}"],
                data={"error": str(exc)},
            )

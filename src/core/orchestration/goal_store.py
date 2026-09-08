"""
Goal Store - SQLite persistence for AuraAI Agent Loop Goals and Steps.
Location: src/core/orchestration/goal_store.py

Provides CRUD operations and lifecycle persistence for Goal and Step records
stored in the central Memory.db database via OrchestrationStore connection management.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

from .goal_state import Goal, GoalStatus, Step, StepStatus
from .orchestration_store import OrchestrationStore

logger = logging.getLogger(__name__)

# Max characters stored for a single tool observation to prevent DB bloat
MAX_OBSERVATION_LENGTH = 10000


def _enum_str(val: Any) -> str:
    if isinstance(val, Enum):
        return val.value
    return str(val)


class GoalStore:
    """
    Thread-safe persistence layer for Goal and Step instances in Memory.db.
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        store: OrchestrationStore | None = None,
    ) -> None:
        self.store = store or OrchestrationStore(db_path=db_path)

    def create_goal(self, goal: Goal) -> None:
        """Persist a new Goal record."""
        with self.store._lock, self.store._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO goals (goal_id, session_id, user_prompt, status, max_steps, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    goal.goal_id,
                    goal.session_id,
                    goal.user_prompt,
                    _enum_str(goal.status),
                    goal.max_steps,
                    goal.created_at,
                ),
            )
            conn.commit()
        logger.debug(f"[GoalStore] Created goal [{goal.goal_id}] for session [{goal.session_id}]")

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Fetch a Goal and its associated Steps by goal_id."""
        with self.store._lock, self.store._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM goals WHERE goal_id = ?;",
                (goal_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            steps = self._get_steps_for_goal_conn(conn, goal_id)
            return Goal(
                goal_id=row["goal_id"],
                session_id=row["session_id"],
                user_prompt=row["user_prompt"],
                status=GoalStatus(row["status"]),
                steps=steps,
                max_steps=row["max_steps"],
                created_at=row["created_at"],
            )

    def list_goals_for_session(self, session_id: str) -> List[Goal]:
        """List all Goals associated with a given session_id in chronological order."""
        with self.store._lock, self.store._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM goals WHERE session_id = ? ORDER BY created_at ASC;",
                (session_id,),
            )
            rows = cursor.fetchall()
            goals: List[Goal] = []
            for row in rows:
                steps = self._get_steps_for_goal_conn(conn, row["goal_id"])
                goals.append(
                    Goal(
                        goal_id=row["goal_id"],
                        session_id=row["session_id"],
                        user_prompt=row["user_prompt"],
                        status=GoalStatus(row["status"]),
                        steps=steps,
                        max_steps=row["max_steps"],
                        created_at=row["created_at"],
                    )
                )
            return goals

    def update_goal_status(self, goal_id: str, status: GoalStatus | str) -> None:
        """Update the status of an existing Goal."""
        status_str = _enum_str(status)
        with self.store._lock, self.store._get_connection() as conn:
            conn.execute(
                "UPDATE goals SET status = ? WHERE goal_id = ?;",
                (status_str, goal_id),
            )
            conn.commit()
        logger.debug(f"[GoalStore] Updated goal [{goal_id}] status to '{status_str}'")

    def add_step(self, step: Step) -> None:
        """Persist a new Step record associated with a Goal."""
        obs = step.observation
        if obs is not None and len(obs) > MAX_OBSERVATION_LENGTH:
            obs = obs[:MAX_OBSERVATION_LENGTH] + "... [TRUNCATED]"

        tool_args_str = json.dumps(step.tool_args or {}, default=str)

        with self.store._lock, self.store._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO goal_steps (
                    step_id, goal_id, tool_name, tool_args, status,
                    observation, verify_reason, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    step.step_id,
                    step.goal_id,
                    step.tool_name,
                    tool_args_str,
                    _enum_str(step.status),
                    obs,
                    step.verify_reason,
                    step.created_at,
                ),
            )
            conn.commit()
        logger.debug(f"[GoalStore] Added step [{step.step_id}] (tool='{step.tool_name}') to goal [{step.goal_id}]")

    def update_step_status(
        self,
        step_id: str,
        status: StepStatus | str,
        observation: Optional[str] = None,
        verify_reason: Optional[str] = None,
    ) -> None:
        """Update the status, observation, and/or verify_reason of a Step."""
        status_str = _enum_str(status)
        fields = ["status = ?"]
        params: List[Any] = [status_str]

        if observation is not None:
            if len(observation) > MAX_OBSERVATION_LENGTH:
                observation = observation[:MAX_OBSERVATION_LENGTH] + "... [TRUNCATED]"
            fields.append("observation = ?")
            params.append(observation)

        if verify_reason is not None:
            fields.append("verify_reason = ?")
            params.append(verify_reason)

        params.append(step_id)
        query = f"UPDATE goal_steps SET {', '.join(fields)} WHERE step_id = ?;"

        with self.store._lock, self.store._get_connection() as conn:
            conn.execute(query, tuple(params))
            conn.commit()
        logger.debug(f"[GoalStore] Updated step [{step_id}] status to '{status_str}'")

    def get_steps_for_goal(self, goal_id: str) -> List[Step]:
        """Fetch all Steps for a Goal in chronological order."""
        with self.store._lock, self.store._get_connection() as conn:
            return self._get_steps_for_goal_conn(conn, goal_id)

    def _get_steps_for_goal_conn(self, conn: Any, goal_id: str) -> List[Step]:
        cursor = conn.execute(
            "SELECT * FROM goal_steps WHERE goal_id = ? ORDER BY created_at ASC;",
            (goal_id,),
        )
        rows = cursor.fetchall()
        steps: List[Step] = []
        for r in rows:
            args = {}
            if r["tool_args"]:
                try:
                    args = json.loads(r["tool_args"])
                except Exception:
                    args = {}
            steps.append(
                Step(
                    step_id=r["step_id"],
                    goal_id=r["goal_id"],
                    tool_name=r["tool_name"],
                    tool_args=args,
                    status=StepStatus(r["status"]),
                    observation=r["observation"],
                    verify_reason=r["verify_reason"],
                    created_at=r["created_at"],
                )
            )
        return steps

"""
Autonomous Coding Agent

An agent that can autonomously generate, save, execute, and debug Python code.
Works like Codex - takes a requirement and executes it automatically without user prompts.
"""

import asyncio
import re
import time
from pathlib import Path
from typing import Any

from core import logger
from core.tools.code_execution.code_execution_tool import CodeExecutionTool


class AutonomousCodingAgent:
    """
    Autonomous coding agent that executes Python code automatically.

    Capabilities:
        - Take natural language requirements
        - Generate Python code using LLM
        - Save code to file
        - Execute code
        - Automatically fix errors
        - Report results
    """

    def __init__(self, aura_core, max_attempts: int = 3, timeout: int = 60):
        """
        Initialize autonomous coding agent.

        Args:
            aura_core: AuraCore instance for LLM access
            max_attempts: Maximum number of retry attempts for error fixing
            timeout: Execution timeout in seconds
        """
        self.aura_core = aura_core
        self.max_attempts = max_attempts
        self.timeout = timeout

        # Get workspace root from aura_core and convert to Path if needed
        workspace = getattr(aura_core, "workspace", None)
        if workspace is None:
            workspace = Path.cwd()
        elif isinstance(workspace, str):
            workspace = Path(workspace)

        self.workspace_root = workspace

        # Initialize code executor
        self.code_executor = CodeExecutionTool(workspace_root=self.workspace_root)

        logger.info("Autonomous Coding Agent initialized")

    async def execute_task(self, requirement: str) -> dict[str, Any]:
        """
        Execute a coding task autonomously.

        Args:
            requirement: Natural language description of what to code

        Returns:
            Dict with execution results:
            {
                'success': bool,
                'output': str,
                'error': str,
                'attempts': int,
                'final_code': str,
                'filename': str,
                'execution_time': float,
                'message': str
            }
        """
        logger.info(f"Starting autonomous task: {requirement[:100]}...")

        result = {
            "success": False,
            "output": "",
            "error": "",
            "attempts": 0,
            "final_code": "",
            "filename": "",
            "execution_time": 0.0,
            "message": "",
        }

        for attempt in range(1, self.max_attempts + 1):
            result["attempts"] = attempt
            logger.info(f"Attempt {attempt}/{self.max_attempts}")

            # Generate code from requirement
            generated_code = await self._generate_code(requirement)

            if not generated_code:
                result["message"] = f"Failed to generate code (attempt {attempt})"
                logger.error(result["message"])
                continue

            result["final_code"] = generated_code

            # Save and execute the code
            execution_result = await self._save_and_execute_code(generated_code)

            if execution_result["success"]:
                # Success!
                result["success"] = True
                result["output"] = execution_result["output"]
                result["filename"] = execution_result["filename"]
                result["execution_time"] = execution_result["execution_time"]
                result["message"] = f"Successfully executed in {attempt} attempt(s)"
                logger.info(f"Task completed successfully in {attempt} attempt(s)")
                break
            else:
                # Code failed - record the error regardless of whether we can retry
                logger.warning(
                    f"Code execution failed (attempt {attempt}): {execution_result['error']}"
                )
                result["error"] = execution_result["error"]

                if attempt < self.max_attempts:
                    # Ask LLM to fix the error
                    fix_attempt = attempt + 1
                    logger.info(f"Requesting fix (attempt {fix_attempt})...")

                    fixed_code = await self._fix_code(
                        generated_code, execution_result["error"], requirement
                    )

                    if not fixed_code:
                        result["message"] = (
                            f"Failed to fix code (attempt {fix_attempt})"
                        )
                        logger.error(result["message"])
                        break

                    result["final_code"] = fixed_code
                    result["error"] = ""  # Clear error for next attempt
                else:
                    # Out of attempts — record a real failure message instead of
                    # leaving result['message'] blank, so callers always know why
                    # the task ultimately failed.
                    result["message"] = (
                        f"Failed after {attempt} attempt(s). "
                        f"Last error: {execution_result['error']}"
                    )
                    result["output"] = execution_result.get("output", "")
                    logger.error(result["message"])

        return result

    async def _call_llm(self, system_prompt: str, user_message: str) -> str | None:
        """
        Call the LLM directly for code generation, bypassing ConversationEngine's
        intent classification entirely.

        Code-generation prompts (which contain instructions like "format as a
        Python code block", URLs, error tracebacks, etc.) are not user chat
        messages, and routing them through the conversational intent router
        (get_ai_response -> ConversationEngine.process) risks the request being
        misclassified as something else (e.g. web_search, memory lookup) instead
        of being sent straight to the model. Calling the Groq client directly
        guarantees the model actually sees the code-generation prompt.

        Args:
            system_prompt: System instructions for the model
            user_message: The user-role message content

        Returns:
            Raw text response from the model, or None on failure
        """
        if (
            not getattr(self.aura_core, "llm_enabled", False)
            or self.aura_core.groq_client is None
        ):
            logger.error("Cannot call LLM directly: Groq client not available/enabled")
            return None

        try:
            model = getattr(self.aura_core, "groq_model", "openai/gpt-oss-120b")

            # Run the blocking Groq SDK call in a thread so we don't block the event loop
            response = await asyncio.to_thread(
                self.aura_core.groq_client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Direct LLM call failed: {e}", exc_info=True)
            return None

    async def _generate_code(self, requirement: str) -> str | None:
        """
        Generate Python code from a requirement using LLM.

        Args:
            requirement: Natural language requirement

        Returns:
            Generated Python code or None if failed
        """
        system_prompt = (
            "You are an expert Python programmer. Generate Python code to "
            "accomplish the given task.\n\n"
            "Requirements:\n"
            "1. Write clean, well-commented Python code\n"
            "2. Use appropriate error handling\n"
            "3. Include necessary imports\n"
            "4. Make the code complete and runnable\n"
            "5. Keep it simple and focused\n\n"
            "Respond with ONLY a single Python code block, formatted exactly as:\n"
            "```python\n"
            "<code here>\n"
            "```\n"
            "Do not include any explanation before or after the code block."
        )

        try:
            # Add context from conversation history
            conversation_history = self.aura_core.get_conversation_history()
            recent_context = "\n".join(
                f"{turn.get('role', '')}: {turn.get('content', '')}"
                for turn in conversation_history[-3:]
            )  # Last 3 turns

            user_message = f"Task: {requirement}"
            if recent_context:
                user_message = (
                    f"Recent conversation context:\n{recent_context}\n\n{user_message}"
                )

            # Get AI response directly from the model (no intent routing)
            response = await self._call_llm(system_prompt, user_message)

            if not response:
                logger.error("No response received from LLM during code generation")
                return None

            # Extract code block from response
            code = self._extract_code_block(response)

            if code:
                logger.info(f"Generated code successfully (length: {len(code)} chars)")
                return code
            else:
                logger.error(
                    "Failed to extract code block from response. Raw response was:\n"
                    f"{response}"
                )
                return None

        except Exception as e:
            logger.error(f"Error generating code: {e}", exc_info=True)
            return None

    async def _fix_code(
        self, original_code: str, error: str, requirement: str
    ) -> str | None:
        """
        Ask LLM to fix code that failed.

        Args:
            original_code: Code that failed
            error: Error message
            requirement: Original requirement

        Returns:
            Fixed code or None if failed
        """
        system_prompt = (
            "You are an expert Python programmer. Fix the Python code that has an error.\n\n"
            "IMPORTANT: The original task/requirement below may include specific constraints "
            "(e.g. 'do not catch this exception', 'let it crash', 'do not validate input'). "
            "Do NOT silently override those constraints just to make the code stop erroring — "
            "for example, do not wrap something in try/except to suppress an error if the "
            "requirement explicitly asked for the error to propagate. Only fix errors that are "
            "not an intentional, requested behavior.\n\n"
            "Requirements:\n"
            "1. Fix the error in the code, respecting the original requirement's intent\n"
            "2. Keep the same structure and logic where possible\n"
            "3. Make the code runnable\n"
            "Respond with ONLY the fixed code as a single Python code block, formatted exactly as:\n"
            "```python\n"
            "<code here>\n"
            "```\n"
            "Do not include any explanation before or after the code block."
        )

        user_message = (
            f"Original requirement: {requirement}\n\n"
            f"Original Code:\n```python\n{original_code}\n```\n\n"
            f"Error:\n{error}\n\n"
            "Fixed Code:"
        )

        try:
            response = await self._call_llm(system_prompt, user_message)

            if not response:
                logger.error("No response received from LLM during code fix")
                return None

            # Extract code block from response
            fixed_code = self._extract_code_block(response)

            if fixed_code:
                logger.info("Fixed code generated successfully")
                return fixed_code
            else:
                logger.error(
                    "Failed to extract fixed code block from response. Raw response was:\n"
                    f"{response}"
                )
                return None

        except Exception as e:
            logger.error(f"Error fixing code: {e}", exc_info=True)
            return None

    async def _save_and_execute_code(self, code: str) -> dict[str, Any]:
        """
        Save code to file and execute it.

        Args:
            code: Python code to execute

        Returns:
            Dict with execution results
        """

        start_time = time.time()

        # Save code to file
        filename = self.code_executor.save_and_execute(code)

        execution_time = time.time() - start_time

        if not filename["success"]:
            return filename  # Error already in the result dict

        # Execute the code
        return self.code_executor._execute_code(
            self.code_executor.code_dir / filename["filename"], self.timeout
        )

    def _extract_code_block(self, text: str) -> str | None:
        """
        Extract Python code block from text.

        Args:
            text: Text that may contain a code block

        Returns:
            Extracted code or None if not found
        """
        if not text:
            return None

        # Primary pattern: ```python ... ``` or ``` ... ```
        code_pattern = r"```(?:python)?\s*([\s\S]*?)```"
        matches = list(re.finditer(code_pattern, text))

        if matches:
            code = matches[0].group(1).strip()
            if code:
                return code

        # Fallback: no fenced block found (or it was empty). If the response
        # looks like it's mostly code already (common indicators: 'import ',
        # 'def ', 'print(' etc. and no prose-like sentence structure), just
        # use the whole response rather than failing outright.
        stripped = text.strip()
        code_indicators = (
            "import ",
            "def ",
            "class ",
            "print(",
            "#!/usr/bin/env python",
        )
        if any(
            stripped.startswith(ind) or f"\n{ind}" in stripped
            for ind in code_indicators
        ):
            logger.warning(
                "No fenced code block found; falling back to raw response as code"
            )
            return stripped

        return None

    def get_status(self) -> dict[str, Any]:
        """
        Get agent status.

        Returns:
            Status dictionary
        """
        return {
            "agent": "AutonomousCodingAgent",
            "max_attempts": self.max_attempts,
            "timeout": self.timeout,
            "workspace_root": str(self.workspace_root),
            "code_directory": str(self.code_executor.code_dir),
            "initialized": self.code_executor is not None,
        }

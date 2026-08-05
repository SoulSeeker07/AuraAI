"""
Response Coordinator

Streams responses with proper formatting.
Everything returns through here, not directly to UI.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from brain.request import AuraResponse, ExecutionResult, ResponseStatus, ToolResult

logger = logging.getLogger(__name__)


class ResponseCoordinator:
    """
    Coordinates response streaming with proper formatting.

    Responsibilities:
        - Stream responses with markdown formatting
        - Add tool result annotations
        - Add thinking/throttling events
        - Add progress indicators
        - Handle errors gracefully

    This ensures all external interfaces (desktop, overlay, API)
    get consistent, well-formatted responses.
    """

    def __init__(self, enable_markdown: bool = True):
        """
        Initialize Response Coordinator.

        Args:
            enable_markdown: Whether to enable markdown formatting
        """
        self.enable_markdown = enable_markdown
        logger.info("Response Coordinator initialized")

    async def stream(self, response: AuraResponse) -> AsyncGenerator[str, None]:
        """
        Stream the response to the user.

        This method yields chunks of text that the UI can display
        in real-time as the response is generated.

        Args:
            response: Complete AuraResponse

        Yields:
            Streaming chunks for UI consumption
        """
        start_time = 0

        # Yield status indicator
        yield self._format_status_header(response.status)

        # Yield tool results if any
        if response.has_tools:
            yield "\n\n"
            for tool_result in response.tool_results:
                yield self._format_tool_result(tool_result)

        # Yield final text with markdown if enabled
        if self.enable_markdown:
            yield self._format_markdown(response.text)
        else:
            yield response.text

        # Yield error/warning indicators if any
        if response.is_error:
            yield self._format_error_indicator()

        # Yield execution time
        if response.execution_time > 0:
            yield self._format_execution_time(response.execution_time)

    def _format_status_header(self, status: ResponseStatus) -> str:
        """Format status header for the response."""
        status_colors = {
            ResponseStatus.SUCCESS: "\033[92m✓",
            ResponseStatus.ERROR: "\033[91m✗",
            ResponseStatus.PARTIAL: "\033[93m⚠",
        }

        color = status_colors.get(status, "\033[0m?")
        return f"{color} Aura Response\n{'-' * 40}\n"

    def _format_markdown(self, text: str) -> str:
        """
        Format text with basic markdown.

        Args:
            text: Plain text

        Returns:
            Markdown-formatted text
        """
        # Escape HTML characters
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Convert bold
        import re

        text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)

        # Convert code blocks
        text = re.sub(
            r"```(\w+)?\n(.*?)```", r"<pre><code>\2</code></pre>", text, flags=re.DOTALL
        )

        # Convert inline code
        text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)

        return text

    def _format_tool_result(self, tool_result: ToolResult) -> str:
        """Format a tool execution result."""
        if tool_result.success:
            return f"**Tool: {tool_result.tool_name}**\n{tool_result.output}\n"
        else:
            return f"**Tool: {tool_result.tool_name} - Failed**\n{tool_result.error}\n"

    def _format_error_indicator(self) -> str:
        """Format error indicator at the end."""
        return "\n\n⚠️ Some operations failed. Please try again."

    def _format_execution_time(self, seconds: float) -> str:
        """Format execution time."""
        return f"\n\n*Execution time: {seconds:.2f}s*"

    async def stream_from_result(
        self, result: ExecutionResult
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from an ExecutionResult.

        This is used internally by AuraBrain before converting to AuraResponse.

        Args:
            result: ExecutionResult from decision execution

        Yields:
            Streaming chunks
        """
        # Yield thinking/throttling events
        if result.thinking:
            yield "Thinking...\n"

        # Yield tool execution results
        if result.has_tools:
            for tool_result in result.tool_results:
                yield f"\n**Tool Result: {tool_result.tool_name}**\n{tool_result.output}\n"

        # Yield final answer
        yield f"{result.text}\n"

        # Yield errors
        if result.errors:
            for error in result.errors:
                yield f"\n⚠️ {error}\n"

    def format_summary(self, response: AuraResponse) -> str:
        """
        Format a summary version of the response.

        This is used for quick summaries, notifications, etc.

        Args:
            response: AuraResponse

        Returns:
            Formatted summary string
        """
        summary_parts = []

        # Status
        status_emoji = {
            ResponseStatus.SUCCESS: "✓",
            ResponseStatus.ERROR: "✗",
            ResponseStatus.PARTIAL: "⚠",
        }
        summary_parts.append(f"{status_emoji[response.status]} Aura Response")

        # Execution time
        if response.execution_time > 0:
            summary_parts.append(f"({response.execution_time:.2f}s)")

        # Text preview
        if response.text:
            preview = response.text[:100]
            summary_parts.append(f"\n{preview}...")

        # Tool results count
        if response.has_tools:
            summary_parts.append(f"\nExecuted {len(response.tool_results)} tools")

        return "\n".join(summary_parts)

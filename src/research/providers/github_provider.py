"""
GitHub Research Provider

Provides research capabilities from GitHub repositories.
"""

import logging
from typing import Any
from urllib.parse import quote

import requests

from ..content_fetcher import ContentFetcher
from ..models import SearchResult
from ..provider_interface import BaseResearchProvider

logger = logging.getLogger(__name__)


class GitHubProvider(BaseResearchProvider):
    """
    GitHub API research provider.

    Searches GitHub for repositories, issues, and pull requests.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize GitHub provider.

        Args:
            config: Provider configuration
        """
        api_token = config.get("api_token")
        super().__init__(config, name="github", trust_level="github")
        self.api_token = api_token
        self.content_fetcher = ContentFetcher()
        self.base_url = "https://api.github.com"

    def is_available(self) -> bool:
        """Check if GitHub API is available."""
        return bool(self.api_token)

    def search(self, query: str, max_results: int = 10, **kwargs) -> list[SearchResult]:
        """
        Perform search on GitHub.

        Args:
            query: Search query
            max_results: Maximum number of results
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        if not self.is_available():
            logger.warning("GitHub API token not configured")
            return []

        try:
            results = []

            # Search repositories
            results.extend(self._search_repositories(query, max_results))

            # Search issues
            results.extend(self._search_issues(query, max_results))

            # Sort by score
            results.sort(key=lambda r: r.score, reverse=True)

            return results[:max_results]

        except Exception as e:
            logger.error(f"GitHub search error: {e}")
            return []

    def _search_repositories(self, query: str, max_results: int) -> list[SearchResult]:
        """
        Search GitHub repositories.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            Repository search results
        """
        try:
            url = f"{self.base_url}/search/repositories"
            headers = {
                "Authorization": f"token {self.api_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            params = {"q": query, "per_page": min(max_results, 100)}

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                result = self._parse_repository(item)
                results.append(result)

            logger.info(f"GitHub search found {len(results)} repositories")
            return results

        except Exception as e:
            logger.error(f"GitHub repository search failed: {e}")
            return []

    def _search_issues(self, query: str, max_results: int) -> list[SearchResult]:
        """
        Search GitHub issues.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            Issue search results
        """
        try:
            url = f"{self.base_url}/search/issues"
            headers = {
                "Authorization": f"token {self.api_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            params = {"q": query, "per_page": min(max_results, 100)}

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                result = self._parse_issue(item)
                results.append(result)

            logger.info(f"GitHub search found {len(results)} issues")
            return results

        except Exception as e:
            logger.error(f"GitHub issue search failed: {e}")
            return []

    def _parse_repository(self, raw_data: dict[str, Any]) -> SearchResult:
        """
        Parse a GitHub repository.

        Args:
            raw_data: Raw repository data

        Returns:
            Parsed search result
        """
        return SearchResult(
            url=raw_data.get("html_url", ""),
            title=raw_data.get("full_name", ""),
            snippet=raw_data.get("description", ""),
            source=self.name,
            score=raw_data.get("score", 50),
            trust_level=self.trust_level,
            raw_data=raw_data,
        )

    def _parse_issue(self, raw_data: dict[str, Any]) -> SearchResult:
        """
        Parse a GitHub issue.

        Args:
            raw_data: Raw issue data

        Returns:
            Parsed search result
        """
        return SearchResult(
            url=raw_data.get("html_url", ""),
            title=raw_data.get("title", ""),
            snippet=raw_data.get("body", "")[:200],
            source=self.name,
            score=raw_data.get("score", 50),
            trust_level=self.trust_level,
            raw_data=raw_data,
        )

    def get_repository_info(self, repo: str) -> dict[str, Any] | None:
        """
        Get detailed information about a repository.

        Args:
            repo: Repository name (owner/repo)

        Returns:
            Repository information or None
        """
        try:
            url = f"{self.base_url}/repos/{quote(repo)}"
            headers = {
                "Authorization": f"token {self.api_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get repository info for {repo}: {e}")
            return None

    def get_issues_for_repo(
        self, repo: str, state: str = "open", per_page: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get issues for a repository.

        Args:
            repo: Repository name
            state: Issue state (open, closed, all)
            per_page: Results per page

        Returns:
            List of issues
        """
        try:
            url = f"{self.base_url}/repos/{quote(repo)}/issues"
            headers = {
                "Authorization": f"token {self.api_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            params = {"state": state, "per_page": per_page}

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get issues for {repo}: {e}")
            return []

    def get_capabilities(self) -> list[str]:
        """Get provider capabilities."""
        return ["search", "repository_info", "issues", "document_fetch"]

    def validate_config(self) -> bool:
        """Validate provider configuration."""
        if not self.api_token:
            logger.warning("GitHub API token not set")
            return False
        return True

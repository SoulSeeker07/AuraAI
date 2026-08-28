"""
Site Registry
Location: src/browser/planner/site_registry.py

Known site profiles for popular platforms (Instagram, GitHub, LinkedIn, YouTube, Google).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SiteProfile:
    name: str
    base_url: str
    profile_url_template: str
    search_url_template: str
    auth_required: bool = True
    username_memory_key: str = ""


class SiteRegistry:
    """
    Registry of known site profiles and URL patterns.
    """

    _SITES: dict[str, SiteProfile] = {
        "instagram": SiteProfile(
            name="instagram",
            base_url="https://www.instagram.com",
            profile_url_template="https://www.instagram.com/{username}/",
            search_url_template="https://www.instagram.com/explore/tags/{query}/",
            auth_required=True,
            username_memory_key="instagram_username",
        ),
        "github": SiteProfile(
            name="github",
            base_url="https://github.com",
            profile_url_template="https://github.com/{username}",
            search_url_template="https://github.com/search?q={query}",
            auth_required=False,
            username_memory_key="github_username",
        ),
        "linkedin": SiteProfile(
            name="linkedin",
            base_url="https://www.linkedin.com",
            profile_url_template="https://www.linkedin.com/in/{username}/",
            search_url_template="https://www.linkedin.com/search/results/all/?keywords={query}",
            auth_required=True,
            username_memory_key="linkedin_username",
        ),
        "youtube": SiteProfile(
            name="youtube",
            base_url="https://www.youtube.com",
            profile_url_template="https://www.youtube.com/@{username}",
            search_url_template="https://www.youtube.com/results?search_query={query}",
            auth_required=False,
            username_memory_key="youtube_username",
        ),
        "google": SiteProfile(
            name="google",
            base_url="https://www.google.com",
            profile_url_template="",
            search_url_template="https://www.google.com/search?q={query}",
            auth_required=False,
            username_memory_key="",
        ),
        "google flights": SiteProfile(
            name="google flights",
            base_url="https://www.google.com/travel/flights",
            profile_url_template="",
            search_url_template="https://www.google.com/travel/flights?q={query}",
            auth_required=False,
            username_memory_key="",
        ),
        "flights": SiteProfile(
            name="flights",
            base_url="https://www.google.com/travel/flights",
            profile_url_template="",
            search_url_template="https://www.google.com/travel/flights?q={query}",
            auth_required=False,
            username_memory_key="",
        ),
        "amazon": SiteProfile(
            name="amazon",
            base_url="https://www.amazon.in",
            profile_url_template="https://www.amazon.in/gp/profile/amzn1.account.{username}",
            search_url_template="https://www.amazon.in/s?k={query}",
            auth_required=False,
            username_memory_key="amazon_username",
        ),
        "ebay": SiteProfile(
            name="ebay",
            base_url="https://www.ebay.com",
            profile_url_template="https://www.ebay.com/usr/{username}",
            search_url_template="https://www.ebay.com/sch/i.html?_nkw={query}",
            auth_required=False,
            username_memory_key="ebay_username",
        ),
        "wikipedia": SiteProfile(
            name="wikipedia",
            base_url="https://en.wikipedia.org",
            profile_url_template="https://en.wikipedia.org/wiki/User:{username}",
            search_url_template="https://en.wikipedia.org/w/index.php?search={query}",
            auth_required=False,
            username_memory_key="",
        ),
        "flipkart": SiteProfile(
            name="flipkart",
            base_url="https://www.flipkart.com",
            profile_url_template="https://www.flipkart.com/account",
            search_url_template="https://www.flipkart.com/search?q={query}",
            auth_required=False,
            username_memory_key="flipkart_username",
        ),
        "walmart": SiteProfile(
            name="walmart",
            base_url="https://www.walmart.com",
            profile_url_template="https://www.walmart.com/account",
            search_url_template="https://www.walmart.com/search?q={query}",
            auth_required=False,
            username_memory_key="walmart_username",
        ),
        "facebook": SiteProfile(
            name="facebook",
            base_url="https://www.facebook.com",
            profile_url_template="https://www.facebook.com/{username}",
            search_url_template="https://www.facebook.com/search/top/?q={query}",
            auth_required=True,
            username_memory_key="facebook_username",
        ),
        "twitter": SiteProfile(
            name="twitter",
            base_url="https://www.x.com",
            profile_url_template="https://www.x.com/{username}",
            search_url_template="https://www.x.com/search?q={query}",
            auth_required=False,
            username_memory_key="twitter_username",
        ),
        "x": SiteProfile(
            name="x",
            base_url="https://www.x.com",
            profile_url_template="https://www.x.com/{username}",
            search_url_template="https://www.x.com/search?q={query}",
            auth_required=False,
            username_memory_key="x_username",
        ),
        "reddit": SiteProfile(
            name="reddit",
            base_url="https://www.reddit.com",
            profile_url_template="https://www.reddit.com/user/{username}/",
            search_url_template="https://www.reddit.com/search/?q={query}",
            auth_required=False,
            username_memory_key="reddit_username",
        ),
    }

    @classmethod
    def get_site(cls, name: str) -> SiteProfile | None:
        return cls._SITES.get(name.lower().strip())

    @classmethod
    def list_sites(cls) -> list[str]:
        return list(cls._SITES.keys())

"""
Dossier Agent - Multi-Source Data Collection Module.

Collects data from:
1. Serper API (Google Search) - news, bios, statements, associates
2. LinkedIn public profile scraping via URL
3. Internal RAG (future extension point)

Each collector returns structured dicts that feed into the research synthesizer.
"""

import os
import re
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class WebSearchResult:
    """A single web search result."""

    title: str
    url: str
    snippet: str
    date: Optional[str] = None


@dataclass
class LinkedInProfile:
    """Extracted LinkedIn profile data."""

    name: str = ""
    headline: str = ""
    location: str = ""
    summary: str = ""
    experience: List[Dict[str, str]] = field(default_factory=list)
    education: List[Dict[str, str]] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "headline": self.headline,
            "location": self.location,
            "summary": self.summary,
            "experience": self.experience,
            "education": self.education,
            "skills": self.skills,
            "url": self.url,
        }


@dataclass
class CollectedData:
    """All data collected for a single person."""

    name: str
    linkedin_url: str = ""
    linkedin_profile: Optional[LinkedInProfile] = None
    web_results: Dict[str, List[WebSearchResult]] = field(default_factory=dict)
    # Category keys: "bio", "news", "statements", "associates"
    raw_page_text: str = ""  # scraped LinkedIn page text fallback

    def to_dict(self) -> Dict[str, Any]:
        web = {}
        for category, results in self.web_results.items():
            web[category] = [
                {"title": r.title, "url": r.url, "snippet": r.snippet, "date": r.date}
                for r in results
            ]
        return {
            "name": self.name,
            "linkedin_url": self.linkedin_url,
            "linkedin_profile": self.linkedin_profile.to_dict()
            if self.linkedin_profile
            else None,
            "web_results": web,
            "raw_page_text": self.raw_page_text[:2000] if self.raw_page_text else "",
        }


# ---------------------------------------------------------------------------
# Serper Web Search
# ---------------------------------------------------------------------------


class SerperClient:
    """Google Search via Serper API."""

    BASE_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")

    async def search(self, query: str, num_results: int = 10) -> List[WebSearchResult]:
        """Execute a single search query and return structured results."""
        if not self.api_key:
            return []

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "num": min(num_results, 20),
            "autocorrect": True,
            "type": "search",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(self.BASE_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            results: List[WebSearchResult] = []

            # Knowledge graph as first result if available
            kg = data.get("knowledgeGraph")
            if kg:
                results.append(
                    WebSearchResult(
                        title=kg.get("title", ""),
                        url=kg.get("website", ""),
                        snippet=kg.get("description", ""),
                        date=None,
                    )
                )

            for item in data.get("organic", []):
                results.append(
                    WebSearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        date=item.get("date"),
                    )
                )

            return results

        except Exception as e:
            print(f"Serper search error for '{query}': {e}")
            return []


# ---------------------------------------------------------------------------
# LinkedIn Public Profile Scraper
# ---------------------------------------------------------------------------


class LinkedInScraper:
    """
    Scrapes publicly visible LinkedIn profile data.

    This uses a two-pronged approach:
    1. Attempt to fetch the public LinkedIn page directly
    2. Fall back to Serper search for "site:linkedin.com/in/ <name>"

    Note: LinkedIn heavily guards its pages. The scraper extracts what is
    publicly visible without login (name, headline, location, summary snippet).
    For richer data, integrate Composio LinkedIn or a third-party API.
    """

    def __init__(self):
        try:
            self._ua = UserAgent()
        except Exception:
            self._ua = None

    def _get_headers(self) -> Dict[str, str]:
        ua_string = (
            self._ua.random
            if self._ua
            else (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        return {
            "User-Agent": ua_string,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def scrape_profile(self, linkedin_url: str) -> LinkedInProfile:
        """
        Attempt to scrape a LinkedIn public profile.

        Returns a LinkedInProfile with whatever data is publicly accessible.
        Fields that cannot be extracted are left as empty strings/lists.
        """
        profile = LinkedInProfile(url=linkedin_url)

        if not linkedin_url:
            return profile

        # Normalise URL
        url = linkedin_url.rstrip("/")
        if not url.startswith("http"):
            url = "https://" + url

        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers=self._get_headers(),
            ) as client:
                resp = await client.get(url)

                if resp.status_code != 200:
                    return profile

                html = resp.text
                soup = BeautifulSoup(html, "html.parser")

                # Extract name from <title> or og:title
                og_title = soup.find("meta", property="og:title")
                if og_title and og_title.get("content"):
                    raw_title = og_title["content"]
                    # LinkedIn titles are "Name - Title - Company | LinkedIn"
                    parts = raw_title.split(" - ")
                    profile.name = parts[0].strip() if parts else raw_title
                    if len(parts) >= 2:
                        profile.headline = (
                            " - ".join(parts[1:]).replace(" | LinkedIn", "").strip()
                        )
                elif soup.title:
                    profile.name = (
                        soup.title.string.split(" - ")[0].strip()
                        if soup.title.string
                        else ""
                    )

                # og:description often has the summary
                og_desc = soup.find("meta", property="og:description")
                if og_desc and og_desc.get("content"):
                    profile.summary = og_desc["content"].strip()

                # Location from structured data
                loc_tag = soup.find("meta", attrs={"name": "geo.placename"})
                if loc_tag and loc_tag.get("content"):
                    profile.location = loc_tag["content"]

                # Try JSON-LD structured data (sometimes present on public profiles)
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json

                        ld = json.loads(script.string)
                        if isinstance(ld, dict):
                            if ld.get("@type") == "Person":
                                profile.name = profile.name or ld.get("name", "")
                                profile.headline = profile.headline or ld.get(
                                    "jobTitle", ""
                                )
                                if ld.get("address"):
                                    addr = ld["address"]
                                    if isinstance(addr, dict):
                                        profile.location = profile.location or addr.get(
                                            "addressLocality", ""
                                        )
                    except Exception:
                        continue

        except Exception as e:
            print(f"LinkedIn scrape error for {linkedin_url}: {e}")

        return profile

    async def scrape_profile_text(self, linkedin_url: str) -> str:
        """
        Fetch the raw visible text from a LinkedIn public page.
        Useful as a fallback blob for the LLM synthesizer.
        """
        if not linkedin_url:
            return ""

        url = linkedin_url.rstrip("/")
        if not url.startswith("http"):
            url = "https://" + url

        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers=self._get_headers(),
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return ""
                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove script/style
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                # Collapse whitespace
                text = re.sub(r"\n{3,}", "\n\n", text)
                return text[:5000]
        except Exception as e:
            print(f"LinkedIn text scrape error: {e}")
            return ""


# ---------------------------------------------------------------------------
# Aggregating Data Collector
# ---------------------------------------------------------------------------


class DataCollector:
    """
    Orchestrates multi-source data collection for a person.

    Usage:
        collector = DataCollector()
        data = await collector.collect(name="Jane Doe", linkedin_url="https://linkedin.com/in/janedoe")
    """

    # Search query templates per category
    SEARCH_QUERIES = {
        "bio": "{name} biography career background",
        "news": "{name} recent news statements interviews {year}",
        "statements": "{name} quotes opinions positions public statements",
        "associates": "{name} colleagues associates network board members",
    }

    def __init__(
        self,
        serper_api_key: Optional[str] = None,
    ):
        self.serper = SerperClient(api_key=serper_api_key)
        self.linkedin = LinkedInScraper()

    async def collect(
        self,
        name: str,
        linkedin_url: str = "",
    ) -> CollectedData:
        """
        Run all data collection in parallel and return aggregated results.
        """
        from datetime import datetime

        year = datetime.now().year

        collected = CollectedData(name=name, linkedin_url=linkedin_url)

        # Build search tasks
        search_tasks = {}
        for category, template in self.SEARCH_QUERIES.items():
            query = template.format(name=name, year=year)
            search_tasks[category] = self.serper.search(query, num_results=8)

        # LinkedIn tasks
        linkedin_profile_task = self.linkedin.scrape_profile(linkedin_url)
        linkedin_text_task = self.linkedin.scrape_profile_text(linkedin_url)

        # Run all in parallel
        all_tasks = list(search_tasks.values()) + [
            linkedin_profile_task,
            linkedin_text_task,
        ]
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Unpack search results
        categories = list(search_tasks.keys())
        for i, category in enumerate(categories):
            result = results[i]
            if isinstance(result, list):
                collected.web_results[category] = result
            else:
                collected.web_results[category] = []

        # Unpack LinkedIn
        linkedin_idx = len(categories)
        profile_result = results[linkedin_idx]
        text_result = results[linkedin_idx + 1]

        if isinstance(profile_result, LinkedInProfile):
            collected.linkedin_profile = profile_result
        if isinstance(text_result, str):
            collected.raw_page_text = text_result

        return collected

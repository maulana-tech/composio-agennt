"""
Dossier Agent - Multi-Source Data Collection Module.

Collects data from:
1. Serper API (Google Search) - news, bios, statements, associates
2. LinkedIn profile data via:
   a. Composio LINKEDIN_GET_MY_INFO (for self-lookup when user researches themselves)
   b. Enhanced Serper multi-query search (for researching other people)
   c. Direct HTTP scraping as best-effort fallback
3. Internal RAG (future extension point)

Each collector returns structured dicts that feed into the research synthesizer.
"""

import os
import re
import asyncio
import time
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from .exceptions import DossierCollectionError


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
    """Google Search via Serper API with in-memory caching."""

    BASE_URL = "https://google.serper.dev/search"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        # Cache: {query_hash: {"results": [...], "timestamp": float}}
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _cache_key(self, query: str, num_results: int) -> str:
        """Generate a deterministic cache key for a query."""
        raw = f"{query.strip().lower()}|{num_results}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[List[WebSearchResult]]:
        """Return cached results if still valid, else None."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self.CACHE_TTL:
            self._cache.pop(key, None)
            return None
        return entry["results"]

    async def search(self, query: str, num_results: int = 10) -> List[WebSearchResult]:
        """Execute a single search query and return structured results.

        Results are cached for up to CACHE_TTL seconds so that duplicate
        queries within a single dossier generation don't hit the API twice.
        """
        if not self.api_key:
            return []

        # Check cache first
        cache_key = self._cache_key(query, num_results)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

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

            # Store in cache
            self._cache[cache_key] = {
                "results": results,
                "timestamp": time.time(),
            }

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
# Composio LinkedIn Client (self-lookup via GET_MY_INFO)
# ---------------------------------------------------------------------------


class ComposioLinkedInClient:
    """
    Fetches the authenticated user's own LinkedIn profile via Composio.

    This is only useful when the user is generating a dossier about THEMSELVES
    (is_self_lookup=True). For researching OTHER people, use the Serper-based
    approach instead since Composio has no action to look up third-party profiles.

    Requires:
    - COMPOSIO_API_KEY env var (or passed explicitly)
    - User must have connected LinkedIn via Composio OAuth
    """

    def __init__(
        self, composio_api_key: Optional[str] = None, user_id: str = "default"
    ):
        self.api_key = composio_api_key or os.environ.get("COMPOSIO_API_KEY", "")
        self.user_id = user_id
        self._client = None

    def _get_client(self):
        """Lazy-init Composio client."""
        if self._client is None and self.api_key:
            try:
                from composio import Composio

                self._client = Composio(api_key=self.api_key)
            except Exception as e:
                print(f"Failed to initialize Composio client: {e}")
        return self._client

    async def get_my_profile(self) -> LinkedInProfile:
        """
        Fetch the authenticated user's own LinkedIn profile via Composio.

        Returns a LinkedInProfile populated from the Composio response.
        If the call fails or Composio is not configured, returns an empty profile.
        """
        profile = LinkedInProfile()
        client = self._get_client()
        if not client:
            return profile

        try:
            # Composio calls are synchronous, run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.tools.execute(
                    slug="LINKEDIN_GET_MY_INFO",
                    arguments={},
                    user_id=self.user_id,
                    dangerously_skip_version_check=True,
                ),
            )

            # Parse the Composio response into LinkedInProfile
            if isinstance(result, dict):
                data = result.get("data", result)
                profile = self._parse_composio_response(data)

        except Exception as e:
            print(f"Composio LinkedIn GET_MY_INFO error: {e}")

        return profile

    def _parse_composio_response(self, data: Dict[str, Any]) -> LinkedInProfile:
        """Parse Composio LINKEDIN_GET_MY_INFO response into LinkedInProfile."""
        profile = LinkedInProfile()

        if not isinstance(data, dict):
            return profile

        # Name: may come as "localizedFirstName" + "localizedLastName" or "name"
        first = data.get("localizedFirstName", "")
        last = data.get("localizedLastName", "")
        if first or last:
            profile.name = f"{first} {last}".strip()
        else:
            profile.name = data.get("name", "")

        # Headline
        profile.headline = data.get("localizedHeadline", "") or data.get("headline", "")

        # Location
        profile.location = data.get("location", "")
        if isinstance(profile.location, dict):
            # Some responses nest location
            profile.location = profile.location.get("name", str(profile.location))

        # Summary / About
        profile.summary = data.get("summary", "") or data.get("about", "")

        # Profile URL
        vanity = data.get("vanityName", "")
        if vanity:
            profile.url = f"https://www.linkedin.com/in/{vanity}"
        else:
            profile.url = data.get("profileUrl", "") or data.get("url", "")

        # Profile picture (store in summary if present, as we don't have a field)
        picture = data.get("profilePicture", "") or data.get("profilePictureUrl", "")
        if picture and not profile.summary:
            profile.summary = ""

        # Experience (if available in response)
        experience = data.get("positions", []) or data.get("experience", [])
        if isinstance(experience, list):
            for exp in experience[:10]:
                if isinstance(exp, dict):
                    profile.experience.append(
                        {
                            "title": exp.get("title", ""),
                            "company": exp.get("companyName", "")
                            or exp.get("company", ""),
                            "duration": exp.get("timePeriod", "")
                            or exp.get("duration", ""),
                        }
                    )

        # Education (if available)
        education = data.get("educations", []) or data.get("education", [])
        if isinstance(education, list):
            for edu in education[:10]:
                if isinstance(edu, dict):
                    profile.education.append(
                        {
                            "school": edu.get("schoolName", "")
                            or edu.get("school", ""),
                            "degree": edu.get("degreeName", "")
                            or edu.get("degree", ""),
                            "field": edu.get("fieldOfStudy", "")
                            or edu.get("field", ""),
                        }
                    )

        # Skills (if available)
        skills = data.get("skills", [])
        if isinstance(skills, list):
            for skill in skills[:20]:
                if isinstance(skill, str):
                    profile.skills.append(skill)
                elif isinstance(skill, dict):
                    profile.skills.append(skill.get("name", str(skill)))

        return profile


# ---------------------------------------------------------------------------
# Aggregating Data Collector
# ---------------------------------------------------------------------------


class DataCollector:
    """
    Orchestrates multi-source data collection for a person.

    Supports two LinkedIn data collection modes:
    - **Self-lookup** (is_self_lookup=True): Uses Composio LINKEDIN_GET_MY_INFO
      to fetch the authenticated user's own profile. Rich data.
    - **Other-lookup** (is_self_lookup=False, default): Uses enhanced Serper
      multi-query search to extract LinkedIn data from Google's index.
      Falls back to direct HTTP scraping as best-effort.

    Usage:
        collector = DataCollector()
        # Research someone else (default)
        data = await collector.collect(name="Jane Doe", linkedin_url="https://linkedin.com/in/janedoe")
        # Research yourself
        data = await collector.collect(name="My Name", is_self_lookup=True, composio_user_id="user123")
    """

    # Search query templates per category
    SEARCH_QUERIES = {
        "bio": "{name} biography career background",
        "news": "{name} recent news statements interviews {year}",
        "statements": "{name} quotes opinions positions public statements",
        "associates": "{name} colleagues associates network board members",
    }

    # Enhanced LinkedIn search queries for extracting profile data from Google
    LINKEDIN_SEARCH_QUERIES = {
        "profile": 'site:linkedin.com/in/ "{name}"',
        "experience": '"{name}" linkedin experience company title',
        "education": '"{name}" linkedin education university degree',
    }

    def __init__(
        self,
        serper_api_key: Optional[str] = None,
        composio_api_key: Optional[str] = None,
    ):
        self.serper = SerperClient(api_key=serper_api_key)
        self.linkedin = LinkedInScraper()
        self._composio_api_key = composio_api_key

    async def collect(
        self,
        name: str,
        linkedin_url: str = "",
        is_self_lookup: bool = False,
        composio_user_id: str = "default",
    ) -> CollectedData:
        """
        Run all data collection in parallel and return aggregated results.

        LinkedIn data collection uses one of two strategies:
        - **Self-lookup** (is_self_lookup=True): Composio LINKEDIN_GET_MY_INFO
          for rich profile data of the authenticated user.
        - **Other-lookup** (default): Enhanced Serper multi-query search to
          extract LinkedIn data from Google's index, with direct HTTP scraping
          as an additional fallback.

        Args:
            name: Full name of the person to research.
            linkedin_url: Optional LinkedIn profile URL.
            is_self_lookup: If True, use Composio to get authenticated user's own profile.
            composio_user_id: Composio user ID (required if is_self_lookup=True).
        """
        from datetime import datetime

        year = datetime.now().year

        collected = CollectedData(name=name, linkedin_url=linkedin_url)

        # Build search tasks
        search_tasks = {}
        for category, template in self.SEARCH_QUERIES.items():
            query = template.format(name=name, year=year)
            search_tasks[category] = self.serper.search(query, num_results=8)

        # --- LinkedIn strategy ---
        if is_self_lookup:
            # Use Composio GET_MY_INFO for self-lookup
            composio_client = ComposioLinkedInClient(
                composio_api_key=self._composio_api_key,
                user_id=composio_user_id,
            )
            linkedin_tasks = [composio_client.get_my_profile()]
            linkedin_mode = "composio"
        else:
            # Use enhanced Serper multi-query + direct scraping for others
            linkedin_tasks = [
                self.linkedin.scrape_profile(linkedin_url),
                self.linkedin.scrape_profile_text(linkedin_url),
            ]
            # Add enhanced Serper LinkedIn queries
            linkedin_serper_tasks = {}
            for qkey, qtemplate in self.LINKEDIN_SEARCH_QUERIES.items():
                query = qtemplate.format(name=name)
                linkedin_serper_tasks[qkey] = self.serper.search(query, num_results=5)
            linkedin_tasks.extend(linkedin_serper_tasks.values())
            linkedin_mode = "serper"

        # Run all in parallel
        all_tasks = list(search_tasks.values()) + linkedin_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Unpack search results
        categories = list(search_tasks.keys())
        for i, category in enumerate(categories):
            result = results[i]
            if isinstance(result, list):
                collected.web_results[category] = result
            else:
                collected.web_results[category] = []

        # Deduplicate web results across categories by URL
        seen_urls: set[str] = set()
        for category in categories:
            unique: List[WebSearchResult] = []
            for r in collected.web_results.get(category, []):
                if r.url and r.url in seen_urls:
                    continue
                if r.url:
                    seen_urls.add(r.url)
                unique.append(r)
            collected.web_results[category] = unique

        # Unpack LinkedIn results based on mode
        linkedin_start = len(categories)

        if linkedin_mode == "composio":
            # Single result: ComposioLinkedInClient.get_my_profile()
            composio_result = results[linkedin_start]
            if isinstance(composio_result, LinkedInProfile):
                collected.linkedin_profile = composio_result
                if composio_result.url and not collected.linkedin_url:
                    collected.linkedin_url = composio_result.url
        else:
            # serper mode: [scrape_profile, scrape_profile_text, serper_profile, serper_experience, serper_education]
            profile_result = results[linkedin_start]
            text_result = results[linkedin_start + 1]

            if isinstance(profile_result, LinkedInProfile):
                collected.linkedin_profile = profile_result
            if isinstance(text_result, str):
                collected.raw_page_text = text_result

            # Process enhanced Serper LinkedIn queries
            serper_query_keys = list(self.LINKEDIN_SEARCH_QUERIES.keys())
            serper_results: Dict[str, List[WebSearchResult]] = {}
            for j, qkey in enumerate(serper_query_keys):
                idx = linkedin_start + 2 + j
                sr = results[idx]
                if isinstance(sr, list):
                    serper_results[qkey] = sr

            # If direct scrape produced an empty profile, try enhanced Serper extraction
            profile = collected.linkedin_profile
            profile_is_empty = profile is None or not profile.name
            if profile_is_empty and name:
                collected = self._extract_from_serper_linkedin(
                    name, linkedin_url, serper_results, collected
                )

        return collected

    def _extract_from_serper_linkedin(
        self,
        name: str,
        original_url: str,
        serper_results: Dict[str, List[WebSearchResult]],
        collected: CollectedData,
    ) -> CollectedData:
        """
        Extract LinkedIn profile data from enhanced Serper search results.

        Uses multiple queries (profile, experience, education) to piece together
        a richer profile than a single search query would provide.
        """
        try:
            profile = collected.linkedin_profile or LinkedInProfile()

            # --- Extract from profile query ---
            profile_results = serper_results.get("profile", [])
            best_profile: Optional[WebSearchResult] = None
            for r in profile_results:
                if "linkedin.com/in/" in (r.url or ""):
                    best_profile = r
                    break

            if best_profile:
                # URL discovery
                if not profile.url:
                    profile.url = best_profile.url or original_url
                if not collected.linkedin_url and best_profile.url:
                    collected.linkedin_url = best_profile.url

                # Parse title: "Name - Headline | LinkedIn"
                title_parts = (
                    (best_profile.title or "").replace(" | LinkedIn", "").split(" - ")
                )
                if not profile.name and title_parts:
                    profile.name = title_parts[0].strip()
                if not profile.headline and len(title_parts) >= 2:
                    profile.headline = " - ".join(title_parts[1:]).strip()
                if not profile.summary and best_profile.snippet:
                    profile.summary = best_profile.snippet.strip()

            # --- Extract experience hints from experience query ---
            experience_results = serper_results.get("experience", [])
            for r in experience_results:
                snippet = r.snippet or ""
                title = r.title or ""
                # Look for patterns like "Title at Company" or "Company - Title"
                if not profile.experience and snippet:
                    # Try to extract company/title from snippet
                    exp_entry = self._parse_experience_snippet(name, snippet, title)
                    if exp_entry:
                        profile.experience.append(exp_entry)

            # --- Extract education hints from education query ---
            education_results = serper_results.get("education", [])
            for r in education_results:
                snippet = r.snippet or ""
                title = r.title or ""
                if not profile.education and snippet:
                    edu_entry = self._parse_education_snippet(name, snippet, title)
                    if edu_entry:
                        profile.education.append(edu_entry)

            # --- Fallback: combine all snippets as summary if still empty ---
            if not profile.summary:
                all_snippets = []
                for qresults in serper_results.values():
                    for r in qresults:
                        if r.snippet and "linkedin.com" in (r.url or ""):
                            all_snippets.append(r.snippet.strip())
                if all_snippets:
                    profile.summary = " ".join(all_snippets[:3])

            collected.linkedin_profile = profile
            return collected

        except Exception as e:
            print(f"Enhanced Serper LinkedIn extraction error: {e}")
            return collected

    @staticmethod
    def _parse_experience_snippet(
        name: str, snippet: str, title: str
    ) -> Optional[Dict[str, str]]:
        """Try to extract experience info from a search snippet."""
        try:
            # Common patterns in LinkedIn-related snippets:
            # "Name is a Title at Company" or "Title at Company"
            # "Company · Title" or "Title · Company"
            lower_name = name.lower()

            # Remove the person's name from the start of snippet
            clean = snippet
            if clean.lower().startswith(lower_name):
                clean = clean[len(name) :].strip().lstrip("is a").lstrip("is").strip()

            # Try "X at Y" pattern
            at_match = re.search(r"(.+?)\s+at\s+(.+?)(?:\.|,|$)", clean)
            if at_match:
                return {
                    "title": at_match.group(1).strip()[:100],
                    "company": at_match.group(2).strip()[:100],
                    "duration": "",
                }

            # Try "Company · Title" pattern (LinkedIn uses middle dot)
            dot_match = re.search(r"(.+?)\s*[·•]\s*(.+?)(?:\.|,|$)", clean)
            if dot_match:
                return {
                    "title": dot_match.group(2).strip()[:100],
                    "company": dot_match.group(1).strip()[:100],
                    "duration": "",
                }

            return None
        except Exception:
            return None

    @staticmethod
    def _parse_education_snippet(
        name: str, snippet: str, title: str
    ) -> Optional[Dict[str, str]]:
        """Try to extract education info from a search snippet."""
        try:
            # Common patterns: "University of X", "X University", "Bachelor", "Master", "MBA"
            edu_keywords = [
                "university",
                "college",
                "institute",
                "school",
                "bachelor",
                "master",
                "mba",
                "phd",
                "degree",
            ]
            lower_snippet = snippet.lower()

            has_edu = any(kw in lower_snippet for kw in edu_keywords)
            if not has_edu:
                return None

            # Try to find university name
            # Match "University of X" or "X University" patterns, stopping at punctuation
            uni_match = re.search(
                r"((?:University|College|Institute|School)\s+of\s+(?:[A-Z][\w]*(?:\s+[A-Z][\w]*)*))"
                r"|"
                r"((?:[A-Z][\w]*(?:\s+[A-Z][\w]*)*)\s+(?:University|College|Institute|School))",
                snippet,
            )
            school = ""
            if uni_match:
                school = (uni_match.group(1) or uni_match.group(2) or "").strip()

            # Try to find degree
            degree_match = re.search(
                r"(Bachelor[\w\s']*|Master[\w\s']*|MBA|Ph\.?D\.?|B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?)",
                snippet,
                re.IGNORECASE,
            )
            degree = degree_match.group(0).strip() if degree_match else ""

            if school or degree:
                return {
                    "school": school[:100],
                    "degree": degree[:100],
                    "field": "",
                }

            return None
        except Exception:
            return None

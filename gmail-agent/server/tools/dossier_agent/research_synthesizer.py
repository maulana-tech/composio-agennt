"""
Dossier Agent - Research Synthesizer (Gemini).

Takes raw collected data (web search results, LinkedIn profile, page text)
and uses Gemini (large-context model) to produce a structured synthesis:

- Biographical context
- Recent notable statements / positions
- Known associates and their relevance
- Key topics and interests
- Potential conversation starters
- Sensitive topics to avoid
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI

from .exceptions import DossierSynthesisError


# ---------------------------------------------------------------------------
# Synthesis Output Model
# ---------------------------------------------------------------------------


@dataclass
class SynthesizedResearch:
    """Structured output from the Gemini research synthesis step."""

    name: str = ""
    linkedin_url: str = ""
    current_role: str = ""
    organization: str = ""
    location: str = ""
    biographical_summary: str = ""
    career_highlights: list = field(default_factory=list)
    recent_statements: list = field(default_factory=list)
    # Each statement: {"quote": str, "source": str, "date": str, "context": str}
    known_associates: list = field(default_factory=list)
    # Each associate: {"name": str, "relationship": str, "context": str}
    key_topics: list = field(default_factory=list)
    education_summary: str = ""
    personality_notes: str = ""
    online_presence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "linkedin_url": self.linkedin_url,
            "current_role": self.current_role,
            "organization": self.organization,
            "location": self.location,
            "biographical_summary": self.biographical_summary,
            "career_highlights": self.career_highlights,
            "recent_statements": self.recent_statements,
            "known_associates": self.known_associates,
            "key_topics": self.key_topics,
            "education_summary": self.education_summary,
            "personality_notes": self.personality_notes,
            "online_presence": self.online_presence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SynthesizedResearch":
        return cls(
            name=data.get("name", ""),
            linkedin_url=data.get("linkedin_url", ""),
            current_role=data.get("current_role", ""),
            organization=data.get("organization", ""),
            location=data.get("location", ""),
            biographical_summary=data.get("biographical_summary", ""),
            career_highlights=data.get("career_highlights", []),
            recent_statements=data.get("recent_statements", []),
            known_associates=data.get("known_associates", []),
            key_topics=data.get("key_topics", []),
            education_summary=data.get("education_summary", ""),
            personality_notes=data.get("personality_notes", ""),
            online_presence=data.get("online_presence", ""),
        )


# ---------------------------------------------------------------------------
# Research Synthesizer
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """\
You are an expert research analyst preparing a meeting briefing.

Given the following raw data about a person, synthesize it into a structured JSON object.
Be factual and precise. Only include information that is supported by the sources.
If data is insufficient for a field, use an empty string or empty list.

# Person
Name: {name}
LinkedIn URL: {linkedin_url}

# LinkedIn Profile Data
{linkedin_data}

# Web Search Results
{web_data}

# LinkedIn Page Text (raw)
{page_text}

---

Return a JSON object with EXACTLY these keys:
{{
  "name": "Full name",
  "current_role": "Current job title / position",
  "organization": "Current company or organization",
  "location": "City, Country",
  "biographical_summary": "2-3 paragraph biography covering career arc and notable achievements",
  "career_highlights": ["highlight 1", "highlight 2", ...],
  "recent_statements": [
    {{"quote": "exact or paraphrased statement", "source": "publication/event", "date": "date if known", "context": "brief context"}}
  ],
  "known_associates": [
    {{"name": "Person name", "relationship": "colleague/board member/mentor/etc", "context": "brief context of relationship"}}
  ],
  "key_topics": ["topic they care about 1", "topic 2", ...],
  "education_summary": "Education background",
  "personality_notes": "Communication style, public persona, known preferences",
  "online_presence": "Summary of social media activity, publication frequency, platforms"
}}

IMPORTANT:
- For recent_statements, include 3-5 most notable/recent statements with sources.
- For known_associates, include 3-7 most relevant professional connections.
- For key_topics, include 5-10 topics they frequently discuss or are associated with.
- Be specific with dates and sources where possible.
- Do not fabricate information. If something is unclear, note the uncertainty.

Return ONLY valid JSON, no markdown code fences, no extra text.
"""


class ResearchSynthesizer:
    """
    Uses Gemini to synthesize multi-source raw data into structured research.
    """

    def __init__(
        self, google_api_key: Optional[str] = None, model: str = "gemini-2.0-flash"
    ):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=0.1,
                google_api_key=api_key,
            )
        else:
            self.llm = None

    async def synthesize(self, collected_data: Dict[str, Any]) -> SynthesizedResearch:
        """
        Take collected data dict and produce a SynthesizedResearch.

        Args:
            collected_data: Output of CollectedData.to_dict()

        Returns:
            SynthesizedResearch with structured fields.
        """
        if not self.llm:
            return self._fallback_synthesis(collected_data)
        # Format LinkedIn data
        linkedin_profile = collected_data.get("linkedin_profile")
        if linkedin_profile:
            linkedin_str = json.dumps(linkedin_profile, indent=2, default=str)
        else:
            linkedin_str = "No LinkedIn profile data available."

        # Format web search results
        web_data = collected_data.get("web_results", {})
        web_lines = []
        for category, results in web_data.items():
            web_lines.append(f"\n## {category.upper()}")
            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                url = r.get("url", "")
                date = r.get("date", "")
                date_str = f" ({date})" if date else ""
                web_lines.append(f"- {title}{date_str}: {snippet}\n  URL: {url}")
        web_str = (
            "\n".join(web_lines) if web_lines else "No web search results available."
        )

        # Page text
        page_text = collected_data.get("raw_page_text", "")[:3000]
        if not page_text:
            page_text = "No raw page text available."

        prompt = SYNTHESIS_PROMPT.format(
            name=collected_data.get("name", "Unknown"),
            linkedin_url=collected_data.get("linkedin_url", ""),
            linkedin_data=linkedin_str,
            web_data=web_str,
            page_text=page_text,
        )

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()

            # Strip markdown fences if present
            if content.startswith("```"):
                # Remove ```json ... ```
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)

            parsed = json.loads(content)
            result = SynthesizedResearch.from_dict(parsed)
            # Preserve linkedin_url from collected data (LLM won't return it)
            result.linkedin_url = collected_data.get("linkedin_url", "")
            return result

        except json.JSONDecodeError as e:
            print(f"Failed to parse Gemini synthesis response as JSON: {e}")
            # Return a minimal result with the raw text as biography
            return SynthesizedResearch(
                name=collected_data.get("name", "Unknown"),
                linkedin_url=collected_data.get("linkedin_url", ""),
                biographical_summary=f"[Synthesis parse error] Raw response:\n{content[:500]}",
            )
        except Exception as e:
            print(f"Research synthesis error: {e}")
            raise DossierSynthesisError(f"Research synthesis failed: {e}") from e

    def _fallback_synthesis(
        self, collected_data: Dict[str, Any]
    ) -> SynthesizedResearch:
        """
        Generate basic synthesis without the LLM.
        Extracts what we can directly from the collected data.
        """
        name = collected_data.get("name", "Unknown")
        linkedin_url = collected_data.get("linkedin_url", "")
        linkedin_profile = collected_data.get("linkedin_profile") or {}

        # Extract from LinkedIn profile if available
        current_role = linkedin_profile.get("headline", "")
        location = linkedin_profile.get("location", "")
        summary = linkedin_profile.get("summary", "")

        # Build bio from web snippets
        bio_results = collected_data.get("web_results", {}).get("bio", [])
        bio_snippets = [r.get("snippet", "") for r in bio_results if r.get("snippet")]
        biographical_summary = summary or " ".join(bio_snippets[:3])

        # Extract statements from web results
        statement_results = collected_data.get("web_results", {}).get("statements", [])
        recent_statements = []
        for r in statement_results[:5]:
            recent_statements.append(
                {
                    "quote": r.get("snippet", ""),
                    "source": r.get("title", ""),
                    "date": r.get("date", ""),
                    "context": "",
                }
            )

        # Extract associates from web results
        associate_results = collected_data.get("web_results", {}).get("associates", [])
        known_associates = []
        for r in associate_results[:5]:
            known_associates.append(
                {
                    "name": r.get("title", ""),
                    "relationship": "mentioned together",
                    "context": r.get("snippet", ""),
                }
            )

        # Extract topics from news results
        news_results = collected_data.get("web_results", {}).get("news", [])
        key_topics = []
        for r in news_results[:5]:
            if r.get("title"):
                key_topics.append(r["title"])

        return SynthesizedResearch(
            name=name,
            linkedin_url=linkedin_url,
            current_role=current_role,
            location=location,
            biographical_summary=biographical_summary
            if biographical_summary
            else f"No detailed biography available for {name}.",
            recent_statements=recent_statements,
            known_associates=known_associates,
            key_topics=key_topics,
        )

"""
Dossier Agent - Strategic Analyzer (Gemini).

Takes synthesized research and produces strategic insights:
- Relationship mapping between the subject and their associates
- Conversation starters tailored to the meeting context
- Potential common ground and shared interests
- Topics to approach with caution
- Recommended meeting strategy
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI


# ---------------------------------------------------------------------------
# Strategic Output Model
# ---------------------------------------------------------------------------


@dataclass
class StrategicInsights:
    """Output from the Gemini strategic analysis."""

    relationship_map: List[Dict[str, str]] = field(default_factory=list)
    # Each: {"person": str, "relationship": str, "leverage": str, "notes": str}
    conversation_starters: List[str] = field(default_factory=list)
    common_ground: List[str] = field(default_factory=list)
    topics_to_avoid: List[str] = field(default_factory=list)
    meeting_strategy: str = ""
    key_motivations: List[str] = field(default_factory=list)
    negotiation_style: str = ""
    recommended_approach: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationship_map": self.relationship_map,
            "conversation_starters": self.conversation_starters,
            "common_ground": self.common_ground,
            "topics_to_avoid": self.topics_to_avoid,
            "meeting_strategy": self.meeting_strategy,
            "key_motivations": self.key_motivations,
            "negotiation_style": self.negotiation_style,
            "recommended_approach": self.recommended_approach,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategicInsights":
        return cls(
            relationship_map=data.get("relationship_map", []),
            conversation_starters=data.get("conversation_starters", []),
            common_ground=data.get("common_ground", []),
            topics_to_avoid=data.get("topics_to_avoid", []),
            meeting_strategy=data.get("meeting_strategy", ""),
            key_motivations=data.get("key_motivations", []),
            negotiation_style=data.get("negotiation_style", ""),
            recommended_approach=data.get("recommended_approach", ""),
        )


# ---------------------------------------------------------------------------
# Strategic Analysis Prompt
# ---------------------------------------------------------------------------

STRATEGY_PROMPT = """\
You are an elite political and business strategist preparing a meeting briefing.

Given the following research synthesis about a person, produce strategic insights
for someone who is about to meet them.

# Person Profile
Name: {name}
Current Role: {current_role}
Organization: {organization}
Location: {location}

## Biography
{biography}

## Career Highlights
{career_highlights}

## Recent Statements
{recent_statements}

## Known Associates
{known_associates}

## Key Topics
{key_topics}

## Personality Notes
{personality_notes}

---

# Meeting Context (if provided)
{meeting_context}

---

Produce a JSON object with EXACTLY these keys:
{{
  "relationship_map": [
    {{"person": "Name", "relationship": "type of relationship", "leverage": "how this connection could be useful", "notes": "relevant context"}}
  ],
  "conversation_starters": [
    "Starter 1 - a specific, informed opening that shows you've done your homework",
    "Starter 2 - references a recent achievement or statement",
    "Starter 3 - connects to a shared interest or mutual connection"
  ],
  "common_ground": [
    "Shared interest or connection point 1",
    "Shared interest or connection point 2"
  ],
  "topics_to_avoid": [
    "Topic 1 - brief reason why",
    "Topic 2 - brief reason why"
  ],
  "meeting_strategy": "A 2-3 sentence recommended approach for the meeting",
  "key_motivations": [
    "What drives this person professionally",
    "What they are currently focused on"
  ],
  "negotiation_style": "Brief assessment of how they likely approach negotiations/discussions",
  "recommended_approach": "Specific tactical advice for the meeting"
}}

IMPORTANT:
- Conversation starters should be specific and show genuine familiarity, not generic.
- Relationship map should prioritize the 3-5 most strategically relevant connections.
- Topics to avoid should be based on evidence (controversial statements, failures, sensitivities).
- Be practical and actionable, not theoretical.

Return ONLY valid JSON, no markdown code fences, no extra text.
"""


# ---------------------------------------------------------------------------
# Strategic Analyzer
# ---------------------------------------------------------------------------


class StrategicAnalyzer:
    """
    Uses Gemini for relationship mapping and strategic meeting insights.
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
    ):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            self.llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=0.3,
                google_api_key=api_key,
            )
        else:
            self.llm = None

    async def analyze(
        self,
        synthesized_data: Dict[str, Any],
        meeting_context: str = "",
    ) -> StrategicInsights:
        """
        Produce strategic insights from synthesized research.

        Args:
            synthesized_data: Output of SynthesizedResearch.to_dict()
            meeting_context: Optional context about why the meeting is happening.

        Returns:
            StrategicInsights with actionable meeting prep data.
        """
        if not self.llm:
            return self._fallback_insights(synthesized_data)

        # Format recent statements
        statements = synthesized_data.get("recent_statements", [])
        statements_str = ""
        for s in statements:
            if isinstance(s, dict):
                statements_str += (
                    f'- "{s.get("quote", "")}" '
                    f"(Source: {s.get('source', 'unknown')}, "
                    f"Date: {s.get('date', 'unknown')})\n"
                )
            else:
                statements_str += f"- {s}\n"

        # Format associates
        associates = synthesized_data.get("known_associates", [])
        associates_str = ""
        for a in associates:
            if isinstance(a, dict):
                associates_str += (
                    f"- {a.get('name', 'Unknown')}: "
                    f"{a.get('relationship', '')} - {a.get('context', '')}\n"
                )
            else:
                associates_str += f"- {a}\n"

        # Format career highlights
        highlights = synthesized_data.get("career_highlights", [])
        highlights_str = (
            "\n".join(f"- {h}" for h in highlights) if highlights else "None available"
        )

        # Format key topics
        topics = synthesized_data.get("key_topics", [])
        topics_str = ", ".join(topics) if topics else "None identified"

        prompt = STRATEGY_PROMPT.format(
            name=synthesized_data.get("name", "Unknown"),
            current_role=synthesized_data.get("current_role", "Unknown"),
            organization=synthesized_data.get("organization", "Unknown"),
            location=synthesized_data.get("location", "Unknown"),
            biography=synthesized_data.get(
                "biographical_summary", "No biography available."
            ),
            career_highlights=highlights_str,
            recent_statements=statements_str or "None available",
            known_associates=associates_str or "None available",
            key_topics=topics_str,
            personality_notes=synthesized_data.get(
                "personality_notes", "No personality data."
            ),
            meeting_context=meeting_context or "No specific meeting context provided.",
        )

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()

            # Strip markdown fences
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)

            parsed = json.loads(content)
            return StrategicInsights.from_dict(parsed)

        except json.JSONDecodeError as e:
            print(f"Failed to parse Gemini strategic response as JSON: {e}")
            return self._fallback_insights(synthesized_data)
        except Exception as e:
            print(f"Strategic analysis error: {e}")
            return self._fallback_insights(synthesized_data)

    def _fallback_insights(self, synthesized_data: Dict[str, Any]) -> StrategicInsights:
        """
        Generate basic insights without the strategic LLM.
        Uses the synthesized data directly to build conversation starters
        and identify key topics.
        """
        name = synthesized_data.get("name", "the person")
        topics = synthesized_data.get("key_topics", [])
        statements = synthesized_data.get("recent_statements", [])
        associates = synthesized_data.get("known_associates", [])

        # Build conversation starters from topics
        starters = []
        if topics:
            starters.append(
                f"I noticed you've been involved in {topics[0]}. What's your current perspective on that?"
            )
        if statements:
            first_stmt = statements[0]
            if isinstance(first_stmt, dict):
                starters.append(
                    f"I read your comment about {first_stmt.get('context', first_stmt.get('quote', '')[:50])}. "
                    f"Could you elaborate on that?"
                )
        if not starters:
            starters.append(
                f"I'd love to hear about your current work at {synthesized_data.get('organization', 'your organization')}."
            )

        # Build relationship map from associates
        rel_map = []
        for a in associates[:5]:
            if isinstance(a, dict):
                rel_map.append(
                    {
                        "person": a.get("name", "Unknown"),
                        "relationship": a.get("relationship", "associate"),
                        "leverage": "Potential mutual connection",
                        "notes": a.get("context", ""),
                    }
                )

        return StrategicInsights(
            relationship_map=rel_map,
            conversation_starters=starters,
            common_ground=[f"Interest in {t}" for t in topics[:3]],
            topics_to_avoid=[
                "Avoid speculative or unverified claims about their background"
            ],
            meeting_strategy=f"Approach {name} with informed curiosity about their current work and recent statements.",
            key_motivations=[synthesized_data.get("personality_notes", "Unknown")]
            if synthesized_data.get("personality_notes")
            else [],
            negotiation_style="Insufficient data for assessment.",
            recommended_approach=f"Lead with specific knowledge about {name}'s recent activities to establish credibility.",
        )

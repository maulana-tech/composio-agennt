"""
Synonym Expander for GIPA Request Agent.

Takes a user's simple keyword and expands it into a legally robust definition
list that catches all variations - scientific names, common aliases,
abbreviations, and related technical terms.

This is a critical "legal shield" mechanism: agencies often try to reject
requests by claiming ambiguity ("We don't know what you mean by 'Dingo'").
By providing comprehensive definitions, we remove that avenue of rejection.
"""

import os
import json
import re
from typing import Dict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage


class SynonymExpander:
    """
    AI-powered keyword synonym/definition expansion for GIPA applications.

    Given a keyword like "Koala", generates a legal definition:
    'Define "Koala" to include: Phascolarctos cinereus, native bear,
    arboreal marsupial, koala habitat, koala population.'
    """

    def __init__(self, google_api_key: Optional[str] = None):
        api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for SynonymExpander")
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.1,
            google_api_key=api_key,
        )
        self._cache: Dict[str, str] = {}

    async def expand_keyword(self, keyword: str) -> str:
        """
        Expand a single keyword into a legal definition string.

        Args:
            keyword: The user's keyword (e.g., "Koala", "Dingo", "water licence").

        Returns:
            Formatted definition string for the Scope & Definitions section.
            e.g., 'Define "Koala" to include: Phascolarctos cinereus, ...'
        """
        # Check cache first
        cache_key = keyword.strip().lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=self._get_system_prompt()),
                    HumanMessage(
                        content=f"Expand this keyword for a GIPA legal definition: {keyword}"
                    ),
                ]
            )

            # Parse the response
            expansions = self._parse_expansions(response.content, keyword)

            # Format into definition string
            if expansions:
                expansion_str = ", ".join(expansions)
                result = f'Define "{keyword}" to include: {expansion_str}.'
            else:
                # Fallback: minimal definition
                result = f'Define "{keyword}" to include all references to {keyword}, including abbreviations, acronyms, and alternative spellings.'

            # Cache the result
            self._cache[cache_key] = result
            return result

        except Exception as e:
            print(f"SynonymExpander error for '{keyword}': {e}")
            return f'Define "{keyword}" to include all references to {keyword}, including abbreviations, acronyms, and alternative spellings.'

    async def expand_keywords(self, keywords: List[str]) -> List[str]:
        """
        Expand multiple keywords into definition strings.

        Args:
            keywords: List of keywords to expand.

        Returns:
            List of formatted definition strings.
        """
        results = []
        for keyword in keywords:
            definition = await self.expand_keyword(keyword)
            results.append(definition)
        return results

    def _get_system_prompt(self) -> str:
        return """You are a legal terminology expansion engine for Australian government information access (GIPA/FOI) applications.

Your task: Given a keyword, generate a comprehensive list of synonyms, alternative names, scientific names, abbreviations, and related terms that a government officer might use when referring to the same concept.

PURPOSE: This definition will be inserted into a formal legal document to prevent the government agency from narrowly interpreting the keyword and excluding relevant records.

RULES:
1. Include scientific/Latin names where applicable (especially for flora/fauna).
2. Include common abbreviations and acronyms.
3. Include Australian-specific colloquialisms and terminology.
4. Include both formal and informal terms government officers might use.
5. Include related program names, policy names, or legislative references if well-known.
6. Keep the list to 5-12 terms maximum - be comprehensive but not absurd.
7. Do NOT include the original keyword itself in the expansion list.
8. Focus on terms that would actually appear in government correspondence.

Return ONLY a JSON array of strings. No explanation, no markdown.

EXAMPLES:
Input: "Koala"
Output: ["Phascolarctos cinereus", "native bear", "arboreal marsupial", "koala habitat", "koala population", "SEPP 44", "koala management area"]

Input: "Dingo"
Output: ["Canis lupus dingo", "wild dog", "native dog", "wild canid", "dingo management", "1080 baiting", "wild dog control"]

Input: "water licence"
Output: ["water access licence", "WAL", "water sharing plan", "water allocation", "water entitlement", "water extraction permit", "bore licence", "groundwater licence"]"""

    def _parse_expansions(self, content: str, keyword: str) -> List[str]:
        """Parse the LLM response into a list of expansion terms."""
        # Try to parse as JSON array
        content = content.strip()

        # Try direct JSON parse
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return [
                    str(item) for item in result if str(item).lower() != keyword.lower()
                ]
        except json.JSONDecodeError:
            pass

        # Try extracting JSON array from markdown
        json_match = re.search(r"\[[\s\S]*?\]", content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if isinstance(result, list):
                    return [
                        str(item)
                        for item in result
                        if str(item).lower() != keyword.lower()
                    ]
            except json.JSONDecodeError:
                pass

        # Fallback: try to split by commas or newlines
        parts = re.split(r"[,\n]", content)
        expansions = []
        for part in parts:
            cleaned = part.strip().strip('"').strip("'").strip("-").strip("*").strip()
            if cleaned and cleaned.lower() != keyword.lower() and len(cleaned) > 1:
                expansions.append(cleaned)

        return expansions[:12]  # Cap at 12 terms

    def clear_cache(self):
        """Clear the synonym expansion cache."""
        self._cache.clear()

import os
import json
import re
from typing import List, Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import httpx
from composio import Composio

from .tools.pdf_generator import generate_pdf_report


class EmailAnalysisAgent:
    """Agent for analyzing emails and extracting factual claims."""

    def __init__(self, google_api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0.2, google_api_key=google_api_key
        )

    async def analyze_email(
        self, email_content: str, user_query: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze email content to extract factual claims that need verification.

        Args:
            email_content: The full email content including subject, sender, body
            user_query: Specific user instruction about what to analyze

        Returns:
            Dictionary with extracted claims, key entities, and analysis summary
        """
        system_prompt = """You are an expert email analysis AI. Your task is to:
1. Read and understand the email content
2. Identify factual claims, statements, or assertions that can be verified
3. Extract key people, organizations, locations, dates, and events
4. Determine what specific claims need fact-checking
5. Prioritize claims that are significant, controversial, or newsworthy

Focus on claims about:
- Political statements, promises, or achievements
- Business claims, financial performance, or product capabilities  
- Scientific or medical assertions
- Historical events or statistics
- Personal achievements or qualifications

Return a structured analysis in JSON format."""

        user_prompt = f"""Analyze this email for factual claims that need verification:

USER QUERY: {user_query}

EMAIL CONTENT:
{email_content}

Please provide:
1. Summary of the email's main points
2. List of factual claims that should be fact-checked
3. Key entities mentioned (people, organizations, locations)
4. Priority level for each claim (high/medium/low) based on importance
5. Suggested search terms for verifying each claim

Format as JSON."""

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )

            # Parse the response to extract structured data
            content = response.content

            # Try to extract JSON from the response
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback if JSON parsing fails
                return {
                    "summary": content,
                    "claims": [],
                    "entities": [],
                    "error": "Could not parse structured response",
                }

        except Exception as e:
            return {
                "error": f"Email analysis failed: {str(e)}",
                "summary": "",
                "claims": [],
                "entities": [],
            }


class ResearchPlanningAgent:
    """Agent for creating research strategies based on email analysis."""

    def __init__(self, google_api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0.1, google_api_key=google_api_key
        )

    async def create_research_plan(
        self, email_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a comprehensive research plan based on email analysis.

        Args:
            email_analysis: Output from EmailAnalysisAgent

        Returns:
            Structured research plan with search strategies and priorities
        """
        system_prompt = """You are a professional research strategist. Your task is to:
1. Review the email analysis and identified claims
2. Create an efficient research strategy to verify each claim
3. Prioritize searches based on claim importance and verifiability
4. Suggest specific search queries for different information sources
5. Plan which types of sources would be most credible for each claim

Consider these source types:
- Major news organizations (Reuters, AP, BBC)
- Government websites and official reports
- Academic papers and research institutions
- Company press releases and financial reports
- Fact-checking organizations (Snopes, FactCheck.org)
- Social media and official statements"""

        user_prompt = f"""Create a research plan to verify these claims from an email:

EMAIL ANALYSIS:
{json.dumps(email_analysis, indent=2)}

Please provide:
1. Overall research strategy
2. Specific search queries for each claim
3. Priority order for investigation
4. Types of sources to prioritize
5. How to handle conflicting information
6. Confidence level expectations

Format as JSON."""

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )

            content = response.content
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "strategy": content,
                    "search_queries": [],
                    "priorities": [],
                    "error": "Could not parse structured response",
                }

        except Exception as e:
            return {
                "error": f"Research planning failed: {str(e)}",
                "strategy": "",
                "search_queries": [],
            }


class WebResearchAgent:
    """Agent for conducting web research using Google Grounding with Search."""

    def __init__(self, google_api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0.1, google_api_key=google_api_key
        )

        # Initialize Google Grounding client
        self.google_api_key = google_api_key
        try:
            from google import genai
            from google.genai import types

            self.genai = genai
            self.types = types
            self.grounding_available = True
        except ImportError:
            self.grounding_available = False

    async def conduct_research(self, research_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the research plan using Google Grounding with Search.

        Args:
            research_plan: Output from ResearchPlanningAgent

        Returns:
            Research findings with sources and evidence from real-time web search
        """
        import asyncio

        if not self.grounding_available:
            return {
                "error": "Google Grounding library not available. Install with: pip install google-genai"
            }

        if not self.google_api_key:
            return {"error": "GOOGLE_API_KEY not configured for web research"}

        research_results = {}

        # Extract search queries from the plan
        search_queries = research_plan.get("search_queries", [])
        if isinstance(search_queries, str):
            search_queries = [search_queries]

        # Limit to 3 queries for performance
        search_queries = search_queries[:3]

        async def search_with_grounding(idx, query):
            try:
                print(f"Researching with Grounding: {query}")

                # Initialize Gemini client
                client = self.genai.Client(api_key=self.google_api_key)

                # Create grounding tool with Google Search
                grounding_tool = self.types.Tool(
                    google_search=self.types.GoogleSearch()
                )

                # Configure generation with grounding tool
                config = self.types.GenerateContentConfig(tools=[grounding_tool])

                # Generate content with grounding
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"Research and provide factual information about: {query}. Include sources and citations.",
                    config=config,
                )

                # Extract response text and metadata
                result_text = response.text or "No results found"

                # Extract sources from grounding metadata
                sources = []
                if response.candidates and response.candidates[0].grounding_metadata:
                    metadata = response.candidates[0].grounding_metadata
                    chunks = metadata.grounding_chunks

                    if chunks:
                        for i, chunk in enumerate(chunks):
                            if chunk.web:
                                sources.append(
                                    {
                                        "title": chunk.web.title or f"Source {i + 1}",
                                        "link": chunk.web.uri,
                                        "index": i + 1,
                                    }
                                )

                enriched_results = [
                    {
                        "title": f"Grounded Research Result for: {query}",
                        "link": sources[0]["link"] if sources else "",
                        "snippet": result_text[:500] + "..."
                        if len(result_text) > 500
                        else result_text,
                        "full_content": result_text,
                        "sources": sources,
                    }
                ]

                return (
                    idx,
                    {
                        "query": query,
                        "results": enriched_results,
                        "success": True,
                    },
                )
            except Exception as e:
                return (
                    idx,
                    {
                        "query": query,
                        "error": str(e),
                        "success": False,
                    },
                )

        # Run all queries in parallel
        tasks = [search_with_grounding(i + 1, q) for i, q in enumerate(search_queries)]
        results = await asyncio.gather(*tasks)
        for idx, res in results:
            research_results[f"query_{idx}"] = res

        # Analyze research findings
        analysis_prompt = f"""Analyze these research results and provide a comprehensive summary:

RESEARCH RESULTS:
{json.dumps(research_results, indent=2)}

Please provide:
1. Key findings for each claim
2. Overall credibility assessment
3. Conflicting information analysis
4. Source quality evaluation
5. Confidence levels for verified claims

Format as JSON."""

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(
                        content="You are an expert research analyst. Provide objective, evidence-based analysis."
                    ),
                    HumanMessage(content=analysis_prompt),
                ]
            )

            content = response.content
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                analysis = {
                    "summary": content,
                    "error": "Could not parse structured analysis",
                }

            return {
                "raw_results": research_results,
                "analysis": analysis,
                "total_queries": len(search_queries),
            }

        except Exception as e:
            return {
                "raw_results": research_results,
                "error": f"Research analysis failed: {str(e)}",
                "analysis": {},
            }


class ReportGenerationAgent:
    """Agent for generating final reports based on research findings."""

    def __init__(self, google_api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0.3, google_api_key=google_api_key
        )

    async def generate_report(
        self,
        email_content: str,
        email_analysis: Dict[str, Any],
        research_plan: Dict[str, Any],
        research_results: Dict[str, Any],
    ) -> str:
        """
        Generate a comprehensive fact-checking report.

        Args:
            email_content: Original email content
            email_analysis: Analysis from EmailAnalysisAgent
            research_plan: Plan from ResearchPlanningAgent
            research_results: Findings from WebResearchAgent

        Returns:
            Markdown-formatted report
        """
        system_prompt = """You are a professional fact-checking reporter. Create a comprehensive, objective report that:

1. Clearly states the original claims being verified
2. Presents evidence for and against each claim
3. Evaluates the credibility of sources
4. Provides a clear verdict on each claim's accuracy
5. Explains the reasoning behind conclusions
6. Notes any limitations or uncertainties

Use this structure:
# Fact-Checking Report

## Executive Summary
[Brief overview of findings]

## Original Claims
[List the claims from the email]

## Investigation Methodology
[Explain how research was conducted]

## Detailed Findings
[Claim by claim analysis with evidence]

## Conclusion
[Overall assessment and final verdict]

## Sources
[List all sources used]

Be thorough, objective, and cite sources properly."""

        user_prompt = f"""Generate a comprehensive fact-checking report based on:

ORIGINAL EMAIL:
{email_content}

EMAIL ANALYSIS:
{json.dumps(email_analysis, indent=2)}

RESEARCH PLAN:
{json.dumps(research_plan, indent=2)}

RESEARCH RESULTS:
{json.dumps(research_results, indent=2)}

Create a detailed, professional report in Markdown format."""

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )

            return response.content

        except Exception as e:
            return f"# Report Generation Failed\n\nError: {str(e)}\n\nPlease try again."


class MultiAgentEmailAnalyzer:
    """Main orchestrator for the multi-agent email analysis system."""

    def __init__(self):
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for email analysis")

        self.email_agent = EmailAnalysisAgent(google_api_key)
        self.planning_agent = ResearchPlanningAgent(google_api_key)
        self.research_agent = WebResearchAgent(google_api_key)
        self.report_agent = ReportGenerationAgent(google_api_key)

    async def analyze_and_report(
        self, email_content: str, user_query: str = "", generate_pdf: bool = True
    ) -> Dict[str, Any]:
        """
        Run the complete multi-agent analysis pipeline.

        Args:
            email_content: Email to analyze
            user_query: Specific user instructions
            generate_pdf: Whether to generate PDF report

        Returns:
            Complete analysis results with optional PDF
        """
        results = {
            "status": "processing",
            "stages": {},
            "final_report": "",
            "pdf_path": "",
        }

        try:
            # Stage 1: Email Analysis
            results["status"] = "analyzing_email"
            results["stages"]["email_analysis"] = await self.email_agent.analyze_email(
                email_content, user_query
            )

            # Stage 2: Research Planning
            results["status"] = "planning_research"
            results["stages"][
                "research_plan"
            ] = await self.planning_agent.create_research_plan(
                results["stages"]["email_analysis"]
            )

            # Stage 3: Web Research
            results["status"] = "conducting_research"
            results["stages"][
                "research_results"
            ] = await self.research_agent.conduct_research(
                results["stages"]["research_plan"]
            )

            # Stage 4: Report Generation
            results["status"] = "generating_report"
            results["final_report"] = await self.report_agent.generate_report(
                email_content,
                results["stages"]["email_analysis"],
                results["stages"]["research_plan"],
                results["stages"]["research_results"],
            )

            # Stage 5: PDF Generation (optional)
            if generate_pdf and results["final_report"]:
                results["status"] = "generating_pdf"
                try:
                    pdf_result = generate_pdf_report.invoke(
                        {
                            "markdown_content": results["final_report"],
                            "filename": "email_fact_check_report.pdf",
                        }
                    )
                    results["pdf_path"] = pdf_result
                except Exception as e:
                    results["pdf_error"] = str(e)

            results["status"] = "completed"
            results["success"] = True

        except Exception as e:
            results["status"] = "failed"
            results["error"] = str(e)
            results["success"] = False

        return results

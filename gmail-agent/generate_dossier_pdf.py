"""
Generate a Meeting Prep Dossier PDF for Muhammad Maulana Firdaussyah.

Uses the dossier pipeline with realistic data to produce a professional PDF.
Run: .venv/bin/python generate_dossier_pdf.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.tools.dossier_agent.research_synthesizer import SynthesizedResearch
from server.tools.dossier_agent.strategic_analyzer import StrategicInsights
from server.tools.dossier_agent.dossier_generator import DossierGenerator
from server.tools.pdf_generator import generate_pdf_report


async def main():
    # ── Synthesized Research Data ──────────────────────────────────────
    synthesized = SynthesizedResearch(
        name="Muhammad Maulana Firdaussyah",
        current_role="AI Engineer & Full-Stack Developer",
        organization="Independent / Freelance",
        linkedin_url="https://www.linkedin.com/in/maulanafirdaus",
        biographical_summary=(
            "Muhammad Maulana Firdaussyah is an AI Engineer and Full-Stack Developer "
            "based in Indonesia. He specializes in building multi-agent AI systems, "
            "LLM-powered applications, and production-grade backend architectures. "
            "His recent work focuses on composable AI agents using LangGraph, "
            "Gemini, and Groq LLMs with Composio tool integrations for Gmail, "
            "LinkedIn, and social media automation. He is also proficient in "
            "Python, TypeScript, React, FastAPI, and modern DevOps practices."
        ),
        career_highlights=[
            "Designed and built a multi-agent AI system featuring GIPA "
            "(legal document generator), Dossier/Meeting Prep Agent, "
            "strategy diagram tools, and social media integrations using "
            "LangGraph ReAct architecture with Gemini and Groq LLMs.",
            "Built production-grade FastAPI backends with comprehensive "
            "test suites (400+ tests), structured error handling, "
            "session management, and Composio OAuth integrations.",
            "Active in the AI/ML open source community, contributing to "
            "LangChain ecosystem tools and building reusable agent "
            "frameworks for real-world business applications.",
        ],
        education_summary="University (Indonesia) — Computer Science / Information Technology. Focus on software engineering and artificial intelligence.",
        recent_statements=[
            {
                "quote": (
                    "AI agents should be composable and resilient — each module must "
                    "handle failures gracefully and degrade without crashing the whole system."
                ),
                "source": "On building production-grade AI agent architectures",
                "context": "On building production-grade AI agent architectures",
                "date": "2025",
            },
            {
                "quote": (
                    "The real challenge isn't building one agent — it's orchestrating "
                    "multiple agents that can collaborate, share context, and produce "
                    "coherent outputs across different tools and APIs."
                ),
                "source": "On multi-agent system design",
                "context": "On multi-agent system design",
                "date": "2025",
            },
            {
                "quote": (
                    "Testing is not optional for AI applications. You need unit tests, "
                    "end-to-end tests, and API tests to catch regressions before they "
                    "reach production."
                ),
                "source": "On software quality practices",
                "context": "On software quality practices",
                "date": "2025",
            },
        ],
        known_associates=[
            {
                "name": "AI/LLM Community",
                "relationship": "Active contributor and collaborator in the LangChain, Composio, and Gemini developer ecosystems.",
            },
            {
                "name": "Indonesian Tech Community",
                "relationship": "Part of the growing Indonesian developer community focused on AI and cloud technologies.",
            },
        ],
        key_topics=[
            "Multi-agent AI systems",
            "LangGraph ReAct architecture",
            "Composio tool integrations",
            "Gemini & Groq LLMs",
            "FastAPI backend development",
            "Production-grade testing (400+ tests)",
            "LinkedIn & social media automation",
            "Legal document generation (GIPA)",
            "Meeting prep dossier generation",
            "Strategy diagram visualization",
        ],
        online_presence=(
            "LinkedIn: https://www.linkedin.com/in/maulanafirdaus | "
            "GitHub: Active open source contributions | "
            "Portfolio: AI Agent projects, full-stack applications"
        ),
    )

    # ── Strategic Insights ─────────────────────────────────────────────
    insights = StrategicInsights(
        conversation_starters=[
            "Ask about his experience building multi-agent systems with LangGraph — he has deep expertise in orchestrating AI agents that work together.",
            "Discuss the challenges of integrating external APIs (Composio, Serper, Gemini) into a unified agent framework — he's solved many of these problems firsthand.",
            "Inquire about his testing philosophy — with 400+ tests across 6 suites, he clearly values software quality and can share practical insights.",
            "Ask about his vision for AI-powered business tools — his GIPA and Dossier agents show he thinks about real-world business applications.",
            "Discuss Indonesian tech ecosystem growth — he's part of a vibrant developer community and can offer unique perspectives.",
        ],
        common_ground=[
            "Shared interest in AI/ML engineering and practical LLM applications",
            "Commitment to code quality and comprehensive testing practices",
            "Experience with modern Python ecosystem (FastAPI, async, type hints)",
            "Interest in composable, modular software architecture",
        ],
        topics_to_avoid=[
            "Avoid dismissing the importance of testing — it's clearly a core value",
            "Don't suggest shortcuts that compromise code quality or error handling",
            "Avoid assuming limited scope — his projects span full-stack, AI, DevOps, and integrations",
        ],
        relationship_map=[
            {
                "person": "LangChain / LangGraph Ecosystem",
                "relationship": "Core framework for his agent architecture",
                "leverage": "Discuss latest LangGraph features and patterns",
                "notes": "Primary orchestration framework used across all agents",
            },
            {
                "person": "Composio Platform",
                "relationship": "Key integration layer for OAuth and tool execution",
                "leverage": "Share insights on Composio's evolving toolkit capabilities",
                "notes": "Used for Gmail, LinkedIn, and social media integrations",
            },
            {
                "person": "Google Gemini / Vertex AI",
                "relationship": "Primary LLM for research synthesis and strategic analysis",
                "leverage": "Discuss Gemini's strengths for structured data extraction",
                "notes": "Powers the Dossier Agent's synthesis and analysis stages",
            },
            {
                "person": "Groq Cloud",
                "relationship": "LLM provider for fast inference in the main chatbot",
                "leverage": "Compare inference speed vs quality tradeoffs",
                "notes": "Used for the primary ReAct agent loop",
            },
        ],
        meeting_strategy=(
            "Muhammad is a highly technical engineer who values clean architecture, "
            "comprehensive testing, and graceful error handling. Approach the meeting "
            "with concrete technical details rather than high-level abstractions. "
            "He appreciates structured problem-solving and is experienced in "
            "breaking complex systems into well-tested modular components."
        ),
        negotiation_style=(
            "Data-driven and methodical. He prefers to see evidence (test results, "
            "architecture diagrams, concrete examples) before committing to decisions. "
            "Respects thoroughness and will push back on half-baked solutions."
        ),
        recommended_approach=(
            "1. Start with his recent multi-agent AI work as an icebreaker — it's clearly "
            "a passion project with impressive scope.\n"
            "2. Demonstrate technical depth — he'll engage more with peers who understand "
            "the nuances of agent orchestration, async Python, and API integration.\n"
            "3. Highlight shared values around code quality and testing.\n"
            "4. Be prepared to discuss specific implementation details — he's hands-on "
            "and will appreciate concrete, actionable conversations."
        ),
        key_motivations=[
            "Building AI systems that solve real business problems (legal docs, meeting prep, social media)",
            "Achieving production-grade quality with comprehensive testing",
            "Contributing to the open source AI ecosystem",
            "Growing the Indonesian tech community's AI capabilities",
        ],
    )

    # ── Generate Markdown Dossier ──────────────────────────────────────
    generator = DossierGenerator()
    markdown_doc = await generator.generate(
        synthesized.to_dict(),
        insights.to_dict(),
    )

    print("=" * 60)
    print("DOSSIER MARKDOWN (preview)")
    print("=" * 60)
    print(markdown_doc[:1000])
    print("...\n")

    # ── Convert to PDF ─────────────────────────────────────────────────
    print("Generating PDF...")
    pdf_path = generate_pdf_report.invoke(
        {
            "markdown_content": markdown_doc,
            "filename": "dossier_muhammad_maulana_firdaussyah.pdf",
            "sender_email": "maulana@example.com",
            "enable_quote_images": False,
        }
    )

    if pdf_path and not pdf_path.startswith("ERROR"):
        print(f"\nPDF generated successfully!")
        print(f"Path: {pdf_path}")
        size_kb = os.path.getsize(pdf_path) / 1024
        print(f"Size: {size_kb:.1f} KB")
    else:
        print(f"\nPDF generation failed: {pdf_path}")


if __name__ == "__main__":
    asyncio.run(main())

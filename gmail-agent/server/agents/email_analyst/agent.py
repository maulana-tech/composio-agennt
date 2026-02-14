"""
Email Analyst Plugin Agent - Fact-checking and email analysis.
"""

import os
from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import MultiAgentEmailAnalyzer

class EmailAnalystPluginAgent(BaseAgent):
    """
    Analyzes emails for factual claims and generates research reports.
    """

    name = "email_analyst"
    description = "Fact-checking and research analysis for email content"
    keywords = ["analyze email", "fact check", "verify claims", "research report"]
    active_statuses = ["analyzing_email", "planning_research", "conducting_research", "generating_report"]

    async def get_status(self, session_id: str = "default", base_url: str = "http://localhost:8000") -> str:
        # Status management for this agent is handled within the MultiAgentEmailAnalyzer instance
        # For simplicity, we return "none" unless a session is globally tracked
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """
        Process user request to analyze an email.
        """
        # This agent typically needs email content. If not provided in metadata, 
        # it might need to fetch from Gmail. For now, assume it's in metadata or message.
        email_content = context.metadata.get("email_content") or message
        
        analyzer = MultiAgentEmailAnalyzer()
        results = await analyzer.analyze_and_report(email_content, user_query=message)
        
        if results.get("success"):
            return AgentResponse(
                message=results.get("final_report", "Report generated."),
                status="completed",
                agent_name=self.name,
                data=results
            )
        else:
            return AgentResponse(
                message=f"❌ Error: {results.get('error', 'Analysis failed')}",
                status="error",
                agent_name=self.name
            )

    def get_tools(self) -> list:
        from .tools import get_email_analyst_tools
        return get_email_analyst_tools()

from langchain_core.tools import tool
from .logic import MultiAgentEmailAnalyzer

@tool
async def analyze_email_content(email_content: str, user_query: str = "") -> str:
    """Analyze email content for factual claims and generate a report."""
    analyzer = MultiAgentEmailAnalyzer()
    results = await analyzer.analyze_and_report(email_content, user_query=user_query)
    return results.get("final_report", "Analysis failed.")

def get_email_analyst_tools() -> list:
    return [analyze_email_content]

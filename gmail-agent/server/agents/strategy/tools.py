"""
Strategy Agent Tools - LangChain tool exports.
"""
from langchain_core.tools import tool
from .logic import analyze_strategic_prompt_logic, generate_mermaid_logic

def get_strategy_tools() -> list:
    @tool("analyze_strategy")
    async def analyze_strategy_tool(prompt: str) -> str:
        """Analyze a strategic situation and identify components for a diagram."""
        return await analyze_strategic_prompt_logic(prompt)

    @tool("generate_strategy_diagram")
    async def generate_mermaid_tool(analysis_json: str, style: str = "professional") -> str:
        """Generate a Mermaid diagram for a strategy based on analysis."""
        return await generate_mermaid_logic(analysis_json, style)

    return [analyze_strategy_tool, generate_mermaid_tool]

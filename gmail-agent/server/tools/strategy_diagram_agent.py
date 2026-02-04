"""
Strategy Diagram Agent
Generates strategic diagrams from text prompts using existing LLMs.
Provides real-time logging of agent progress.
"""

import os
import json
import re
from typing import Optional, AsyncGenerator
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from composio import Composio


def get_llm(groq_api_key: str = None):
    """Get LLM with fallback: Groq -> Google Gemini."""
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    if groq_api_key:
        try:
            return ChatGroq(
                model="llama-3.1-8b-instant", temperature=0.3, groq_api_key=groq_api_key
            ), "groq"
        except Exception as e:
            print(f"Groq init failed: {e}")

    if google_api_key:
        try:
            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", temperature=0.3, google_api_key=google_api_key
            ), "gemini"
        except Exception as e:
            print(f"Gemini init failed: {e}")

    raise ValueError("No LLM available")


def log_step(step: str, detail: str = "", progress: float = 0.0) -> dict:
    """Create a log step for streaming."""
    return {
        "type": "log",
        "status": "running",
        "step": step,
        "detail": detail,
        "progress": progress,
        "icon": get_step_icon(step),
    }


def get_step_icon(step: str) -> str:
    """Get icon for step type."""
    icons = {
        "analyzing": "🔍",
        "reasoning": "🧠",
        "generating": "⚙️",
        "validating": "✅",
        "completed": "🎉",
        "error": "❌",
    }
    step_lower = step.lower()
    for key, icon in icons.items():
        if key in step_lower:
            return icon
    return "📋"


@tool
def analyze_strategic_prompt(prompt: str) -> str:
    """Analyze strategic prompt to identify stakeholders, relationships, and diagram type."""
    groq_api_key = os.environ.get("GROQ_API_KEY")

    analysis_prompt = """
Analyze this strategic situation and provide JSON analysis:

PROMPT: {}

Format:
{{
    "stakeholders": ["list"],
    "relationships": ["key relationships"],
    "diagram_type": "flowchart|mindmap|swimlane",
    "flow_direction": "top-down|left-right",
    "key_points": ["essential elements"]
}}

Return ONLY valid JSON.
""".format(prompt)

    try:
        llm, provider = get_llm(groq_api_key)
        response = llm.invoke(analysis_prompt)

        content = response.content.strip()
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        content = content.strip()

        return content
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def generate_mermaid_diagram(
    analysis_json: str, custom_style: str = "professional"
) -> str:
    """Generate Mermaid.js diagram code from strategic analysis."""
    groq_api_key = os.environ.get("GROQ_API_KEY")

    try:
        analysis = json.loads(analysis_json)
    except:
        return "%% Error: Invalid analysis JSON"

    diagram_prompt = """
Generate ONLY valid Mermaid.js code (no explanations, no markdown):

Analysis:
{}

Style: {}

Requirements:
1. Use: graph LR or graph TD
2. Node IDs: A, B, C, D, E
3. Format: A[Label] or A{{Decision}}
4. Arrows: A --> B or A -->|label| B
5. Include all stakeholders

Example:
graph LR
    A[Marketing] --> B[Sales]
    B -->|approves| C[Product]

Generate now:
""".format(json.dumps(analysis), custom_style)

    try:
        llm, provider = get_llm(groq_api_key)
        response = llm.invoke(diagram_prompt)

        content = response.content.strip()

        # Remove any code blocks
        content = re.sub(r"```mermaid", "", content)
        content = re.sub(r"```", "", content)

        # Remove any Python-like syntax
        lines = content.split("\n")
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line and not any(
                x in line for x in ["print(", "Decision =", "return", "def ", "import "]
            ):
                # Remove trailing variable assignments
                line = re.sub(r"\s*=\s*.*$", "", line)
                clean_lines.append(line)

        content = "\n".join(clean_lines).strip()

        # Ensure it starts with graph
        if not content.lower().startswith("graph"):
            content = "graph LR\n" + content

        return content

    except Exception as e:
        return "%% Error: " + str(e)


@tool
def generate_graphviz_diagram(analysis_json: str) -> str:
    """Generate Graphviz DOT code from strategic analysis."""
    groq_api_key = os.environ.get("GROQ_API_KEY")

    try:
        analysis = json.loads(analysis_json)
    except:
        return "// Error: Invalid analysis JSON"

    dot_prompt = """
Generate ONLY valid Graphviz DOT code (no explanations, no markdown):

Analysis:
{}

Requirements:
1. Start with: digraph G {{ or graph G {{
2. Format: A [label="Label"]
3. Edges: A -> B [label="label"]
4. Include all stakeholders

Example:
digraph G {{
    A [label="Marketing"]
    B [label="Sales"]
    A -> B [label="coordinates"]
}}

Generate now:
""".format(json.dumps(analysis))

    try:
        llm, provider = get_llm(groq_api_key)
        response = llm.invoke(dot_prompt)

        content = response.content.strip()
        content = re.sub(r"```dot", "", content)
        content = re.sub(r"```", "", content)

        # Clean up
        lines = content.split("\n")
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line and not any(
                x in line for x in ["print(", "return", "def ", "import "]
            ):
                clean_lines.append(line)

        content = "\n".join(clean_lines).strip()

        return content

    except Exception as e:
        return "// Error: " + str(e)


@tool
def validate_diagram_code(diagram_code: str, format_type: str = "mermaid") -> str:
    """Validate and improve diagram code."""
    errors = []
    suggestions = []

    if not diagram_code:
        return json.dumps(
            {"valid": False, "errors": ["Empty diagram code"], "suggestions": []}
        )

    if format_type == "mermaid":
        if "graph" not in diagram_code and "sequenceDiagram" not in diagram_code:
            errors.append("Missing graph or sequenceDiagram declaration")

        # Count nodes
        nodes = len(re.findall(r"[A-Z]\[[^\]]+\]|[A-Z]\{[^\}]+\}", diagram_code))
        if nodes < 2:
            suggestions.append("Consider adding more nodes for clarity")

    elif format_type == "graphviz":
        if "digraph" not in diagram_code and "graph" not in diagram_code:
            errors.append("Missing digraph or graph declaration")

    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "suggestions": suggestions,
        "code_length": len(diagram_code),
        "nodes_count": len(re.findall(r"[A-Z]", diagram_code)),
    }

    return json.dumps(result)


@tool
def create_strategy_diagram(
    prompt: str,
    format_type: str = "mermaid",
    style: str = "professional",
    include_analysis: bool = True,
) -> str:
    """Create a complete strategy diagram from prompt with full workflow logging."""

    result = {
        "status": "running",
        "prompt": prompt,
        "format": format_type,
        "style": style,
        "progress": {"analyzing": 0, "generating": 0, "validating": 0, "completed": 0},
        "steps": [],
        "analysis": None,
        "diagram_code": None,
        "validation": None,
        "error": None,
    }

    try:
        # Step 1: Analyze prompt
        result["steps"].append(
            log_step("analyzing", "Analyzing strategic prompt...", 10)
        )
        analysis = analyze_strategic_prompt.invoke({"prompt": prompt})

        try:
            analysis_data = json.loads(analysis)
            result["analysis"] = analysis_data
        except:
            result["analysis"] = {"raw": analysis}

        result["progress"]["analyzing"] = 100

        # Step 2: Generate diagram
        result["steps"].append(log_step("generating", "Generating diagram code...", 40))

        if format_type == "mermaid":
            diagram_code = generate_mermaid_diagram.invoke(
                {"analysis_json": analysis, "custom_style": style}
            )
        else:
            diagram_code = generate_graphviz_diagram.invoke({"analysis_json": analysis})

        result["diagram_code"] = diagram_code
        result["progress"]["generating"] = 100

        # Step 3: Validate
        result["steps"].append(log_step("validating", "Validating diagram code...", 80))

        validation = validate_diagram_code.invoke(
            {"diagram_code": diagram_code, "format_type": format_type}
        )

        result["validation"] = json.loads(validation)
        result["progress"]["validating"] = 100

        # Complete
        result["status"] = "completed"
        result["steps"].append(
            log_step("completed", "Strategy diagram created successfully!", 100)
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["steps"].append(log_step("error", "Error: " + str(e), 0))
        return json.dumps(result, indent=2)


@tool
def preview_mermaid_diagram(diagram_code: str) -> str:
    """Preview Mermaid diagram and return rendering information."""
    try:
        nodes = re.findall(r"([A-Z])\[[^\]]+\]|\{[A-Z][^\}]+\}", diagram_code)
        all_nodes = list(set(nodes))

        preview_info = {
            "valid": True,
            "node_count": len(all_nodes),
            "nodes": all_nodes[:10],
            "rendering_hints": {
                "mermaid_live": "https://mermaid.live/edit",
            },
        }

        return json.dumps(preview_info)
    except Exception as e:
        return json.dumps({"valid": False, "error": str(e)})


async def generate_strategy_diagram_stream(
    prompt: str,
    groq_api_key: str,
    format_type: str = "mermaid",
    style: str = "professional",
) -> AsyncGenerator[str, None]:
    """Generate strategy diagram with real-time streaming progress."""
    os.environ["GROQ_API_KEY"] = groq_api_key

    try:
        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "starting",
                    "step": "initializing",
                    "detail": "Setting up strategy diagram generator...",
                    "progress": 5,
                    "icon": "🚀",
                }
            )
            + "\n"
        )

        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "running",
                    "step": "analyzing",
                    "detail": "🔍 Analyzing strategic prompt...",
                    "progress": 10,
                    "icon": "🔍",
                }
            )
            + "\n"
        )

        from .strategy_diagram_agent import analyze_strategic_prompt

        analysis = analyze_strategic_prompt.invoke({"prompt": prompt})

        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "progress",
                    "step": "analyzing",
                    "detail": "✅ Analysis complete",
                    "progress": 35,
                    "icon": "✅",
                }
            )
            + "\n"
        )

        try:
            analysis_data = json.loads(analysis)
            stakeholders = analysis_data.get("stakeholders", [])[:5]
            yield (
                json.dumps(
                    {
                        "type": "log",
                        "status": "info",
                        "step": "analyzing",
                        "detail": "Found: " + ", ".join(stakeholders),
                        "progress": 35,
                        "icon": "👥",
                    }
                )
                + "\n"
            )
        except:
            pass

        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "running",
                    "step": "generating",
                    "detail": "⚙️ Generating diagram code...",
                    "progress": 40,
                    "icon": "⚙️",
                }
            )
            + "\n"
        )

        from .strategy_diagram_agent import generate_mermaid_diagram

        if format_type == "mermaid":
            diagram_code = generate_mermaid_diagram.invoke(
                {"analysis_json": analysis, "custom_style": style}
            )
        else:
            from .strategy_diagram_agent import generate_graphviz_diagram

            diagram_code = generate_graphviz_diagram.invoke({"analysis_json": analysis})

        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "progress",
                    "step": "generating",
                    "detail": "✅ Diagram generated",
                    "progress": 70,
                    "icon": "✅",
                }
            )
            + "\n"
        )

        from .strategy_diagram_agent import validate_diagram_code

        validation = validate_diagram_code.invoke(
            {"diagram_code": diagram_code, "format_type": format_type}
        )
        validation_data = json.loads(validation)
        is_valid = validation_data.get("valid", False)

        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "completed",
                    "step": "completed",
                    "detail": "🎉 Strategy diagram ready!",
                    "progress": 100,
                    "icon": "🎉",
                    "result": {
                        "diagram_code": diagram_code,
                        "format": format_type,
                        "validation": validation_data,
                    },
                }
            )
            + "\n"
        )

    except Exception as e:
        yield (
            json.dumps(
                {
                    "type": "error",
                    "status": "error",
                    "step": "error",
                    "detail": "❌ Error: " + str(e),
                    "error": str(e),
                }
            )
            + "\n"
        )


def get_strategy_diagram_tools():
    """Get LangChain tools for strategy diagram agent."""
    return [
        create_strategy_diagram,
        analyze_strategic_prompt,
        generate_mermaid_diagram,
        generate_graphviz_diagram,
        validate_diagram_code,
        preview_mermaid_diagram,
    ]


__all__ = [
    "create_strategy_diagram",
    "analyze_strategic_prompt",
    "generate_mermaid_diagram",
    "generate_graphviz_diagram",
    "validate_diagram_code",
    "preview_mermaid_diagram",
    "generate_strategy_diagram_stream",
    "get_strategy_diagram_tools",
]

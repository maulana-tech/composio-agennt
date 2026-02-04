"""
Strategy Diagram Agent
Generates strategic diagrams from text prompts using existing LLMs.
Provides real-time logging of agent progress.
"""

import os
import json
import re
import base64
import time
from typing import Optional, AsyncGenerator
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from composio import Composio

# Optional imports for Mermaid conversion
try:
    import mermaid as md
    from mermaid.graph import Graph

    MERMAID_AVAILABLE = True
except ImportError:
    MERMAID_AVAILABLE = False
    md = None
    Graph = None

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def get_llm():
    """Get LLM with fallback: Groq -> Google Gemini."""
    groq_api_key = os.environ.get("GROQ_API_KEY")
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    if groq_api_key:
        try:
            return ChatGroq(
                model="llama-3.1-8b-instant", temperature=0.3, groq_api_key=groq_api_key
            )
        except Exception as e:
            print(f"Groq init failed: {e}")

    if google_api_key:
        try:
            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", temperature=0.3, google_api_key=google_api_key
            )
        except Exception as e:
            print(f"Gemini init failed: {e}")

    raise ValueError("No LLM available")


def clean_json_response(text: str) -> str:
    """Clean JSON response from LLM."""
    text = re.sub(
        r"^(?:Here\'s?|Here is|Below is|Ini adalah|Berikut adalah)[\s:\-]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^```json?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = text.strip()
    return text


def clean_mermaid_response(text: str) -> str:
    """Clean Mermaid response from LLM."""
    text = re.sub(
        r"^(?:Here\'s?|Here is|Mermaid code|Below is|Inilah)[\s:\-]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^```mermaid\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        if any(
            x in line.lower()
            for x in ["this code", "generates", "creates", "shows", "example:", "note:"]
        ):
            break
        clean_lines.append(line)
    text = "\n".join(clean_lines).strip()
    if not text.lower().startswith("graph") and not text.lower().startswith("sequence"):
        match = re.search(r"(graph\s+[A-Z]+.*)", text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1)
        else:
            text = "graph LR\n" + text
    return text


@tool
def analyze_strategic_prompt(prompt: str) -> str:
    """Analyze strategic prompt to identify stakeholders, relationships, and diagram type."""
    llm = get_llm()

    analysis_prompt = f"""
Analyze this strategic situation and return ONLY valid JSON:

PROMPT: {prompt}

Format (NO markdown, NO explanations):
{{"stakeholders": ["list of entities"], "relationships": ["key relationships"], "diagram_type": "flowchart|mindmap|swimlane", "flow_direction": "top-down|left-right", "key_points": ["essential elements"]}}

Return ONLY JSON:
"""

    try:
        response = llm.invoke(analysis_prompt)
        content = clean_json_response(str(response.content))

        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > 0:
            content = content[start:end]

        json.loads(content)
        return content
    except Exception as e:
        fallback = {
            "stakeholders": ["Stakeholder 1", "Stakeholder 2"],
            "relationships": ["coordination"],
            "diagram_type": "flowchart",
            "flow_direction": "left-right",
            "key_points": ["Key Point 1"],
        }
        return json.dumps(fallback)


@tool
def generate_mermaid_diagram(
    analysis_json: str, custom_style: str = "professional"
) -> str:
    """Generate Mermaid.js diagram code from strategic analysis."""
    llm = get_llm()

    try:
        analysis = json.loads(analysis_json)
    except:
        return "%% Error: Invalid analysis JSON"

    diagram_prompt = f"""
Generate ONLY valid Mermaid code (no markdown, no explanations):

Analysis: {json.dumps(analysis)}

Requirements:
1. Start with: graph LR or graph TD
2. Use simple IDs: A, B, C, D, E
3. Format: A[Label] or A{{Decision}}
4. Arrows: A --> B
5. Include all stakeholders
6. NO markdown code blocks
7. NO text before or after code

Example:
graph LR
    A[Marketing] --> B[Sales]

Generate now:
"""

    try:
        response = llm.invoke(diagram_prompt)
        content = clean_mermaid_response(str(response.content))
        return content
    except Exception as e:
        return "%% Error: " + str(e)


@tool
def generate_graphviz_diagram(analysis_json: str) -> str:
    """Generate Graphviz DOT code from strategic analysis."""
    llm = get_llm()

    try:
        analysis = json.loads(analysis_json)
    except:
        return "// Error: Invalid analysis JSON"

    dot_prompt = f"""
Generate ONLY valid Graphviz DOT code (no markdown, no explanations):

Analysis: {json.dumps(analysis)}

Requirements:
1. Start with: digraph G {{ or graph G {{
2. Format: A [label="Label"]
3. Edges: A -> B [label="desc"]
4. Include all stakeholders
5. NO markdown code blocks
6. NO text before or after code

Example:
digraph G {{
    A [label="Marketing"]
    B [label="Sales"]
    A -> B
}}

Generate now:
"""

    try:
        response = llm.invoke(dot_prompt)
        content = str(response.content).strip()
        content = re.sub(r"^```dot\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        if not content.lower().startswith("digraph") and not content.lower().startswith(
            "graph"
        ):
            content = "digraph G {\n" + content + "\n}"
        return content
    except Exception as e:
        return "// Error: " + str(e)


@tool
def validate_diagram_code(diagram_code: str, format_type: str = "mermaid") -> str:
    """Validate and improve diagram code."""
    errors = []
    suggestions = []

    if not diagram_code or len(diagram_code) < 10:
        return json.dumps(
            {"valid": False, "errors": ["Empty or too short"], "suggestions": []}
        )

    if format_type == "mermaid":
        if (
            "graph" not in diagram_code.lower()
            and "sequence" not in diagram_code.lower()
        ):
            errors.append("Missing graph or sequenceDiagram declaration")
        nodes = len(re.findall(r"[A-Z]\[[^\]]+\]|\{[A-Z][^\}]+\}", diagram_code))
        if nodes < 2:
            suggestions.append("Consider adding more nodes for clarity")

    elif format_type == "graphviz":
        if (
            "digraph" not in diagram_code.lower()
            and "graph " not in diagram_code.lower()
        ):
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
        result["steps"].append(
            {
                "type": "log",
                "status": "running",
                "step": "analyzing",
                "detail": "Analyzing strategic prompt...",
                "progress": 10,
                "icon": "🔍",
            }
        )

        analysis = analyze_strategic_prompt.invoke({"prompt": prompt})

        try:
            analysis_data = json.loads(analysis)
            result["analysis"] = analysis_data
        except:
            result["analysis"] = {"raw": analysis}

        result["progress"]["analyzing"] = 100

        result["steps"].append(
            {
                "type": "log",
                "status": "running",
                "step": "generating",
                "detail": "Generating diagram code...",
                "progress": 40,
                "icon": "⚙️",
            }
        )

        if format_type == "mermaid":
            diagram_code = generate_mermaid_diagram.invoke(
                {"analysis_json": analysis, "custom_style": style}
            )
        else:
            diagram_code = generate_graphviz_diagram.invoke({"analysis_json": analysis})

        result["diagram_code"] = diagram_code
        result["progress"]["generating"] = 100

        result["steps"].append(
            {
                "type": "log",
                "status": "running",
                "step": "validating",
                "detail": "Validating diagram code...",
                "progress": 80,
                "icon": "✅",
            }
        )

        validation = validate_diagram_code.invoke(
            {"diagram_code": diagram_code, "format_type": format_type}
        )

        result["validation"] = json.loads(validation)
        result["progress"]["validating"] = 100

        result["status"] = "completed"
        result["steps"].append(
            {
                "type": "log",
                "status": "completed",
                "step": "completed",
                "detail": "Strategy diagram created successfully!",
                "progress": 100,
                "icon": "🎉",
            }
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["steps"].append(
            {
                "type": "log",
                "status": "error",
                "step": "error",
                "detail": "Error: " + str(e),
                "progress": 0,
                "icon": "❌",
            }
        )
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


@tool
def convert_mermaid_to_image(
    diagram_code: str,
    output_format: str = "png",
    theme: str = "default",
) -> str:
    """Convert Mermaid diagram to image using mermaid-py library.

    Args:
        diagram_code: The Mermaid diagram code (with or without markdown blocks)
        output_format: "png" or "svg"
        theme: Mermaid theme - "default", "dark", "forest", "neutral"

    Returns:
        JSON string with image path, base64 data, and rendering info
    """
    if not MERMAID_AVAILABLE or md is None or Graph is None:
        return json.dumps(
            {
                "success": False,
                "error": "mermaid-py not installed",
                "message": "Install: pip install mermaid-py",
                "alternative": {"mermaid_live": "https://mermaid.live/edit"},
            }
        )

    try:
        clean_code = diagram_code.strip()
        clean_code = re.sub(r"^```mermaid\s*", "", clean_code)
        clean_code = re.sub(r"\s*```$", "", clean_code)

        graph = Graph("strategy-diagram", clean_code)
        mermaid_obj = md.Mermaid(graph)

        output_dir = "/tmp/mermaid_images"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"diagram_{int(time.time())}.{output_format}"
        )

        if output_format == "svg":
            mermaid_obj.to_svg(output_path)
            with open(output_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            with open(output_path, "rb") as f:
                file_size = len(f.read())

            base64_svg = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
            data_url = f"data:image/svg+xml;base64,{base64_svg}"

            return json.dumps(
                {
                    "success": True,
                    "format": "svg",
                    "path": output_path,
                    "file_size": file_size,
                    "data_url": data_url,
                    "base64": base64_svg,
                    "message": f"SVG saved to {output_path}",
                }
            )

        else:
            mermaid_obj.to_png(output_path)

            with open(output_path, "rb") as f:
                png_bytes = f.read()
                file_size = len(png_bytes)

            base64_png = base64.b64encode(png_bytes).decode("utf-8")
            data_url = f"data:image/png;base64,{base64_png}"

            width, height = 0, 0
            if PIL_AVAILABLE and Image is not None:
                with Image.open(output_path) as img:
                    width, height = img.size

            return json.dumps(
                {
                    "success": True,
                    "format": "png",
                    "path": output_path,
                    "file_size": file_size,
                    "width": width,
                    "height": height,
                    "data_url": data_url,
                    "base64": base64_png,
                    "embed_code": f"![Mermaid Diagram]({data_url})",
                    "html_img": f'<img src="{data_url}" alt="Strategy Diagram" />',
                    "message": f"PNG saved to {output_path} ({width}x{height}px)",
                }
            )

    except ImportError:
        return json.dumps(
            {
                "success": False,
                "error": "mermaid-py not installed",
                "message": "Install: pip install mermaid-py",
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "message": "Failed to convert diagram to image",
            }
        )


@tool
def get_diagram_image_url(diagram_code: str, output_format: str = "png") -> str:
    """Get direct URL for Mermaid diagram using mermaid.ink API.

    Args:
        diagram_code: The Mermaid diagram code
        output_format: "png" or "svg"

    Returns:
        JSON string with direct URL for embedding
    """
    try:
        clean_code = diagram_code.strip()
        clean_code = re.sub(r"^```mermaid\s*", "", clean_code)
        clean_code = re.sub(r"\s*```$", "", clean_code)

        encoded = (
            clean_code.replace("\n", "%0A").replace(" ", "%20").replace("'", "%27")
        )
        base = "https://mermaid.ink"

        if output_format == "svg":
            url = f"{base}/svg/{encoded}"
            return json.dumps(
                {
                    "success": True,
                    "format": "svg",
                    "url": url,
                    "embed_html": f'<img src="{url}" alt="Mermaid Diagram" />',
                    "markdown": f"![Diagram]({url})",
                }
            )

        url = f"{base}/img/{encoded}"
        return json.dumps(
            {
                "success": True,
                "format": "png",
                "url": url,
                "embed_html": f'<img src="{url}" alt="Mermaid Diagram" />',
                "markdown": f"![Diagram]({url})",
            }
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
def render_mermaid_online(diagram_code: str) -> str:
    """Get online rendering URLs for Mermaid diagram."""
    clean_code = diagram_code.strip()
    clean_code = re.sub(r"^```mermaid\s*", "", clean_code)
    clean_code = re.sub(r"\s*```$", "", clean_code)
    encoded_code = (
        clean_code.replace("\n", "%0A").replace(" ", "%20").replace("'", "%27")
    )

    urls = {
        "mermaid_live": f"https://mermaid.live/edit#code={encoded_code}",
        "mermaid_js": f"https://mermaid-js.github.io/mermaid-live-editor/#/edit/{encoded_code}",
        "quickchart": f"https://quickchart.io/graphviz?graph={encoded_code}"
        if "graph" in clean_code.lower()
        else None,
    }

    return json.dumps(
        {
            "success": True,
            "rendering_urls": urls,
            "diagram_length": len(clean_code),
            "message": "Click URLs to view rendered diagram",
        }
    )


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
                    "detail": "Setting up...",
                    "progress": 5,
                    "icon": "🚀",
                }
            )
            + "\n"
        )

        from .strategy_diagram_agent import analyze_strategic_prompt

        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "running",
                    "step": "analyzing",
                    "detail": "🔍 Analyzing...",
                    "progress": 10,
                    "icon": "🔍",
                }
            )
            + "\n"
        )

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
                    "detail": "⚙️ Generating...",
                    "progress": 40,
                    "icon": "⚙️",
                }
            )
            + "\n"
        )

        if format_type == "mermaid":
            from .strategy_diagram_agent import generate_mermaid_diagram

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
                    "detail": "✅ Generated",
                    "progress": 70,
                    "icon": "✅",
                }
            )
            + "\n"
        )

        from .strategy_diagram_agent import (
            validate_diagram_code,
            convert_mermaid_to_image,
        )

        validation = validate_diagram_code.invoke(
            {"diagram_code": diagram_code, "format_type": format_type}
        )
        validation_data = json.loads(validation)
        is_valid = validation_data.get("valid", False)

        image_result = None
        if format_type == "mermaid" and is_valid:
            image_data = convert_mermaid_to_image.invoke({"diagram_code": diagram_code})
            try:
                image_result = json.loads(image_data)
            except:
                pass

        yield (
            json.dumps(
                {
                    "type": "log",
                    "status": "completed",
                    "step": "completed",
                    "detail": "🎉 Ready!",
                    "progress": 100,
                    "icon": "🎉",
                    "result": {
                        "diagram_code": diagram_code,
                        "format": format_type,
                        "validation": validation_data,
                        "image": image_result,
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
        convert_mermaid_to_image,
        render_mermaid_online,
    ]


__all__ = [
    "create_strategy_diagram",
    "analyze_strategic_prompt",
    "generate_mermaid_diagram",
    "generate_graphviz_diagram",
    "validate_diagram_code",
    "preview_mermaid_diagram",
    "convert_mermaid_to_image",
    "render_mermaid_online",
    "generate_strategy_diagram_stream",
    "get_strategy_diagram_tools",
]

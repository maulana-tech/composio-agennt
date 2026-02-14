import os
import json
import httpx
import re
from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from composio_langchain import LangchainProvider
from composio import Composio

from server.prompts.main_prompt import SYSTEM_PROMPT
from server.agents import create_default_registry, AgentRouter
from server.agents import create_default_registry, AgentRouter


def get_llm_with_fallback(groq_api_key: str):
    """
    Get LLM with fallback: Groq -> Google Gemini.
    Returns (llm, provider_name) tuple.
    """
    # Check for Google API key
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    # Primary: Groq
    if groq_api_key:
        try:
            llm = ChatGroq(
                model="llama-3.1-8b-instant", temperature=0, groq_api_key=groq_api_key
            )
            return llm, "groq"
        except Exception as e:
            print(f"Groq init failed: {e}")

    # Fallback: Google Gemini
    if google_api_key:
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", temperature=0, google_api_key=google_api_key
            )
            return llm, "gemini"
        except Exception as e:
            print(f"Gemini init failed: {e}")

    raise ValueError("No LLM available. Please provide GROQ_API_KEY or GOOGLE_API_KEY.")


async def run_agent_with_fallback(agent_factory, inputs: dict, groq_api_key: str):
    """
    Run agent with automatic fallback to Gemini on rate limit errors.
    agent_factory is a function that takes (llm, provider_name) and returns agent.
    """
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    # Try Groq first
    if groq_api_key:
        try:
            llm = ChatGroq(
                model="llama-3.1-8b-instant", temperature=0, groq_api_key=groq_api_key
            )
            agent = agent_factory(llm, "groq")
            state = await agent.ainvoke(inputs, config={"recursion_limit": 15})
            return state, "groq"
        except Exception as e:
            error_str = str(e).lower()
            # Check if it's a rate limit, tool use failure, or generation failure
            if any(
                err in error_str
                for err in [
                    "413",
                    "rate_limit",
                    "tokens",
                    "tool_use_failed",
                    "failed_generation",
                    "failed to call",
                    "adjust your prompt",
                ]
            ):
                print(f"Groq error ({e}), falling back to Gemini.")
            else:
                raise e

    # Fallback to Gemini
    if google_api_key:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0, google_api_key=google_api_key
        )
        agent = agent_factory(llm, "gemini")
        state = await agent.ainvoke(inputs, config={"recursion_limit": 15})
        return state, "gemini"

    raise ValueError("Groq rate limited and no GOOGLE_API_KEY available for fallback.")


# Initialize global agent registry and router
_agent_registry = create_default_registry()
_agent_router = AgentRouter(_agent_registry)


async def handle_gipa_request(
    user_message: str, conversation_history: List[Dict] = None, user_id: str = "default"
) -> dict:
    """
    Legacy wrapper - delegates to GIPAPluginAgent via AgentRouter.
    Kept for backward compatibility with existing callers.
    """
    from server.agents.base import AgentContext

    context = AgentContext(
        user_id=user_id,
        session_id="default",
        conversation_history=conversation_history,
    )
    gipa_agent = _agent_registry.get("gipa")
    if gipa_agent:
        response = await gipa_agent.handle(user_message, context)
        return response.to_dict()
    return {
        "type": "final_result",
        "message": "❌ GIPA agent not registered.",
        "intent": {"action": "gipa_error", "query": user_message},
    }


def convert_history(history: List[Dict]) -> List[BaseMessage]:
    messages = []
    if not history:
        return messages
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))
    return messages




def get_agent_tools(user_id: str):
    """Create all tools for the agent with specific user context."""
    from server.tools import get_all_tools
    
    # Get all aggregated tools from all modular agents
    return get_all_tools(user_id)




async def chat(
    user_message: str,
    groq_api_key: str,
    user_id: str,
    conversation_history: list = None,
    auto_execute: bool = True,
    session_id: str = "default",
) -> dict:
    """
    LangGraph-based Agent Chat (Blocking).
    """

    # 0. Detect if this is a pure question/generation (no tool intent)
    import re

    tool_keywords = [
        r"\b(pdf|lampiran|kirim|email|draft|generate|buat file|download|search|cari|extract|visit|web|ringkasan|summary|laporan|report|attach)\b",
        # Political research keywords
        r"\b(prabowo|jokowi|politik|politician|presiden|menteri|quotes|kutipan|statement|pernyataan|isu|issue|kebijakan|policy|kampanye|campaign|twitter|x\.com|instagram|social media)\b",
        # Social media posting keywords
        r"\b(post|share|upload|twitter|x\.com|facebook|fb|instagram|ig|social media|media sosial|posting|unggah|bagikan)\b",
        # Deep research keywords
        r"\b(analisis|analysis|research|investigate|investigasi|fakta|fact check|verifikasi|verify|bandingkan|compare|sejarah|history|timeline|data|statistik)\b",
        # Document generation keywords
        r"\b(dokumen|document|file|word|excel|csv|presentasi|presentation|slide|export|save|simpan|arsip|archive)\b",
        # GIPA / FOI / Government Information Access keywords
        r"\b(gipa|foi|freedom of information|government information|public access|information request|information access|right to information|rti)\b",
        # Dossier / Meeting Prep keywords
        r"\b(dossier|meeting prep|meeting preparation|briefing|background check|profile research|profil|person research|relationship map)\b",
        # LinkedIn posting/management keywords
        r"\b(linkedin|linked in|post on linkedin|linkedin post|linkedin article|linkedin connection|linkedin company|linkedin profile)\b",
    ]

    # Check for explicit tool intent
    is_tool_intent = any(
        re.search(pattern, user_message, re.IGNORECASE) for pattern in tool_keywords
    )

    # Also check conversation history for context
    has_research_context = False
    if conversation_history and len(conversation_history) >= 2:
        # Check if previous messages indicate ongoing research
        recent_messages = conversation_history[-3:]  # Last 3 messages
        research_indicators = [
            "cari",
            "research",
            "find",
            "cari tahu",
            "analisis",
            "analysis",
            "laporan",
            "report",
            "quotes",
            "kutipan",
            "statement",
            "pernyataan",
        ]
        for msg in recent_messages:
            if any(
                indicator in msg.get("content", "").lower()
                for indicator in research_indicators
            ):
                has_research_context = True
                break

    # Combine checks
    if has_research_context and not is_tool_intent:
        # If there's research context but no explicit tool keywords,
        # still treat as tool intent for better continuity
        is_tool_intent = True

    # AGENT ROUTER: Check if any specialized agent (GIPA, Dossier, etc.) should handle this
    router_result = await _agent_router.route(
        message=user_message,
        user_id=user_id,
        session_id=session_id,
        conversation_history=conversation_history,
    )
    if router_result:
        return router_result.to_dict()

    if not is_tool_intent:
        # Use Gemini directly for pure generation/QA
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key:
            return {
                "type": "final_result",
                "message": "Error: GOOGLE_API_KEY not configured.",
                "intent": {"action": "direct_gemini", "query": user_message},
            }
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0.2, google_api_key=google_api_key
        )
        formatted_history = convert_history(conversation_history)
        messages = formatted_history + [HumanMessage(content=user_message)]
        # Use only the last 5 messages for context
        messages = messages[-5:]
        response = await llm.ainvoke(messages)
        return {
            "type": "final_result",
            "message": response.content,
            "intent": {"action": "direct_gemini", "query": user_message},
        }

    # 1. Setup Tools
    tools = get_agent_tools(user_id)

    # 2. Setup Agent Factory
    def create_agent(llm, provider_name):
        return create_react_agent(
            model=llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
        )

    # 3. Execute
    formatted_history = convert_history(conversation_history)
    inputs = {"messages": formatted_history + [HumanMessage(content=user_message)]}
    try:
        state, provider_used = await run_agent_with_fallback(
            create_agent, inputs, groq_api_key
        )
        last_message = state["messages"][-1]
        response_message = last_message.content
        if provider_used == "gemini":
            response_message = (
                f"*[Using Gemini - Groq rate limited]*\n\n{response_message}"
            )
    except Exception as e:
        response_message = f"Error executing task: {str(e)}"
    return {
        "type": "final_result",
        "message": response_message,
        "intent": {"action": "autonomous_agent", "query": user_message},
    }


async def run_agent_stream_with_fallback(
    agent_factory, inputs: dict, groq_api_key: str
):
    """Run agent stream with fallback."""
    google_api_key = os.environ.get("GOOGLE_API_KEY")

    async def iterate_events(agent, provider):
        async for event in agent.astream_events(
            inputs, version="v1", config={"recursion_limit": 15}
        ):
            yield event, provider

    # Try Groq
    if groq_api_key:
        try:
            llm = ChatGroq(
                model="llama-3.1-8b-instant", temperature=0, groq_api_key=groq_api_key
            )
            agent = agent_factory(llm, "groq")
            async for event, prov in iterate_events(agent, "groq"):
                yield event, prov
            return
        except Exception as e:
            error_str = str(e).lower()
            if any(
                err in error_str
                for err in [
                    "413",
                    "rate_limit",
                    "tool_use_failed",
                    "failed_generation",
                    "failed to call",
                    "adjust your prompt",
                ]
            ):
                print(f"Groq error (stream), falling back to Gemini.")
            else:
                raise e

    # Fallback Gemini
    if google_api_key:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", temperature=0, google_api_key=google_api_key
        )
        agent = agent_factory(llm, "gemini")
        async for event, prov in iterate_events(agent, "gemini"):
            yield event, prov


async def chat_stream(
    user_message: str,
    groq_api_key: str,
    user_id: str,
    conversation_history: list = None,
    session_id: str = "default",
):
    """
    Stream events from the agent.
    Yields JSON strings: {type: "log"|"final", ...}
    """
    # AGENT ROUTER: Check if any specialized agent should handle this
    _router_result = await _agent_router.route(
        message=user_message,
        user_id=user_id,
        session_id=session_id,
        conversation_history=conversation_history,
    )
    if _router_result:
        yield json.dumps({
            "type": "log",
            "status": "running",
            "title": f"{_router_result.agent_name.upper()} Handler",
            "detail": f"Processing via {_router_result.agent_name} agent...",
        }) + "\n"
        yield json.dumps({"type": "token", "content": _router_result.message}) + "\n"
        yield json.dumps({"type": "final_result", "message": _router_result.message}) + "\n"
        return

    tools = get_agent_tools(user_id)

    def create_agent(llm, provider_name):
        return create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)

    formatted_history = convert_history(conversation_history)
    inputs = {"messages": formatted_history + [HumanMessage(content=user_message)]}

    final_content = ""

    try:
        async for event, provider in run_agent_stream_with_fallback(
            create_agent, inputs, groq_api_key
        ):
            event_type = event["event"]

            # Log Tool Usage
            if event_type == "on_tool_start":
                tool_name = event["name"]
                tool_input = event["data"].get("input")
                yield (
                    json.dumps(
                        {
                            "type": "log",
                            "status": "running",
                            "title": f"Using Tool: {tool_name}",
                            "detail": str(tool_input)[:200],
                        }
                    )
                    + "\n"
                )

            elif event_type == "on_tool_end":
                tool_name = event["name"]
                output = event["data"].get("output")
                yield (
                    json.dumps(
                        {
                            "type": "log",
                            "status": "success",
                            "title": f"Using Tool: {tool_name}",
                            "detail": f"Completed. Output: {str(output)[:100]}...",
                        }
                    )
                    + "\n"
                )

            elif event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield json.dumps({"type": "token", "content": chunk.content}) + "\n"
                    final_content += chunk.content

    except Exception as e:
        yield json.dumps({"type": "error", "message": str(e)}) + "\n"
        return

    # Yield final marker if content was gathered
    # Note: token stream might be fragmented. The UI needs to accumulate 'token' events.
    yield json.dumps({"type": "final_result", "message": final_content}) + "\n"

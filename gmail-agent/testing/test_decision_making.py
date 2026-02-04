#!/usr/bin/env python3
"""
Test 2: Agent Decision-Making Test
Testing if the agent can correctly decide between:
1. Serper/Google Search for current events and recent information
2. Grounding search for fact-checking and verification
3. Direct AI response for general knowledge concepts

Test Cases:
1. "Carilah artikel tentang budaya nepotisme" -> Should use Serper (recent articles)
2. "Apa itu Nepotisme?" -> Should use direct AI response (general concept)
"""

import asyncio
import json
import os
from server.chatbot import chat, get_agent_tools, SYSTEM_PROMPT
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI


class TestLogger:
    def __init__(self):
        self.logs = []

    def log(self, test_name, message, data=None):
        log_entry = {
            "test": test_name,
            "message": message,
            "data": data,
            "timestamp": asyncio.get_event_loop().time(),
        }
        self.logs.append(log_entry)
        print(f"🔍 [{test_name}] {message}")
        if data:
            print(f"   Data: {json.dumps(data, indent=2, default=str)}")


class SearchToolTracker:
    """Track which search tools are being called"""

    def __init__(self):
        self.serper_calls = []
        self.grounding_calls = []
        self.ai_only_calls = []

    def track_serper_call(self, tool_name, query):
        self.serper_calls.append({"tool": tool_name, "query": query})

    def track_grounding_call(self, tool_name, query):
        self.grounding_calls.append({"tool": tool_name, "query": query})

    def track_ai_only_call(self, query):
        self.ai_only_calls.append({"query": query})


def create_tracked_tools(user_id, tracker):
    """Create tools with tracking capabilities"""
    from server.chatbot import create_serper_tools, create_grounding_tools
    from composio import Composio
    import os

    # Get original tools
    serper_tools = create_serper_tools()
    grounding_tools = create_grounding_tools()

    # Wrap serper tools with tracking
    tracked_serper = []
    for tool_func in serper_tools:
        original_run = tool_func.func if hasattr(tool_func, "func") else tool_func

        @tool
        def tracked_tool(*args, **kwargs):
            query = kwargs.get("query", args[0] if args else "unknown")
            tracker.track_serper_call(tool_func.name, query)
            return original_run(*args, **kwargs)

        tracked_tool.name = tool_func.name
        tracked_tool.description = tool_func.description
        tracked_serper.append(tracked_tool)

    # Wrap grounding tools with tracking
    tracked_grounding = []
    for tool_func in grounding_tools:
        original_run = tool_func.func if hasattr(tool_func, "func") else tool_func

        @tool
        def tracked_tool(*args, **kwargs):
            query = kwargs.get("query", args[0] if args else "unknown")
            tracker.track_grounding_call(tool_func.name, query)
            return original_run(*args, **kwargs)

        tracked_tool.name = tool_func.name
        tracked_tool.description = tool_func.description
        tracked_grounding.append(tracked_tool)

    return tracked_serper + tracked_grounding


async def test_case_1_nepotisme_articles(logger, tracker):
    """
    Test Case 1: "Carilah artikel tentang budaya nepotisme"
    Expected: Should use Serper search to find recent articles
    """
    logger.log("Test 1", "Starting: Nepotisme Articles Search")

    user_message = "Carilah artikel tentang budaya nepotisme"
    logger.log("Test 1", f"User message: {user_message}")

    # Set up test environment
    os.environ["SERPER_API_KEY"] = os.environ.get("SERPER_API_KEY", "test-key")
    os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "test-key")

    try:
        # Track the intent detection
        from server.chatbot import chat

        # Mock conversation history
        conversation_history = []

        result = await chat(
            user_message=user_message,
            groq_api_key="test-key",
            user_id="test-user",
            conversation_history=conversation_history,
            auto_execute=True,
        )

        logger.log(
            "Test 1",
            "Chat response received",
            {
                "type": result.get("type"),
                "intent": result.get("intent"),
                "message_length": len(result.get("message", "")),
            },
        )

        # Check if search tools were used appropriately
        expected_behavior = "Should use Serper search for recent articles"
        actual_behavior = (
            "Direct AI response"
            if result.get("intent", {}).get("action") == "direct_gemini"
            else "Agent with tools"
        )

        logger.log("Test 1", f"Expected: {expected_behavior}")
        logger.log("Test 1", f"Actual: {actual_behavior}")

        # Extract tool usage from response if available
        if "tool_calls" in str(result):
            logger.log("Test 1", "Tool usage detected in response")

        return {
            "test": "nepotisme_articles",
            "expected": "serper_search",
            "actual": actual_behavior,
            "success": actual_behavior
            != "Direct AI response",  # Should NOT be direct AI only
            "response": result.get("message", "")[:500] + "..."
            if len(result.get("message", "")) > 500
            else result.get("message", ""),
        }

    except Exception as e:
        logger.log("Test 1", f"Error occurred: {str(e)}")
        return {
            "test": "nepotisme_articles",
            "expected": "serper_search",
            "actual": "error",
            "success": False,
            "error": str(e),
        }


async def test_case_2_nepotisme_definition(logger, tracker):
    """
    Test Case 2: "Apa itu Nepotisme?"
    Expected: Should use direct AI response for general concept
    """
    logger.log("Test 2", "Starting: Nepotisme Definition")

    user_message = "Apa itu Nepotisme?"
    logger.log("Test 2", f"User message: {user_message}")

    try:
        from server.chatbot import chat

        conversation_history = []

        result = await chat(
            user_message=user_message,
            groq_api_key="test-key",
            user_id="test-user",
            conversation_history=conversation_history,
            auto_execute=True,
        )

        logger.log(
            "Test 2",
            "Chat response received",
            {
                "type": result.get("type"),
                "intent": result.get("intent"),
                "message_length": len(result.get("message", "")),
            },
        )

        # Check decision making
        expected_behavior = "Direct AI response for general concept"
        actual_behavior = (
            "Direct AI response"
            if result.get("intent", {}).get("action") == "direct_gemini"
            else "Agent with tools"
        )

        logger.log("Test 2", f"Expected: {expected_behavior}")
        logger.log("Test 2", f"Actual: {actual_behavior}")

        # Analyze response content quality
        response_content = result.get("message", "")
        has_definition_keywords = any(
            keyword in response_content.lower()
            for keyword in ["definisi", "adalah", "merupakan", "pengertian"]
        )

        logger.log(
            "Test 2",
            "Response analysis",
            {
                "has_definition_keywords": has_definition_keywords,
                "response_length": len(response_content),
            },
        )

        return {
            "test": "nepotisme_definition",
            "expected": "direct_ai",
            "actual": actual_behavior,
            "success": result.get("intent", {}).get("action") == "direct_gemini",
            "response": response_content[:500] + "..."
            if len(response_content) > 500
            else response_content,
            "has_definition_content": has_definition_keywords,
        }

    except Exception as e:
        logger.log("Test 2", f"Error occurred: {str(e)}")
        return {
            "test": "nepotisme_definition",
            "expected": "direct_ai",
            "actual": "error",
            "success": False,
            "error": str(e),
        }


def analyze_intent_detection_logic():
    """Analyze the intent detection logic in chatbot.py"""
    logger.log("Analysis", "Analyzing intent detection logic")

    # Check tool keywords from the chatbot file
    tool_keywords = [
        r"\b(pdf|lampiran|kirim|email|draft|generate|buat file|download|search|cari|extract|visit|web|ringkasan|summary|laporan|report|attach)\b",
        r"\b(prabowo|jokowi|politik|politician|presiden|menteri|quotes|kutipan|statement|pernyataan|isu|issue|kebijakan|policy|kampanye|campaign|twitter|x\.com|instagram|social media)\b",
        r"\b(post|share|upload|twitter|x\.com|facebook|fb|instagram|ig|social media|media sosial|posting|unggah|bagikan)\b",
        r"\b(analisis|analysis|research|investigate|investigasi|fakta|fact check|verifikasi|verify|bandingkan|compare|sejarah|history|timeline|data|statistik)\b",
        r"\b(dokumen|document|file|word|excel|csv|presentasi|presentation|slide|export|save|simpan|arsip|archive)\b",
    ]

    test_cases = [
        ("Carilah artikel tentang budaya nepotisme", ["cari", "search", "analisis"]),
        ("Apa itu Nepotisme?", []),
        ("Prabowo quotes 2024", ["prabowo", "quotes"]),
        ("Buat PDF report", ["pdf", "buat file", "report"]),
        ("Kirim ke email", ["kirim", "email"]),
    ]

    intent_analysis = {}

    for message, expected_matches in test_cases:
        message_lower = message.lower()
        matched_keywords = []

        for pattern in tool_keywords:
            import re

            if re.search(pattern, message_lower, re.IGNORECASE):
                matched_keywords.append(pattern)

        tool_intent = len(matched_keywords) > 0
        intent_analysis[message] = {
            "matched_keywords": matched_keywords,
            "tool_intent": tool_intent,
            "expected_tool_intent": len(expected_matches) > 0,
            "decision_correct": tool_intent == (len(expected_matches) > 0),
        }

    logger.log("Analysis", "Intent detection results", intent_analysis)
    return intent_analysis


async def main():
    """Main test runner"""
    print("🚀 Starting Test 2: Agent Decision-Making Test")
    print("=" * 60)

    logger = TestLogger()
    tracker = SearchToolTracker()

    # Analyze intent detection logic first
    logger.log("Setup", "Analyzing intent detection logic")
    intent_analysis = analyze_intent_detection_logic()

    # Run test cases
    logger.log("Setup", "Running test cases")

    try:
        result1 = await test_case_1_nepotisme_articles(logger, tracker)
        result2 = await test_case_2_nepotisme_definition(logger, tracker)
    except Exception as e:
        logger.log("Error", f"Test execution failed: {str(e)}")
        return

    # Print comprehensive results
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)

    print(f"\n🔍 INTENT ANALYSIS:")
    for message, analysis in intent_analysis.items():
        status = "✅" if analysis["decision_correct"] else "❌"
        print(f"   {status} '{message}'")
        print(f"      Tool intent: {analysis['tool_intent']}")
        print(f"      Decision correct: {analysis['decision_correct']}")

    print(f"\n📈 TEST CASE RESULTS:")

    print(f"\n1️⃣ Test 1: Nepotisme Articles")
    print(f"   Expected: {result1['expected']}")
    print(f"   Actual: {result1['actual']}")
    print(f"   Success: {'✅' if result1['success'] else '❌'}")
    if not result1["success"] and "error" in result1:
        print(f"   Error: {result1['error']}")
    else:
        print(f"   Response preview: {result1.get('response', 'N/A')[:100]}...")

    print(f"\n2️⃣ Test 2: Nepotisme Definition")
    print(f"   Expected: {result2['expected']}")
    print(f"   Actual: {result2['actual']}")
    print(f"   Success: {'✅' if result2['success'] else '❌'}")
    if not result2["success"] and "error" in result2:
        print(f"   Error: {result2['error']}")
    else:
        print(f"   Response preview: {result2.get('response', 'N/A')[:100]}...")
        if "has_definition_content" in result2:
            print(
                f"   Has definition: {'✅' if result2['has_definition_content'] else '❌'}"
            )

    print(f"\n📋 SUMMARY:")
    total_tests = 2
    passed_tests = sum(1 for r in [result1, result2] if r.get("success", False))
    intent_correct = sum(1 for a in intent_analysis.values() if a["decision_correct"])

    print(f"   Total tests: {total_tests}")
    print(f"   Passed: {passed_tests}/{total_tests}")
    print(f"   Intent detection accuracy: {intent_correct}/{len(intent_analysis)}")

    if passed_tests == total_tests and intent_correct == len(intent_analysis):
        print(f"\n🎉 ALL TESTS PASSED! Agent decision-making is working correctly.")
    else:
        print(f"\n⚠️  Some tests failed. Review the implementation.")

    # Print tool usage tracking
    print(f"\n🔧 TOOL USAGE TRACKING:")
    print(f"   Serper calls: {len(tracker.serper_calls)}")
    print(f"   Grounding calls: {len(tracker.grounding_calls)}")
    print(f"   AI-only calls: {len(tracker.ai_only_calls)}")

    # Print detailed logs if needed
    if logger.logs:
        print(f"\n📝 DETAILED LOGS:")
        for log in logger.logs:
            print(f"   [{log['test']}] {log['message']}")


if __name__ == "__main__":
    asyncio.run(main())

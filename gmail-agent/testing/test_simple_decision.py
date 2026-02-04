#!/usr/bin/env python3
"""
Simplified Decision Making Test
Test intent detection logic without running the full agent
"""

import re


def analyze_intent_detection_logic():
    """Analyze the intent detection logic from chatbot.py"""

    # Tool keywords from chatbot.py lines 1194-1204
    tool_keywords = [
        r"\b(pdf|lampiran|kirim|email|draft|generate|buat file|download|search|cari|extract|visit|web|ringkasan|summary|laporan|report|attach)\b",
        r"\b(prabowo|jokowi|politik|politician|presiden|menteri|quotes|kutipan|statement|pernyataan|isu|issue|kebijakan|policy|kampanye|campaign|twitter|x\.com|instagram|social media)\b",
        r"\b(post|share|upload|twitter|x\.com|facebook|fb|instagram|ig|social media|media sosial|posting|unggah|bagikan)\b",
        r"\b(analisis|analysis|research|investigate|investigasi|fakta|fact check|verifikasi|verify|bandingkan|compare|sejarah|history|timeline|data|statistik)\b",
        r"\b(dokumen|document|file|word|excel|csv|presentasi|presentation|slide|export|save|simpan|arsip|archive)\b",
    ]

    test_cases = [
        # Test Case 1: Should use Serper (recent articles search)
        {
            "message": "Carilah artikel tentang budaya nepotisme",
            "expected_tool_intent": True,
            "reason": "Contains 'cari' keyword - should trigger search tools",
        },
        # Test Case 2: Should use direct AI (general concept)
        {
            "message": "Apa itu Nepotisme?",
            "expected_tool_intent": False,
            "reason": "No tool keywords - should use direct AI response",
        },
        # Additional test cases
        {
            "message": "Prabowo quotes 2024",
            "expected_tool_intent": True,
            "reason": "Contains 'prabowo' and 'quotes' - political research",
        },
        {
            "message": "Buat PDF report",
            "expected_tool_intent": True,
            "reason": "Contains 'pdf' and 'report' - document generation",
        },
        {
            "message": "Kirim ke email",
            "expected_tool_intent": True,
            "reason": "Contains 'kirim' and 'email' - email action",
        },
        {
            "message": "Apa itu demokrasi?",
            "expected_tool_intent": False,
            "reason": "General knowledge concept - no tool keywords",
        },
        {
            "message": "Latest news about Indonesia",
            "expected_tool_intent": True,
            "reason": "Contains 'latest' - should trigger search (but not in current regex)",
        },
        {
            "message": "Jelaskan fotosintesis",
            "expected_tool_intent": False,
            "reason": "General scientific concept - no tool keywords",
        },
    ]

    results = []

    print("🔍 ANALYZING INTENT DETECTION LOGIC")
    print("=" * 60)

    for i, test_case in enumerate(test_cases, 1):
        message = test_case["message"]
        expected = test_case["expected_tool_intent"]
        reason = test_case["reason"]

        # Test intent detection
        message_lower = message.lower()
        matched_keywords = []

        for pattern in tool_keywords:
            if re.search(pattern, message_lower, re.IGNORECASE):
                matched_keywords.append(pattern)

        actual_tool_intent = len(matched_keywords) > 0
        decision_correct = actual_tool_intent == expected

        result = {
            "test_num": i,
            "message": message,
            "expected_tool_intent": expected,
            "actual_tool_intent": actual_tool_intent,
            "matched_keywords": matched_keywords,
            "decision_correct": decision_correct,
            "reason": reason,
        }

        results.append(result)

        # Print result
        status = "✅" if decision_correct else "❌"
        print(f"\n{i}. {status} '{message}'")
        print(f"   Expected: {'Tool' if expected else 'Direct AI'}")
        print(f"   Actual: {'Tool' if actual_tool_intent else 'Direct AI'}")
        print(f"   Matched keywords: {len(matched_keywords)} patterns")
        print(f"   Reason: {reason}")

        if not decision_correct:
            print(f"   ⚠️  ISSUE: Expected {expected} but got {actual_tool_intent}")
            if matched_keywords:
                print(f"   Matched patterns: {matched_keywords}")

    # Summary
    print(f"\n📊 SUMMARY")
    print("=" * 60)

    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["decision_correct"])
    accuracy = (passed_tests / total_tests) * 100

    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Accuracy: {accuracy:.1f}%")

    # Failed tests analysis
    failed_tests = [r for r in results if not r["decision_correct"]]
    if failed_tests:
        print(f"\n❌ FAILED TESTS ANALYSIS:")
        for test in failed_tests:
            print(f"   '{test['message']}'")
            print(
                f"   Expected: {test['expected_tool_intent']}, Got: {test['actual_tool_intent']}"
            )
            print(f"   Reason: {test['reason']}")

    # Recommendations for improvement
    print(f"\n💡 RECOMMENDATIONS:")

    # Check for specific issues
    temporal_keywords = [
        "latest",
        "recent",
        "current",
        "breaking",
        "today",
        "yesterday",
    ]
    temporal_missing = any(
        any(keyword in test["message"].lower() for keyword in temporal_keywords)
        and not test["decision_correct"]
        for test in results
    )

    if temporal_missing:
        print(
            "   • Add temporal keywords to tool patterns (latest, recent, current, etc.)"
        )

    general_questions = [
        test
        for test in results
        if not test["expected_tool_intent"] and not test["decision_correct"]
    ]
    if general_questions:
        print("   • Improve patterns to better distinguish general vs specific queries")

    print("   • Consider context-aware detection (conversation history)")
    print("   • Add semantic analysis beyond keyword matching")

    return results


def suggest_improved_keywords():
    """Suggest improved keyword patterns"""

    print(f"\n🔧 SUGGESTED IMPROVED KEYWORD PATTERNS:")
    print("=" * 60)

    improved_patterns = {
        "Temporal/Current Events": r"\b(latest|recent|current|breaking|today|yesterday|news|sekarang|terkini|baru|hari ini|kemarin|berita)\b",
        "Document Generation": r"\b(pdf|lampiran|kirim|email|draft|generate|buat file|download|ringkasan|summary|laporan|report|attach|dokumen|document|file|presentasi|presentation|slide)\b",
        "Search & Research": r"\b(search|cari|extract|visit|web|analisis|analysis|research|investigate|investigasi|fakta|fact check|verifikasi|verify|bandingkan|compare|sejarah|history|timeline|data|statistik)\b",
        "Political/Current Events": r"\b(prabowo|jokowi|politik|politician|presiden|menteri|quotes|kutipan|statement|pernyataan|isu|issue|kebijakan|policy|kampanye|campaign|twitter|x\.com|instagram|social media)\b",
        "Social Media Actions": r"\b(post|share|upload|twitter|x\.com|facebook|fb|instagram|ig|social media|media sosial|posting|unggah|bagikan)\b",
        "General Question Indicators": r"\b(apa itu|apa yang|bagaimana|kenapa|mengapa|jelaskan|definisi|pengertian|arti|makna)\b",
    }

    for category, pattern in improved_patterns.items():
        print(f"\n{category}:")
        print(f"   {pattern}")

    print(f"\n📝 SUGGESTED DECISION LOGIC:")
    print("=" * 60)
    print("""
1. PRIMARY CHECK - Temporal/Current Keywords:
   If matches → Use Search Tools (Serper/Grounding)
   
2. SECONDARY CHECK - Tool-Specific Keywords:
   If matches → Use Agent with Tools
   
3. CONTEXT CHECK - Question Type:
   If general question indicators AND no temporal keywords → Direct AI
   
4. FALLBACK - Research Context:
   If conversation history suggests ongoing research → Agent with Tools
""")


if __name__ == "__main__":
    print("🚀 Starting Simplified Decision Making Test")
    print("=" * 60)

    results = analyze_intent_detection_logic()
    suggest_improved_keywords()

    print(f"\n🎯 CONCLUSION:")
    print("=" * 60)

    passed = sum(1 for r in results if r["decision_correct"])
    total = len(results)

    if passed == total:
        print("✅ All intent detection tests passed!")
        print(
            "   The agent should make correct decisions between search tools and AI response."
        )
    else:
        print("⚠️  Some intent detection tests failed.")
        print("   The agent may make incorrect decisions in certain scenarios.")
        print("   Consider implementing the suggested improvements.")

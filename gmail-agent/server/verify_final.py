
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from server.agents import create_default_registry
    from server.tools import get_all_tools

    print("--- Verifying Agent Registry ---")
    registry = create_default_registry()
    agents = registry.get_all_agents()
    print(f"Registered agents: {[a.name for a in agents]}")
    
    expected_agents = ["gipa", "dossier", "email_analyst", "pdf", "research", "social_media", "gmail", "linkedin", "quote", "strategy"]
    missing_agents = [a for a in expected_agents if a not in [ag.name for ag in agents]]
    if missing_agents:
        print(f"❌ Missing agents: {missing_agents}")
    else:
        print("✅ All expected agents are registered.")

    print("\n--- Verifying Tool Aggregation ---")
    # Set dummy API keys for verification
    os.environ["COMPOSIO_API_KEY"] = "dummy"
    os.environ["SERPER_API_KEY"] = "dummy"
    os.environ["GOOGLE_API_KEY"] = "dummy"
    os.environ["OPENAI_API_KEY"] = "dummy"
    
    tools = get_all_tools(user_id="test_user")
    print(f"Total tools aggregated: {len(tools)}")
    tool_names = [t.name for t in tools]
    print(f"Sample tool names: {tool_names[:10]}...")

    # Check for some essential tools
    essential_tools = ["generate_pdf_report_tool", "search_web", "post_to_twitter", "gmail_send_email", "linkedin_post", "generate_quote_image", "analyze_strategy"]
    missing_tools = [t for t in essential_tools if t not in tool_names]
    if missing_tools:
        print(f"❌ Missing essential tools: {missing_tools}")
    else:
        print("✅ All essential tools are present in aggregation.")

    print("\n--- Verification Successful ---")

except Exception as e:
    print(f"\n❌ Verification failed with error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

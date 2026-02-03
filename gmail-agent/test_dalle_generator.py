#!/usr/bin/env python3
"""
Standalone Test Script for DALL-E Political Quote Image Generator
Run this to test generating 1 image and sending to developerlana0@gmail.com
"""

import os
import sys

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.tools.dalle_quote_generator import test_generate_and_send_email

if __name__ == "__main__":
    print("=" * 70)
    print("🎨 DALL-E Political Quote Image Generator - Test")
    print("=" * 70)
    print("\n📋 Configuration:")
    print("   Sender: firdaussyah03@gmail.com")
    print("   Recipient: developerlana0@gmail.com")
    print("   Model: DALL-E 3 (1024x1024)")
    print("   Style: Digital Art")
    print("\n" + "=" * 70)

    # Check environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n❌ Error: OPENAI_API_KEY not set!")
        print("   Please set your OpenAI API key:")
        print("   export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    if not os.environ.get("COMPOSIO_API_KEY"):
        print("\n❌ Error: COMPOSIO_API_KEY not set!")
        print("   Please set your Composio API key:")
        print("   export COMPOSIO_API_KEY='your-key'")
        sys.exit(1)

    print("\n✅ Environment variables found!")
    print("🚀 Starting test...\n")

    # Run the test
    test_generate_and_send_email()

    print("\n" + "=" * 70)
    print("✅ Test completed!")
    print("=" * 70)

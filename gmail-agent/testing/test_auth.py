#!/usr/bin/env python3
"""
Test script for Social Media Authentication
Run this to verify your authentication setup.
"""

import os
import sys
from composio import Composio

def test_authentication():
    """Test social media authentication setup."""
    
    # Load API key
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        print("❌ COMPOSIO_API_KEY not found in environment")
        sys.exit(1)
    
    print("✅ COMPOSIO_API_KEY found")
    print()
    
    # Initialize client
    try:
        client = Composio(api_key=api_key)
        print("✅ Composio client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Composio client: {e}")
        sys.exit(1)
    
    print()
    
    # Test user
    user_id = "default"
    required_toolkits = ["twitter", "facebook", "instagram"]
    
    print(f"Testing authentication for user: {user_id}")
    print(f"Required toolkits: {', '.join(required_toolkits)}")
    print()
    
    # Create session
    try:
        session = client.create(
            user_id=user_id,
            toolkits=required_toolkits
        )
        print("✅ Session created")
    except Exception as e:
        print(f"❌ Failed to create session: {e}")
        sys.exit(1)
    
    print()
    
    # Check toolkit status
    print("=" * 60)
    print("TOOLKIT CONNECTION STATUS")
    print("=" * 60)
    
    try:
        toolkit_status = session.toolkits()
        
        all_connected = True
        pending_toolkits = []
        
        for toolkit in toolkit_status.items:
            is_connected = (
                toolkit.connection 
                and hasattr(toolkit.connection, 'is_active') 
                and toolkit.connection.is_active
            )
            
            status_icon = "✅" if is_connected else "❌"
            status_text = "CONNECTED" if is_connected else "NOT CONNECTED"
            
            print(f"{status_icon} {toolkit.name.upper()}: {status_text}")
            
            if is_connected and toolkit.connection.connected_account:
                print(f"   Connection ID: {toolkit.connection.connected_account.id}")
            
            if not is_connected:
                all_connected = False
                pending_toolkits.append(toolkit.slug)
        
        print()
        
        if all_connected:
            print("🎉 All toolkits are connected! You're ready to go.")
            print()
            
            # Test tools fetch
            print("=" * 60)
            print("AVAILABLE TOOLS")
            print("=" * 60)
            
            tools = session.tools()
            print(f"Total tools loaded: {len(tools)}")
            print()
            print("Sample tools:")
            for i, tool in enumerate(tools[:10]):
                tool_name = "unknown"
                if hasattr(tool, 'name'):
                    tool_name = tool.name
                elif hasattr(tool, 'function') and isinstance(tool.function, dict):
                    tool_name = tool.function.get('name', 'unknown')
                elif isinstance(tool, dict) and 'function' in tool:
                    tool_name = tool['function'].get('name', 'unknown')
                
                print(f"  {i+1}. {tool_name}")
            
            if len(tools) > 10:
                print(f"  ... and {len(tools) - 10} more")
            
        else:
            print("⚠️  Some toolkits are not connected.")
            print()
            print("To connect pending toolkits, you need to:")
            print()
            
            for toolkit_slug in pending_toolkits:
                print(f"1. Authorize {toolkit_slug}:")
                
                try:
                    connection_request = session.authorize(toolkit_slug)
                    print(f"   🔗 Open this URL: {connection_request.redirect_url}")
                    print()
                except Exception as e:
                    print(f"   ❌ Failed to get auth URL: {e}")
                    print()
            
            print("OR use the API endpoints:")
            print(f"   POST http://localhost:8000/toolkits/{user_id}/authorize/twitter")
            print(f"   POST http://localhost:8000/toolkits/{user_id}/authorize/facebook")
            print(f"   POST http://localhost:8000/toolkits/{user_id}/authorize/instagram")
        
    except Exception as e:
        print(f"❌ Failed to check toolkit status: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_authentication()

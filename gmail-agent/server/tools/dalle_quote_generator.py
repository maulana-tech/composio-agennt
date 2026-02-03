"""
OpenAI DALL-E Image Generator for Political Quotes
Extension of pdf_generator.py with DALL-E support
Can be used as a LangChain tool for AI agents
"""

import os
import openai
from typing import Optional
from pathlib import Path
from datetime import datetime
import requests
from langchain.tools import tool


def generate_quote_image_dalle(
    quote_text: str,
    author: str,
    context: str = "",
    style: str = "digital art",
    api_key: str = None,
    output_path: str = None,
) -> Optional[str]:
    """
    Generate an AI image for a political quote using OpenAI DALL-E.

    Args:
        quote_text: The quote text (will be truncated if too long)
        author: Name of the politician
        context: Additional context about the quote
        style: Image style (digital art, photorealistic, watercolor, etc.)
        api_key: OpenAI API key (or uses OPENAI_API_KEY env var)
        output_path: Where to save the image (auto-generated if None)

    Returns:
        Path to the generated image file, or None if failed
    """
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        return None

    try:
        client = openai.OpenAI(api_key=api_key)

        # Create clean, minimalist prompt focused on readable typography
        prompt = f"""Create a clean, minimalist quote graphic.

THE EXACT QUOTE TO DISPLAY:
"{quote_text[:150]}"

— {author}

CRITICAL DESIGN RULES:
1. TYPOGRAPHY IS THE ONLY FOCUS - the quote text must be 100% readable and spelled correctly
2. Use LARGE, BOLD, CLEAN sans-serif typography like Helvetica or Arial
3. WHITE or very light colored text on a SIMPLE dark solid background
4. Background: Single solid color - deep navy blue (#1a1a2e) or dark charcoal (#2d2d2d)
5. NO decorative elements, NO icons, NO patterns, NO geometric shapes
6. NO borders, NO frames, NO lines
7. Just the quote centered on a plain dark background
8. The author name should be smaller, positioned below the quote
9. Generous spacing around the text
10. Style: {style}

This should look like a simple PowerPoint slide with just text - nothing else. Clean and professional."""

        print(f"🎨 Generating DALL-E image for quote by {author}...")

        # Generate image with DALL-E 3 in landscape format
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",  # Landscape format
            quality="standard",
            n=1,
        )

        # Get image URL
        image_url = response.data[0].url

        # Download image
        print(f"⬇️  Downloading generated image...")
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()

        # Save to attachment folder if no output_path specified
        if not output_path:
            attachment_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "attachment"
            )
            os.makedirs(attachment_dir, exist_ok=True)
            
            safe_author = author.lower().replace(' ', '_')[:15]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dalle_quote_{safe_author}_{timestamp}.png"
            output_path = os.path.join(attachment_dir, filename)

        # Save to file
        with open(output_path, 'wb') as f:
            f.write(img_response.content)

        print(f"✅ Image saved: {output_path}")
        return output_path

    except openai.APIError as e:
        print(f"❌ OpenAI API Error: {e}")
        return None
    except requests.RequestException as e:
        print(f"❌ Network Error downloading image: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return None


def test_generate_and_send_email():
    """
    Test function: Generate 1 political quote image and send to developerlana0@gmail.com
    Uses firdaussyah03@gmail.com as sender.
    """
    print("\n" + "=" * 60)
    print("🧪 TEST: Generate Political Quote Image with DALL-E")
    print("=" * 60)

    # Test quote - Prabowo on defense modernization (English)
    test_quote = "We are committed to building a strong and modern defense system to protect our nation's sovereignty and ensure long-term security for all citizens."
    test_author = "Prabowo Subianto"
    test_context = "Presidential Address on National Defense Policy, January 2025"

    # Generate image
    print(f'\n📝 Quote: "{test_quote}"')
    print(f"👤 Author: {test_author}")
    print(f"📅 Context: {test_context}")

    image_path = generate_quote_image_dalle(
        quote_text=test_quote,
        author=test_author,
        context=test_context,
        style="digital art",
    )

    if not image_path:
        print("\n❌ Failed to generate image. Aborting email send.")
        return

    print(f"\n📧 Preparing to send email...")

    # Email configuration
    sender_email = "firdaussyah03@gmail.com"
    recipient_email = "developerlana0@gmail.com"
    subject = f"🎨 AI-Generated Quote Image: {test_author}"

    # Email body with formatted content
    body = f"""Dear Developer,

Berikut adalah hasil generate gambar AI untuk quote politik menggunakan DALL-E:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 QUOTE DETAILS

Author: {test_author}
Context: {test_context}
Generated: {datetime.now().strftime("%B %d, %Y at %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 THE QUOTE

"{test_quote}"

— {test_author} ({test_context})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🖼️ IMAGE ATTACHMENT

Lihat file terlampir untuk visualisasi AI dari quote di atas.
Gambar dihasilkan menggunakan OpenAI DALL-E 3 dengan style digital art.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Terima kasih,
AI Quote Generator System
Powered by OpenAI DALL-E 3
"""

    # Send email
    try:
        from composio import Composio

        print(f"📤 Sending email from {sender_email} to {recipient_email}...")

        composio_client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

        result = composio_client.tools.execute(
            slug="GMAIL_SEND_EMAIL",
            arguments={
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "attachment": image_path,
                "is_html": False,
            },
            user_id="firdaussyah03@gmail.com",
            dangerously_skip_version_check=True,
        )

        print(f"\n✅ SUCCESS! Email sent to {recipient_email}")
        print(f"📎 Attachment: {os.path.basename(image_path)}")
        print(f"📊 Result: {result}")

        # Cleanup
        try:
            os.remove(image_path)
            print(f"🧹 Cleaned up temporary image file")
        except:
            pass

    except Exception as e:
        print(f"\n❌ Failed to send email: {e}")
        print(f"💡 Image saved at: {image_path} (not deleted due to error)")


# ============================================================
# LangChain Tool for Agent Integration
# ============================================================

@tool
def generate_dalle_quote_image_tool(
    quote_text: str,
    author: str,
    context: str = "",
    style: str = "digital art",
) -> str:
    """
    Generate a quote image using OpenAI DALL-E 3.
    Use this for AI-generated artistic quote graphics. Note: DALL-E may have imperfect text rendering.
    For 100% accurate text, use generate_quote_image_tool (Pillow-based) instead.
    
    Args:
        quote_text: The quote text to display (max ~150 characters for best results)
        author: Name of the person who said the quote
        context: Optional context like "Presidential Speech, 2025"
        style: Image style - "digital art", "photorealistic", "watercolor", etc.
    
    Returns:
        Absolute path to the generated PNG image file
    """
    result = generate_quote_image_dalle(
        quote_text=quote_text,
        author=author,
        context=context,
        style=style,
    )
    
    if result:
        return f"DALL-E quote image generated successfully: {result}"
    else:
        return "Failed to generate DALL-E quote image. Check if OPENAI_API_KEY is set."


if __name__ == "__main__":
    # Run test
    test_generate_and_send_email()

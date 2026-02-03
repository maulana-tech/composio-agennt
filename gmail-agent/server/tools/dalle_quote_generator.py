"""
OpenAI DALL-E Image Generator for Political Quotes
Extension of pdf_generator.py with DALL-E support
"""

import os
import openai
from typing import Optional
from pathlib import Path
from datetime import datetime
import requests
import tempfile


def generate_quote_image_dalle(
    quote_text: str,
    author: str,
    context: str = "",
    style: str = "digital art",
    api_key: str = None,
) -> Optional[str]:
    """
    Generate an AI image for a political quote using OpenAI DALL-E.

    Args:
        quote_text: The quote text (will be truncated if too long)
        author: Name of the politician
        context: Additional context about the quote
        style: Image style (digital art, photorealistic, watercolor, etc.)
        api_key: OpenAI API key (or uses OPENAI_API_KEY env var)

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

        # Create professional prompt for political quote visualization
        prompt = f"""Create a professional, elegant visual quote image for:

QUOTE: "{quote_text[:200]}"

AUTHOR: {author}
CONTEXT: {context if context else "Political statement"}

DESIGN REQUIREMENTS:
- Style: {style} with professional, modern aesthetic
- Background: Subtle gradient using Indonesian national colors (red and white) or professional navy blue
- Typography: Clean, readable font showing the quote prominently
- Layout: Balanced composition with quote text as focal point
- Author name: Displayed elegantly at bottom
- Mood: Inspiring, authoritative, presidential
- Quality: High resolution, suitable for professional reports and presentations
- No clutter, minimalist design, focus on the message
- Add subtle decorative elements like geometric patterns or soft light effects

Make it look like a professional social media graphic or presentation slide."""

        print(f"🎨 Generating DALL-E image for quote by {author}...")

        # Generate image with DALL-E 3
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        # Get image URL
        image_url = response.data[0].url

        # Download image
        print(f"⬇️  Downloading generated image...")
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()

        # Save to file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".png",
            prefix=f"quote_{author.lower().replace(' ', '_')}_",
        )
        temp_file.write(img_response.content)
        temp_file.close()

        print(f"✅ Image saved: {temp_file.name}")
        return temp_file.name

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

    # Test quote - Prabowo on defense policy
    test_quote = "Kita akan membangun pertahanan yang kuat untuk melindungi kedaulatan dan keamanan bangsa."
    test_author = "Prabowo Subianto"
    test_context = "Defense Policy Statement 2024"

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


if __name__ == "__main__":
    # Run test
    test_generate_and_send_email()

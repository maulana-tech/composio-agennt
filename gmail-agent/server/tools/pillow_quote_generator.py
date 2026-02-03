"""
Pillow-based Quote Image Generator
Generates professional quote images with 100% accurate text (no AI typos)
Can be used as a LangChain tool for AI agents
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from langchain.tools import tool
import textwrap


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a clean sans-serif font. Falls back to default if not available."""
    font_paths = [
        # macOS fonts
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        # Linux fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    
    if bold:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ] + font_paths
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    
    # Fallback to default
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list:
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines


def generate_quote_image(
    quote_text: str,
    author: str,
    context: str = "",
    output_path: Optional[str] = None,
    width: int = 1792,
    height: int = 1024,
    bg_color: Tuple[int, int, int] = (26, 26, 46),  # Dark navy
    text_color: Tuple[int, int, int] = (255, 255, 255),  # White
    accent_color: Tuple[int, int, int] = (100, 149, 237),  # Cornflower blue
) -> Optional[str]:
    """
    Generate a professional quote image with Pillow.
    
    Args:
        quote_text: The quote to display
        author: Author name
        context: Optional context (e.g., "Presidential Address, 2025")
        output_path: Where to save the image (auto-generated if None)
        width: Image width in pixels
        height: Image height in pixels
        bg_color: Background color RGB tuple
        text_color: Text color RGB tuple
        accent_color: Accent color for decorative elements
    
    Returns:
        Path to the generated image, or None if failed
    """
    try:
        # Create image
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Calculate margins and text area
        margin_x = int(width * 0.1)  # 10% margin
        margin_y = int(height * 0.15)  # 15% margin
        text_area_width = width - (2 * margin_x)
        
        # Get fonts
        quote_font_size = 56
        author_font_size = 32
        context_font_size = 24
        
        quote_font = get_font(quote_font_size, bold=True)
        author_font = get_font(author_font_size, bold=False)
        context_font = get_font(context_font_size, bold=False)
        
        # Wrap quote text
        quote_lines = wrap_text(quote_text, quote_font, text_area_width, draw)
        
        # Calculate total text height
        line_spacing = 1.4
        quote_line_height = int(quote_font_size * line_spacing)
        total_quote_height = len(quote_lines) * quote_line_height
        
        author_height = author_font_size + 20
        context_height = context_font_size + 10 if context else 0
        
        total_text_height = total_quote_height + 60 + author_height + context_height
        
        # Starting Y position (centered vertically)
        start_y = (height - total_text_height) // 2
        
        # Draw opening quotation mark
        quote_mark_font = get_font(120, bold=True)
        draw.text(
            (margin_x - 30, start_y - 80),
            '"',
            font=quote_mark_font,
            fill=accent_color
        )
        
        # Draw quote text
        current_y = start_y
        for line in quote_lines:
            bbox = draw.textbbox((0, 0), line, font=quote_font)
            line_width = bbox[2] - bbox[0]
            x = (width - line_width) // 2  # Center each line
            draw.text((x, current_y), line, font=quote_font, fill=text_color)
            current_y += quote_line_height
        
        # Draw horizontal line separator
        line_y = current_y + 30
        line_width_px = 100
        line_start_x = (width - line_width_px) // 2
        draw.line(
            [(line_start_x, line_y), (line_start_x + line_width_px, line_y)],
            fill=accent_color,
            width=3
        )
        
        # Draw author name
        author_y = line_y + 30
        author_text = f"— {author}"
        bbox = draw.textbbox((0, 0), author_text, font=author_font)
        author_width = bbox[2] - bbox[0]
        author_x = (width - author_width) // 2
        draw.text((author_x, author_y), author_text, font=author_font, fill=text_color)
        
        # Draw context if provided
        if context:
            context_y = author_y + author_height
            bbox = draw.textbbox((0, 0), context, font=context_font)
            context_width = bbox[2] - bbox[0]
            context_x = (width - context_width) // 2
            # Slightly dimmer color for context
            context_color = tuple(int(c * 0.7) for c in text_color)
            draw.text((context_x, context_y), context, font=context_font, fill=context_color)
        
        # Generate output path if not provided
        if not output_path:
            import tempfile
            safe_author = author.lower().replace(' ', '_')[:20]
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.png',
                prefix=f'quote_{safe_author}_'
            )
            output_path = temp_file.name
            temp_file.close()
        
        # Save image
        img.save(output_path, 'PNG', quality=95)
        print(f"✅ Quote image saved: {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        return None


def test_quote_generator():
    """Test the quote image generator."""
    print("\n" + "=" * 60)
    print("🎨 Pillow Quote Image Generator - Test")
    print("=" * 60)
    
    # Test quote
    quote = "We are committed to building a strong and modern defense system to protect our nation's sovereignty and ensure long-term security for all citizens."
    author = "Prabowo Subianto"
    context = "Presidential Address on National Defense Policy, January 2025"
    
    print(f'\n📝 Quote: "{quote}"')
    print(f"👤 Author: {author}")
    print(f"📅 Context: {context}")
    print("\n🚀 Generating image...")
    
    # Save to attachment folder
    from datetime import datetime
    attachment_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "attachment"
    )
    os.makedirs(attachment_dir, exist_ok=True)
    
    safe_author = author.lower().replace(' ', '_')[:15]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quote_{safe_author}_{timestamp}.png"
    output_path = os.path.join(attachment_dir, filename)
    
    # Generate image
    result = generate_quote_image(
        quote_text=quote,
        author=author,
        context=context,
        output_path=output_path
    )
    
    if output_path:
        print(f"\n✅ SUCCESS!")
        print(f"📁 Image saved at: {output_path}")
        
        # Get file size
        size = os.path.getsize(output_path)
        print(f"📊 File size: {size / 1024:.1f} KB")
    else:
        print("\n❌ Failed to generate image")
    
    print("\n" + "=" * 60)
    return output_path


# ============================================================
# LangChain Tool for Agent Integration
# ============================================================

@tool
def generate_quote_image_tool(
    quote_text: str,
    author: str,
    context: str = "",
) -> str:
    """
    Generate a professional quote image with perfect text rendering.
    Use this tool when user asks to create a visual quote, quote poster, or quote graphic.
    Unlike AI image generators, this produces 100% accurate text with no typos.
    
    Args:
        quote_text: The quote text to display (max ~200 characters for best results)
        author: Name of the person who said the quote
        context: Optional context like "Presidential Speech, 2025" or "Interview with BBC"
    
    Returns:
        Absolute path to the generated PNG image file
    """
    # Use the attachment directory for consistent file location
    attachment_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "attachment"
    )
    os.makedirs(attachment_dir, exist_ok=True)
    
    # Generate unique filename
    from datetime import datetime
    safe_author = author.lower().replace(' ', '_')[:15]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quote_{safe_author}_{timestamp}.png"
    output_path = os.path.join(attachment_dir, filename)
    
    result = generate_quote_image(
        quote_text=quote_text,
        author=author,
        context=context,
        output_path=output_path
    )
    
    if result:
        return f"Quote image generated successfully: {result}"
    else:
        return "Failed to generate quote image"


@tool
def generate_and_send_quote_email(
    quote_text: str,
    author: str,
    recipient_email: str,
    context: str = "",
    subject: str = "",
    additional_message: str = "",
) -> str:
    """
    Generate a professional quote image and send it via email as an attachment.
    This combines quote image generation with email sending in one step.
    
    Args:
        quote_text: The quote text to display
        author: Name of the person who said the quote
        recipient_email: Email address to send the quote image to
        context: Optional context like "Speech at UN, 2025"
        subject: Email subject (auto-generated if empty)
        additional_message: Additional message to include in email body
    
    Returns:
        Status message indicating success or failure
    """
    from datetime import datetime
    
    # Generate the quote image
    attachment_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "attachment"
    )
    os.makedirs(attachment_dir, exist_ok=True)
    
    safe_author = author.lower().replace(' ', '_')[:15]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quote_{safe_author}_{timestamp}.png"
    output_path = os.path.join(attachment_dir, filename)
    
    image_path = generate_quote_image(
        quote_text=quote_text,
        author=author,
        context=context,
        output_path=output_path
    )
    
    if not image_path:
        return "Failed to generate quote image"
    
    # Prepare email
    if not subject:
        subject = f"📜 Quote Image: {author}"
    
    body = f"""Dear Recipient,

Please find attached a professionally designed quote image.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 QUOTE DETAILS

Author: {author}
Context: {context if context else "N/A"}
Generated: {datetime.now().strftime("%B %d, %Y at %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 THE QUOTE

"{quote_text}"

— {author}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{additional_message if additional_message else ""}

Best regards,
AI Quote Generator
"""

    # Send via Composio
    try:
        from composio import Composio
        
        composio_api_key = os.environ.get("COMPOSIO_API_KEY")
        if not composio_api_key:
            return f"Quote image generated at {image_path}, but COMPOSIO_API_KEY not set for email sending"
        
        client = Composio(api_key=composio_api_key)
        
        result = client.tools.execute(
            slug="GMAIL_SEND_EMAIL",
            arguments={
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "attachment": image_path,
                "is_html": False,
            },
            user_id="default",
            dangerously_skip_version_check=True,
        )
        
        return f"✅ Quote image sent successfully to {recipient_email}! Image path: {image_path}"
        
    except Exception as e:
        return f"Quote image generated at {image_path}, but email sending failed: {str(e)}"


if __name__ == "__main__":
    test_quote_generator()


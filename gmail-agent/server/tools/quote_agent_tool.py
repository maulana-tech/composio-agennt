
"""
Quote Agent Tool
Consolidates all quote generation capabilities (Simple/Pillow, DALL-E, Avatar) into a single module.
"""

import os
import io
import requests
import textwrap
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path

# External Dependencies
try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
except ImportError:
    Image = None

try:
    import openai
except ImportError:
    openai = None

from langchain_core.tools import tool

# ============================================================================
# Shared Utilities
# ============================================================================

def get_font(size: int, bold: bool = False):
    """Get a clean sans-serif font. Falls back to default if not available."""
    if not Image:
        return None

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
    
    return ImageFont.load_default()

def wrap_text(text: str, font, max_width: int, draw) -> list:
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
        except AttributeError:
             # Fallback for older Pillow
             width = draw.textlength(test_line, font=font)

        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def _get_attachment_path(filename_prefix: str) -> str:
    """Helper to generate consistent output path."""
    attachment_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "attachment" # Assuming this file is in server/tools, go up to server/attachment? no, previous code went up 3 levels from tools/file?
        # Previous code: os.path.dirname(os.path.dirname(os.path.dirname(__file__))) -> attachment
        # New file is in server/tools/quote_agent_tool.py
        # __file__ dir is server/tools
        # up 1: server
        # up 2: gmail-agent (root)
        # attachment is in root?
        # Let's check previous code paths.
        # pillow: os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # File is server/tools/pillow_quote_generator.py
        # 1. tools, 2. server, 3. gmail-agent. Correct.
    )
    grand_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    attachment_dir = os.path.join(grand_parent, "attachment")
    
    # Force fix if path looks wrong (common issue in refactors)
    if not os.path.exists(os.path.dirname(attachment_dir)):
         # Try assuming cwd is project root
         attachment_dir = os.path.abspath("attachment")

    os.makedirs(attachment_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.png"
    return os.path.join(attachment_dir, filename)

def download_image(url: str):
    """Download an image from URL and return as PIL Image."""
    if not Image: return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        img = Image.open(io.BytesIO(response.content))
        return img.convert("RGB")
    except Exception as e:
        print(f"❌ Error downloading image: {e}")
        return None

def search_person_image(person_name: str, api_key: str = None) -> Optional[str]:
    """Search for a person's image using Serper API."""
    if not api_key:
        api_key = os.environ.get("SERPER_API_KEY")
    
    if not api_key:
        print("⚠️ SERPER_API_KEY not found, cannot search for images")
        return None
    
    try:
        url = "https://google.serper.dev/images"
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {"q": f"{person_name} official portrait photo", "num": 5}
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        images = data.get("images", [])
        
        if images:
            for img in images:
                img_url = img.get("imageUrl")
                if img_url:
                    return img_url
        return None
    except Exception as e:
        print(f"❌ Error searching for image: {e}")
        return None

# ============================================================================
# Logic: Simple Quote (Pillow)
# ============================================================================

def _generate_quote_simple(
    quote_text: str,
    author: str,
    context: str = "",
    bg_color: Tuple[int, int, int] = (26, 26, 46),
    text_color: Tuple[int, int, int] = (255, 255, 255),
    accent_color: Tuple[int, int, int] = (100, 149, 237),
) -> str:
    if not Image:
        raise ImportError("Pillow library not installed.")

    width, height = 1792, 1024
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    margin_x = int(width * 0.1)
    text_area_width = width - (2 * margin_x)
    
    quote_font = get_font(56, bold=True)
    author_font = get_font(32, bold=False)
    context_font = get_font(24, bold=False)
    
    quote_lines = wrap_text(quote_text, quote_font, text_area_width, draw)
    
    # Calculate heights (simplified)
    line_height = int(56 * 1.4)
    total_text_height = (len(quote_lines) * line_height) + 60 + 52 + (34 if context else 0)
    
    start_y = (height - total_text_height) // 2
    
    # Draw Quote Mark
    draw.text((margin_x - 30, start_y - 80), '"', font=get_font(120, bold=True), fill=accent_color)
    
    # Draw Text
    current_y = start_y
    for line in quote_lines:
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        line_w = bbox[2] - bbox[0]
        x = (width - line_w) // 2
        draw.text((x, current_y), line, font=quote_font, fill=text_color)
        current_y += line_height
        
    # Separator
    line_y = current_y + 30
    line_start = (width - 100) // 2
    draw.line([(line_start, line_y), (line_start + 100, line_y)], fill=accent_color, width=3)
    
    # Author
    author_y = line_y + 30
    author_text = f"— {author}"
    bbox = draw.textbbox((0, 0), author_text, font=author_font)
    author_w = bbox[2] - bbox[0]
    draw.text(((width - author_w) // 2, author_y), author_text, font=author_font, fill=text_color)
    
    # Context
    if context:
        context_y = author_y + 52
        bbox = draw.textbbox((0, 0), context, font=context_font)
        context_w = bbox[2] - bbox[0]
        c_color = tuple(int(c * 0.7) for c in text_color)
        draw.text(((width - context_w) // 2, context_y), context, font=context_font, fill=c_color)
        
    output_path = _get_attachment_path(f"quote_{author.lower().replace(' ', '_')[:15]}")
    img.save(output_path, 'PNG', quality=95)
    return output_path

# ============================================================================
# Logic: Avatar Quote
# ============================================================================

def _generate_quote_avatar(
    quote_text: str,
    person_name: str,
    context: str = "",
    width: int = 1792,
    height: int = 1024,
) -> Optional[str]:
    if not Image: return None
    
    # 1. Get Background
    img_url = search_person_image(person_name)
    bg_image = download_image(img_url) if img_url else None
    
    if bg_image:
        # Resize/Crop logic
        bg_ratio = bg_image.width / bg_image.height
        target_ratio = width / height
        if bg_ratio > target_ratio:
            new_h, new_w = height, int(height * bg_ratio)
        else:
            new_w, new_h = width, int(width / bg_ratio)
        
        bg_image = bg_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left, top = (new_w - width) // 2, (new_h - height) // 2
        bg_image = bg_image.crop((left, top, left + width, top + height))
        bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=3))
        
        overlay = Image.new('RGB', (width, height), (0, 0, 0))
        bg_image = Image.blend(bg_image, overlay, 0.6)
        img = bg_image
    else:
        img = Image.new('RGB', (width, height), (26, 26, 46))

    draw = ImageDraw.Draw(img)
    
    # Use logic similar to simple quote but with shadows
    quote_font = get_font(52, bold=True)
    author_font = get_font(28, bold=False)
    context_font = get_font(20, bold=False)
    
    margin_x = int(width * 0.08)
    text_width = width - (2 * margin_x)
    quote_lines = wrap_text(quote_text, quote_font, text_width, draw)
    
    line_height = int(52 * 1.4)
    total_h = (len(quote_lines) * line_height) + 60 + 48 + (30 if context else 0)
    start_y = (height - total_h) // 2
    
    # Helper to draw with shadow
    def draw_shadowed(x, y, text, font, color=(255,255,255)):
        draw.text((x+2, y+2), text, font=font, fill=(0,0,0))
        draw.text((x, y), text, font=font, fill=color)

    # Quote
    cur_y = start_y
    for line in quote_lines:
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        lw = bbox[2] - bbox[0]
        draw_shadowed((width - lw)//2, cur_y, line, quote_font)
        cur_y += line_height
        
    # Separator
    ly = cur_y + 25
    lx = (width - 80) // 2
    draw.line([(lx, ly), (lx+80, ly)], fill=(255, 215, 0), width=3)
    
    # Author
    ay = ly + 25
    at = f"— {person_name}"
    bbox = draw.textbbox((0, 0), at, font=author_font)
    aw = bbox[2] - bbox[0]
    draw_shadowed((width - aw)//2, ay, at, author_font)
    
    # Context
    if context:
        cy = ay + 48
        bbox = draw.textbbox((0, 0), context, font=context_font)
        cw = bbox[2] - bbox[0]
        draw.text(((width - cw)//2, cy), context, font=context_font, fill=(200, 200, 200))

    output_path = _get_attachment_path(f"avatar_quote_{person_name.lower().replace(' ', '_')[:15]}")
    img.save(output_path, 'PNG', quality=95)
    return output_path

# ============================================================================
# Logic: DALL-E Quote
# ============================================================================

def _generate_quote_dalle(
    quote_text: str,
    author: str,
    context: str = "",
    style: str = "digital art",
) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not openai:
        return None

    client = openai.OpenAI(api_key=api_key)
    prompt = f"""Create a clean, minimalist quote graphic.
    THE EXACT QUOTE TO DISPLAY: "{quote_text[:150]}"
    — {author}
    DESIGN RULES:
    1. TYPOGRAPHY IS THE ONLY FOCUS - readable, correct spelling.
    2. Large, bold sans-serif font on simple dark background.
    3. Style: {style}
    """
    
    try:
        response = client.images.generate(
            model="dall-e-3", prompt=prompt, size="1792x1024", quality="standard", n=1
        )
        url = response.data[0].url
        
        img_resp = requests.get(url, timeout=30)
        img_resp.raise_for_status()
        
        output_path = _get_attachment_path(f"dalle_quote_{author.lower().replace(' ', '_')[:15]}")
        with open(output_path, 'wb') as f:
            f.write(img_resp.content)
            
        return output_path
    except Exception as e:
        print(f"DALL-E Error: {e}")
        return None

# ============================================================================
# Tools
# ============================================================================

@tool
def generate_quote_image_tool(quote_text: str, author: str, context: str = "") -> str:
    """
    Generate a professional quote image using standard typography (100% accurate text).
    Use this for clear, readable, branded quote cards.
    """
    try:
        path = _generate_quote_simple(quote_text, author, context)
        return f"Quote image generated: {path}"
    except Exception as e:
        return f"Failed: {str(e)}"

@tool
def generate_dalle_quote_image_tool(quote_text: str, author: str, context: str = "", style: str = "digital art") -> str:
    """
    Generate an artistic AI quote image using DALL-E 3.
    Use this for creative, visually striking visuals, but text spelling might vary.
    """
    path = _generate_quote_dalle(quote_text, author, context, style)
    if path:
        return f"DALL-E image generated: {path}"
    return "Failed to generate DALL-E image."

@tool
def generate_quote_with_person_photo(quote_text: str, person_name: str, context: str = "") -> str:
    """
    Generate a quote image with the person's photo as background.
    Automatically searches for the person's portrait.
    """
    path = _generate_quote_avatar(quote_text, person_name, context)
    if path:
        return f"Avatar quote image generated: {path}"
    return "Failed to generate avatar quote image."

@tool
def generate_and_send_quote_email(
    quote_text: str, author: str, recipient_email: str, context: str = "", subject: str = ""
) -> str:
    """Generate a quote image and email it."""
    # 1. Generate
    try:
        path = _generate_quote_simple(quote_text, author, context)
    except Exception as e:
        return f"Generation failed: {e}"

    # 2. Email
    from composio import Composio
    client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))
    
    if not subject: subject = f"Quote: {author}"
    
    try:
        client.tools.execute(
            slug="GMAIL_SEND_EMAIL",
            arguments={
                "recipient_email": recipient_email,
                "subject": subject,
                "body": f"Please find attached the quote by {author}.",
                "attachment": path,
                "is_html": False
            },
            user_id="default",
            dangerously_skip_version_check=True
        )
        return f"Sent quote image to {recipient_email}. Path: {path}"
    except Exception as e:
        return f"Generated {path} but failed to email: {e}"


def get_quote_tools() -> list:
    return [
        generate_quote_image_tool,
        generate_dalle_quote_image_tool,
        generate_quote_with_person_photo,
        generate_and_send_quote_email
    ]

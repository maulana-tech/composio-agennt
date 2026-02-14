"""
Quote Agent Logic - Consolidates all quote generation capabilities.
"""
import os
import io
import requests
from typing import Optional, Tuple
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

def get_font(size: int, bold: bool = False):
    """Get a clean sans-serif font."""
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    if bold: font_paths = ["/Library/Fonts/Arial Bold.ttf"] + font_paths
    for path in font_paths:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: continue
    return ImageFont.load_default()

def wrap_text(text: str, font, max_width: int, draw) -> list:
    """Wrap text to fit within max_width."""
    words = text.split(); lines = []; current_line = []
    for word in words:
        test_line = ' '.join(current_line + [word])
        try: width = draw.textbbox((0, 0), test_line, font=font)[2]
        except: width = draw.textlength(test_line, font=font)
        if width <= max_width: current_line.append(word)
        else:
            if current_line: lines.append(' '.join(current_line))
            current_line = [word]
    if current_line: lines.append(' '.join(current_line))
    return lines

def _get_attachment_path(prefix: str) -> str:
    """Generate consistent output path in the project's attachment folder."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    path = os.path.join(root, "attachment")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

async def generate_simple_quote(quote_text: str, author: str, context: str = "") -> str:
    """Draw a simple typography quote card."""
    width, height = 1792, 1024
    img = Image.new('RGB', (width, height), (26, 26, 46))
    draw = ImageDraw.Draw(img)
    margin = int(width * 0.1); tw = width - (2 * margin)
    qf, af, cf = get_font(56, True), get_font(32), get_font(24)
    lines = wrap_text(quote_text, qf, tw, draw)
    cur_y = (height - (len(lines)*78 + 150)) // 2
    for line in lines:
        w = draw.textbbox((0,0), line, font=qf)[2]; draw.text(((width-w)//2, cur_y), line, font=qf, fill=(255,255,255))
        cur_y += 78
    author_text = f"— {author}"
    w = draw.textbbox((0,0), author_text, font=af)[2]; draw.text(((width-w)//2, cur_y+60), author_text, font=af, fill=(255,255,255))
    out = _get_attachment_path(f"quote_{author.lower().replace(' ', '_')[:10]}")
    img.save(out); return out

async def generate_dalle_quote(quote_text: str, author: str, style: str = "digital art") -> Optional[str]:
    """Generate quote via DALL-E."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    prompt = f'Minimalist quote graphic: "{quote_text[:100]}" — {author}. Style: {style}'
    resp = client.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024")
    url = resp.data[0].url
    out = _get_attachment_path("dalle_quote")
    with open(out, 'wb') as f: f.write(requests.get(url).content)
    return out

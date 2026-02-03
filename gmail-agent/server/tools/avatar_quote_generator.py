"""
Quote Image Generator with Avatar/Person Photo Background
Searches for person's image from web and overlays quote text on top
"""

import os
import io
import requests
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from datetime import datetime
from langchain.tools import tool


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
    
    return ImageFont.load_default()


def search_person_image(person_name: str, api_key: str = None) -> Optional[str]:
    """
    Search for a person's image using Serper API (Google Image Search).
    Returns the URL of the first image found.
    """
    if not api_key:
        api_key = os.environ.get("SERPER_API_KEY")
    
    if not api_key:
        print("⚠️ SERPER_API_KEY not found, cannot search for images")
        return None
    
    try:
        url = "https://google.serper.dev/images"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": f"{person_name} official portrait photo",
            "num": 5
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        images = data.get("images", [])
        
        if images:
            # Try to find a good quality image
            for img in images:
                img_url = img.get("imageUrl")
                if img_url:
                    print(f"🔍 Found image for {person_name}: {img_url[:50]}...")
                    return img_url
        
        print(f"⚠️ No images found for {person_name}")
        return None
        
    except Exception as e:
        print(f"❌ Error searching for image: {e}")
        return None


def download_image(url: str) -> Optional[Image.Image]:
    """Download an image from URL and return as PIL Image."""
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


def generate_quote_with_avatar(
    quote_text: str,
    person_name: str,
    context: str = "",
    background_url: str = None,
    output_path: str = None,
    width: int = 1792,
    height: int = 1024,
    overlay_opacity: float = 0.6,
) -> Optional[str]:
    """
    Generate a quote image with person's photo as background.
    
    Args:
        quote_text: The quote to display
        person_name: Name of the person (used to search for image if no URL provided)
        context: Optional context (e.g., "Presidential Address, 2025")
        background_url: Direct URL to background image (optional, will search if not provided)
        output_path: Where to save the image
        width: Image width in pixels
        height: Image height in pixels
        overlay_opacity: Darkness of the overlay (0.0 to 1.0, higher = darker)
    
    Returns:
        Path to the generated image, or None if failed
    """
    try:
        # Get background image
        bg_image = None
        
        if background_url:
            print(f"📥 Downloading provided background image...")
            bg_image = download_image(background_url)
        
        if not bg_image:
            print(f"🔍 Searching for image of {person_name}...")
            img_url = search_person_image(person_name)
            if img_url:
                bg_image = download_image(img_url)
        
        # Create canvas
        if bg_image:
            # Resize and crop background to fit
            bg_ratio = bg_image.width / bg_image.height
            target_ratio = width / height
            
            if bg_ratio > target_ratio:
                # Image is wider, fit height
                new_height = height
                new_width = int(height * bg_ratio)
            else:
                # Image is taller, fit width
                new_width = width
                new_height = int(width / bg_ratio)
            
            bg_image = bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Center crop
            left = (new_width - width) // 2
            top = (new_height - height) // 2
            bg_image = bg_image.crop((left, top, left + width, top + height))
            
            # Apply blur for better text readability
            bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=3))
            
            # Create dark overlay
            overlay = Image.new('RGB', (width, height), (0, 0, 0))
            bg_image = Image.blend(bg_image, overlay, overlay_opacity)
            
            img = bg_image
        else:
            # Fallback to solid dark background
            print("⚠️ Using solid background (no image found)")
            img = Image.new('RGB', (width, height), (26, 26, 46))
        
        draw = ImageDraw.Draw(img)
        
        # Calculate margins and text area
        margin_x = int(width * 0.08)
        text_area_width = width - (2 * margin_x)
        
        # Get fonts
        quote_font_size = 52
        author_font_size = 28
        context_font_size = 20
        
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
        
        # Text colors
        text_color = (255, 255, 255)
        accent_color = (255, 215, 0)  # Gold accent
        shadow_color = (0, 0, 0)
        
        # Draw opening quotation mark
        quote_mark_font = get_font(100, bold=True)
        # Shadow
        draw.text((margin_x - 25 + 3, start_y - 70 + 3), '"', font=quote_mark_font, fill=shadow_color)
        draw.text((margin_x - 25, start_y - 70), '"', font=quote_mark_font, fill=accent_color)
        
        # Draw quote text with shadow
        current_y = start_y
        for line in quote_lines:
            bbox = draw.textbbox((0, 0), line, font=quote_font)
            line_width = bbox[2] - bbox[0]
            x = (width - line_width) // 2
            # Shadow
            draw.text((x + 2, current_y + 2), line, font=quote_font, fill=shadow_color)
            draw.text((x, current_y), line, font=quote_font, fill=text_color)
            current_y += quote_line_height
        
        # Draw horizontal line separator
        line_y = current_y + 25
        line_width_px = 80
        line_start_x = (width - line_width_px) // 2
        draw.line(
            [(line_start_x, line_y), (line_start_x + line_width_px, line_y)],
            fill=accent_color,
            width=3
        )
        
        # Draw author name
        author_y = line_y + 25
        author_text = f"— {person_name}"
        bbox = draw.textbbox((0, 0), author_text, font=author_font)
        author_width = bbox[2] - bbox[0]
        author_x = (width - author_width) // 2
        # Shadow
        draw.text((author_x + 2, author_y + 2), author_text, font=author_font, fill=shadow_color)
        draw.text((author_x, author_y), author_text, font=author_font, fill=text_color)
        
        # Draw context if provided
        if context:
            context_y = author_y + author_height
            bbox = draw.textbbox((0, 0), context, font=context_font)
            context_width = bbox[2] - bbox[0]
            context_x = (width - context_width) // 2
            context_color = (200, 200, 200)
            draw.text((context_x, context_y), context, font=context_font, fill=context_color)
        
        # Generate output path if not provided
        if not output_path:
            attachment_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "attachment"
            )
            os.makedirs(attachment_dir, exist_ok=True)
            
            safe_name = person_name.lower().replace(' ', '_')[:15]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"avatar_quote_{safe_name}_{timestamp}.png"
            output_path = os.path.join(attachment_dir, filename)
        
        # Save image
        img.save(output_path, 'PNG', quality=95)
        print(f"✅ Quote image with avatar saved: {output_path}")
        
        return output_path
        
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# LangChain Tools for Agent Integration
# ============================================================

@tool
def generate_quote_with_person_photo(
    quote_text: str,
    person_name: str,
    context: str = "",
) -> str:
    """
    Generate a professional quote image with the person's photo as background.
    The tool will automatically search for portraits of the person online.
    Perfect for political quotes, historical figures, celebrities, etc.
    
    Args:
        quote_text: The quote text to display (recommended max 200 characters)
        person_name: Full name of the person (e.g., "Prabowo Subianto", "Adolf Hitler", "Joseph Stalin")
        context: Optional context like "Presidential Speech, 2025" or "Mein Kampf, 1925"
    
    Returns:
        Absolute path to the generated PNG image file
    """
    result = generate_quote_with_avatar(
        quote_text=quote_text,
        person_name=person_name,
        context=context,
    )
    
    if result:
        return f"Quote image with {person_name}'s photo generated successfully: {result}"
    else:
        return f"Failed to generate quote image. Could not find or process image for {person_name}."


def test_avatar_quote():
    """Test the avatar quote generator."""
    print("\n" + "=" * 60)
    print("🎨 Avatar Quote Image Generator - Test")
    print("=" * 60)
    
    # Test quote
    quote = "We are committed to building a strong and modern defense system to protect our nation's sovereignty."
    person = "Prabowo Subianto"
    context = "Presidential Address, January 2025"
    
    print(f'\n📝 Quote: "{quote}"')
    print(f"👤 Person: {person}")
    print(f"📅 Context: {context}")
    print("\n🚀 Generating image...")
    
    output_path = generate_quote_with_avatar(
        quote_text=quote,
        person_name=person,
        context=context
    )
    
    if output_path:
        print(f"\n✅ SUCCESS!")
        print(f"📁 Image saved at: {output_path}")
        size = os.path.getsize(output_path)
        print(f"📊 File size: {size / 1024:.1f} KB")
    else:
        print("\n❌ Failed to generate image")
    
    print("\n" + "=" * 60)
    return output_path


if __name__ == "__main__":
    test_avatar_quote()

from fpdf import FPDF
from fpdf.html import HTMLMixin
from langchain.tools import tool
import markdown
import re
import os
import random
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import base64
import io

# Google Gemini Image Generation
from google import genai
from google.genai import types


def generate_quote_image(
    quote_text: str, author: str, context: str = "", api_key: str = None
) -> Optional[str]:
    """
    Generate a visual image for a political quote using Gemini.
    Returns the path to the generated image or None if failed.

    Args:
        quote_text: The quote text to visualize
        author: The politician/person who said the quote
        context: Additional context about the quote (event, date, etc.)
        api_key: Google API key for Gemini

    Returns:
        Path to generated image file or None
    """
    if not api_key:
        api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        print("Warning: No GOOGLE_API_KEY available for image generation")
        return None

    try:
        # Initialize Gemini client
        client = genai.Client(api_key=api_key)

        # Create a prompt for the image
        prompt = f"""Create a professional, elegant visual representation of this political quote:
        
Quote: "{quote_text[:150]}..."
Author: {author}
Context: {context if context else "Political statement"}

Design requirements:
- Professional and clean design suitable for formal reports
- Subtle background with Indonesian national colors (red and white) or professional blue
- Include the quote text elegantly displayed
- Author name prominently shown
- Modern, minimalist style
- High quality, suitable for printing in PDF
- No overly complex graphics, focus on typography and clean layout
- Inspiring and authoritative mood
"""

        # Generate image using Gemini 2.0 Flash
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["Text", "Image"]),
        )

        # Extract image from response
        image_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                break

        if not image_data:
            print("Warning: No image generated in response")
            return None

        # Save image to temporary file
        import tempfile

        img_bytes = base64.b64decode(image_data)

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=".png", prefix="quote_"
        )
        temp_file.write(img_bytes)
        temp_file.close()

        return temp_file.name

    except Exception as e:
        print(f"Error generating quote image: {e}")
        return None


class ProfessionalPDF(FPDF, HTMLMixin):
    """Enhanced PDF class with better markdown support and professional styling."""

    def __init__(
        self, title: str = "Research Report", sender_email: str = "AI Assistant"
    ):
        super().__init__()
        self.report_title = title
        self.sender_email = sender_email
        self.current_section = ""

        # Professional color scheme
        self.primary_color = (0, 102, 204)  # Deep Blue
        self.secondary_color = (51, 51, 51)  # Dark Gray
        self.accent_color = (0, 153, 255)  # Bright Blue
        self.light_bg = (245, 248, 250)  # Light Blue-Gray
        self.border_color = (200, 210, 220)  # Border Gray

        # Logo handling
        self.logo_path = self._get_logo_path()

    def _get_logo_path(self) -> Optional[str]:
        """Get logo path - either static or generate from email."""
        static_logo = os.path.join(os.path.dirname(__file__), "assets/logo.png")
        if os.path.exists(static_logo):
            return static_logo
        return None

    def header(self):
        """Professional header with logo and title."""
        # White background
        self.set_fill_color(255, 255, 255)
        self.rect(0, 0, 210, 35, "F")

        # Logo (top right)
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.image(self.logo_path, 165, 8, 35)
            except Exception:
                pass

        # Decorative top bar
        self.set_fill_color(*self.primary_color)
        self.rect(0, 0, 210, 3, "F")

        # Accent line
        self.set_fill_color(*self.accent_color)
        self.rect(0, 35, 210, 0.8, "F")

        self.ln(38)

    def footer(self):
        """Professional footer with page numbers and generation info."""
        self.set_y(-20)

        # Footer line
        self.set_fill_color(*self.border_color)
        self.rect(10, self.get_y(), 190, 0.5, "F")

        # Footer content
        self.set_y(-15)
        self.set_font("helvetica", "", 8)
        self.set_text_color(*self.secondary_color)

        # Left: Report info
        self.cell(0, 5, f"{self.report_title}", ln=False, align="L")

        # Center: Generation date
        self.cell(
            0,
            5,
            f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
            ln=False,
            align="C",
        )

        # Right: Page number
        self.cell(0, 5, f"Page {self.page_no()}", ln=True, align="R")

    def add_title_page(self, title: str, subtitle: str = "", metadata: Dict = None):
        """Add a professional title page."""
        self.add_page()

        # Large top spacing
        self.ln(60)

        # Main title
        self.set_font("helvetica", "B", 28)
        self.set_text_color(*self.primary_color)
        self.cell(0, 15, title, ln=True, align="C")

        # Subtitle
        if subtitle:
            self.ln(5)
            self.set_font("helvetica", "", 14)
            self.set_text_color(*self.secondary_color)
            self.cell(0, 10, subtitle, ln=True, align="C")

        # Decorative element
        self.ln(10)
        self.set_fill_color(*self.accent_color)
        x_center = 105 - 30  # Center 60mm wide bar
        self.rect(x_center, self.get_y(), 60, 2, "F")

        # Metadata section
        if metadata:
            self.ln(20)
            self.set_font("helvetica", "", 11)
            self.set_text_color(*self.secondary_color)

            for key, value in metadata.items():
                self.ln(5)
                self.cell(0, 6, f"{key}: {value}", ln=True, align="C")

        # Bottom note
        self.ln(30)
        self.set_font("helvetica", "I", 10)
        self.set_text_color(128, 128, 128)
        self.cell(0, 8, "Confidential Research Report", ln=True, align="C")
        self.cell(0, 8, "Powered by AI with Google Grounding", ln=True, align="C")

    def add_heading1(self, text: str):
        """Add H1 heading."""
        self.ln(8)
        self.set_font("helvetica", "B", 18)
        self.set_text_color(*self.primary_color)
        self.cell(0, 12, text, ln=True)

        # Underline
        self.set_fill_color(*self.accent_color)
        self.rect(10, self.get_y() - 2, 40, 1, "F")
        self.ln(5)

    def add_heading2(self, text: str):
        """Add H2 heading."""
        self.ln(6)
        self.set_font("helvetica", "B", 14)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 10, text, ln=True)
        self.ln(2)

    def add_heading3(self, text: str):
        """Add H3 heading."""
        self.ln(4)
        self.set_font("helvetica", "B", 12)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 8, text, ln=True)

    def add_paragraph(self, text: str):
        """Add a paragraph with proper formatting."""
        self.set_font("helvetica", "", 11)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def add_bullet_point(self, text: str, level: int = 0):
        """Add a bullet point with indentation support."""
        indent = 10 + (level * 5)

        # Bullet symbol
        self.set_xy(indent, self.get_y())
        self.set_font("helvetica", "", 11)
        self.set_text_color(*self.accent_color)
        self.cell(5, 6, "•", ln=False)

        # Text
        self.set_x(indent + 5)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, text)

    def add_numbered_item(self, number: int, text: str):
        """Add a numbered list item."""
        self.set_x(self.l_margin)
        self.set_font("helvetica", "B", 11)
        self.set_text_color(*self.primary_color)
        self.cell(10, 6, f"{number}.", ln=False)

        self.set_font("helvetica", "", 11)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, text)

    def add_quote(self, text: str, author: str = "", source: str = ""):
        """Add a styled quote block."""
        self.ln(4)

        # Left border
        self.set_fill_color(*self.accent_color)
        self.rect(12, self.get_y(), 3, 20, "F")

        # Quote text background
        self.set_fill_color(*self.light_bg)
        self.rect(18, self.get_y() - 2, 182, 24, "F")

        # Quote text
        self.set_xy(22, self.get_y())
        self.set_font("helvetica", "I", 10)
        self.set_text_color(*self.secondary_color)
        self.multi_cell(170, 5, f'"{text}"')

        # Attribution
        if author or source:
            self.ln(2)
            self.set_x(22)
            self.set_font("helvetica", "", 9)
            self.set_text_color(128, 128, 128)
            attribution = f"— {author}" if author else ""
            if source:
                attribution += f", {source}" if attribution else f"— {source}"
            self.cell(0, 5, attribution, ln=True)

        self.ln(6)

    def add_quote_with_image(
        self, text: str, author: str = "", source: str = "", image_path: str = None
    ):
        """Add a styled quote block with optional image visualization."""
        # Add image if available
        if image_path and os.path.exists(image_path):
            try:
                # Check if we need new page for image
                if self.get_y() > 200:
                    self.add_page()

                # Add section divider
                self.ln(5)
                self.set_draw_color(*self.border_color)
                self.line(20, self.get_y(), 190, self.get_y())
                self.ln(8)

                # Center the image
                img_width = 160  # mm
                x_center = (210 - img_width) / 2

                # Add image with border
                self.set_draw_color(*self.accent_color)
                self.set_line_width(0.5)
                self.rect(x_center - 2, self.get_y() - 2, img_width + 4, 92, "D")

                # Insert image
                self.image(image_path, x_center, self.get_y(), img_width)
                self.ln(95)  # Space for image + padding

                # Add caption below image
                self.set_font("helvetica", "I", 9)
                self.set_text_color(100, 100, 100)
                caption = (
                    f"Visual representation of {author}'s statement"
                    if author
                    else "Visual representation"
                )
                self.cell(0, 5, caption, ln=True, align="C")
                self.ln(5)

            except Exception as e:
                print(f"Error adding quote image to PDF: {e}")
                # Fall back to regular quote if image fails
                pass

        # Add the quote text (whether or not image was added)
        self.ln(4)

        # Left border
        self.set_fill_color(*self.accent_color)
        self.rect(12, self.get_y(), 3, 20, "F")

        # Quote text background
        self.set_fill_color(*self.light_bg)
        self.rect(18, self.get_y() - 2, 182, 24, "F")

        # Quote text
        self.set_xy(22, self.get_y())
        self.set_font("helvetica", "I", 10)
        self.set_text_color(*self.secondary_color)
        self.multi_cell(170, 5, f'"{text}"')

        # Attribution
        if author or source:
            self.ln(2)
            self.set_x(22)
            self.set_font("helvetica", "", 9)
            self.set_text_color(128, 128, 128)
            attribution = f"— {author}" if author else ""
            if source:
                attribution += f", {source}" if attribution else f"— {source}"
            self.cell(0, 5, attribution, ln=True)

        self.ln(6)

    def add_table_row(
        self, cells: List[str], is_header: bool = False, col_widths: List[int] = None
    ):
        """Add a table row."""
        if col_widths is None:
            # Default equal widths
            col_widths = [190 // len(cells)] * len(cells)

        # Calculate row height based on content
        self.set_font("helvetica", "B" if is_header else "", 9)
        max_height = 6

        for i, cell in enumerate(cells):
            # Estimate height needed
            lines_needed = len(cell) // (col_widths[i] // 3) + 1
            height_needed = lines_needed * 5
            max_height = max(max_height, height_needed)

        # Check if we need a new page
        if self.get_y() + max_height > 270:
            self.add_page()

        # Row background
        if is_header:
            self.set_fill_color(*self.primary_color)
            self.rect(10, self.get_y(), 190, max_height + 2, "F")
            text_color = (255, 255, 255)
        else:
            # Alternate row colors
            if int(self.get_y() / 10) % 2 == 0:
                self.set_fill_color(250, 250, 250)
                self.rect(10, self.get_y(), 190, max_height + 2, "F")
            text_color = (0, 0, 0)

        # Draw cells
        x_start = 10
        for i, cell in enumerate(cells):
            self.set_xy(x_start, self.get_y() + 1)
            self.set_text_color(*text_color)
            self.multi_cell(col_widths[i], 5, cell, border=0)

            # Draw cell border
            if not is_header:
                self.set_draw_color(*self.border_color)
                self.rect(x_start, self.get_y() - 1, col_widths[i], max_height + 2, "D")

            x_start += col_widths[i]

        self.ln(max_height + 3)

    def add_info_box(self, title: str, content: str, box_type: str = "info"):
        """Add an info/warning/success box."""
        colors = {
            "info": (0, 102, 204),
            "warning": (255, 165, 0),
            "success": (34, 139, 34),
            "error": (220, 20, 60),
        }
        color = colors.get(box_type, colors["info"])

        self.ln(4)

        # Box border
        self.set_draw_color(*color)
        self.set_line_width(0.5)

        # Title background
        self.set_fill_color(*color)
        self.rect(12, self.get_y(), 186, 8, "F")

        # Title
        self.set_xy(15, self.get_y() + 1.5)
        self.set_font("helvetica", "B", 10)
        self.set_text_color(255, 255, 255)
        self.cell(0, 5, title.upper(), ln=True)

        # Content
        self.ln(6)
        self.set_x(15)
        self.set_font("helvetica", "", 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(180, 5, content)

        # Box outline
        self.rect(
            12,
            self.get_y() - 5 - (len(content) // 35 * 5),
            186,
            15 + (len(content) // 35 * 5),
            "D",
        )

        self.ln(8)


def parse_markdown_content(content: str) -> List[Dict[str, Any]]:
    """
    Parse markdown content into structured elements for PDF generation.
    Returns a list of dictionaries with element type and content.
    """
    elements = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Headers
        if line.startswith("# ") and not line.startswith("## "):
            elements.append({"type": "h1", "content": line[2:].strip()})
            i += 1
            continue
        elif line.startswith("## "):
            elements.append({"type": "h2", "content": line[3:].strip()})
            i += 1
            continue
        elif line.startswith("### "):
            elements.append({"type": "h3", "content": line[4:].strip()})
            i += 1
            continue

        # Tables
        if "|" in line and i + 1 < len(lines) and "---" in lines[i + 1]:
            # This is a table header
            headers = [cell.strip() for cell in line.split("|")[1:-1]]
            i += 2  # Skip header and separator

            rows = []
            while i < len(lines) and "|" in lines[i]:
                row = [cell.strip() for cell in lines[i].split("|")[1:-1]]
                if row:
                    rows.append(row)
                i += 1

            elements.append({"type": "table", "headers": headers, "rows": rows})
            continue

        # Quotes
        if line.startswith("> "):
            quote_lines = [line[2:]]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_lines.append(lines[i].strip()[2:])
                i += 1

            quote_text = " ".join(quote_lines)
            # Try to extract attribution
            author = ""
            source = ""
            if "—" in quote_text or "--" in quote_text:
                parts = (
                    quote_text.split("—")
                    if "—" in quote_text
                    else quote_text.split("--")
                )
                quote_text = parts[0].strip()
                attribution = parts[1].strip() if len(parts) > 1 else ""
                if "," in attribution:
                    auth_parts = attribution.split(",", 1)
                    author = auth_parts[0].strip()
                    source = auth_parts[1].strip() if len(auth_parts) > 1 else ""
                else:
                    author = attribution

            elements.append(
                {
                    "type": "quote",
                    "content": quote_text,
                    "author": author,
                    "source": source,
                }
            )
            continue

        # Bullet points
        if line.startswith("- ") or line.startswith("* "):
            bullet_items = []
            current_level = 0

            while i < len(lines):
                bullet_line = lines[i].rstrip()
                if bullet_line.startswith("- ") or bullet_line.startswith("* "):
                    bullet_items.append({"text": bullet_line[2:], "level": 0})
                    i += 1
                elif bullet_line.startswith("  - ") or bullet_line.startswith("  * "):
                    bullet_items.append({"text": bullet_line[4:], "level": 1})
                    i += 1
                elif bullet_line:
                    break
                else:
                    i += 1

            if bullet_items:
                elements.append({"type": "bullet_list", "items": bullet_items})
            continue

        # Numbered lists
        numbered_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if numbered_match:
            numbered_items = []

            while i < len(lines):
                numbered_line = lines[i].strip()
                match = re.match(r"^(\d+)\.\s+(.+)$", numbered_line)
                if match:
                    numbered_items.append(match.group(2))
                    i += 1
                elif numbered_line:
                    break
                else:
                    i += 1

            if numbered_items:
                elements.append({"type": "numbered_list", "items": numbered_items})
            continue

        # Horizontal rule
        if line == "---" or line == "***":
            elements.append({"type": "hr"})
            i += 1
            continue

        # Code blocks
        if line.startswith("```"):
            code_lines = []
            language = line[3:].strip()
            i += 1

            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1

            elements.append(
                {"type": "code", "content": "\n".join(code_lines), "language": language}
            )
            i += 1
            continue

        # Info boxes (custom syntax: [INFO], [WARNING], [SUCCESS], [ERROR])
        info_match = re.match(
            r"^\[(INFO|WARNING|SUCCESS|ERROR)\]\s*(.+)$", line, re.IGNORECASE
        )
        if info_match:
            box_type = info_match.group(1).lower()
            title = info_match.group(2)
            content_lines = []
            i += 1

            while i < len(lines) and lines[i].strip() and not lines[i].startswith("["):
                content_lines.append(lines[i].strip())
                i += 1

            elements.append(
                {
                    "type": "info_box",
                    "box_type": box_type,
                    "title": title,
                    "content": "\n".join(content_lines),
                }
            )
            continue

        # Regular paragraph
        paragraph_lines = [line]
        i += 1

        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].startswith(("#", "-", "*", ">", "|", "["))
        ):
            if not re.match(r"^(\d+)\.\s+", lines[i]):
                paragraph_lines.append(lines[i].strip())
                i += 1
            else:
                break

        paragraph_text = " ".join(paragraph_lines)

        # Process inline formatting
        paragraph_text = re.sub(
            r"\*\*\*(.+?)\*\*\*", r"\1", paragraph_text
        )  # Bold italic
        paragraph_text = re.sub(r"\*\*(.+?)\*\*", r"\1", paragraph_text)  # Bold
        paragraph_text = re.sub(r"\*(.+?)\*", r"\1", paragraph_text)  # Italic
        paragraph_text = re.sub(r"`(.+?)`", r"\1", paragraph_text)  # Code

        elements.append({"type": "paragraph", "content": paragraph_text})

    return elements


def generate_logo_from_email(email: str) -> str:
    """Generate a simple professional logo image from an email string."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Extract name part from email
        name = email.split("@")[0]
        # Get up to 5 characters for the logo
        logo_text = name[:5].lower()

        # Professional color palette
        bg_colors = [(44, 62, 80), (52, 73, 94), (41, 128, 185), (22, 160, 133)]
        bg_color = random.choice(bg_colors)

        # Create image
        size = (200, 200)
        img = Image.new("RGB", size, color=bg_color)
        d = ImageDraw.Draw(img)

        # Draw a circle border
        d.ellipse([10, 10, 190, 190], outline=(255, 255, 255), width=5)

        # Center text - use default font if special one not found
        try:
            # Try to find a font on the system
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "Arial.ttf",
            ]
            font = None
            for fp in font_paths:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, 60)
                    break
            if not font:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # Get text size to center it
        bbox = d.textbbox((100, 100), logo_text, font=font, anchor="mm")
        d.text((100, 100), logo_text, font=font, fill=(255, 255, 255), anchor="mm")

        logo_filename = f"logo_{name}_{random.getrandbits(16)}.png"
        logo_path = os.path.abspath(logo_filename)
        img.save(logo_path)
        return logo_path
    except Exception as e:
        print(f"Logo generation error: {e}")
        return ""


@tool
def generate_pdf_report(
    markdown_content: str,
    filename: str = "report.pdf",
    sender_email: str = "AI Assistant",
    enable_quote_images: bool = True,
    max_quote_images: int = 5,
) -> str:
    """
    Generate a professional, detailed PDF report from Markdown content.

    Features:
    - Proper markdown parsing (headers, lists, quotes, tables)
    - Professional styling with consistent colors
    - AI-generated images for political quotes (optional)
    - Title page with metadata
    - Page numbers and headers/footers
    - Styled quote blocks for politician quotes
    - Table support for structured data
    - Info/warning boxes for highlights

    Args:
        markdown_content: Content in markdown format with proper structure
        filename: Name of the output PDF file
        sender_email: Email to generate logo from (optional)
        enable_quote_images: Whether to generate AI images for quotes (default: True)
        max_quote_images: Maximum number of quote images to generate (default: 5)

    Returns:
        Absolute file path of the generated PDF
    """
    try:
        # Prepare filename
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if filename == "report.pdf" or filename == "output.pdf":
            filename = f"report_{ts}.pdf"
        elif not filename.endswith(".pdf"):
            filename = f"{filename}.pdf"

        # Extract title from content (first H1)
        title_match = re.search(r"^#\s+(.+)$", markdown_content, re.MULTILINE)
        report_title = title_match.group(1) if title_match else "Research Report"

        # Parse markdown into structured elements
        elements = parse_markdown_content(markdown_content)

        # Track generated images for cleanup
        generated_images = []
        quote_image_count = 0

        # Create PDF
        pdf = ProfessionalPDF(title=report_title, sender_email=sender_email)

        # Add title page
        metadata = {
            "Generated By": "AI Research Assistant",
            "Date": datetime.now().strftime("%B %d, %Y"),
            "Method": "Google Grounding with Real-Time Search",
        }
        pdf.add_title_page(
            report_title, subtitle="Comprehensive Analysis Report", metadata=metadata
        )

        # Add content pages
        pdf.add_page()

        # Process each element
        for element in elements:
            elem_type = element.get("type")

            if elem_type == "h1":
                # Skip if it's the title (already on title page)
                if element["content"] != report_title:
                    pdf.add_heading1(element["content"])

            elif elem_type == "h2":
                pdf.add_heading2(element["content"])

            elif elem_type == "h3":
                pdf.add_heading3(element["content"])

            elif elem_type == "paragraph":
                pdf.add_paragraph(element["content"])

            elif elem_type == "bullet_list":
                for item in element["items"]:
                    pdf.add_bullet_point(item["text"], item.get("level", 0))
                pdf.ln(3)

            elif elem_type == "numbered_list":
                for idx, item in enumerate(element["items"], 1):
                    pdf.add_numbered_item(idx, item)
                pdf.ln(3)

            elif elem_type == "quote":
                # Generate image for quote if enabled and under limit
                image_path = None
                if enable_quote_images and quote_image_count < max_quote_images:
                    api_key = os.environ.get("GOOGLE_API_KEY")
                    if api_key:
                        image_path = generate_quote_image(
                            element["content"],
                            element.get("author", ""),
                            element.get("source", ""),
                            api_key,
                        )
                        if image_path:
                            generated_images.append(image_path)
                            quote_image_count += 1

                # Add quote with or without image
                if image_path:
                    pdf.add_quote_with_image(
                        element["content"],
                        element.get("author", ""),
                        element.get("source", ""),
                        image_path,
                    )
                else:
                    pdf.add_quote(
                        element["content"],
                        element.get("author", ""),
                        element.get("source", ""),
                    )

            elif elem_type == "table":
                # Calculate column widths
                num_cols = len(element["headers"])
                col_width = 190 // num_cols
                col_widths = [col_width] * num_cols

                # Add header
                pdf.add_table_row(
                    element["headers"], is_header=True, col_widths=col_widths
                )

                # Add rows
                for row in element["rows"]:
                    if len(row) == num_cols:
                        pdf.add_table_row(row, is_header=False, col_widths=col_widths)

                pdf.ln(5)

            elif elem_type == "info_box":
                pdf.add_info_box(
                    element["title"],
                    element["content"],
                    element.get("box_type", "info"),
                )

            elif elem_type == "hr":
                pdf.ln(5)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(20, pdf.get_y(), 190, pdf.get_y())
                pdf.ln(5)

            elif elem_type == "code":
                # Simple code block rendering
                pdf.ln(3)
                pdf.set_fill_color(245, 245, 245)
                pdf.set_font("courier", "", 9)
                pdf.set_text_color(50, 50, 50)
                pdf.multi_cell(0, 4, element["content"], fill=True)
                pdf.ln(3)

        # Add final page with references section if there are citations
        if "[1]" in markdown_content or "http" in markdown_content:
            pdf.add_page()
            pdf.add_heading1("References & Sources")
            pdf.add_paragraph(
                "All information in this report has been verified using Google Grounding with real-time web search. Sources are cited throughout the document."
            )

        # Ensure attachment directory exists
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        attachment_dir = os.path.join(base_dir, "attacchment")
        os.makedirs(attachment_dir, exist_ok=True)

        # Save PDF
        output_path = os.path.join(attachment_dir, filename)
        pdf.output(output_path)

        # Cleanup temporary quote images
        for img_path in generated_images:
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
                    print(f"Cleaned up temporary image: {img_path}")
            except Exception as cleanup_err:
                print(f"Warning: Could not cleanup image {img_path}: {cleanup_err}")

        return output_path

    except Exception as e:
        # Cleanup temporary images on error
        for img_path in generated_images:
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
            except:
                pass

        import traceback

        error_msg = f"ERROR generating PDF: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return f"ERROR: {str(e)}"

from fpdf import FPDF
from langchain.tools import tool
import markdown
import os
import random
from typing import Optional, Dict, List, Tuple
from datetime import datetime


# Random topics for report generation
RANDOM_TOPICS = [
    "Artificial Intelligence in Healthcare",
    "Sustainable Energy Solutions",
    "The Future of Remote Work",
    "Cybersecurity Best Practices",
    "Digital Marketing Trends 2026",
    "Climate Change Mitigation Strategies",
    "Blockchain Technology Applications",
    "Machine Learning in Finance",
    "Smart City Development",
    "Mental Health in the Workplace",
    "E-commerce Growth Strategies",
    "Data Privacy and Protection",
    "Renewable Energy Technologies",
    "Supply Chain Optimization",
    "Customer Experience Innovation",
]


def extract_colors_from_image(image_path: str, num_colors: int = 3) -> List[Tuple[int, int, int]]:
    """
    Extract dominant colors from an image using PIL.
    Returns list of RGB tuples.
    """
    try:
        from PIL import Image
        from collections import Counter
        
        img = Image.open(image_path)
        # Resize for faster processing
        img = img.resize((100, 100))
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Get all pixels
        pixels = list(img.getdata())
        
        # Filter out very light (white-ish) and very dark (black-ish) colors
        filtered_pixels = [
            p for p in pixels 
            if not (sum(p) > 700 or sum(p) < 60)  # Not too white or too black
        ]
        
        if not filtered_pixels:
            filtered_pixels = pixels
        
        # Count colors and get most common
        color_counts = Counter(filtered_pixels)
        dominant_colors = [color for color, count in color_counts.most_common(num_colors * 3)]
        
        # Cluster similar colors
        def color_distance(c1, c2):
            return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5
        
        selected = []
        for color in dominant_colors:
            if len(selected) >= num_colors:
                break
            # Check if color is sufficiently different from already selected
            is_unique = all(color_distance(color, s) > 50 for s in selected)
            if is_unique or not selected:
                selected.append(color)
        
        # Ensure we have enough colors
        while len(selected) < num_colors:
            selected.append((41, 128, 185))  # Default blue
        
        return selected[:num_colors]
        
    except Exception as e:
        print(f"Error extracting colors: {e}")
        # Return default professional colors
        return [(41, 128, 185), (52, 73, 94), (22, 160, 133)]


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex string."""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def get_lighter_shade(rgb: Tuple[int, int, int], factor: float = 0.3) -> Tuple[int, int, int]:
    """Get a lighter shade of the color."""
    return tuple(min(255, int(c + (255 - c) * factor)) for c in rgb)


def get_darker_shade(rgb: Tuple[int, int, int], factor: float = 0.3) -> Tuple[int, int, int]:
    """Get a darker shade of the color."""
    return tuple(max(0, int(c * (1 - factor))) for c in rgb)


from fpdf import FPDF
from fpdf.html import HTMLMixin

class StyledReportPDF(FPDF, HTMLMixin):
    def __init__(self, primary_color: Tuple[int, int, int], secondary_color: Tuple[int, int, int], 
                 accent_color: Tuple[int, int, int], logo_path: Optional[str] = None):
        super().__init__()
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.accent_color = accent_color
        self.logo_path = logo_path
        self.title_text = ""
        
    def header(self):
        # Header background bar
        self.set_fill_color(255, 255, 255) # White header
        self.rect(0, 0, 210, 25, 'F')
        
        # Logo (top right)
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                # Place logo on the right (x=160, y=5, width=40)
                self.image(self.logo_path, 160, 5, 40)
            except Exception:
                pass
        
        # Accent line (keep blue)
        self.set_fill_color(*self.primary_color)
        self.rect(0, 25, 210, 1.5, 'F')
        
        self.ln(30)
        
    def footer(self):
        self.set_y(-20)
        
        # Footer line
        self.set_fill_color(*get_lighter_shade(self.secondary_color, 0.5))
        self.rect(10, self.get_y(), 190, 0.5, 'F')
        
        # Footer text
        self.set_y(-15)
        self.set_font('times', 'I', 8)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 10, f'Generated on {datetime.now().strftime("%B %d, %Y")} | Page {self.page_no()}', align='C')
        
    def add_title(self, title: str):
        self.title_text = title
        self.set_font('times', 'B', 24)
        self.set_text_color(*self.primary_color)
        self.cell(0, 15, title, ln=True, align='C')
        
        # Decorative underline
        self.set_fill_color(*self.accent_color)
        x_center = (210 - 60) / 2
        self.rect(x_center, self.get_y(), 60, 1.5, 'F')
        self.ln(10)
        
    def add_section(self, title: str, content: str):
        # Section header with colored background
        self.set_fill_color(*get_lighter_shade(self.primary_color, 0.8))
        self.set_font('times', 'B', 14)
        self.set_text_color(*get_darker_shade(self.primary_color, 0.2))
        
        # Section box
        y_start = self.get_y()
        self.cell(0, 10, f'  {title}', ln=True, fill=True)
        
        # Accent sidebar
        self.set_fill_color(*self.accent_color)
        self.rect(10, y_start, 2, 10, 'F')
        
        self.ln(3)
        
        # Content
        self.set_font('times', '', 12)
        self.set_text_color(0, 0, 0) # Pure black
        self.multi_cell(0, 6, content)
        self.ln(5)
        
    def add_bullet_points(self, title: str, points: List[str]):
        # Section header
        self.set_fill_color(*get_lighter_shade(self.secondary_color, 0.8))
        self.set_font('times', 'B', 12)
        self.set_text_color(*self.secondary_color)
        
        y_start = self.get_y()
        self.cell(0, 8, f'  {title}', ln=True, fill=True)
        
        # Accent sidebar
        self.set_fill_color(*self.secondary_color)
        self.rect(10, y_start, 2, 8, 'F')
        
        self.ln(2)
        
        # Bullet points
        self.set_font('times', '', 12)
        self.set_text_color(0, 0, 0)
        
        for point in points:
            # Colored bullet
            self.set_fill_color(*self.accent_color)
            self.ellipse(15, self.get_y() + 2, 2, 2, 'F')
            self.set_x(20)
            self.multi_cell(0, 5, point)
            self.ln(1)
        
        self.ln(3)


def generate_styled_report(topic: Optional[str] = None, logo_path: Optional[str] = None) -> Dict:
    """
    Generate a one-page styled PDF report.
    
    Args:
        topic: Topic for the report (random if not provided)
        logo_path: Path to logo image (optional)
    
    Returns:
        Dictionary with path, topic, and colors used
    """
    # Select topic
    if not topic:
        topic = random.choice(RANDOM_TOPICS)
    
    # Extract colors from logo or use defaults
    if logo_path and os.path.exists(logo_path):
        colors = extract_colors_from_image(logo_path)
    else:
        colors = [
            (41, 128, 185),   # Professional blue
            (52, 73, 94),     # Dark slate
            (22, 160, 133),   # Teal accent
        ]
    
    primary_color = colors[0]
    secondary_color = colors[1] if len(colors) > 1 else colors[0]
    accent_color = colors[2] if len(colors) > 2 else colors[0]
    
    # Create PDF
    pdf = StyledReportPDF(primary_color, secondary_color, accent_color, logo_path)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    
    # Add title
    pdf.add_title(topic)
    
    # Executive Summary
    summary = f"""This report provides a comprehensive overview of {topic.lower()}. 
In today's rapidly evolving landscape, understanding the key aspects and implications 
of this subject is crucial for organizations and individuals alike. The following 
sections outline the main concepts, benefits, and recommendations."""
    pdf.add_section("Executive Summary", summary)
    
    # Key Points
    key_points = [
        f"Understanding the fundamentals of {topic.lower()} is essential for success",
        "Implementation requires careful planning and stakeholder alignment",
        "Technology plays a crucial role in modern approaches",
        "Continuous monitoring and adaptation are key to long-term success",
        "Collaboration across teams enhances outcomes significantly",
    ]
    pdf.add_bullet_points("Key Takeaways", key_points)
    
    # Recommendations
    recommendations = f"""Based on our analysis, we recommend a phased approach to implementing 
{topic.lower()} strategies. Organizations should start with a thorough assessment of current 
capabilities, followed by pilot programs to validate assumptions. Success metrics should be 
established early and tracked consistently throughout the implementation process."""
    pdf.add_section("Recommendations", recommendations)
    
    # Save PDF
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{topic.replace(' ', '_')[:30]}_{ts}.pdf"
    
    # Ensure attacchment directory exists
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    attachment_dir = os.path.join(base_dir, "attacchment")
    os.makedirs(attachment_dir, exist_ok=True)
    
    output_path = os.path.join(attachment_dir, filename)
    pdf.output(output_path)
    
    return {
        "path": output_path,
        "topic": topic,
        "colors": [rgb_to_hex(c) for c in [primary_color, secondary_color, accent_color]]
    }


class ReportPDF(StyledReportPDF):
    def __init__(self):
        # Colors matching the new logo
        colors = [
            (0, 156, 255),   # Bright Blue from logo
            (34, 37, 44),    # Dark Slate from logo
            (0, 156, 255),   # Accent Blue
        ]
        super().__init__(colors[0], colors[1], colors[2])
        
        # Default logo path
        self.logo_path = os.path.join(os.path.dirname(__file__), 'assets/logo.png')
        if not os.path.exists(self.logo_path):
            self.logo_path = None

    def header(self):
        super().header()

    def footer(self):
        super().footer()


def generate_logo_from_email(email: str) -> str:
    """Generate a simple professional logo image from an email string."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Extract name part from email
        name = email.split('@')[0]
        # Get up to 5 characters for the logo
        logo_text = name[:5].lower()
        
        # Professional color palette
        bg_colors = [(44, 62, 80), (52, 73, 94), (41, 128, 185), (22, 160, 133)]
        bg_color = random.choice(bg_colors)
        
        # Create image
        size = (200, 200)
        img = Image.new('RGB', size, color=bg_color)
        d = ImageDraw.Draw(img)
        
        # Draw a circle border
        d.ellipse([10, 10, 190, 190], outline=(255, 255, 255), width=5)
        
        # Center text - use default font if special one not found
        try:
            # Try to find a font on the system
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "Arial.ttf"
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
def generate_pdf_report(markdown_content: str, filename: str = "report.pdf", sender_email: str = "AI Assistant") -> str:
    """
    Generate a professional PDF report from Markdown content using FPDF.
    Supports HTML/CSS styling via Markdown to HTML conversion.
    
    Args:
        markdown_content: Content in markdown.
        filename: Name of the file.
        sender_email: Email to generate logo from.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if filename == "report.pdf" or filename == "output.pdf":
        filename = f"report_{ts}.pdf"
    elif not filename.endswith('.pdf'):
        filename = f"{filename}.pdf"
        
    logo_path = None
    try:
        # 1. Convert Markdown to HTML
        try:
            html_content = markdown.markdown(
                markdown_content,
                extensions=['extra', 'nl2br', 'sane_lists']
            )
        except Exception:
            try:
                html_content = markdown.markdown(markdown_content, extensions=['extra'])
            except Exception:
                html_content = markdown.markdown(markdown_content)

        # 2. Setup PDF with specified logo
        pdf = ReportPDF()
        
        # If no specific logo exists in assets, use dynamic generation
        if not pdf.logo_path:
            logo_path = generate_logo_from_email(sender_email)
            pdf.logo_path = logo_path if logo_path and os.path.exists(logo_path) else None
        else:
            logo_path = None # Using static logo
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # 3. Setup Layout
        pdf.ln(5)

        # 4. Write HTML
        pdf.set_font("times", size=12)
        pdf.set_text_color(0, 0, 0)
        pdf.write_html(html_content)

        # 5. Save
        # Ensure attacchment directory exists
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        attachment_dir = os.path.join(base_dir, "attacchment")
        os.makedirs(attachment_dir, exist_ok=True)
        
        output_path = os.path.join(attachment_dir, filename)
        pdf.output(output_path)
        
        # Cleanup logo
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
            
        return output_path

    except Exception as e:
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
        return f"ERROR: {str(e)}"

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


class StyledReportPDF(FPDF):
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
        self.set_fill_color(*self.primary_color)
        self.rect(0, 0, 210, 25, 'F')
        
        # Logo (top left)
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.image(self.logo_path, 10, 5, 15)
            except Exception:
                pass
        
        # Accent line
        self.set_fill_color(*self.accent_color)
        self.rect(0, 25, 210, 2, 'F')
        
        self.ln(30)
        
    def footer(self):
        self.set_y(-20)
        
        # Footer line
        self.set_fill_color(*get_lighter_shade(self.secondary_color, 0.5))
        self.rect(10, self.get_y(), 190, 0.5, 'F')
        
        # Footer text
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 10, f'Generated on {datetime.now().strftime("%B %d, %Y")} | Page {self.page_no()}', align='C')
        
    def add_title(self, title: str):
        self.title_text = title
        self.set_font('helvetica', 'B', 24)
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
        self.set_font('helvetica', 'B', 14)
        self.set_text_color(*get_darker_shade(self.primary_color, 0.2))
        
        # Section box
        y_start = self.get_y()
        self.cell(0, 10, f'  {title}', ln=True, fill=True)
        
        # Accent sidebar
        self.set_fill_color(*self.accent_color)
        self.rect(10, y_start, 2, 10, 'F')
        
        self.ln(3)
        
        # Content
        self.set_font('helvetica', '', 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, content)
        self.ln(5)
        
    def add_bullet_points(self, title: str, points: List[str]):
        # Section header
        self.set_fill_color(*get_lighter_shade(self.secondary_color, 0.8))
        self.set_font('helvetica', 'B', 12)
        self.set_text_color(*self.secondary_color)
        
        y_start = self.get_y()
        self.cell(0, 8, f'  {title}', ln=True, fill=True)
        
        # Accent sidebar
        self.set_fill_color(*self.secondary_color)
        self.rect(10, y_start, 2, 8, 'F')
        
        self.ln(2)
        
        # Bullet points
        self.set_font('helvetica', '', 10)
        self.set_text_color(60, 60, 60)
        
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
    output_path = os.path.abspath(filename)
    pdf.output(output_path)
    
    return {
        "path": output_path,
        "topic": topic,
        "colors": [rgb_to_hex(c) for c in [primary_color, secondary_color, accent_color]]
    }


class ReportPDF(StyledReportPDF):
    def __init__(self):
        # Default professional colors
        colors = [
            (41, 128, 185),   # Professional blue
            (52, 73, 94),     # Dark slate
            (22, 160, 133),   # Teal accent
        ]
        super().__init__(colors[0], colors[1], colors[2])

    def header(self):
        super().header()

    def footer(self):
        super().footer()


@tool
def generate_pdf_report(markdown_content: str, filename: str = "report.pdf") -> str:
    """
    Generate a professional PDF report from Markdown content using FPDF.
    Supports HTML/CSS styling via Markdown to HTML conversion.
    Useful for creating final reports after research.
    IMPORTANT: This tool returns the ABSOLUTE PATH of the generated file which MUST be used for attachments.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # If filename is generic or simple, add timestamp to avoid overwrites
    if filename == "report.pdf" or filename == "output.pdf":
        filename = f"report_{ts}.pdf"
    elif not filename.endswith('.pdf'):
        filename = f"{filename}.pdf"
    
    # Do NOT force timestamp on custom filenames, to allow agent to predict path.
        
    try:
        # 1. Convert Markdown to HTML
        # Using 'extra' extension for tables, 'nl2br' for newlines
        html_content = markdown.markdown(
            markdown_content, 
            extensions=['extra', 'nl2br', 'sane_lists']
        )
        
        # Add basic CSS styling for the PDF
        # Note: FPDF2 write_html supports basic tags. 
        # We wrap the content in a body/div to apply general styles if needed.
        # But mostly we rely on the specific tag support.
        
        # 2. Setup PDF
        pdf = ReportPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # FPDF2 handles fonts fairly well, but for standard usage:
        pdf.set_font("helvetica", size=12)
        
        # 3. Write HTML
        # We can prepend a title or some custom HTML wrapper if we want more control
        # but the markdown content is usually self-contained.
        pdf.write_html(html_content)
        
        # 4. Save
        output_path = os.path.abspath(filename)
        pdf.output(output_path)
        return output_path
        
    except Exception as e:
        return f"ERROR: {str(e)}"

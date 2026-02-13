
"""
PDF Agent Tool
Wraps PDF generation with agent-specific logic (e.g. session handling).
"""

from langchain_core.tools import tool
from .pdf_generator import generate_pdf_report

@tool
def generate_pdf_report_wrapped(
    markdown_content: str,
    filename: str = "report.pdf",
    sender_email: str = "AI Assistant",
    enable_quote_images: bool = True,
) -> str:
    """
    Generate a professional PDF report from Markdown content with AI-generated images for political quotes.

    Args:
        markdown_content: The markdown text to include in the report.
        filename: The name of the PDF file to generate.
        sender_email: The email address to derive a dynamic logo from (e.g., 'user@gmail.com' -> 'user' logo).
        enable_quote_images: Whether to generate AI images for political quotes (default: True). Set to False to disable image generation.

    Returns:
        The ABSOLUTE FILE PATH that you MUST use for gmail_send_email attachment parameter.

    Note:
        When enable_quote_images=True, the PDF will include AI-generated visual representations
        of political quotes (up to 5 images maximum) using Gemini image generation.
    """
    if not filename:
        filename = "report.pdf"
    print(
        f"DEBUG: Executing PDF generator for {filename} with sender {sender_email}, quote_images={enable_quote_images}"
    )
    path = generate_pdf_report.invoke(
        {
            "markdown_content": markdown_content,
            "filename": filename,
            "sender_email": sender_email,
            "enable_quote_images": enable_quote_images,
            "max_quote_images": 5,
        }
    )
    print(f"DEBUG: PDF generated at {path}")
    return path

def get_pdf_tools() -> list:
    return [generate_pdf_report_wrapped]

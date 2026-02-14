"""
PDF Agent Logic - Wraps PDF generation.
"""
from .generator import generate_pdf_report

async def generate_pdf(markdown_content: str, filename: str = "report.pdf", sender_email: str = "AI Assistant", enable_quote_images: bool = True) -> str:
    """Core logic for generating a PDF report."""
    if not filename:
        filename = "report.pdf"
    
    # We use .invoke directly as it's a LangChain tool-like function
    path = generate_pdf_report.invoke({
        "markdown_content": markdown_content,
        "filename": filename,
        "sender_email": sender_email,
        "enable_quote_images": enable_quote_images,
        "max_quote_images": 5,
    })
    return path

"""
PDF Agent Tools - LangChain tool exports.
"""
from langchain_core.tools import tool
from .logic import generate_pdf

@tool
async def generate_pdf_report_tool(
    markdown_content: str,
    filename: str = "report.pdf",
    sender_email: str = "AI Assistant",
    enable_quote_images: bool = True,
) -> str:
    """
    Generate a professional PDF report from Markdown content.
    
    Returns the absolute file path for downloading or attaching.
    """
    return await generate_pdf(
        markdown_content=markdown_content,
        filename=filename,
        sender_email=sender_email,
        enable_quote_images=enable_quote_images
    )

def get_pdf_tools() -> list:
    return [generate_pdf_report_tool]

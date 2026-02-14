"""
PDF Plugin Agent - Handles PDF report generation.
"""

from ..core.base import BaseAgent, AgentContext, AgentResponse
from .logic import generate_pdf


class PDFPluginAgent(BaseAgent):
    """
    Agent responsible for generating professional PDF reports.
    """

    name = "pdf"
    description = "Generates professional PDF reports from Markdown content"
    keywords = ["pdf", "report", "document", "export pdf", "buat pdf", "laporan pdf"]

    async def get_status(
        self, session_id: str = "default", base_url: str = "http://localhost:8000"
    ) -> str:
        """PDF generation is stateless - always returns none."""
        return "none"

    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """
        Process a request to generate a PDF.
        Typically used when a user says 'buatkan laporan PDF dari rangkuman tadi'.
        """
        # In a real scenario, we'd extract the content from context or previous messages.
        # For simplicity, we assume the message or context contains the needed markdown.
        content = context.metadata.get("markdown_content") or message
        filename = context.metadata.get("filename", "report.pdf")

        path = await generate_pdf(content, filename=filename)

        return AgentResponse(
            message=f"✅ Laporan PDF berhasil dibuat: {path}",
            status="completed",
            agent_name=self.name,
            data={"pdf_path": path},
        )

    def get_tools(self) -> list:
        from .tools import get_pdf_tools

        return get_pdf_tools()

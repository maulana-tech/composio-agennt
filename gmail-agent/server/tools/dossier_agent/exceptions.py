"""
Dossier Agent - Custom Exception Hierarchy.

Provides structured error classes for each pipeline stage so callers
can distinguish between collection failures, synthesis failures,
analysis failures, and generation failures.
"""


class DossierError(Exception):
    """Base exception for all dossier-related errors."""

    def __init__(self, message: str = "", stage: str = ""):
        self.stage = stage
        super().__init__(message)


class DossierCollectionError(DossierError):
    """Raised when data collection (Serper / LinkedIn) fails."""

    def __init__(self, message: str = "Data collection failed"):
        super().__init__(message, stage="collecting")


class DossierSynthesisError(DossierError):
    """Raised when the Gemini research synthesis step fails."""

    def __init__(self, message: str = "Research synthesis failed"):
        super().__init__(message, stage="researching")


class DossierAnalysisError(DossierError):
    """Raised when the Gemini strategic analysis step fails."""

    def __init__(self, message: str = "Strategic analysis failed"):
        super().__init__(message, stage="analyzing")


class DossierGenerationError(DossierError):
    """Raised when the Markdown document assembly step fails."""

    def __init__(self, message: str = "Document generation failed"):
        super().__init__(message, stage="generating")


class DossierSessionError(DossierError):
    """Raised for session lookup / management errors."""

    def __init__(self, message: str = "Session error"):
        super().__init__(message, stage="session")

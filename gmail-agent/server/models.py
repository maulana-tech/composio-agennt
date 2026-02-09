from pydantic import BaseModel, Field
from typing import List, Optional, Any


class CreateConnectionRequest(BaseModel):
    user_id: str = Field(default="default")
    auth_config_id: Optional[str] = None


class CreateConnectionResponse(BaseModel):
    connection_id: str
    redirect_url: str


class ConnectionStatusRequest(BaseModel):
    user_id: str = Field(default="default")
    connection_id: str


class ConnectionStatusResponse(BaseModel):
    status: str
    connected: bool


class ConnectionExistsResponse(BaseModel):
    exists: bool
    user_id: str


class SendEmailRequest(BaseModel):
    user_id: str = Field(default="default")
    recipient_email: str
    subject: str
    body: str
    attachment: Optional[str] = None


class FetchEmailsRequest(BaseModel):
    user_id: str = Field(default="default")
    limit: int = Field(default=5, ge=1, le=50)


class CreateDraftRequest(BaseModel):
    user_id: str = Field(default="default")
    recipient_email: str
    subject: str
    body: str


class ToolExecutionResponse(BaseModel):
    successful: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    user_id: str = Field(default="pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58")
    auto_execute: bool = Field(default=True)
    conversation_history: Optional[List[dict]] = None
    session_id: Optional[str] = None


# ========== Session Models ==========


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="default")
    title: Optional[str] = None


class MessageModel(BaseModel):
    id: str
    role: str
    content: str
    action: Optional[str] = None
    success: Optional[bool] = None
    created_at: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    messages: List[MessageModel] = []


class SessionSummary(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int
    preview: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: List[SessionSummary]


class AddMessageRequest(BaseModel):
    role: str
    content: str
    action: Optional[str] = None
    success: Optional[bool] = None


class UpdateSessionRequest(BaseModel):
    title: str


# ========== PDF Models ==========


class GeneratePDFRequest(BaseModel):
    topic: Optional[str] = None
    logo_url: Optional[str] = None


# ========== Email Analysis Models ==========


class EmailAnalysisRequest(BaseModel):
    user_id: str = Field(default="default")
    email_content: str
    user_query: Optional[str] = ""
    generate_pdf: bool = Field(default=True)
    auto_execute: bool = Field(default=True)


class EmailAnalysisResponse(BaseModel):
    success: bool
    status: str
    stages: Optional[dict] = None
    final_report: Optional[str] = None
    pdf_path: Optional[str] = None
    error: Optional[str] = None
    reply_sent: Optional[dict] = None


class FetchSpecificEmailRequest(BaseModel):
    user_id: str = Field(default="default")
    email_id: str
    query: Optional[str] = ""


# ========== GIPA Models ==========


class GIPAStartRequest(BaseModel):
    session_id: str = Field(default="default")


class GIPAAnswerRequest(BaseModel):
    session_id: str = Field(default="default")
    answer: str


class GIPAGenerateRequest(BaseModel):
    session_id: str = Field(default="default")


class GIPAExpandKeywordsRequest(BaseModel):
    keywords: List[str] = Field(min_length=1)


class GIPAResponse(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    document: Optional[str] = None
    html_body: Optional[str] = None
    draft_recipient: Optional[str] = None
    draft_subject: Optional[str] = None
    error: Optional[str] = None


# ========== Dossier Models ==========


class DossierGenerateRequest(BaseModel):
    name: str
    linkedin_url: str = Field(default="")
    meeting_context: str = Field(default="")
    dossier_id: str = Field(default="default")


class DossierUpdateRequest(BaseModel):
    additional_context: str
    dossier_id: str = Field(default="default")


class DossierStatusRequest(BaseModel):
    dossier_id: str = Field(default="default")


class DossierResponse(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    document: Optional[str] = None
    error: Optional[str] = None


# ========== LinkedIn Models ==========


class LinkedInPostRequest(BaseModel):
    user_id: str = Field(default="default")
    author: str
    commentary: str
    visibility: str = Field(default="PUBLIC")
    lifecycle_state: str = Field(default="PUBLISHED")
    is_reshare_disabled: bool = Field(default=False)


class LinkedInDeletePostRequest(BaseModel):
    user_id: str = Field(default="default")
    share_id: str


class LinkedInMyInfoRequest(BaseModel):
    user_id: str = Field(default="default")


class LinkedInCompanyInfoRequest(BaseModel):
    user_id: str = Field(default="default")
    count: Optional[int] = None
    role: Optional[str] = None
    start: Optional[int] = None
    state: Optional[str] = None

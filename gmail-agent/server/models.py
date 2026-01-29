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
    user_id: str = Field(default="default")
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

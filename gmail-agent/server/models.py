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

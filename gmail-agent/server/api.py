import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import ComposioClient
from .models import (
    CreateConnectionRequest, CreateConnectionResponse,
    ConnectionStatusRequest, ConnectionStatusResponse, ConnectionExistsResponse,
    SendEmailRequest, FetchEmailsRequest, CreateDraftRequest,
    ToolExecutionResponse, ChatRequest,
)
from .auth import create_connection, check_connected_account_exists, get_connection_status
from .actions import send_email, fetch_emails, create_draft
from .chatbot import chat


def create_app() -> FastAPI:
    app = FastAPI(title="Gmail Agent API", version="2.0.0")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    def root():
        return {
            "message": "Gmail Agent API",
            "version": "2.0.0",
            "docs": "/docs"
        }
    
    @app.get("/health")
    def health_check():
        return {"status": "healthy"}
    
    @app.post("/connection/exists", response_model=ConnectionExistsResponse)
    def connection_exists(composio_client: ComposioClient) -> ConnectionExistsResponse:
        user_id = "default"
        exists = check_connected_account_exists(composio_client, user_id)
        return ConnectionExistsResponse(exists=exists, user_id=user_id)
    
    @app.post("/connection/create", response_model=CreateConnectionResponse)
    def _create_connection(request: CreateConnectionRequest, composio_client: ComposioClient) -> CreateConnectionResponse:
        try:
            conn = create_connection(composio_client, request.user_id, request.auth_config_id)
            return CreateConnectionResponse(connection_id=conn.id, redirect_url=conn.redirect_url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/connection/status", response_model=ConnectionStatusResponse)
    def _connection_status(request: ConnectionStatusRequest, composio_client: ComposioClient) -> ConnectionStatusResponse:
        try:
            conn = get_connection_status(composio_client, request.connection_id)
            return ConnectionStatusResponse(status=conn.status, connected=conn.status == "ACTIVE")
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))
    
    def validate_user(user_id: str, composio_client) -> str:
        if check_connected_account_exists(composio_client, user_id):
            return user_id
        raise HTTPException(status_code=404, detail=f"No connection for user: {user_id}")
    
    @app.post("/actions/send_email", response_model=ToolExecutionResponse)
    def _send_email(request: SendEmailRequest, composio_client: ComposioClient) -> ToolExecutionResponse:
        try:
            user_id = validate_user(request.user_id, composio_client)
            result = send_email(composio_client, user_id, request.recipient_email, request.subject, request.body)
            return ToolExecutionResponse(successful=True, data=result)
        except HTTPException:
            raise
        except Exception as e:
            return ToolExecutionResponse(successful=False, error=str(e))
    
    @app.post("/actions/fetch_emails", response_model=ToolExecutionResponse)
    def _fetch_emails(request: FetchEmailsRequest, composio_client: ComposioClient) -> ToolExecutionResponse:
        try:
            user_id = validate_user(request.user_id, composio_client)
            result = fetch_emails(composio_client, user_id, request.limit)
            return ToolExecutionResponse(successful=True, data=result)
        except HTTPException:
            raise
        except Exception as e:
            return ToolExecutionResponse(successful=False, error=str(e))
    
    @app.post("/actions/create_draft", response_model=ToolExecutionResponse)
    def _create_draft(request: CreateDraftRequest, composio_client: ComposioClient) -> ToolExecutionResponse:
        try:
            user_id = validate_user(request.user_id, composio_client)
            result = create_draft(composio_client, user_id, request.recipient_email, request.subject, request.body)
            return ToolExecutionResponse(successful=True, data=result)
        except HTTPException:
            raise
        except Exception as e:
            return ToolExecutionResponse(successful=False, error=str(e))
    
    @app.post("/chat")
    async def _chat(request: ChatRequest, composio_client: ComposioClient):
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
        
        try:
            if request.auto_execute:
                validate_user(request.user_id, composio_client)
            return await chat(request.message, groq_api_key, request.user_id, request.conversation_history, request.auto_execute)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return app


app = create_app()

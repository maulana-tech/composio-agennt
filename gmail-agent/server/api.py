import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
import shutil

from .dependencies import ComposioClient
from .models import (
    CreateConnectionRequest, CreateConnectionResponse,
    ConnectionStatusRequest, ConnectionStatusResponse, ConnectionExistsResponse,
    SendEmailRequest, FetchEmailsRequest, CreateDraftRequest,
    ToolExecutionResponse, ChatRequest,
    CreateSessionRequest, SessionResponse, SessionListResponse, 
    AddMessageRequest, UpdateSessionRequest, GeneratePDFRequest,
)
from .auth import create_connection, check_connected_account_exists, get_connection_status
from .actions import send_email, fetch_emails, create_draft
from .chatbot import chat, chat_stream
from . import sessions


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
    
    # ========== Session Endpoints ==========
    
    @app.post("/sessions", response_model=SessionResponse)
    def create_session(request: CreateSessionRequest):
        """Create a new chat session."""
        session = sessions.create_session(request.user_id, request.title)
        return SessionResponse(**session)
    
    @app.get("/sessions/{user_id}", response_model=SessionListResponse)
    def list_user_sessions(user_id: str, limit: int = 50):
        """List all sessions for a user."""
        session_list = sessions.list_sessions(user_id, limit)
        return SessionListResponse(sessions=session_list)
    
    @app.get("/session/{session_id}", response_model=SessionResponse)
    def get_session(session_id: str):
        """Get a session with all messages."""
        session = sessions.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(**session)
    
    @app.post("/session/{session_id}/message")
    def add_message_to_session(session_id: str, request: AddMessageRequest):
        """Add a message to a session."""
        message = sessions.add_message(
            session_id, 
            request.role, 
            request.content, 
            request.action, 
            request.success
        )
        return message
    
    @app.put("/session/{session_id}")
    def update_session(session_id: str, request: UpdateSessionRequest):
        """Update session title."""
        success = sessions.update_session_title(session_id, request.title)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True}
    
    @app.delete("/session/{session_id}")
    def delete_session(session_id: str):
        """Delete a session."""
        success = sessions.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True}
    
    # ========== PDF Generation Endpoint ==========
    
    @app.post("/generate-pdf")
    async def generate_pdf_endpoint(
        topic: Optional[str] = Form(None),
        logo: Optional[UploadFile] = File(None)
    ):
        """Generate a styled PDF report with optional logo."""
        from .tools.pdf_generator import generate_styled_report
        
        logo_path = None
        if logo:
            # Save uploaded logo temporarily
            upload_dir = "uploads"
            os.makedirs(upload_dir, exist_ok=True)
            logo_path = os.path.join(upload_dir, logo.filename)
            with open(logo_path, "wb") as f:
                shutil.copyfileobj(logo.file, f)
        
        try:
            result = generate_styled_report(topic=topic, logo_path=logo_path)
            return {"success": True, "path": result["path"], "topic": result["topic"], "colors": result["colors"]}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # Cleanup uploaded logo
            if logo_path and os.path.exists(logo_path):
                os.remove(logo_path)
    
    # ========== Connection Endpoints ==========
    
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
            
            # Get conversation history from session if provided
            conversation_history = request.conversation_history
            if request.session_id:
                session = sessions.get_session(request.session_id)
                if session:
                    conversation_history = [
                        {"role": m["role"], "content": m["content"]} 
                        for m in session["messages"]
                    ]
            
            result = await chat(request.message, groq_api_key, request.user_id, conversation_history, request.auto_execute)
            
            # Save messages to session if provided
            if request.session_id:
                sessions.add_message(request.session_id, "user", request.message)
                sessions.add_message(
                    request.session_id, 
                    "assistant", 
                    result.get("message", ""),
                    result.get("intent", {}).get("action"),
                    result.get("type") == "final_result"
                )
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/chat/stream")
    async def _chat_stream(request: ChatRequest, composio_client: ComposioClient):
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
            
        try:
            if request.auto_execute:
                validate_user(request.user_id, composio_client)
                
            # Get conversation history from session if provided
            conversation_history = request.conversation_history
            if request.session_id:
                session = sessions.get_session(request.session_id)
                if session:
                    conversation_history = [
                        {"role": m["role"], "content": m["content"]} 
                        for m in session["messages"]
                    ]
            
            # Save user message immediately
            if request.session_id:
                sessions.add_message(request.session_id, "user", request.message)

            async def stream_wrapper():
                full_response = ""
                async for chunk in chat_stream(request.message, groq_api_key, request.user_id, conversation_history):
                    yield chunk
                    # Capture final content for saving history
                    # We might need to parse the chunks if we want to save purely the content
                    # But the 'token' events carry content.
                    # Or we can just trust the 'final_result' event.
                    
                    # Hack: parse JSON to find final message
                    try:
                        import json
                        data = json.loads(chunk)
                        if data.get("type") == "final_result":
                            full_response = data.get("message", "")
                        elif data.get("type") == "token":
                            # full_response += data.get("content", "") # accumulated in chat_stream too
                            pass
                    except: pass
                
                # Save assistant response after stream
                if request.session_id and full_response:
                    sessions.add_message(request.session_id, "assistant", full_response, None, True)

            return StreamingResponse(stream_wrapper(), media_type="application/x-ndjson")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()

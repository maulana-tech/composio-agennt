"""
Session management for chat history persistence.
Uses SQLite for lightweight local storage.
"""
import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

DATABASE_PATH = "sessions.db"


def init_database():
    """Initialize the SQLite database with required tables."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                action TEXT,
                success INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        
        conn.commit()


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_session(user_id: str, title: Optional[str] = None) -> Dict:
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, title or "New Chat", now, now)
        )
        conn.commit()
    
    return {
        "id": session_id,
        "user_id": user_id,
        "title": title or "New Chat",
        "created_at": now,
        "updated_at": now,
        "messages": []
    }


def get_session(session_id: str) -> Optional[Dict]:
    """Get a session with all its messages."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get session
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session_row = cursor.fetchone()
        
        if not session_row:
            return None
        
        # Get messages
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        )
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "action": row["action"],
                "success": bool(row["success"]) if row["success"] is not None else None,
                "created_at": row["created_at"]
            })
        
        return {
            "id": session_row["id"],
            "user_id": session_row["user_id"],
            "title": session_row["title"],
            "created_at": session_row["created_at"],
            "updated_at": session_row["updated_at"],
            "messages": messages
        }


def list_sessions(user_id: str, limit: int = 50) -> List[Dict]:
    """List all sessions for a user, most recent first."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.*, 
                   (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count,
                   (SELECT content FROM messages WHERE session_id = s.id ORDER BY created_at ASC LIMIT 1) as first_message
            FROM sessions s 
            WHERE user_id = ? 
            ORDER BY updated_at DESC 
            LIMIT ?
            """,
            (user_id, limit)
        )
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row["message_count"],
                "preview": row["first_message"][:100] if row["first_message"] else None
            })
        
        return sessions


def add_message(session_id: str, role: str, content: str, action: str = None, success: bool = None) -> Dict:
    """Add a message to a session."""
    message_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Insert message
        cursor.execute(
            "INSERT INTO messages (id, session_id, role, content, action, success, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, action, 1 if success else (0 if success is False else None), now)
        )
        
        # Update session title if it's the first user message
        cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'user'", (session_id,))
        user_msg_count = cursor.fetchone()[0]
        
        if user_msg_count == 1 and role == "user":
            # Auto-generate title from first message
            title = content[:50] + "..." if len(content) > 50 else content
            cursor.execute("UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?", (title, now, session_id))
        else:
            cursor.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        
        conn.commit()
    
    return {
        "id": message_id,
        "role": role,
        "content": content,
        "action": action,
        "success": success,
        "created_at": now
    }


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_session_title(session_id: str, title: str) -> bool:
    """Update session title."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, datetime.utcnow().isoformat(), session_id)
        )
        conn.commit()
        return cursor.rowcount > 0


# Initialize database on module load
init_database()

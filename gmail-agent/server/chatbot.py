import os
import json
import httpx

SYSTEM_PROMPT = """Kamu adalah asisten email. Parse pesan user dan tentukan action yang diinginkan.

Available actions:
- send_email: Kirim email (butuh: recipient_email, subject, body)
- create_draft: Buat draft email (butuh: recipient_email, subject, body)  
- fetch_emails: Ambil email terbaru (optional: limit)

Jika user tidak kasih email penerima, tanya dulu. Buat subject dan body yang profesional.

Respond dalam JSON:
{
    "action": "send_email|create_draft|fetch_emails",
    "recipient_email": "email@example.com",
    "recipient_name": "Nama",
    "subject": "Subject",
    "body": "Isi email",
    "limit": 5,
    "need_more_info": false,
    "question": "Pertanyaan jika butuh info"
}
"""


async def parse_intent_with_groq(user_message: str, groq_api_key: str, conversation_history: list = None) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            },
            timeout=30.0
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)


async def execute_email_action(intent: dict, user_id: str, base_url: str = "http://localhost:8000") -> dict:
    action = intent.get("action")
    
    async with httpx.AsyncClient() as client:
        if action == "send_email":
            response = await client.post(f"{base_url}/actions/send_email", json={
                "user_id": user_id,
                "recipient_email": intent["recipient_email"],
                "subject": intent["subject"],
                "body": intent["body"]
            })
        elif action == "create_draft":
            response = await client.post(f"{base_url}/actions/create_draft", json={
                "user_id": user_id,
                "recipient_email": intent["recipient_email"],
                "subject": intent["subject"],
                "body": intent["body"]
            })
        elif action == "fetch_emails":
            response = await client.post(f"{base_url}/actions/fetch_emails", json={
                "user_id": user_id,
                "limit": intent.get("limit", 5)
            })
        else:
            return {"error": f"Unknown action: {action}"}
        
        return response.json()


async def chat(user_message: str, groq_api_key: str, user_id: str, conversation_history: list = None, auto_execute: bool = True) -> dict:
    intent = await parse_intent_with_groq(user_message, groq_api_key, conversation_history)
    
    if intent.get("need_more_info"):
        return {"type": "question", "message": intent.get("question", "Bisa kasih info lebih detail?"), "intent": intent}
    
    if auto_execute and intent.get("action"):
        result = await execute_email_action(intent, user_id)
        return {"type": "action_result", "action": intent["action"], "intent": intent, "result": result}
    
    return {"type": "intent_parsed", "intent": intent}

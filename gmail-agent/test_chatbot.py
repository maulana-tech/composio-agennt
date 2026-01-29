import os
import asyncio
from server.chatbot import chat
from dotenv import load_dotenv

load_dotenv()

async def test_chat():
    groq_api_key = os.environ.get("GROQ_API_KEY")
    user_id = "default"
    
    print("--- Test: Research & Email ---")
    res = await chat(
        user_message="Cari detail lengkap UU Perlindungan Data Pribadi (UU PDP) Indonesia terbaru. Buat rangkuman PDF yang bagus dan kirimkan ke developerlana0@gmail.com.",
        groq_api_key=groq_api_key,
        user_id=user_id,
        conversation_history=[]
    )
    print(res["message"])
    
    # We won't run full flow to save tokens/time, but this confirms the search tool works.

if __name__ == "__main__":
    asyncio.run(test_chat())

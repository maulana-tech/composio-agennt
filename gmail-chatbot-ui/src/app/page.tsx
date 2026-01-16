"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: string;
  success?: boolean;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Halo! Saya asisten email kamu.\n\n• Kirim email\n• Buat draft\n• Ambil email terbaru\n\nContoh: \"Kirim email ke john@example.com tentang meeting besok\"",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const userId = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58";
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const currentInput = input;
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: "user", content: currentInput }]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: currentInput, user_id: userId, auto_execute: true }),
      });

      const data = await response.json();
      let content = "";
      let action = "";
      let success = false;

      if (data.type === "action_result") {
        action = data.action;
        success = data.result?.successful;

        if (data.action === "send_email" && success) {
          content = `✅ Email terkirim!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}\n\n${data.intent.body}`;
        } else if (data.action === "create_draft" && success) {
          content = `✅ Draft dibuat!\n\n📧 ${data.intent.recipient_email}\n📝 ${data.intent.subject}`;
        } else if (data.action === "fetch_emails" && success) {
          const emails = data.result?.data?.data?.messages || [];
          if (emails.length > 0) {
            content = `📬 ${emails.length} email:\n\n`;
            emails.forEach((email: { subject: string; sender: string; preview?: { body: string } }, i: number) => {
              content += `${i + 1}. ${email.subject}\n   ${email.sender}\n\n`;
            });
          } else {
            content = "📭 Tidak ada email.";
          }
        } else {
          content = `❌ Gagal: ${data.result?.error || "Unknown error"}`;
        }
      } else if (data.type === "question") {
        content = data.message;
      } else if (data.detail) {
        content = `❌ ${data.detail}`;
      }

      setMessages((prev) => [...prev, { id: (Date.now() + 1).toString(), role: "assistant", content, action, success }]);
    } catch (error) {
      setMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `❌ ${error instanceof Error ? error.message : "Connection failed"}`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      <header className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-semibold text-white">📧 Gmail Chatbot</h1>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            Connected
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto p-4">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === "user" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-100 border border-gray-700"
              }`}>
                <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content}</pre>
                {msg.action && (
                  <div className={`mt-2 text-xs ${msg.success ? "text-green-400" : "text-red-400"}`}>
                    {msg.action}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 border border-gray-700 rounded-2xl px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></span>
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></span>
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>

      <footer className="bg-gray-800 border-t border-gray-700 p-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Ketik pesan..."
              className="flex-1 bg-gray-700 text-white rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-400"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl font-medium transition-colors"
            >
              Kirim
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}

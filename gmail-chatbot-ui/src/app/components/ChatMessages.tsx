"use client";

import { Message } from "../types";
import { RefObject } from "react";

interface ChatMessagesProps {
  messages: Message[];
  isLoading: boolean;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  compact?: boolean;
}

export default function ChatMessages({ messages, isLoading, messagesEndRef, compact = false }: ChatMessagesProps) {
  return (
    <>
      {messages.map((msg) => (
        <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
          <div
            className={`${compact ? "max-w-[85%]" : "max-w-[80%]"} rounded-2xl ${compact ? "px-4 py-2.5" : "px-5 py-3"} ${
              msg.role === "user"
                ? "bg-gradient-to-r from-teal-500 to-cyan-500 text-white"
                : "bg-[#1a2332]/80 backdrop-blur-sm text-gray-100 border border-gray-700/50"
            }`}
          >
            <pre className={`whitespace-pre-wrap font-sans text-sm ${!compact && "leading-relaxed"}`}>{msg.content}</pre>
            <p className={`text-xs mt-1 ${msg.role === "user" ? "text-teal-100" : "text-gray-500"}`}>{msg.timestamp}</p>
          </div>
        </div>
      ))}
      {isLoading && (
        <div className="flex justify-start">
          <div className="bg-[#1a2332]/80 border border-gray-700/50 rounded-2xl px-4 py-3">
            <div className="flex gap-1.5">
              <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce"></span>
              <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></span>
              <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></span>
            </div>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </>
  );
}

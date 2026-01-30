"use client";

import { Message } from "../types";
import { RefObject } from "react";
import ReactMarkdown from "react-markdown";

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
            {msg.role === "user" ? (
              <pre className={`whitespace-pre-wrap font-sans text-sm ${!compact && "leading-relaxed"}`}>{msg.content}</pre>
            ) : (
              <div className={`prose prose-sm prose-invert max-w-none ${!compact && "leading-relaxed"}`}>
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-teal-400 hover:text-teal-300 underline underline-offset-2"
                      >
                        {children}
                      </a>
                    ),
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                    ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                    li: ({ children }) => <li className="text-gray-200">{children}</li>,
                    h1: ({ children }) => <h1 className="text-lg font-bold mb-2 text-white">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-base font-bold mb-2 text-white">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-bold mb-1 text-white">{children}</h3>,
                    code: ({ children }) => (
                      <code className="bg-gray-800 px-1.5 py-0.5 rounded text-teal-300 text-xs">{children}</code>
                    ),
                    pre: ({ children }) => (
                      <pre className="bg-gray-800 p-3 rounded-lg overflow-x-auto my-2">{children}</pre>
                    ),
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              </div>
            )}
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

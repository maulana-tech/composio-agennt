"use client";

import { SparkleIcon, SendIcon, AttachIcon } from "./icons";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
  placeholder?: string;
  compact?: boolean;
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  isLoading,
  placeholder = "Ask me anything...",
  compact = false,
}: ChatInputProps) {
  return (
    <div className={`bg-[#1a2332]/80 backdrop-blur-sm rounded-2xl border border-gray-700/50 ${compact ? "p-3" : "p-4"}`}>
      <div className="flex items-center gap-3">
        <div className="text-teal-400">
          <SparkleIcon />
        </div>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSend()}
          placeholder={placeholder}
          className={`flex-1 bg-transparent text-gray-200 placeholder-gray-500 focus:outline-none ${compact ? "text-sm" : "text-lg"}`}
          disabled={isLoading}
        />
        {compact && (
          <button
            onClick={onSend}
            disabled={isLoading || !value.trim()}
            className="w-9 h-9 bg-teal-500 hover:bg-teal-400 disabled:bg-gray-600 rounded-lg flex items-center justify-center transition-colors"
          >
            <SendIcon />
          </button>
        )}
      </div>
      {!compact && (
        <div className="flex items-center justify-between mt-4">
          <button className="flex items-center gap-2 text-gray-400 hover:text-gray-300 transition-colors text-sm px-3 py-1.5 rounded-lg hover:bg-gray-700/30">
            <AttachIcon /> Attach file
          </button>
          <button
            onClick={onSend}
            disabled={isLoading || !value.trim()}
            className="w-10 h-10 bg-teal-500 hover:bg-teal-400 disabled:bg-gray-600 rounded-xl flex items-center justify-center transition-colors"
          >
            <SendIcon />
          </button>
        </div>
      )}
    </div>
  );
}

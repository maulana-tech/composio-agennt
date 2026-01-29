"use client";

import { suggestions, getCardColor } from "../utils/constants";
import ChatInput from "./ChatInput";

interface WelcomeScreenProps {
  input: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
}

export default function WelcomeScreen({ input, onInputChange, onSend, isLoading }: WelcomeScreenProps) {
  return (
    <div className="w-full max-w-3xl flex flex-col items-center">
      {/* 3D Sphere */}
      <div className="relative w-56 h-56 mb-6">
        <div className="absolute inset-0 rounded-full bg-gradient-to-b from-teal-500/20 via-cyan-500/10 to-transparent blur-xl" />
        <div className="absolute inset-4 rounded-full bg-gradient-to-br from-slate-800/80 to-slate-900/80 border border-teal-500/20 overflow-hidden">
          <div className="absolute inset-0 opacity-30">
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="absolute inset-0 border border-teal-400/30 rounded-full"
                style={{ transform: `rotateX(${i * 22.5}deg)` }}
              />
            ))}
            {[...Array(8)].map((_, i) => (
              <div
                key={`v-${i}`}
                className="absolute inset-0 border border-teal-400/30 rounded-full"
                style={{ transform: `rotateY(${i * 22.5}deg)` }}
              />
            ))}
          </div>
          <div className="absolute top-1/4 left-1/4 w-1/2 h-1/2 bg-gradient-to-br from-teal-400/20 to-transparent rounded-full blur-md" />
        </div>
      </div>

      <h1 className="text-4xl font-light text-gray-100 mb-2">
        Hey! <span className="font-normal">User</span>
      </h1>
      <p className="text-2xl font-light text-gray-400 mb-10">What can I help with?</p>

      {/* Suggestion Cards */}
      <div className="flex gap-4 mb-10 flex-wrap justify-center">
        {suggestions.map((s, i) => (
          <button
            key={s.id}
            onClick={() => onInputChange(s.prompt)}
            className={`px-5 py-4 rounded-xl border backdrop-blur-sm transition-all duration-300 hover:scale-105 text-left min-w-[160px] bg-gradient-to-br ${getCardColor(i)}`}
          >
            <span className="text-2xl mb-2 block">{s.icon}</span>
            <span className="text-sm font-medium text-gray-200 block">{s.title}</span>
            <span className="text-xs text-gray-400">{s.description}</span>
          </button>
        ))}
      </div>

      {/* Input Box */}
      <div className="w-full max-w-2xl">
        <ChatInput value={input} onChange={onInputChange} onSend={onSend} isLoading={isLoading} />
      </div>
    </div>
  );
}

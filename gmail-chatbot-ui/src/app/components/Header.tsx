"use client";

import { Session } from "../types";
import { ChevronRightIcon } from "./icons";

interface HeaderProps {
  showHistory: boolean;
  sessionsCount: number;
  isAgentWorking: boolean;
  onShowHistory: () => void;
  onExitAgentView: () => void;
}

export default function Header({
  showHistory,
  sessionsCount,
  isAgentWorking,
  onShowHistory,
  onExitAgentView,
}: HeaderProps) {
  return (
    <header className="absolute top-0 right-0 z-20 flex items-center gap-3 p-4">
      {!showHistory && sessionsCount > 0 && (
        <button
          onClick={onShowHistory}
          className="text-gray-500 hover:text-gray-300 p-2 rounded-lg hover:bg-gray-800/50"
        >
          <ChevronRightIcon />
        </button>
      )}
      {isAgentWorking && (
        <button
          onClick={onExitAgentView}
          className="text-xs text-gray-500 hover:text-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-800/50"
        >
          Exit Agent View
        </button>
      )}
      <div className="flex items-center gap-2">
        <span className="text-gray-300 text-sm">User</span>
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center">
          <span className="text-white text-sm font-medium">U</span>
        </div>
      </div>
      {/* Just Chat logo and text */}
      <div className="flex items-center gap-1 ml-4">
        <img src="/justchat-logo.svg" alt="Just Chat Logo" className="w-7 h-7" />
        <span className="text-teal-300 text-xs font-bold tracking-wide">Just Chat</span>
      </div>
    </header>
  );
}

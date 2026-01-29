"use client";

import { Session } from "../types";
import { ChevronLeftIcon, PlusIcon, TrashIcon } from "./icons";
import { formatDate } from "../utils/constants";

interface HistorySidebarProps {
  show: boolean;
  sessions: Session[];
  currentSessionId: string | null;
  onClose: () => void;
  onNewChat: () => void;
  onLoadSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
}

export default function HistorySidebar({
  show,
  sessions,
  currentSessionId,
  onClose,
  onNewChat,
  onLoadSession,
  onDeleteSession,
}: HistorySidebarProps) {
  return (
    <div
      className={`bg-[#0d1321] border-r border-gray-800/50 flex flex-col transition-all duration-300 ${
        show ? "w-72" : "w-0 overflow-hidden"
      }`}
    >
      {show && (
        <>
          <div className="p-4 border-b border-gray-800/50">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-gray-200">Chat History</h2>
              <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
                <ChevronLeftIcon />
              </button>
            </div>
            <button
              onClick={onNewChat}
              className="w-full flex items-center gap-2 px-4 py-2.5 bg-teal-500/20 hover:bg-teal-500/30 text-teal-400 rounded-lg transition-colors"
            >
              <PlusIcon /> New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {sessions.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <p className="text-sm">No conversations yet</p>
              </div>
            ) : (
              <div className="space-y-1">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => onLoadSession(session.id)}
                    className={`group px-3 py-3 rounded-lg cursor-pointer transition-colors ${
                      currentSessionId === session.id
                        ? "bg-gray-800/70 border border-teal-500/30"
                        : "hover:bg-gray-800/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-200 truncate font-medium">
                          {session.title || "New Chat"}
                        </p>
                        {session.preview && (
                          <p className="text-xs text-gray-500 truncate mt-1">{session.preview}</p>
                        )}
                        <p className="text-xs text-gray-600 mt-1">{formatDate(session.updated_at)}</p>
                      </div>
                      <button
                        onClick={(e) => onDeleteSession(session.id, e)}
                        className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-all p-1"
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

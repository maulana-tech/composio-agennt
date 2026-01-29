"use client";

import { RefObject } from "react";
import { AgentLog, FilePreview, Message } from "../types";
import { SearchIcon, FileIcon, CheckIcon, AlertIcon, RefreshIcon, ExpandIcon, DownloadIcon, XIcon, ExtractIcon, GlobeIcon, MapIcon, MailIcon } from "./icons";
import { getLogTypeColor } from "../utils/constants";
import ChatMessages from "./ChatMessages";
import ChatInput from "./ChatInput";

interface AgentPanelLayoutProps {
  agentLogs: AgentLog[];
  messages: Message[];
  filePreview: FilePreview | null;
  input: string;
  isLoading: boolean;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onClearLogs: () => void;
  onClosePreview: () => void;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  logsEndRef: RefObject<HTMLDivElement | null>;
}

const getLogIcon = (type: string) => {
  switch (type) {
    case "search": return <SearchIcon />;
    case "extract": return <ExtractIcon />;
    case "crawl": return <GlobeIcon />;
    case "map": return <MapIcon />;
    case "email": return <MailIcon />;
    case "pdf": return <FileIcon />;
    default: return <SearchIcon />;
  }
};

export default function AgentPanelLayout({
  agentLogs,
  messages,
  filePreview,
  input,
  isLoading,
  onInputChange,
  onSend,
  onClearLogs,
  onClosePreview,
  messagesEndRef,
  logsEndRef,
}: AgentPanelLayoutProps) {
  return (
    <div className="flex-1 flex relative z-10">
      {/* Left Panel - Agent Logs */}
      <div className="flex-1 flex flex-col border-r border-gray-800/50">
        <div className="px-4 py-3 border-b border-gray-800/50 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300 flex items-center gap-2">
            <span className="w-2 h-2 bg-teal-400 rounded-full animate-pulse"></span>
            Agent Activity
          </h3>
          <button onClick={onClearLogs} className="text-xs text-gray-500 hover:text-gray-300">
            Clear
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {agentLogs.length === 0 ? (
            <div className="text-center py-8">
              <div className="w-12 h-12 rounded-full bg-gray-800/50 flex items-center justify-center mx-auto mb-3 text-gray-500">
                <SearchIcon />
              </div>
              <p className="text-gray-500 text-sm">Waiting for agent actions...</p>
            </div>
          ) : (
            agentLogs.map((log) => (
              <div key={log.id} className={`rounded-lg p-3 border ${getLogTypeColor(log.type)}`}>
                <div className="flex items-start gap-3">
                  <div className="p-1.5 rounded">{getLogIcon(log.type)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-gray-200">{log.title}</p>
                      {log.status === "running" ? (
                        <RefreshIcon />
                      ) : log.status === "success" ? (
                        <span className="text-green-400"><CheckIcon /></span>
                      ) : (
                        <span className="text-red-400"><AlertIcon /></span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">{log.detail}</p>
                    <p className="text-xs text-gray-600 mt-1">{log.timestamp}</p>
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Center Panel - Chat */}
      <div className="flex-1 flex flex-col border-r border-gray-800/50">
        <div className="px-4 py-3 border-b border-gray-800/50">
          <h3 className="text-sm font-medium text-gray-300">Conversation</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <ChatMessages messages={messages} isLoading={isLoading} messagesEndRef={messagesEndRef} compact />
        </div>
        <div className="p-3 border-t border-gray-800/50">
          <ChatInput
            value={input}
            onChange={onInputChange}
            onSend={onSend}
            isLoading={isLoading}
            placeholder="Type a message..."
            compact
          />
        </div>
      </div>

      {/* Right Panel - Preview */}
      <div className="flex-1 flex flex-col">
        <div className="px-4 py-3 border-b border-gray-800/50 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">Preview</h3>
          {filePreview && (
            <div className="flex items-center gap-1">
              <button className="p-1.5 text-gray-500 hover:text-gray-300 rounded"><ExpandIcon /></button>
              <button className="p-1.5 text-gray-500 hover:text-gray-300 rounded"><DownloadIcon /></button>
              <button onClick={onClosePreview} className="p-1.5 text-gray-500 hover:text-gray-300 rounded"><XIcon /></button>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {filePreview ? (
            <div className="h-full">
              {filePreview.type === "pdf" && filePreview.url && (
                <iframe src={filePreview.url} className="w-full h-full rounded-lg border border-gray-700/50" />
              )}
              {filePreview.type === "image" && filePreview.url && (
                <img src={filePreview.url} alt={filePreview.name} className="max-w-full rounded-lg" />
              )}
              {(filePreview.type === "text" || filePreview.type === "json") && (
                <pre className="text-xs text-gray-300 bg-gray-800/50 p-4 rounded-lg overflow-auto">
                  {filePreview.content}
                </pre>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 rounded-full bg-gray-800/50 flex items-center justify-center mb-3 text-gray-500">
                <FileIcon />
              </div>
              <p className="text-gray-500 text-sm">No preview available</p>
              <p className="text-gray-600 text-xs mt-1">PDFs, images, and files will appear here</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

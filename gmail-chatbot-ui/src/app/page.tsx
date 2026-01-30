"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { useChat } from "./hooks";
import {
  Sidebar,
  HistorySidebar,
  WelcomeScreen,
  AgentPanelLayout,
  ChatMessages,
  ChatInput,
  Header,
} from "./components";
import PDFExportButton from "./components/PDFExportButton";

export default function Home() {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  
  const {
    messages,
    input,
    isLoading,
    isConversationStarted,
    sessions,
    currentSessionId,
    showHistory,
    agentLogs,
    filePreview,
    isAgentWorking,
    setInput,
    setShowHistory,
    setAgentLogs,
    setFilePreview,
    setIsAgentWorking,
    fetchSessions,
    loadSession,
    deleteSession,
    startNewChat,
    sendMessage,
  } = useChat();

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Check if user is near bottom of chat container
  const handleScroll = useCallback(() => {
    const container = chatContainerRef.current;
    if (!container) return;
    
    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShouldAutoScroll(isNearBottom);
  }, []);

  // Auto-scroll only if user is at bottom (for regular chat view)
  useEffect(() => {
    if (shouldAutoScroll && !isAgentWorking) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, shouldAutoScroll, isAgentWorking]);

  const handleExitAgentView = () => {
    setIsAgentWorking(false);
    setAgentLogs([]);
    setFilePreview(null);
  };

  return (
    <div className="h-screen flex bg-[#0a0f1a] text-white overflow-hidden">
      {/* Main Sidebar */}
      <Sidebar
        showHistory={showHistory}
        onHomeClick={startNewChat}
        onHistoryClick={() => setShowHistory(!showHistory)}
      />

      {/* History Sidebar */}
      <HistorySidebar
        show={showHistory}
        sessions={sessions}
        currentSessionId={currentSessionId}
        onClose={() => setShowHistory(false)}
        onNewChat={startNewChat}
        onLoadSession={loadSession}
        onDeleteSession={deleteSession}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Header */}
        <Header
          showHistory={showHistory}
          sessionsCount={sessions.length}
          isAgentWorking={isAgentWorking}
          onShowHistory={() => setShowHistory(true)}
          onExitAgentView={handleExitAgentView}
        />

        <main className="flex-1 overflow-hidden">
          {!isConversationStarted ? (
            <div className="h-full flex items-center justify-center px-4">
              <WelcomeScreen
                input={input}
                isLoading={isLoading}
                onInputChange={setInput}
                onSend={() => sendMessage()}
              />
            </div>
          ) : isAgentWorking ? (
            <AgentPanelLayout
              messages={messages}
              agentLogs={agentLogs}
              filePreview={filePreview}
              isLoading={isLoading}
              input={input}
              onInputChange={setInput}
              onSend={() => sendMessage()}
              onClearLogs={() => setAgentLogs([])}
              onClosePreview={() => setFilePreview(null)}
              messagesEndRef={messagesEndRef}
              logsEndRef={logsEndRef}
            />
          ) : (
            <div className="h-full flex flex-col relative">
              <div 
                ref={chatContainerRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto py-6 px-4"
              >
                <div className="max-w-4xl mx-auto h-full">
                  <ChatMessages
                    messages={messages}
                    isLoading={isLoading}
                    messagesEndRef={messagesEndRef}
                  />
                  {/* PDF Export Button for last assistant message */}
                  {messages.length > 0 && messages[messages.length-1].role === "assistant" && messages[messages.length-1].content && (
                    <div className="mt-4 flex justify-end">
                      <PDFExportButton markdown={messages[messages.length-1].content} />
                    </div>
                  )}
                </div>
              </div>
              <div className="bg-[#0a0f1a] py-4 border-t border-gray-800/30 px-4">
                <div className="max-w-4xl mx-auto">
                    <ChatInput
                      value={input}
                      isLoading={isLoading}
                      onChange={setInput}
                      onSend={() => sendMessage()}
                    />
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

import { useState, useCallback } from "react";
import { Session, Message, AgentLog, FilePreview } from "../types";
import { API_URL, needsAgentPanel, detectLogType } from "../utils/constants";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isConversationStarted, setIsConversationStarted] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>([]);
  const [filePreview, setFilePreview] = useState<FilePreview | null>(null);
  const [isAgentWorking, setIsAgentWorking] = useState(false);
  const userId = "default";

  const fetchSessions = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/sessions/${userId}`);
      if (response.ok) {
        const data = await response.json();
        setSessions(data.sessions || []);
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  }, [userId]);

  const createSession = useCallback(async (): Promise<string | null> => {
    try {
      const response = await fetch(`${API_URL}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
      if (response.ok) {
        const data = await response.json();
        await fetchSessions();
        return data.id;
      }
    } catch (error) {
      console.error("Failed to create session:", error);
    }
    return null;
  }, [userId, fetchSessions]);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`${API_URL}/session/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setCurrentSessionId(sessionId);
        setMessages(data.messages || []);
        setIsConversationStarted(data.messages && data.messages.length > 0);
        setShowHistory(false);
        setAgentLogs([]);
        setIsAgentWorking(false);
      }
    } catch (error) {
      console.error("Failed to load session:", error);
    }
  }, []);

  const deleteSession = useCallback(async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const response = await fetch(`${API_URL}/session/${sessionId}`, { method: "DELETE" });
      if (response.ok) {
        await fetchSessions();
        if (currentSessionId === sessionId) {
          setMessages([]);
          setCurrentSessionId(null);
          setIsConversationStarted(false);
          setShowHistory(false);
          setAgentLogs([]);
          setFilePreview(null);
          setIsAgentWorking(false);
        }
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  }, [currentSessionId, fetchSessions]);

  const startNewChat = useCallback(() => {
    setMessages([]);
    setCurrentSessionId(null);
    setIsConversationStarted(false);
    setShowHistory(false);
    setAgentLogs([]);
    setFilePreview(null);
    setIsAgentWorking(false);
  }, []);

  const addAgentLog = useCallback((log: Omit<AgentLog, "id" | "timestamp">) => {
    const newLog: AgentLog = {
      ...log,
      id: Date.now().toString(),
      timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    };
    setAgentLogs((prev) => [...prev, newLog]);
    return newLog.id;
  }, []);

  const updateAgentLog = useCallback((id: string, updates: Partial<AgentLog>) => {
    setAgentLogs((prev) => prev.map((log) => (log.id === id ? { ...log, ...updates } : log)));
  }, []);

  const mapToolToLogType = (title: string): "search" | "extract" | "crawl" | "map" | "email" | "pdf" | "info" => {
    const lower = title.toLowerCase();
    if (lower.includes("search")) return "search";
    if (lower.includes("pdf") || lower.includes("document")) return "pdf";
    if (lower.includes("email") || lower.includes("mail") || lower.includes("draft")) return "email";
    if (lower.includes("visit") || lower.includes("browse") || lower.includes("webpage")) return "crawl";
    if (lower.includes("map") || lower.includes("location")) return "map";
    if (lower.includes("extract")) return "extract";
    return "info";
  };

  const sendMessage = useCallback(async (messageText?: string) => {
    const textToSend = messageText || input;
    if (!textToSend.trim() || isLoading) return;

    let sessionId = currentSessionId;
    if (!sessionId) {
      sessionId = await createSession();
      if (!sessionId) return;
      setCurrentSessionId(sessionId);
    }

    if (!isConversationStarted) setIsConversationStarted(true);

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: textToSend,
      timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Initial check for UI feedback
    if (needsAgentPanel(textToSend)) {
      setIsAgentWorking(true);
    }

    let logId: string | null = null;

    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: textToSend, user_id: userId, auto_execute: true, session_id: sessionId }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessageContent = "";
      let buffer = "";
      
      // Create empty assistant message to stream into
      const assistantMsgId = (Date.now() + 1).toString();
      setMessages((prev) => [...prev, {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
      }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer
        
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            
            if (data.type === "log") {
               if (data.status === "running") {
                  // Only create new log if we don't have an active one or it's a different tool
                  // For simplicity, we just add a new one for every "start" event
                  const type = mapToolToLogType(data.title || "Tool");
                  logId = addAgentLog({ 
                      type, 
                      title: data.title || "Processing", 
                      detail: data.detail || "Working...", 
                      status: "running" 
                  });
                  if (!isAgentWorking) setIsAgentWorking(true);
               } else if (data.status === "success" && logId) {
                  updateAgentLog(logId, { status: "success", detail: data.detail || "Completed" });
                  logId = null; 
               }
            } 
            else if (data.type === "token") {
               assistantMessageContent += data.content;
               setMessages((prev) => prev.map(msg => 
                 msg.id === assistantMsgId ? { ...msg, content: assistantMessageContent } : msg
               ));
            }
            else if (data.type === "final_result") {
               if (!assistantMessageContent) {
                   assistantMessageContent = data.message;
                   setMessages((prev) => prev.map(msg => 
                     msg.id === assistantMsgId ? { ...msg, content: assistantMessageContent } : msg
                   ));
               }
               // Maybe update last log if pending
               if (logId) updateAgentLog(logId, { status: "success" });
            }
             else if (data.type === "error") {
               if (logId) updateAgentLog(logId, { status: "error", detail: data.message });
               assistantMessageContent += `\n❌ ${data.message}`;
               setMessages((prev) => prev.map(msg => 
                 msg.id === assistantMsgId ? { ...msg, content: assistantMessageContent } : msg
               ));
            }

          } catch (e) {
            console.error("Error parsing JSON chunk", e);
          }
        }
      }

      await fetchSessions();
    } catch (error) {
      if (logId) updateAgentLog(logId, { status: "error", detail: "Connection failed" });
      
      setMessages((prev) => {
         const last = prev[prev.length - 1];
         // Check if we are upgrading the streaming message or adding a new error
         if (last.role === "assistant" && (last.id === (Date.now() + 1).toString() || last.content === "")) {
              // We likely have the streaming message ID reference, but we can't clear access it safely here due to closure.
              // Instead, we just append to the active message if it exists and is the assistant's.
              return prev.map((msg, i) => i === prev.length - 1 && msg.role === 'assistant' 
                  ? { ...msg, content: msg.content + `\n❌ ${error instanceof Error ? error.message : "Connection failed"}` } 
                  : msg);
         }
         return [...prev, {
            id: (Date.now() + 1).toString(),
            role: "assistant",
            content: `❌ ${error instanceof Error ? error.message : "Connection failed"}`,
            timestamp: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
         }];
      });
    } finally {
      setIsLoading(false);
      setIsAgentWorking(false);
    }
  }, [input, isLoading, currentSessionId, isConversationStarted, createSession, addAgentLog, updateAgentLog, fetchSessions, userId]);

  return {
    // State
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
    
    // Setters
    setInput,
    setShowHistory,
    setAgentLogs,
    setFilePreview,
    setIsAgentWorking,
    
    // Actions
    fetchSessions,
    loadSession,
    deleteSession,
    startNewChat,
    sendMessage,
  };
}

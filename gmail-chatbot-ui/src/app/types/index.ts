// Types and Interfaces

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  action?: string;
  success?: boolean;
  timestamp?: string;
}

export interface Session {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  preview?: string;
}

export interface AgentLog {
  id: string;
  type: "search" | "extract" | "crawl" | "map" | "email" | "pdf" | "info";
  title: string;
  detail: string;
  timestamp: string;
  status: "running" | "success" | "error";
  data?: unknown;
}

export interface FilePreview {
  id: string;
  name: string;
  type: "pdf" | "image" | "text" | "json";
  url?: string;
  content?: string;
}

export interface SuggestionCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  prompt: string;
}

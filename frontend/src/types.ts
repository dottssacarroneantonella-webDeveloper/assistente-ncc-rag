export interface Source {
  rank: number;
  file: string;
  page: number;
  score: number;
  excerpt: string;
}

export interface ChatMessage {
  id: string;
  direction: "in" | "out";
  body: string;
  status: string;
  in_reply_to: string | null;
  sources: Source[];
  created_at: string;
}

export interface Conversation {
  id: string;
  welcome: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface DocumentItem {
  id: string;
  original_name: string;
  stored_name: string;
  size_bytes: number;
  pages: number | null;
  status: "uploaded" | "indexed" | "error";
  uploaded_at: string;
}

export interface IndexJob {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  chunks: number | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ConversationSummary {
  id: string;
  channel: "web" | "whatsapp";
  contact: string | null;
  messages: number;
  started_at: string;
  last_message_at: string;
}

export interface AdminMessage extends ChatMessage {
  kind: string;
  generator: string | null;
  processing_ms: number | null;
}

export interface UnansweredItem {
  id: string;
  question: string;
  conversation_id: string;
  asked_at: string;
  best_score: number | null;
  status: "open" | "handled";
  note: string | null;
  handled_at: string | null;
}

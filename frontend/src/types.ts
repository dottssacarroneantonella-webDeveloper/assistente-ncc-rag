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

import type {
  AdminMessage,
  ApiErrorBody,
  ChatMessage,
  Conversation,
  ConversationSummary,
  DocumentItem,
  IndexJob,
  Page,
  UnansweredItem,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

/** Valore del cookie csrf_token impostato dal server al login (double-submit). */
export function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (method !== "GET") headers.set("X-CSRF-Token", csrfToken());
  const response = await fetch(`${BASE}${path}`, { credentials: "same-origin", ...init, method, headers });
  if (!response.ok) {
    let code = "error";
    let message = `Errore ${response.status}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      code = body.error.code;
      message = body.error.message;
    } catch {
      /* risposta non JSON */
    }
    throw new ApiError(response.status, code, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  createConversation: () => request<Conversation>("/chat/conversations", { method: "POST" }),

  sendMessage: (conversationId: string, text: string) =>
    request<{ message_id: string }>(`/chat/conversations/${conversationId}/messages`, {
      method: "POST",
      body: json({ text }),
    }),

  listMessages: (conversationId: string, after?: string) => {
    const query = after ? `?after=${encodeURIComponent(after)}` : "";
    return request<{ items: ChatMessage[] }>(`/chat/conversations/${conversationId}/messages${query}`);
  },
};

export const adminApi = {
  login: (email: string, password: string) =>
    request<void>("/auth/login", { method: "POST", body: json({ email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<{ email: string }>("/auth/me"),

  documents: () => request<{ items: DocumentItem[] }>("/admin/documents"),
  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentItem>("/admin/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => request<void>(`/admin/documents/${id}`, { method: "DELETE" }),

  startIndexJob: () => request<IndexJob>("/admin/index-jobs", { method: "POST" }),
  indexJobs: (limit = 5) => request<{ items: IndexJob[] }>(`/admin/index-jobs?limit=${limit}`),
  indexJob: (id: string) => request<IndexJob>(`/admin/index-jobs/${id}`),

  conversations: (page: number, size: number, channel?: string) => {
    const params = new URLSearchParams({ page: String(page), size: String(size) });
    if (channel) params.set("channel", channel);
    return request<Page<ConversationSummary>>(`/admin/conversations?${params}`);
  },
  conversation: (id: string) =>
    request<{ conversation: ConversationSummary; messages: AdminMessage[] }>(`/admin/conversations/${id}`),

  unanswered: (status: "open" | "handled", page = 1, size = 20) =>
    request<Page<UnansweredItem>>(`/admin/unanswered?status=${status}&page=${page}&size=${size}`),
  updateUnanswered: (id: string, status: "open" | "handled", note: string | null) =>
    request<UnansweredItem>(`/admin/unanswered/${id}`, { method: "PATCH", body: json({ status, note }) }),
};

/** Attende la risposta a un messaggio interrogando l'API ogni `intervalMs` (polling). */
export async function waitForReply(
  conversationId: string,
  messageId: string,
  { intervalMs = 1000, timeoutMs = 60000 } = {},
): Promise<ChatMessage[]> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const { items } = await api.listMessages(conversationId);
    if (items.some((m) => m.in_reply_to === messageId)) return items;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new ApiError(504, "timeout", "La risposta sta impiegando troppo tempo. Riprova.");
}

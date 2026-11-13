import type { ApiErrorBody, ChatMessage, Conversation } from "./types";

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...init,
  });
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
  return (await response.json()) as T;
}

export const api = {
  createConversation: () => request<Conversation>("/chat/conversations", { method: "POST" }),

  sendMessage: (conversationId: string, text: string) =>
    request<{ message_id: string }>(`/chat/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  listMessages: (conversationId: string, after?: string) => {
    const query = after ? `?after=${encodeURIComponent(after)}` : "";
    return request<{ items: ChatMessage[] }>(`/chat/conversations/${conversationId}/messages${query}`);
  },
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

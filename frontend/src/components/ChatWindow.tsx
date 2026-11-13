import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, waitForReply } from "../api";
import type { ChatMessage, Conversation } from "../types";
import { MessageBubble } from "./MessageBubble";

const MAX_CHARS = 1000;
const SUGGESTIONS = [
  "Quanto costa il transfer dall'aeroporto di Bari a Monopoli?",
  "Accettate animali a bordo?",
  "Come posso disdire una prenotazione?",
];

const STORAGE_KEY = "assistente-ncc.conversation";

function loadStoredConversation(): Conversation | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Conversation) : null;
    return parsed && typeof parsed.id === "string" ? parsed : null;
  } catch {
    return null;
  }
}

function storeConversation(conversation: Conversation): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(conversation));
  } catch {
    /* storage non disponibile: la chat funziona comunque */
  }
}

function forgetConversation(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignorato */
  }
}

interface Props {
  businessName: string;
  pollIntervalMs?: number;
}

export function ChatWindow({ businessName, pollIntervalMs = 1000 }: Props) {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [welcome, setWelcome] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function start() {
      // la conversazione sopravvive al ricaricamento della pagina, ma non alla chiusura della scheda
      const stored = loadStoredConversation();
      if (stored) {
        try {
          const { items } = await api.listMessages(stored.id);
          if (cancelled) return;
          setConversationId(stored.id);
          setWelcome(stored.welcome);
          setMessages(items);
          return;
        } catch {
          forgetConversation(); // scaduta o cancellata: se ne crea una nuova
        }
      }
      const conversation = await api.createConversation();
      if (cancelled) return;
      storeConversation(conversation);
      setConversationId(conversation.id);
      setWelcome(conversation.welcome);
    }
    start().catch(() => !cancelled && setError("Il servizio non è raggiungibile. Riprova più tardi."));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, waiting]);

  async function send(text: string) {
    const question = text.trim();
    if (!conversationId || !question || waiting) return;
    setError(null);
    setDraft("");
    setWaiting(true);
    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      direction: "in",
      body: question,
      status: "received",
      in_reply_to: null,
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimistic]);
    try {
      const { message_id } = await api.sendMessage(conversationId, question);
      setMessages(await waitForReply(conversationId, message_id, { intervalMs: pollIntervalMs }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Errore di rete. Riprova.");
      setMessages((current) => current.filter((m) => m.id !== optimistic.id));
      setDraft(question);
    } finally {
      setWaiting(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  return (
    <section className="chat" aria-label={`Chat con ${businessName}`}>
      <header className="chat__header">
        <div className="chat__avatar" aria-hidden="true">🚗</div>
        <div>
          <h1 className="chat__title">{businessName}</h1>
          <p className="chat__subtitle">{waiting ? "sta scrivendo…" : "assistente virtuale · demo"}</p>
        </div>
      </header>

      <ol className="chat__messages" ref={listRef} aria-live="polite">
        {welcome && (
          <li className="bubble bubble--bot">
            <p className="bubble__text">{welcome}</p>
          </li>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {waiting && (
          <li className="bubble bubble--bot bubble--typing" aria-label="L'assistente sta scrivendo">
            <span />
            <span />
            <span />
          </li>
        )}
      </ol>

      {messages.length === 0 && conversationId && (
        <div className="chat__suggestions" role="group" aria-label="Domande di esempio">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" onClick={() => void send(s)} disabled={waiting}>
              {s}
            </button>
          ))}
        </div>
      )}

      {error && (
        <p className="chat__error" role="alert">
          {error}
        </p>
      )}

      <form className="chat__composer" onSubmit={onSubmit}>
        <label htmlFor="question" className="visually-hidden">
          Scrivi un messaggio
        </label>
        <input
          id="question"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Scrivi un messaggio"
          maxLength={MAX_CHARS}
          autoComplete="off"
          disabled={!conversationId}
        />
        <button type="submit" disabled={!conversationId || waiting || !draft.trim()} aria-label="Invia">
          ➤
        </button>
      </form>
    </section>
  );
}

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { adminApi } from "../api";
import type { AdminMessage, ConversationSummary } from "../types";
import { formatDateTime, STATUS_LABELS } from "./format";

export function ConversationDetailPage() {
  const { id = "" } = useParams();
  const [conversation, setConversation] = useState<ConversationSummary | null>(null);
  const [messages, setMessages] = useState<AdminMessage[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    adminApi
      .conversation(id)
      .then((data) => {
        setConversation(data.conversation);
        setMessages(data.messages);
      })
      .catch(() => setError(true));
  }, [id]);

  if (error)
    return (
      <p className="form-error" role="alert">
        Conversazione non trovata. <Link to="/admin/conversazioni">Torna all'elenco</Link>
      </p>
    );
  if (!conversation) return <p>Caricamento…</p>;

  return (
    <section>
      <p>
        <Link to="/admin/conversazioni">← Conversazioni</Link>
      </p>
      <h1>
        {conversation.channel === "web" ? "Chat web" : "WhatsApp"} {conversation.contact ?? ""}
      </h1>
      <p className="muted">
        Iniziata {formatDateTime(conversation.started_at)} · {conversation.messages} messaggi
      </p>
      <ol className="transcript">
        {messages.map((m) => (
          <li key={m.id} className={`transcript__item transcript__item--${m.direction}`}>
            <div className="transcript__meta">
              {m.direction === "in" ? "Cliente" : "Assistente"} · {formatDateTime(m.created_at)} ·{" "}
              {STATUS_LABELS[m.status] ?? m.status}
              {m.generator && ` · ${m.generator}`}
              {m.processing_ms != null && ` · ${m.processing_ms} ms`}
            </div>
            <p className="transcript__body">{m.body}</p>
            {m.sources.length > 0 && (
              <table className="table table--compact">
                <caption className="visually-hidden">Fonti della risposta</caption>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Fonte</th>
                    <th scope="col">Punteggio</th>
                    <th scope="col">Estratto</th>
                  </tr>
                </thead>
                <tbody>
                  {m.sources.map((s) => (
                    <tr key={s.rank}>
                      <td>{s.rank}</td>
                      <td>
                        {s.file} p.{s.page}
                      </td>
                      <td>{s.score.toFixed(3)}</td>
                      <td className="excerpt">{s.excerpt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router";
import { adminApi } from "../api";
import type { ConversationSummary, Page } from "../types";
import { formatDateTime } from "./format";

const SIZE = 20;

export function ConversationsPage() {
  const [channel, setChannel] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<ConversationSummary> | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    adminApi
      .conversations(page, SIZE, channel || undefined)
      .then(setData)
      .catch(() => setError(true));
  }, [page, channel]);

  const pages = data ? Math.max(1, Math.ceil(data.total / SIZE)) : 1;

  return (
    <section>
      <header className="page-header">
        <h1>Conversazioni</h1>
        <label className="page-header__actions">
          Canale
          <select
            value={channel}
            onChange={(e) => {
              setChannel(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Tutti</option>
            <option value="web">Chat web</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
        </label>
      </header>
      {error && (
        <p className="form-error" role="alert">
          Impossibile caricare le conversazioni.
        </p>
      )}
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Ultimo messaggio</th>
            <th scope="col">Canale</th>
            <th scope="col">Contatto</th>
            <th scope="col">Messaggi</th>
            <th scope="col">
              <span className="visually-hidden">Dettaglio</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {data?.items.length === 0 && (
            <tr>
              <td colSpan={5}>Nessuna conversazione.</td>
            </tr>
          )}
          {data?.items.map((c) => (
            <tr key={c.id}>
              <td>{formatDateTime(c.last_message_at)}</td>
              <td>{c.channel === "web" ? "Chat web" : "WhatsApp"}</td>
              <td>{c.contact ?? "–"}</td>
              <td>{c.messages}</td>
              <td>
                <Link to={`/admin/conversazioni/${c.id}`}>Apri</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <nav className="pager" aria-label="Pagine">
        <button type="button" className="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          ← Precedente
        </button>
        <span>
          Pagina {page} di {pages}
        </span>
        <button type="button" className="button" disabled={page >= pages} onClick={() => setPage(page + 1)}>
          Successiva →
        </button>
      </nav>
    </section>
  );
}

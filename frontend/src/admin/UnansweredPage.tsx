import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { adminApi, ApiError } from "../api";
import type { Page, UnansweredItem } from "../types";
import { formatDateTime } from "./format";

type Tab = "open" | "handled";

export function UnansweredPage() {
  const [tab, setTab] = useState<Tab>("open");
  const [data, setData] = useState<Page<UnansweredItem> | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    adminApi
      .unanswered(tab)
      .then(setData)
      .catch(() => setError("Impossibile caricare le domande."));
  }, [tab]);

  useEffect(load, [load]);

  async function setStatus(item: UnansweredItem, status: Tab) {
    try {
      await adminApi.updateUnanswered(item.id, status, notes[item.id]?.trim() || item.note);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Aggiornamento non riuscito.");
    }
  }

  return (
    <section>
      <header className="page-header">
        <h1>Domande senza risposta</h1>
      </header>
      <p className="muted">
        Domande a cui l'assistente non ha trovato risposta nei documenti: aggiungi l'informazione in un PDF,
        reindicizza e segna la domanda come gestita.
      </p>
      <div className="tabs" role="tablist" aria-label="Stato delle domande">
        {(["open", "handled"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            className={`tabs__tab${tab === value ? " tabs__tab--active" : ""}`}
            onClick={() => setTab(value)}
          >
            {value === "open" ? "Aperte" : "Gestite"}
            {tab === value && data ? ` (${data.total})` : ""}
          </button>
        ))}
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {data?.items.length === 0 && <p>{tab === "open" ? "Nessuna domanda aperta. 🎉" : "Nessuna domanda gestita."}</p>}
      <ul className="questions">
        {data?.items.map((item) => (
          <li key={item.id} className="card">
            <p className="questions__text">«{item.question}»</p>
            <p className="muted">
              {formatDateTime(item.asked_at)}
              {item.best_score != null && ` · punteggio migliore ${item.best_score.toFixed(3)}`} ·{" "}
              <Link to={`/admin/conversazioni/${item.conversation_id}`}>conversazione</Link>
            </p>
            {tab === "open" ? (
              <div className="questions__actions">
                <label>
                  <span className="visually-hidden">Nota per «{item.question}»</span>
                  <input
                    placeholder="Nota (facoltativa), es. aggiunto alle FAQ"
                    maxLength={500}
                    value={notes[item.id] ?? ""}
                    onChange={(e) => setNotes({ ...notes, [item.id]: e.target.value })}
                  />
                </label>
                <button type="button" className="button button--primary" onClick={() => void setStatus(item, "handled")}>
                  Segna come gestita
                </button>
              </div>
            ) : (
              <div className="questions__actions">
                <span>
                  Gestita il {formatDateTime(item.handled_at)}
                  {item.note && ` · ${item.note}`}
                </span>
                <button type="button" className="button" onClick={() => void setStatus(item, "open")}>
                  Riapri
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

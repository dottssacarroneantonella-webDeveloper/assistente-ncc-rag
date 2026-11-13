import { useCallback, useEffect, useRef, useState } from "react";
import { adminApi, ApiError } from "../api";
import type { DocumentItem, IndexJob } from "../types";
import { formatBytes, formatDateTime, STATUS_LABELS } from "./format";

const MAX_MB = 10;

export function DocumentsPage({ pollIntervalMs = 1500 }: { pollIntervalMs?: number }) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [jobs, setJobs] = useState<IndexJob[]>([]);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [docs, recent] = await Promise.all([adminApi.documents(), adminApi.indexJobs(5)]);
    setDocuments(docs.items);
    setJobs(recent.items);
    return recent.items;
  }, []);

  useEffect(() => {
    refresh().catch(() => setMessage({ kind: "error", text: "Impossibile caricare i documenti." }));
  }, [refresh]);

  // aggiorna lo stato finché c'è un job attivo
  const active = jobs.find((j) => j.status === "queued" || j.status === "running");
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void refresh(), pollIntervalMs);
    return () => clearInterval(timer);
  }, [active, refresh, pollIntervalMs]);

  async function onUpload(file: File) {
    if (file.size > MAX_MB * 1024 * 1024) {
      setMessage({ kind: "error", text: `Il file supera ${MAX_MB} MB.` });
      return;
    }
    setBusy(true);
    try {
      const document = await adminApi.uploadDocument(file);
      setMessage({ kind: "ok", text: `Caricato ${document.stored_name}. Avvia la reindicizzazione per usarlo.` });
      await refresh();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Caricamento non riuscito." });
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function onDelete(document: DocumentItem) {
    if (!window.confirm(`Eliminare ${document.stored_name}?`)) return;
    try {
      await adminApi.deleteDocument(document.id);
      setMessage({ kind: "ok", text: `Eliminato ${document.stored_name}. Reindicizza per aggiornare il bot.` });
      await refresh();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Eliminazione non riuscita." });
    }
  }

  async function onReindex() {
    try {
      await adminApi.startIndexJob();
      setMessage({ kind: "ok", text: "Reindicizzazione avviata." });
      await refresh();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Avvio non riuscito." });
    }
  }

  const pending = documents.some((d) => d.status !== "indexed");

  return (
    <section>
      <header className="page-header">
        <h1>Documenti</h1>
        <div className="page-header__actions">
          <label className="button">
            {busy ? "Caricamento…" : "Carica PDF"}
            <input
              ref={fileInput}
              type="file"
              accept="application/pdf"
              className="visually-hidden"
              disabled={busy}
              onChange={(e) => e.target.files?.[0] && void onUpload(e.target.files[0])}
            />
          </label>
          <button type="button" className="button button--primary" onClick={() => void onReindex()} disabled={!!active}>
            {active ? "Reindicizzazione in corso…" : "Reindicizza"}
          </button>
        </div>
      </header>

      {message && (
        <p className={message.kind === "ok" ? "notice" : "form-error"} role={message.kind === "ok" ? "status" : "alert"}>
          {message.text}
        </p>
      )}
      {pending && !active && <p className="notice">Ci sono documenti non ancora indicizzati.</p>}

      <table className="table">
        <thead>
          <tr>
            <th scope="col">File</th>
            <th scope="col">Pagine</th>
            <th scope="col">Dimensione</th>
            <th scope="col">Caricato</th>
            <th scope="col">Stato</th>
            <th scope="col">
              <span className="visually-hidden">Azioni</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.length === 0 && (
            <tr>
              <td colSpan={6}>Nessun documento caricato.</td>
            </tr>
          )}
          {documents.map((d) => (
            <tr key={d.id}>
              <td>{d.stored_name}</td>
              <td>{d.pages ?? "–"}</td>
              <td>{formatBytes(d.size_bytes)}</td>
              <td>{formatDateTime(d.uploaded_at)}</td>
              <td>
                <span className={`badge badge--${d.status}`}>{STATUS_LABELS[d.status]}</span>
              </td>
              <td>
                <button type="button" className="button button--danger" onClick={() => void onDelete(d)}>
                  Elimina<span className="visually-hidden"> {d.stored_name}</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Ultime reindicizzazioni</h2>
      <ul className="jobs">
        {jobs.map((j) => (
          <li key={j.id}>
            <span className={`badge badge--${j.status}`}>{STATUS_LABELS[j.status]}</span> {formatDateTime(j.created_at)}
            {j.chunks != null && ` · ${j.chunks} blocchi di testo`}
            {j.error && <span className="jobs__error"> · {j.error}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

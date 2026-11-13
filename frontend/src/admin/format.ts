export function formatDateTime(iso: string | null): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const STATUS_LABELS: Record<string, string> = {
  uploaded: "da indicizzare",
  indexed: "indicizzato",
  error: "errore",
  queued: "in coda",
  running: "in corso",
  done: "completato",
  failed: "fallito",
  answered: "risposta",
  not_found: "non trovata",
  sent: "inviato",
  received: "ricevuto",
  processing: "in elaborazione",
};

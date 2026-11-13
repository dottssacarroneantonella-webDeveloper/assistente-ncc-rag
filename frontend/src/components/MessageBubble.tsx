import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
}

/** Rimuove le citazioni inline "[file.pdf p.N]": le fonti sono mostrate sotto la risposta. */
function cleanBody(body: string): string {
  return body.replace(/\s*\[[^\]]+\.pdf p\.\d+\]/g, "").trim();
}

export function MessageBubble({ message }: Props) {
  const mine = message.direction === "in";
  const failed = message.status === "failed";
  const sources = Array.from(
    new Map(message.sources.map((s) => [`${s.file}#${s.page}`, s])).values(),
  );
  return (
    <li className={`bubble ${mine ? "bubble--mine" : "bubble--bot"}${failed ? " bubble--failed" : ""}`}>
      <p className="bubble__text">{mine ? message.body : cleanBody(message.body)}</p>
      {!mine && sources.length > 0 && (
        <details className="bubble__sources">
          <summary>Fonti ({sources.length})</summary>
          <ul>
            {sources.map((s) => (
              <li key={`${s.file}-${s.page}`} title={s.excerpt}>
                📄 {s.file}, pag. {s.page}
              </li>
            ))}
          </ul>
        </details>
      )}
      <time className="bubble__time" dateTime={message.created_at}>
        {formatTime(message.created_at)}
        {mine && <span aria-label={message.status === "received" ? "inviato" : "letto"}> ✓✓</span>}
      </time>
    </li>
  );
}

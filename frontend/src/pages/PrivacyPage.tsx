import { Link } from "react-router";

/** Informativa sintetica (RNF-07). Testo di esempio per un'attività fittizia: va adattato e
 * verificato da chi gestisce davvero il servizio prima di usarlo in produzione. */
export function PrivacyPage() {
  return (
    <main className="privacy">
      <article className="privacy__card">
        <p>
          <Link to="/">← Torna alla chat</Link>
        </p>
        <h1>Informativa privacy</h1>
        <p className="privacy__note">
          Questa è una demo con un'attività fittizia ("NCC Levante Transfer"). Il testo mostra come il progetto
          tratta i dati; non è un'informativa legale valida per un'attività reale.
        </p>

        <h2>Quali dati trattiamo</h2>
        <ul>
          <li>Il testo dei messaggi che scrivi all'assistente e le risposte generate.</li>
          <li>
            Per WhatsApp: il numero di telefono <strong>non viene salvato</strong>. Conserviamo solo un codice
            cifrato (HMAC-SHA256) che permette di riconoscere la stessa conversazione e le ultime 4 cifre.
          </li>
          <li>Nessun nome, nessuna posizione, nessun cookie di profilazione.</li>
        </ul>

        <h2>Perché</h2>
        <p>Solo per rispondere alle tue domande sul servizio e per migliorare i documenti su cui si basano le risposte.</p>

        <h2>Per quanto tempo</h2>
        <p>
          Le conversazioni vengono eliminate automaticamente dopo <strong>30 giorni</strong> dall'ultimo messaggio.
        </p>

        <h2>I tuoi diritti</h2>
        <p>
          Puoi cancellare in qualsiasi momento la tua conversazione scrivendo <strong>CANCELLA DATI</strong>, sia
          nella chat sia su WhatsApp. Per le altre richieste (accesso, rettifica, opposizione) puoi contattare il
          titolare del trattamento.
        </p>

        <h2>Chi vede i dati</h2>
        <p>
          Solo l'amministratore dell'attività, dall'area riservata. Con il generatore locale (Ollama) i messaggi non
          escono dal server; con un servizio esterno compatibile OpenAI la domanda e i brani dei documenti vengono
          inviati a quel fornitore.
        </p>
      </article>
    </main>
  );
}

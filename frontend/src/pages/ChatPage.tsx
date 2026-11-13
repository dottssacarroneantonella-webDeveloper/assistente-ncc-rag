import { Link } from "react-router";
import { ChatWindow } from "../components/ChatWindow";

const BUSINESS_NAME = "NCC Levante Transfer";

export function ChatPage() {
  return (
    <main className="page">
      <ChatWindow businessName={BUSINESS_NAME} />
      <p className="page__note">
        Demo con dati fittizi: l'assistente risponde solo usando i documenti dell'attività (listino, condizioni,
        FAQ) e cita le fonti. <strong>Non inserire dati personali.</strong> Scrivi <strong>CANCELLA DATI</strong>{" "}
        per eliminare la conversazione. <Link to="/privacy">Informativa privacy</Link>
      </p>
    </main>
  );
}

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatWindow } from "./ChatWindow";

const CONVERSATION = { id: "c1", welcome: "Ciao! Sono l'assistente virtuale." };
const QUESTION = { id: "m1", direction: "in", body: "Quanto costa Bari–Monopoli?", status: "answered",
  in_reply_to: null, sources: [], created_at: "2026-11-13T10:00:00Z" };
const REPLY = { id: "m2", direction: "out", body: "Il transfer costa 85 euro. [listino_2026.pdf p.1]",
  status: "answered", in_reply_to: "m1",
  sources: [{ rank: 1, file: "listino_2026.pdf", page: 1, score: 0.5, excerpt: "..." }],
  created_at: "2026-11-13T10:00:01Z" };

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

describe("ChatWindow", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    sessionStorage.clear();
    fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/chat/conversations") && init?.method === "POST") return json(CONVERSATION, 201);
      if (url.endsWith("/messages") && init?.method === "POST") return json({ message_id: "m1" }, 202);
      if (url.includes("/messages")) return json({ items: [QUESTION, REPLY] });
      return json({ error: { code: "not_found", message: "?" } }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => vi.unstubAllGlobals());

  it("mostra il messaggio di benvenuto", async () => {
    render(<ChatWindow businessName="NCC Levante Transfer" />);
    expect(await screen.findByText(CONVERSATION.welcome)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "NCC Levante Transfer" })).toBeInTheDocument();
  });

  it("invia una domanda e mostra risposta e fonti", async () => {
    render(<ChatWindow businessName="NCC" pollIntervalMs={10} />);
    await screen.findByText(CONVERSATION.welcome);
    await userEvent.type(screen.getByLabelText("Scrivi un messaggio"), QUESTION.body);
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    expect(await screen.findByText("Il transfer costa 85 euro.")).toBeInTheDocument();
    expect(screen.getByText(/listino_2026\.pdf, pag\. 1/)).toBeInTheDocument();
    const posted = fetchMock.mock.calls.find(([u, i]) => String(u).endsWith("/messages") && i?.method === "POST");
    expect(JSON.parse(String(posted?.[1]?.body))).toEqual({ text: QUESTION.body });
  });

  it("mostra un errore se il servizio non risponde", async () => {
    fetchMock.mockImplementationOnce(() => Promise.reject(new TypeError("offline")));
    render(<ChatWindow businessName="NCC" />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("non è raggiungibile"));
  });

  it("riprende la conversazione dopo il ricaricamento della pagina", async () => {
    sessionStorage.setItem("assistente-ncc.conversation", JSON.stringify(CONVERSATION));
    render(<ChatWindow businessName="NCC" />);
    expect(await screen.findByText("Il transfer costa 85 euro.")).toBeInTheDocument();
    const created = fetchMock.mock.calls.some(([u, i]) => String(u).endsWith("/chat/conversations") && i?.method === "POST");
    expect(created).toBe(false);
  });

  it("crea una nuova conversazione se quella salvata non esiste più", async () => {
    sessionStorage.setItem("assistente-ncc.conversation", JSON.stringify({ id: "scaduta", welcome: "vecchio" }));
    fetchMock.mockImplementationOnce(() => json({ error: { code: "conversation_not_found", message: "x" } }, 404));
    render(<ChatWindow businessName="NCC" />);
    expect(await screen.findByText(CONVERSATION.welcome)).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem("assistente-ncc.conversation")!).id).toBe("c1");
  });

  it("disabilita l'invio con il campo vuoto", async () => {
    render(<ChatWindow businessName="NCC" />);
    await screen.findByText(CONVERSATION.welcome);
    expect(screen.getByRole("button", { name: "Invia" })).toBeDisabled();
  });
});

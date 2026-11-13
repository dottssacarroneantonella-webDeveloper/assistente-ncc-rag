import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function json(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const DOCS = {
  items: [
    { id: "d1", original_name: "listino_2026.pdf", stored_name: "listino_2026.pdf", size_bytes: 2048,
      pages: 2, status: "indexed", uploaded_at: "2026-11-13T10:00:00Z" },
  ],
};
const JOBS = { items: [{ id: "j1", status: "done", chunks: 6, error: null, created_at: "2026-11-13T10:00:00Z",
  started_at: null, finished_at: null }] };
const OPEN = { items: [{ id: "u1", question: "Accettate cani?", conversation_id: "c1", asked_at: "2026-11-13T10:00:00Z",
  best_score: 0.04, status: "open", note: null, handled_at: null }], total: 1, page: 1, size: 20 };

let loggedIn: boolean;
let routes: Handler;

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  loggedIn = false;
  routes = (url, init) => {
    const method = init.method ?? "GET";
    if (url.endsWith("/auth/me")) return loggedIn ? json({ email: "admin@example.com" }) : json({ error: {} }, 401);
    if (url.endsWith("/auth/login")) {
      const body = JSON.parse(String(init.body));
      if (body.password === "giusta-e-lunga") {
        loggedIn = true;
        return json(null, 204);
      }
      return json({ error: { code: "invalid_credentials", message: "x" } }, 401);
    }
    if (url.endsWith("/admin/documents")) return json(DOCS);
    if (url.includes("/admin/index-jobs") && method === "POST") return json({ ...JOBS.items[0], status: "queued" }, 202);
    if (url.includes("/admin/index-jobs")) return json(JOBS);
    if (url.includes("/admin/unanswered/u1")) return json({ ...OPEN.items[0], status: "handled" });
    if (url.includes("/admin/unanswered")) return json(OPEN);
    return json({ error: { code: "not_found", message: "?" } }, 404);
  };
  vi.stubGlobal("fetch", vi.fn((url: string, init: RequestInit = {}) => Promise.resolve(routes(url, init))));
});

afterEach(() => vi.unstubAllGlobals());

describe("area admin", () => {
  it("senza login reindirizza alla pagina di accesso", async () => {
    renderAt("/admin/documenti");
    expect(await screen.findByRole("heading", { name: "Area riservata" })).toBeInTheDocument();
  });

  it("mostra un errore generico con credenziali errate", async () => {
    renderAt("/admin/login");
    await userEvent.type(await screen.findByLabelText("Email"), "admin@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "sbagliata");
    await userEvent.click(screen.getByRole("button", { name: "Accedi" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email o password non corrette.");
  });

  it("dopo il login mostra i documenti e invia il token CSRF", async () => {
    document.cookie = "csrf_token=abc123";
    renderAt("/admin/login");
    await userEvent.type(await screen.findByLabelText("Email"), "admin@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "giusta-e-lunga");
    await userEvent.click(screen.getByRole("button", { name: "Accedi" }));
    expect(await screen.findByRole("heading", { name: "Documenti" })).toBeInTheDocument();
    const row = (await screen.findByText("listino_2026.pdf")).closest("tr")!;
    expect(within(row).getByText("indicizzato")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Reindicizza" }));
    const fetchMock = vi.mocked(fetch);
    const post = fetchMock.mock.calls.find(([u, i]) => String(u).includes("index-jobs") && i?.method === "POST");
    expect(new Headers(post?.[1]?.headers).get("X-CSRF-Token")).toBe("abc123");
  });

  it("segna una domanda come gestita", async () => {
    loggedIn = true;
    renderAt("/admin/domande");
    expect(await screen.findByText("«Accettate cani?»")).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText(/Nota/), "Aggiunto alle condizioni");
    await userEvent.click(screen.getByRole("button", { name: "Segna come gestita" }));
    await waitFor(() => {
      const patch = vi.mocked(fetch).mock.calls.find(([, i]) => i?.method === "PATCH");
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ status: "handled", note: "Aggiunto alle condizioni" });
    });
  });
});

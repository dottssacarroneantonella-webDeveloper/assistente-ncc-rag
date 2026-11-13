/**
 * Controlli automatici di accessibilità (WCAG 2.1 A/AA) con axe-core sulle schermate principali.
 * Il contrasto dei colori richiede un browser reale (layout e CSS calcolati): in jsdom è escluso
 * e va verificato a mano o con Playwright.
 */
import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

async function violations(container: HTMLElement) {
  const results = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init: RequestInit = {}) => {
      if (url.endsWith("/chat/conversations") && init.method === "POST") return json({ id: "c1", welcome: "Ciao!" }, 201);
      if (url.endsWith("/auth/me")) return json({ error: { code: "unauthorized", message: "x" } }, 401);
      return json({ items: [] });
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("accessibilità", () => {
  it("chat demo", async () => {
    const { container } = renderAt("/");
    await screen.findByText("Ciao!");
    expect(await violations(container)).toEqual([]);
  });

  it("informativa privacy", async () => {
    const { container } = renderAt("/privacy");
    await screen.findByRole("heading", { name: "Informativa privacy" });
    expect(await violations(container)).toEqual([]);
  });

  it("login admin", async () => {
    const { container } = renderAt("/admin/login");
    await screen.findByRole("heading", { name: "Area riservata" });
    expect(await violations(container)).toEqual([]);
  });
});

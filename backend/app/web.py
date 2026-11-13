"""Pubblicazione del frontend compilato dalla stessa applicazione (demo con un solo servizio).

- ``/assets/*``: file con hash nel nome → cache lunga e immutabile;
- qualsiasi altro percorso non ``/api`` → ``index.html`` (routing lato client di React Router);
- le pagine HTML ricevono una Content-Security-Policy restrittiva: solo risorse dello stesso
  dominio, nessuno script inline, nessun frame.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

FRONTEND_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def mount_frontend(app: FastAPI, static_dir: Path, api_prefix: str) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"STATIC_DIR non contiene index.html: {root}")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith(api_prefix.strip("/")):
            raise StarletteHTTPException(status_code=404)
        candidate = (root / path).resolve()
        # niente path traversal: solo file dentro la cartella del frontend
        if path and candidate.is_file() and candidate.is_relative_to(root):
            immutable = path.startswith("assets/")
            cache = "public, max-age=31536000, immutable" if immutable else "public, max-age=3600"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(
            index, headers={"Cache-Control": "no-cache", "Content-Security-Policy": FRONTEND_CSP}
        )

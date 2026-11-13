"""Area admin: documenti, reindicizzazione, conversazioni, domande senza risposta."""

from __future__ import annotations

import io

from sqlalchemy import select

from app.db.models import IndexJob
from app.services import indexing

BASE = "/api/v1/admin"


def pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.drawString(72, 750, text)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def upload(client, name: str, data: bytes, content_type: str = "application/pdf"):
    return client.post(f"{BASE}/documents", files={"file": (name, data, content_type)})


def test_admin_endpoints_require_login(client) -> None:
    for path in ("/documents", "/index-jobs", "/conversations", "/unanswered"):
        response = client.get(BASE + path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "unauthorized"


def test_mutations_require_csrf(admin) -> None:
    admin.headers.pop("X-CSRF-Token")
    assert upload(admin, "nuovo.pdf", pdf_bytes("x")).status_code == 403
    assert admin.post(f"{BASE}/index-jobs").status_code == 403


def test_list_seed_documents(admin) -> None:
    items = admin.get(f"{BASE}/documents").json()["items"]
    assert {d["stored_name"] for d in items} == {"listino_2026.pdf", "condizioni_servizio.pdf", "faq.pdf"}
    assert all(d["status"] == "indexed" and d["pages"] == 2 for d in items)


def test_upload_valid_pdf(admin, settings) -> None:
    response = upload(admin, "Listino Estate 2026.pdf", pdf_bytes("Listino estivo: Bari-Lecce 120 euro."))
    assert response.status_code == 201
    body = response.json()
    assert body["stored_name"] == "listino_estate_2026.pdf"
    assert body["status"] == "uploaded" and body["pages"] == 1
    assert (settings.docs_dir / "listino_estate_2026.pdf").exists()


def test_upload_rejects_non_pdf(admin) -> None:
    assert upload(admin, "nota.txt", b"ciao", "text/plain").status_code == 415
    fake = upload(admin, "finto.pdf", b"MZ non sono un pdf")
    assert fake.status_code == 415
    assert fake.json()["error"]["message"] == "Il file non è un PDF valido"


def test_upload_rejects_large_file(admin, settings) -> None:
    big = b"%PDF-1.4\n" + b"0" * (settings.max_upload_mb * 1024 * 1024)
    response = upload(admin, "grande.pdf", big)
    assert response.status_code == 413


def test_upload_duplicate(admin) -> None:
    data = pdf_bytes("Documento unico")
    assert upload(admin, "a.pdf", data).status_code == 201
    duplicate = upload(admin, "b.pdf", data)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_document"


def test_delete_document(admin, settings) -> None:
    document = upload(admin, "temporaneo.pdf", pdf_bytes("Da eliminare")).json()
    assert admin.delete(f"{BASE}/documents/{document['id']}").status_code == 204
    assert not (settings.docs_dir / "temporaneo.pdf").exists()
    assert admin.delete(f"{BASE}/documents/{document['id']}").status_code == 404


def test_reindex_uses_new_document(admin, ask) -> None:
    upload(admin, "novita.pdf", pdf_bytes("Il nuovo servizio navetta per Matera costa 150 euro."))
    response = admin.post(f"{BASE}/index-jobs")
    assert response.status_code == 202
    job = admin.get(f"{BASE}/index-jobs/{response.json()['id']}").json()
    assert job["status"] == "done" and job["chunks"] > 0 and job["finished_at"]
    documents = admin.get(f"{BASE}/documents").json()["items"]
    assert {d["status"] for d in documents} == {"indexed"}
    reply = ask("Quanto costa la navetta per Matera?")["reply"]
    assert "150 euro" in reply["body"]
    assert reply["sources"][0]["file"] == "novita.pdf"


def test_second_job_while_running_returns_409(admin) -> None:
    db = admin.app.state.services.db
    with db.session() as session:
        session.add(IndexJob(status="running"))
    response = admin.post(f"{BASE}/index-jobs")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "job_already_running"


def test_list_jobs(admin) -> None:
    items = admin.get(f"{BASE}/index-jobs", params={"limit": 5}).json()["items"]
    assert items and items[0]["status"] == "done"  # job iniziale dei documenti di esempio


def test_interrupted_jobs_are_recovered(admin) -> None:
    db = admin.app.state.services.db
    with db.session() as session:
        session.add(IndexJob(status="running"))
    assert indexing.recover_interrupted_jobs(db) == 1
    with db.session() as session:
        assert session.scalar(select(IndexJob).where(IndexJob.status == "running")) is None


def test_conversations_list_and_detail(admin, ask) -> None:
    result = ask("Quanto costa il transfer dall'aeroporto di Bari a Monopoli?")
    ask("Ciao")
    page = admin.get(f"{BASE}/conversations", params={"page": 1, "size": 1}).json()
    assert page["total"] == 2 and page["size"] == 1 and len(page["items"]) == 1
    listing = admin.get(f"{BASE}/conversations").json()["items"]
    first = next(c for c in listing if c["id"] == result["conversation_id"])
    assert first["channel"] == "web" and first["messages"] == 2 and first["contact"] is None
    detail = admin.get(f"{BASE}/conversations/{result['conversation_id']}").json()
    reply = detail["messages"][1]
    assert reply["generator"] == "extractive"
    assert reply["sources"][0]["file"] == "listino_2026.pdf" and reply["sources"][0]["score"] > 0
    assert admin.get(f"{BASE}/conversations", params={"channel": "whatsapp"}).json()["total"] == 0
    assert admin.get(f"{BASE}/conversations", params={"channel": "sms"}).status_code == 422


def test_conversation_detail_404(admin) -> None:
    import uuid

    assert admin.get(f"{BASE}/conversations/{uuid.uuid4()}").status_code == 404


def test_unanswered_flow(admin, ask) -> None:
    ask("Qual è la capitale della Francia?")
    open_items = admin.get(f"{BASE}/unanswered").json()
    assert open_items["total"] == 1
    item = open_items["items"][0]
    assert item["question"] == "Qual è la capitale della Francia?" and item["status"] == "open"

    patched = admin.patch(
        f"{BASE}/unanswered/{item['id']}", json={"status": "handled", "note": "Fuori tema, nessuna azione"}
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "handled" and patched.json()["handled_at"]
    assert admin.get(f"{BASE}/unanswered").json()["total"] == 0
    handled = admin.get(f"{BASE}/unanswered", params={"status": "handled"}).json()["items"]
    assert handled[0]["note"] == "Fuori tema, nessuna azione"


def test_unanswered_validation(admin) -> None:
    import uuid

    missing = admin.patch(f"{BASE}/unanswered/{uuid.uuid4()}", json={"status": "handled"})
    assert missing.status_code == 404
    bad = admin.patch(f"{BASE}/unanswered/{uuid.uuid4()}", json={"status": "chiuso"})
    assert bad.status_code == 422
    too_long = admin.patch(f"{BASE}/unanswered/{uuid.uuid4()}", json={"status": "handled", "note": "x" * 501})
    assert too_long.status_code == 422

from app.services.documents import safe_pdf_name


def test_safe_name_strips_paths_and_accents() -> None:
    assert safe_pdf_name("../../Listino Prezzi Città 2026.PDF", set()) == "listino_prezzi_citta_2026.pdf"


def test_safe_name_avoids_collisions() -> None:
    assert safe_pdf_name("faq.pdf", {"faq.pdf"}) == "faq_2.pdf"
    assert safe_pdf_name("faq.pdf", {"faq.pdf", "faq_2.pdf"}) == "faq_3.pdf"


def test_safe_name_fallback() -> None:
    assert safe_pdf_name("€€€.pdf", set()) == "documento.pdf"

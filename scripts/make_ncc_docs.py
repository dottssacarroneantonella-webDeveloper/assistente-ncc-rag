"""Genera i PDF di esempio dell'attività fittizia "NCC Levante Transfer".

I documenti sono inventati: servono solo per la demo e per i test.
Uso:  python scripts/make_ncc_docs.py   (richiede: pip install reportlab)
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "examples" / "ncc-docs"
NOTE = "Documento fittizio creato per dimostrare il progetto assistente-ncc-rag."

LISTINO = [
    ("Listino prezzi 2026 – NCC Levante Transfer", "t"),
    (NOTE, "i"),
    ("Transfer dall'aeroporto di Bari", "h"),
    (
        "Il transfer dall'aeroporto di Bari Palese a Bari centro costa 45 euro. "
        "Il transfer dall'aeroporto di Bari a Polignano a Mare costa 75 euro. "
        "Il transfer dall'aeroporto di Bari a Monopoli costa 85 euro. "
        "Il transfer dall'aeroporto di Bari ad Alberobello costa 95 euro. "
        "I prezzi si intendono per auto berlina fino a 3 passeggeri con bagaglio standard.",
        None,
    ),
    ("Transfer dall'aeroporto di Brindisi", "h"),
    (
        "Il transfer dall'aeroporto di Brindisi a Ostuni costa 70 euro. "
        "Il transfer dall'aeroporto di Brindisi a Lecce costa 80 euro.",
        None,
    ),
    "BREAK",
    ("Van e supplementi", "h"),
    (
        "Per gruppi da 4 a 8 passeggeri è disponibile il van, con un supplemento del 30% sul prezzo "
        "della berlina. Le corse notturne tra le 22:00 e le 6:00 hanno un supplemento di 15 euro. "
        "Il seggiolino per bambini è gratuito ma va richiesto al momento della prenotazione. "
        "L'attesa in aeroporto è gratuita per i primi 60 minuti dall'atterraggio; ogni ulteriore "
        "mezz'ora di attesa costa 10 euro.",
        None,
    ),
    ("Tour e servizi a ore", "h"),
    (
        "Il servizio a disposizione con autista costa 50 euro l'ora, con un minimo di 3 ore. "
        "Il tour della Valle d'Itria (Alberobello, Locorotondo e Martina Franca) dura 8 ore e costa "
        "380 euro per auto.",
        None,
    ),
]

CONDIZIONI = [
    ("Condizioni del servizio – NCC Levante Transfer", "t"),
    (NOTE, "i"),
    ("Prenotazione", "h"),
    (
        "Le prenotazioni si effettuano almeno 24 ore prima del servizio, via email o WhatsApp. "
        "La prenotazione è confermata con un messaggio che riporta data, orario, punto di ritiro e prezzo. "
        "Per i transfer dall'aeroporto è necessario indicare il numero del volo.",
        None,
    ),
    ("Pagamenti", "h"),
    (
        "Il pagamento avviene a bordo in contanti oppure con carta di credito, bancomat o Satispay. "
        "Su richiesta viene rilasciata la ricevuta fiscale o la fattura.",
        None,
    ),
    "BREAK",
    ("Disdetta e modifiche", "h"),
    (
        "Per disdire una prenotazione basta scrivere via email o WhatsApp. "
        "La disdetta è gratuita fino a 24 ore prima del servizio. Per le disdette comunicate tra 24 e "
        "6 ore prima viene addebitato il 50% del prezzo; sotto le 6 ore viene addebitato l'intero importo. "
        "Le modifiche di orario sono gratuite se comunicate almeno 12 ore prima.",
        None,
    ),
    ("Bagagli e animali", "h"),
    (
        "Ogni passeggero può portare una valigia grande e un bagaglio a mano. Biciclette, attrezzatura "
        "da golf e bagagli voluminosi vanno segnalati al momento della prenotazione. "
        "Accettiamo animali a bordo: gli animali domestici di piccola taglia sono ammessi nel trasportino "
        "senza costi aggiuntivi; "
        "per i cani di taglia media o grande è previsto un supplemento di 10 euro per la pulizia.",
        None,
    ),
    ("Ritardi del volo", "h"),
    (
        "In caso di ritardo del volo l'autista monitora l'orario di arrivo: l'attesa dovuta al ritardo "
        "del volo non viene addebitata.",
        None,
    ),
]

FAQ = [
    ("Domande frequenti – NCC Levante Transfer", "t"),
    (NOTE, "i"),
    ("Orari e contatti", "h"),
    (
        "Il servizio è attivo 24 ore su 24, tutti i giorni dell'anno, su prenotazione. "
        "L'ufficio prenotazioni risponde dal lunedì al sabato dalle 8:00 alle 20:00. "
        "L'indirizzo email per le prenotazioni è prenotazioni@ncc-levante.example.",
        None,
    ),
    ("Dove ci incontriamo in aeroporto?", "h"),
    (
        "All'aeroporto di Bari l'autista attende nella sala arrivi, davanti all'uscita principale, "
        "con un cartello con il nome del passeggero.",
        None,
    ),
    "BREAK",
    ("Le auto", "h"),
    (
        "La flotta comprende berline Mercedes Classe E e van Mercedes Classe V con aria condizionata, "
        "Wi-Fi gratuito e acqua a bordo. Tutti i veicoli sono assicurati per il trasporto di persone.",
        None,
    ),
    ("Lingue parlate", "h"),
    (
        "Gli autisti parlano italiano e inglese; su richiesta è disponibile un autista che parla tedesco.",
        None,
    ),
]


def build(path: Path, content: list) -> None:
    styles = getSampleStyleSheet()
    style_for = {
        "t": styles["Title"],
        "h": styles["Heading2"],
        "i": styles["Italic"],
        None: styles["BodyText"],
    }
    story = []
    for item in content:
        if item == "BREAK":
            story.append(PageBreak())
            continue
        text, kind = item
        story.append(Paragraph(text, style_for[kind]))
        story.append(Spacer(1, 6))
    SimpleDocTemplate(
        str(path), pagesize=A4, title=content[0][0], author="NCC Levante Transfer (fittizio)", invariant=1
    ).build(story)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, content in [
        ("listino_2026.pdf", LISTINO),
        ("condizioni_servizio.pdf", CONDIZIONI),
        ("faq.pdf", FAQ),
    ]:
        build(OUT / name, content)
        print(f"Creato {OUT / name}")

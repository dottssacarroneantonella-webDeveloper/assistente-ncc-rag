import pytest
from app.worker.intents import Intent, detect_intent, welcome_message


@pytest.mark.parametrize("text", ["Ciao", "ciao!", "Buongiorno", "salve a tutti", "MENU", "aiuto"])
def test_short_greetings(text: str) -> None:
    assert detect_intent(text) is Intent.GREETING


@pytest.mark.parametrize(
    "text",
    [
        "Ciao, quanto costa il transfer da Bari a Monopoli?",
        "Accettate animali a bordo?",
        "info sui pagamenti con carta di credito",
    ],
)
def test_questions_go_to_rag(text: str) -> None:
    assert detect_intent(text) is Intent.QUESTION


@pytest.mark.parametrize("text", ["CANCELLA DATI", "cancella i miei dati", "  Cancella dati. "])
def test_delete_data(text: str) -> None:
    assert detect_intent(text) is Intent.DELETE_DATA


def test_delete_requires_exact_command() -> None:
    assert detect_intent("come faccio a cancellare i dati della prenotazione?") is Intent.QUESTION


def test_non_text() -> None:
    assert detect_intent("", kind="audio") is Intent.NON_TEXT


def test_welcome_contains_business_name() -> None:
    assert "NCC Levante Transfer" in welcome_message("NCC Levante Transfer")

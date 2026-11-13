from app.core.security import hash_contact, normalize_phone, sign_meta_body, verify_meta_signature

SECRET = "segreto-di-test"  # noqa: S105 - valore fittizio per i test


def test_valid_signature() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    assert verify_meta_signature(body, sign_meta_body(body, SECRET), SECRET)


def test_signature_of_other_body_is_rejected() -> None:
    assert not verify_meta_signature(b"{}", sign_meta_body(b"{ }", SECRET), SECRET)


def test_wrong_secret_is_rejected() -> None:
    body = b"{}"
    assert not verify_meta_signature(body, sign_meta_body(body, "altro"), SECRET)


def test_missing_or_malformed_header_is_rejected() -> None:
    assert not verify_meta_signature(b"{}", None, SECRET)
    assert not verify_meta_signature(b"{}", "", SECRET)
    assert not verify_meta_signature(b"{}", "md5=abc", SECRET)


def test_empty_secret_never_validates() -> None:
    assert not verify_meta_signature(b"{}", sign_meta_body(b"{}", ""), "")


def test_hash_contact_is_stable_and_hides_number() -> None:
    digest, hint = hash_contact("+39 333 123 4567", "chiave")
    same, _ = hash_contact("393331234567", "chiave")
    other_key, _ = hash_contact("393331234567", "altra-chiave")
    assert digest == same != other_key
    assert len(digest) == 64 and "3331234567" not in digest
    assert hint == "4567"


def test_normalize_phone() -> None:
    assert normalize_phone("+39 (333) 123-4567") == "393331234567"

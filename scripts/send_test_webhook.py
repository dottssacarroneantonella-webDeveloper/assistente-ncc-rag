"""Simula un messaggio WhatsApp firmato come farebbe Meta (prova locale senza account Meta).

Uso:
    META_APP_SECRET=... python scripts/send_test_webhook.py "Quanto costa Bari–Monopoli?"

Richiede l'API avviata con WHATSAPP_ENABLED=true. La risposta del worker verrà inviata
alla Graph API: senza credenziali reali l'invio fallisce (lo si vede nel log), ma domanda
e risposta restano salvate nel database.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
import uuid


def main() -> int:
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=formatter)
    parser.add_argument("text", help="testo del messaggio")
    parser.add_argument("--url", default="http://localhost:8000/api/v1/whatsapp/webhook")
    parser.add_argument("--sender", default="390000000000", help="numero fittizio del mittente")
    args = parser.parse_args()

    secret = os.environ.get("META_APP_SECRET")
    if not secret:
        print("Imposta META_APP_SECRET (lo stesso valore del file .env)", file=sys.stderr)
        return 2
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "0",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": args.sender,
                                    "id": f"wamid.test.{uuid.uuid4().hex}",
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": args.text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(  # noqa: S310 - URL scelto dall'utente per la prova locale
        args.url,
        data=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        print(response.status, response.read().decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

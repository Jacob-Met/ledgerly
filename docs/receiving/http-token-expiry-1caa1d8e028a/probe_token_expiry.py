"""Exercise the real HTTP-client GET path with a deterministic in-memory transport."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from unittest.mock import patch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from ledgerly.paypal import HttpPayPalClient, PayPalError

    source = args.source / "ledgerly/paypal.py"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    clock = [100.0]
    active_token = [None]
    token_deadline = [0.0]
    calls = []
    responses = []

    class Reply(io.BytesIO):
        status = 200

    def urlopen(request, timeout):
        if request.full_url == "https://synthetic-paypal.invalid/v1/oauth2/token":
            token = f"synthetic-token-{len([c for c in calls if c['operation'] == 'token']) + 1}"
            active_token[0] = token
            token_deadline[0] = clock[0] + 10.0
            calls.append({"operation": "token", "time": clock[0], "method": request.method,
                          "timeout": timeout, "body": request.data.decode("ascii")})
            response = Reply(json.dumps({"access_token": token, "expires_in": 10}).encode())
        elif request.full_url == "https://synthetic-paypal.invalid/v2/invoicing/invoices/INV-SYNTHETIC":
            token = request.get_header("Authorization")
            accepted = token == f"Bearer {active_token[0]}" and clock[0] < token_deadline[0]
            calls.append({"operation": "invoice_get", "time": clock[0], "method": request.method,
                          "timeout": timeout, "synthetic_bearer": token, "accepted": accepted})
            if not accepted:
                body = Reply(b'{"name":"AUTHENTICATION_FAILURE","message":"Synthetic token expired"}')
                responses.append(body)
                raise urllib.error.HTTPError(request.full_url, 401, "Synthetic token expired", {}, body)
            response = Reply(b'{"id":"INV-SYNTHETIC","status":"DRAFT"}')
        else:
            raise AssertionError("Unexpected URL: " + request.full_url)
        responses.append(response)
        return response

    results = []
    with patch.dict(os.environ, {"LEDGERLY_ALLOW_NETWORK": "1"}), \
            patch.object(urllib.request, "urlopen", side_effect=urlopen), \
            patch.object(time, "monotonic", side_effect=lambda: clock[0]):
        client = HttpPayPalClient("synthetic-client", "synthetic-secret", "https://synthetic-paypal.invalid")
        for moment in (100.0, 109.999, 110.0):
            clock[0] = moment
            try:
                response = client.get_invoice("INV-SYNTHETIC")
                results.append({"time": moment, "status": response.status, "body": response.body})
            except PayPalError as error:
                results.append({"time": moment, "error": type(error).__name__,
                                "http_status": error.http_status, "message": str(error)})
    for response in responses:
        response.close()
    after = hashlib.sha256(source.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError("Source changed during receiving")
    receipt = {"schema": "ledgerly.http-token-expiry.original-consumer.v1",
               "source_sha256": before, "source_unchanged": True,
               "runtime": sys.version, "transport": "in-memory urlopen replacement; no socket or provider",
               "calls": calls, "results": results}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()

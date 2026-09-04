#!/usr/bin/env python3
"""A second device, in about three hundred lines.

This is the conformance client. It pretends to be another copy of Dig: it
pairs, takes a snapshot, makes a change, pushes it, pulls it back, sends a file
and fetches it again, and prints pass or fail for each step.

It is the thing to check an Android client against. If this passes against your
server, the protocol in docs/SYNC.md is being spoken correctly.

    python tools/sync-client/dig_sync_client.py --address 100.101.102.103 --port 8787 --code AB12-CD34-EF56

Nothing here is part of the app. It only ever talks to a Dig you have paired it
with, over your own network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
import uuid

TIMEOUT = 10


class Client:
    def __init__(self, address: str, port: int, name: str = "Conformance client") -> None:
        self.base = f"http://{address}:{port}/v1"
        self.name = name
        self.token = ""
        self.device = str(uuid.uuid4())
        self.cursor = 0
        self.schema = 0

    # ------------------------------------------------------------------ http

    def _call(self, path: str, method: str = "GET", body=None, raw: bytes | None = None):
        url = self.base + path
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        request = urllib.request.Request(url, data=data, method=method)
        if self.token:
            request.add_header("Authorization", "Bearer " + self.token)
        if data is not None:
            request.add_header(
                "Content-Type",
                "application/octet-stream" if raw is not None else "application/json",
            )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = response.read()
                kind = response.headers.get("Content-Type", "")
                if "octet-stream" in kind:
                    return response.status, payload
                try:
                    return response.status, json.loads(payload.decode("utf-8"))
                except Exception:
                    return response.status, payload
        except urllib.error.HTTPError as error:
            payload = error.read()
            try:
                return error.code, json.loads(payload.decode("utf-8"))
            except Exception:
                return error.code, payload
        except urllib.error.URLError as error:
            return 0, {"ok": False, "reason": str(error.reason)}

    # ---------------------------------------------------------------- the api

    def hello(self):
        return self._call("/hello")

    def pair(self, code: str):
        status, body = self._call(
            "/pair", "POST",
            {"code": code, "name": self.name, "device": self.device, "schema": self.schema},
        )
        if status == 200 and isinstance(body, dict) and body.get("ok"):
            self.token = body["token"]
        return status, body

    def snapshot(self):
        status, body = self._call("/state")
        if status == 200 and isinstance(body, dict) and body.get("ok"):
            self.cursor = body.get("cursor", 0)
        return status, body

    def changes(self, since: int | None = None):
        status, body = self._call(f"/changes?since={self.cursor if since is None else since}")
        if status == 200 and isinstance(body, dict) and body.get("ok"):
            self.cursor = body.get("cursor", self.cursor)
        return status, body

    def push(self, changes: list):
        return self._call("/push", "POST", {"schema": self.schema, "changes": changes})

    def get_blob(self, sha: str):
        return self._call(f"/blobs/{sha}")

    def put_blob(self, data: bytes):
        sha = hashlib.sha256(data).hexdigest()
        return sha, self._call(f"/blobs/{sha}/upload", "POST", raw=data)


# --------------------------------------------------------------------- checks

class Run:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        mark = "pass" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f"   {detail}" if detail and not ok else ""))
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        return ok


def conform(address: str, port: int, code: str) -> int:
    run = Run()
    client = Client(address, port)
    print(f"Talking to Dig at {address}:{port}\n")

    print("Identity")
    status, body = client.hello()
    run.check("hello answers", status == 200 and isinstance(body, dict), str(body)[:120])
    if isinstance(body, dict):
        client.schema = body.get("schema", 0)
        run.check("it says which schema it speaks", bool(client.schema))
        run.check("it names itself", bool(body.get("name")))

    print("\nBefore pairing")
    status, _ = client.snapshot()
    run.check("a snapshot is refused", status == 401)
    status, _ = client.changes()
    run.check("changes are refused", status == 401)

    print("\nPairing")
    status, body = client.pair("NOT-A-REAL-CODE")
    run.check("a wrong code is refused", status == 403)
    status, body = client.pair(code)
    run.check("the real code pairs", status == 200 and bool(client.token), str(body)[:160])
    if not client.token:
        print("\nCannot go on without a token.")
        return 1
    status, body = client.pair(code)
    run.check("the code cannot be used twice", status == 403)

    print("\nFirst sync")
    status, body = client.snapshot()
    ok = status == 200 and isinstance(body, dict) and body.get("ok")
    run.check("a full snapshot comes back", bool(ok))
    if not ok:
        return 1
    state = body["state"] or {}
    run.check("it holds the collections", isinstance(state.get("projects"), list))
    start_cursor = client.cursor
    run.check("it comes with a cursor", start_cursor >= 0)

    status, body = client.changes()
    run.check("nothing new since that cursor", status == 200 and body.get("changes") == [])

    print("\nPushing a change")
    made = str(uuid.uuid4())
    change = {
        "collection": "ideas", "record_id": made, "op": "create", "rev": 1,
        "at": "2099-01-01T00:00:00.000000", "device": client.device,
        "payload": {"text": "Written by the conformance client", "descr": "",
                    "at": "2099-01-01T00:00:00", "opened": None, "group_id": None,
                    "example": 0, "position": 0},
    }
    status, body = client.push([change])
    accepted = (
        status == 200 and isinstance(body, dict)
        and body.get("results") and body["results"][0]["result"] == "accepted"
    )
    run.check("the change is accepted", bool(accepted), str(body)[:160])

    status, body = client.snapshot()
    texts = [i.get("text") for i in (body.get("state") or {}).get("ideas", [])]
    run.check("it comes back on the next snapshot", "Written by the conformance client" in texts)

    status, body = client.changes(since=start_cursor)
    ours = [c for c in body.get("changes", []) if c.get("record_id") == made]
    run.check("and it appears in the change log", bool(ours))

    print("\nSending it again should change nothing")
    status, body = client.push([change])
    again = body.get("results", [{}])[0].get("result") if isinstance(body, dict) else ""
    run.check("a repeat is ignored, not doubled", again in ("ignored", "accepted"))
    status, body = client.snapshot()
    count = sum(
        1 for i in (body.get("state") or {}).get("ideas", [])
        if i.get("text") == "Written by the conformance client"
    )
    run.check("there is still only one of it", count == 1, f"found {count}")

    print("\nDeleting it")
    status, body = client.push([{
        "collection": "ideas", "record_id": made, "op": "delete", "rev": 2,
        "at": "2099-01-02T00:00:00.000000", "device": client.device, "payload": {},
    }])
    run.check("the delete is accepted", status == 200)
    status, body = client.snapshot()
    gone = all(
        i.get("id") != made for i in (body.get("state") or {}).get("ideas", [])
    )
    run.check("it is gone from the snapshot", gone)

    status, body = client.push([{
        "collection": "ideas", "record_id": made, "op": "update", "rev": 3,
        "at": "2099-01-03T00:00:00.000000", "device": client.device,
        "payload": {"text": "trying to come back"},
    }])
    result = body.get("results", [{}])[0].get("result") if isinstance(body, dict) else ""
    run.check("an edit does not resurrect it", result == "conflict", str(body)[:160])

    print("\nFiles")
    payload = b"conformance client bytes " + made.encode()
    sha, (status, body) = client.put_blob(payload)
    run.check("a file uploads", status == 200 and isinstance(body, dict) and body.get("ok"),
              str(body)[:160])
    status, back = client.get_blob(sha)
    run.check("it comes back byte for byte", status == 200 and back == payload)
    status, body = client.get_blob("0" * 64)
    run.check("a file that is not there is a clean 404", status == 404)

    bad_sha = hashlib.sha256(b"something else").hexdigest()
    status, body = client._call(f"/blobs/{bad_sha}/upload", "POST", raw=payload)
    run.check("bytes that do not match their hash are refused", status == 400)

    print("\nVersions")
    status, body = client._call(
        "/push", "POST", {"schema": (client.schema or 1) + 99, "changes": []}
    )
    run.check("a different schema is refused", status == 409, str(body)[:160])

    print("\nAfter revoking")
    print("  (revoke this device in Dig's settings, then run with --after-revoke)")

    print(f"\n{run.passed} passed, {run.failed} failed")
    return 0 if run.failed == 0 else 1


def check_revoked(address: str, port: int, token: str) -> int:
    client = Client(address, port)
    client.token = token
    run = Run()
    status, _ = client.snapshot()
    run.check("a revoked token is refused", status == 401)
    print(f"\n{run.passed} passed, {run.failed} failed")
    return 0 if run.failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Pretend to be a second Dig.")
    parser.add_argument("--address", required=True)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--code", help="the one time pairing code from Dig's settings")
    parser.add_argument("--after-revoke", dest="token", help="check a token that has been revoked")
    parser.add_argument("--pairing", help="the pairing payload from the QR code, instead of the rest")
    args = parser.parse_args()

    if args.pairing:
        payload = json.loads(args.pairing)
        return conform(payload["address"], payload["port"], payload["code"])
    if args.token:
        return check_revoked(args.address, args.port, args.token)
    if not args.code:
        parser.error("give it --code, or --pairing with what the QR code holds")
    return conform(args.address, args.port, args.code)


if __name__ == "__main__":
    sys.exit(main())

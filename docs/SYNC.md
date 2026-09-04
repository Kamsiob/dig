# Sync

Dig syncs between your own devices, over your own private network, with nothing
passing through anyone else's servers. It is off by default. When you turn it
on, your computer answers on loopback and on its Tailscale address, and nowhere
else. If there is no Tailscale interface it refuses to start and says why.

Tailscale already gives you an encrypted private network and device identity.
Pairing sits on top of that, so a device that is on your tailnet but is not one
you paired still cannot read anything.

This document is complete enough to build a client from. The reference client
lives at `tools/sync-client/dig_sync_client.py`; if it passes against your
server, you are speaking the protocol correctly.

## The shape of the data

Dig keeps one record per thing, across a table per collection. Every record
carries what a sync needs to reason about it:

| Column | What it is |
|---|---|
| `id` | a UUID, made by whichever device created the record |
| `created_at` | ISO 8601 with microseconds |
| `updated_at` | ISO 8601 with microseconds, the basis for who wins |
| `updated_by` | the device id that last changed it |
| `rev` | a counter, one per change on this device |
| `deleted` | 0 or 1. A delete is a tombstone, never a removed row |
| `deleted_at` | when it went |

The collections are: `groups`, `types`, `projects`, `checklist_items`,
`decisions`, `releases`, `people`, `links`, `stage_history`, `wait_history`,
`log_entries`, `ideas`, `inbox`, `library`, `activity`, `files`, `templates`.
`settings` is a separate key and value table and syncs the same way, with the
key standing in for the record id.

Tombstones are kept for 90 days and are only purged once every known device has
acknowledged them. A device that has been away for a week learns that something
went away, rather than pushing it back.

### Files

Files are content addressed. A `files` record carries a `sha256` and the name,
document id, version, description and stage; the bytes live once under that hash.
Moving a file between a project, a group and the Library changes the record
only. Two devices holding the same bytes exchange the record, notice they both
have the hash, and send nothing.

### Decision numbers

`D-0001` is display only and is never stored. Numbers are derived at read time by
ordering every live decision by `at`, then by `updated_by`, then by `id`, and
counting from one. Two devices with the same records therefore show the same
numbers. Never key anything off the number; the identity is the uuid.

### The oplog

Every write goes through one function that updates the row and appends to
`oplog` in the same transaction:

| Column | What it is |
|---|---|
| `seq` | the cursor. Monotonic, per device |
| `collection`, `record_id`, `rev` | which record, and which revision |
| `op` | `create`, `update` or `delete` |
| `payload` | the fields that were written, as JSON |
| `at`, `device` | when, and by whom |

## Pairing

1. In Dig: Settings, then Sync with my other devices, then Pair a device.
2. Dig shows a one time code and a QR code. The QR holds exactly:

   ```json
   {"v":1,"address":"100.101.102.103","port":8787,"code":"AB12-CD34-EF56","name":"this computer"}
   ```

3. The code is good for five minutes and works once. Using it, or letting it
   expire, clears it.
4. The client posts the code to `/v1/pair` and gets a bearer token back. Every
   later request carries `Authorization: Bearer <token>`.
5. Revoking a device in Settings clears its token immediately. The next request
   it makes gets a 401.

## The API

Everything is JSON over HTTP, under `/v1`. Every request except `/v1/hello` and
`/v1/pair` needs the bearer token; without it the answer is `401` and
`{"ok": false, "reason": "not paired"}`.

### `GET /v1/hello`

No token needed. Who this is and what it speaks.

```json
{"app":"Dig","version":"2.0.0","schema":3,"device":"<uuid>","name":"this computer"}
```

Check `schema` before anything else. A client speaking a different schema must
stop, not guess.

### `POST /v1/pair`

```json
{"code":"AB12-CD34-EF56","name":"Pixel 8","device":"<uuid the client made>","schema":3}
```

`200` with `{"ok":true,"token":"...","device":"<server uuid>","schema":3}`.
`403` when the code is wrong or has expired. `409` when the schema differs.

### `GET /v1/changes?since=<cursor>`

Everything after that cursor, oldest first, up to 500 at a time.

```json
{"ok":true,"cursor":812,"more":false,"changes":[
  {"seq":811,"collection":"projects","record_id":"<uuid>","rev":4,"op":"update",
   "payload":"{\"name\":\"Website refresh\"}","at":"2026-09-04T16:20:11.442","device":"<uuid>"}]}
```

Keep the returned `cursor` and pass it next time. When `more` is true, ask
again straight away.

### `POST /v1/push`

```json
{"schema":3,"changes":[{"collection":"ideas","record_id":"<uuid>","op":"create","rev":1,
  "at":"2026-09-04T16:22:00.000000","device":"<uuid>","payload":{"text":"..."}}]}
```

The whole batch is applied in one transaction. The answer says what happened to
each one:

```json
{"ok":true,"cursor":815,"results":[{"id":"<uuid>","collection":"ideas","result":"accepted","why":""}]}
```

`result` is `accepted`, `conflict`, or `ignored`. `409` when the schema differs.

`payload` may be an object or a JSON string; both are read.

### `GET /v1/state`

The whole document, for a first sync. Comes with the cursor to carry on from.

### `GET /v1/blobs/{sha256}`

The bytes, as `application/octet-stream`. `404` when there is no such file.

### `POST /v1/blobs/{sha256}/upload`

The bytes in the body. The server hashes what it received and refuses with `400`
if it does not match the hash in the path. Sending bytes that are already there
is accepted and stores nothing twice.

## How a disagreement is settled

In order:

1. **A record we have never seen is taken.** A delete for a record we have never
   seen creates the tombstone, so it cannot arrive later by another route.
2. **A delete beats a concurrent edit.** The tombstone wins. If our copy had
   been edited more recently than the delete, that edit is written to the
   `conflicts` table rather than thrown away.
3. **An edit does not undo a delete.** An update arriving for something already
   deleted here is refused with `conflict`, and the incoming version is written
   to `conflicts`.
4. **Otherwise the later `updated_at` wins,** field by field. When two changes
   carry the same timestamp, the higher `updated_by` wins, so both sides reach
   the same answer without talking again.

Records that are naturally additive, checklist items, decisions, releases,
people, files, log entries and links, are separate records with their own ids,
so two devices adding different ones simply end up with both. A release added on
two devices from the same version and date gets the same derived id and
converges to one.

Conflicts are shown in Settings, under "Where two devices disagreed", with the
version that lost. Nothing is silently dropped.

## What the Android client must implement

1. **Pairing.** Read the QR, or take the code typed in. `POST /v1/pair`. Keep
   the token in the platform keystore. Handle `403` and `409` with a plain
   sentence.
2. **First sync.** `GET /v1/state`, store it, keep the cursor.
3. **Pulling.** `GET /v1/changes?since=<cursor>` on a schedule and when the app
   comes to the front. Apply with the same four rules above, in the same order.
   Loop while `more` is true.
4. **Pushing.** Keep your own oplog. Send everything after the last cursor the
   server acknowledged, in `seq` order. Treat `ignored` as fine and `conflict`
   as something to show the person.
5. **Files.** Before pushing a `files` record, `POST` its bytes. Before showing
   one, `GET` its bytes if you do not already hold that hash. Verify the hash on
   both sides; never trust a name.
6. **Identity.** Make one device uuid on first run and keep it. Stamp it into
   `updated_by` on everything you write.
7. **Timestamps.** ISO 8601, microseconds, local time without an offset, which
   is what Dig writes. Compare as strings.
8. **Schema.** Refuse to sync when `/v1/hello` reports a schema you do not
   speak. Do not migrate someone else's data.
9. **Revocation.** A `401` at any point means the pairing is gone. Drop the
   token and ask to pair again.
10. **Never guess.** If a record does not fit the shape you expect, leave it
    alone and sync it back untouched.

## Checking a client

```
python tools/sync-client/dig_sync_client.py --address 100.101.102.103 --port 8787 --code AB12-CD34-EF56
```

It pairs, checks that an unpaired request is refused, takes a snapshot, pushes a
change, pulls it back, sends it again to check nothing doubles, deletes it,
checks an edit cannot resurrect it, uploads and downloads a file, checks that
mismatched bytes are refused, and checks that a different schema is refused.
Twenty five checks. Every one has to pass.

To check revocation, revoke the device in Settings and run:

```
python tools/sync-client/dig_sync_client.py --address 100.101.102.103 --port 8787 --after-revoke <token>
```

## What is written down about each exchange

Every request is recorded locally with the device, the time, what it asked for,
and how it went. That log is in Settings and stays on this computer.

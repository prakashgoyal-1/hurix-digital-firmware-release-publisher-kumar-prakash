# Firmware Release Publisher

## 1. What happened

The firmware code-signing key got rotated. Since then, every release bundle
the old publisher sends to the distribution gateway gets rejected with
`UNTRUSTED_SIGNATURE`, because it's still signing with the old, revoked key.
There's no publisher program yet — it has to be written.

## 2. What to build

Write exactly one file:

```
/app/publisher/release-publisher.mjs
```

Run it like this:

```
cd /app
npm run report
```

(`npm run report` is set up in `/app/package.json` to run
`node publisher/release-publisher.mjs --report`.)

When it runs, it needs to:

1. Read the build manifest and reconcile it.
2. Sign each bundle that's publishable, using the key that's currently
   active.
3. Send each signed bundle to the distribution gateway over HTTP.
4. Save the gateway's receipts and its own idempotency tokens, so running it
   again doesn't publish the same thing twice.
5. Print a status report to stdout that comes out the same every time.

### Command-line rules

- Only `--report` is a valid argument — run normally in that case.
- Zero arguments, an argument it doesn't recognize, or anything extra on top
  of `--report` — all of these should make it exit with a non-zero status,
  print nothing to stdout, and print a non-empty error to stderr.

## 3. Paths and services involved

| Path / URL | What it is |
|---|---|
| `/app/fixtures/build_manifest.csv` | Raw input manifest. Read-only. |
| `/app/reports/publications.expected.txt` | Golden reference output (receipt values get masked when compared). Read-only, just for checking your own work. |
| `/app/keys/current/current.key.pem`, `/app/keys/current/current.cert.pem` | The signing keypair that's currently in force. Use this to sign. |
| `/app/keys/revoked/revoked.key.pem`, `/app/keys/revoked/revoked.cert.pem` | The old, rotated-out keypair. Never sign with this. |
| `/app/distribution-gateway/` | The provided Express gateway service (already running on port 7070 when the program runs). Don't modify its code. Don't read or write `/app/distribution-gateway/data/` — its private ledger is off-limits; talk to it only over HTTP. |
| `/app/publisher/release-publisher.mjs` | The one file to deliver. The folder exists but is empty until you add it. |
| `/app/releases.duckdb` | Local persistence. Gets created by the program at runtime — don't pre-create it or ship one. |

## 4. Manifest format

CSV columns, in order:

```
entry_id,bundle_id,component_id,version,size_bytes,record_type,supersedes_id,recorded_at
```

- `record_type` is either `BUILD` or `WITHDRAWAL`.
- On a `WITHDRAWAL` row, `supersedes_id` holds the `entry_id` of the `BUILD`
  row it cancels.

## 5. Reconciliation rules (has to be SQL run in DuckDB)

1. **Dedupe exact duplicates.** If two manifest rows are identical in every
   single column, that's the same record sent twice — count it once.
2. **Apply withdrawals.** Any `BUILD` row whose `entry_id` shows up as a
   `WITHDRAWAL` row's `supersedes_id` is cancelled — drop it before anything
   else.
3. **Work out which bundles are publishable.** After steps 1 and 2, a
   `bundle_id` is publishable if at least one `BUILD` row is still there for
   it. If every build for a bundle got withdrawn, skip that bundle
   completely — no report line for it, and it never goes to the gateway.
4. For each publishable bundle, work out:
   - `artifact_count` — how many `BUILD` rows survived for it.
   - `total_bytes` — the total `size_bytes` across those surviving rows.
5. Go through bundles in ascending `bundle_id` order everywhere — in the
   report, when sending to the gateway, and in whatever gets saved.

## 6. Signing

- Base URL: `http://127.0.0.1:7070`.
- `GET /v1/signing-key/current` gives back
  `{ key_id, algorithm, certificate_ref, status }`. Use whatever this
  returns to decide the key id to report and the algorithm to sign with —
  don't assume fixed values. If `status` isn't `"current"`, or the
  `algorithm` isn't one the program supports, treat that as a fatal error.
- For each publishable bundle, build a descriptor containing exactly
  `bundle_id`, `artifact_count`, and `total_bytes` — as **UTF-8 JSON with
  keys sorted alphabetically and no extra whitespace**. Whatever bytes get
  signed must be exactly the same bytes sent as `descriptor` — the gateway
  checks the signature against the exact descriptor bytes it receives.
- Sign the descriptor using the current key (`/app/keys/current/`) as a
  detached, PEM-encoded CMS signature. Never sign with the revoked key
  (`/app/keys/revoked/`). Check `/app/distribution-gateway/README.md` for
  the exact verification command the gateway runs, so the signature
  produced actually gets accepted.

## 7. Sending to the gateway

- `POST /v1/publications` with JSON body
  `{ descriptor, signature, request_token }`.
- On success: `{ publication_id, request_token, status: "PUBLISHED" }`.
- If the signature doesn't verify against the current certificate:
  `{ "error": "UNTRUSTED_SIGNATURE" }` — this should never actually happen
  if the program only ever signs with the current key.
- Use a fixed request token per bundle: `token-<bundle_id>`.
- Sending an already-published `request_token` again just replays the
  original receipt instead of making a new publication — that's what makes
  idempotency work on the gateway's side. But also check local state first,
  so a re-run doesn't even need to contact the gateway for bundles already
  published.

## 8. Saving state and idempotency

- In `/app/releases.duckdb`, store at least: `bundle_id`, `request_token`,
  `publication_id`, `status`, the `key_id` used, and the descriptor that got
  signed — for every bundle successfully published.
- Running the program a second time (manifest and gateway state unchanged)
  must:
  - print exactly the same stdout as the first run, and
  - not create any new or duplicate publication on the gateway — reuse the
    stored receipt and token for bundles already published.

## 9. What to print

For each publishable bundle, in ascending `bundle_id` order, print exactly
two lines to stdout (nothing else — no extra logging when everything
succeeds):

```
BUNDLE <bundle_id> SIGNED KEY=<key_id>
BUNDLE <bundle_id> PUBLISHED RECEIPT=<publication_id> TOKEN=<request_token> STATUS=PUBLISHED
```

`<key_id>` is whatever `GET /v1/signing-key/current` returned for that run.

Check your work against `/app/reports/publications.expected.txt` (only the
`RECEIPT=` value gets masked out when it's compared).

## 10. Things not to do

- Only talk to the distribution gateway over HTTP. Never read or write its
  private ledger at `/app/distribution-gateway/data/`.
- Never change any file under `/app/distribution-gateway/`.
- Never disable, skip, or weaken signature verification, and never sign
  with the revoked key.
- Never hardcode the golden report text, receipt ids, row counts, or
  anything else that should instead come from the manifest and the
  gateway's live responses — the program has to stay correct even if the
  manifest or gateway data changes.
- The main reconciliation logic (dedup, withdrawals, per-bundle totals) has
  to be SQL run against DuckDB — not just computed by looping over rows in
  JavaScript.

## 11. When is it done

The program is correct when, in a freshly built container:

- `npm run report` matches `/app/reports/publications.expected.txt`
  (receipt masked), in the same order.
- Every bundle that gets submitted ends up `PUBLISHED` — none get rejected
  with `UNTRUSTED_SIGNATURE`.
- `/app/releases.duckdb` has the receipts and tokens described in Section 8.
- Running `npm run report` again gives identical output and doesn't create
  duplicate publications on the gateway.
- Bad ways of running it (Section 2) get rejected the way that's specified.

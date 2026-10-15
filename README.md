# hurix-digital-firmware-release-publisher-kumar-prakash

This is a Hurix Systems assessment task I built. The task: fix a firmware
publisher that broke after a signing key rotation.

## What's the problem

Firmware releases get signed before they go out to a distribution gateway.
The signing key got rotated, but the old publisher program still signs
with the old (now revoked) key. So the gateway rejects everything with
`UNTRUSTED_SIGNATURE`. There is no publisher yet — candidate has to write
one from scratch.

## What candidate has to build

One file: `publisher/release-publisher.mjs`, run with `npm run report`.

It should:

1. Read the build manifest CSV, clean it up using SQL (DuckDB) — remove
   duplicate rows, drop builds that got withdrawn later.
2. Check with the gateway which key is currently active, sign each
   remaining bundle with that key only (never the revoked one).
3. Send each signed bundle to the gateway over HTTP.
4. Save the receipt + a token locally, so running it again doesn't publish
   the same thing twice.
5. Print a fixed report to the screen.

Full rules are in [instruction.md](instruction.md). [CANDIDATE_GUIDE.md](CANDIDATE_GUIDE.md)
has a walkthrough if you want a suggested order to do things in.

## Files in this repo

- `instruction.md` — the actual task spec, this is what gets graded against.
- `CANDIDATE_GUIDE.md` — step by step guide, not the answer.
- `AUTHOR_NOTES.md` — my own notes while building this task + proof it works.
- `task.toml` — task settings (difficulty, tags, limits).
- `environment/` — docker build stuff: fixtures, the gateway service, keys, Dockerfile.
- `solution/` — my reference solution + script to install it.
- `tests/` — the verifier (`test.sh` + `test_outputs.py`).

## How to build and check it

Build the image:

```powershell
docker build -t hurix-firmware-task .\environment
```

**Check 1 — no publisher yet, should fail:**

```powershell
docker run --rm -it --name hurix-proof-a `
  -v "${PWD}\tests:/tests:ro" `
  hurix-firmware-task bash
bash /tests/test.sh   # should fail, reward.txt = 0
```

**Check 2 — with my reference solution installed, should pass:**

```powershell
docker run --rm -it --name hurix-proof-b `
  -v "${PWD}\solution:/solution:ro" `
  -v "${PWD}\tests:/tests:ro" `
  hurix-firmware-task bash
bash /solution/publish.sh
bash /tests/test.sh   # should pass all 13, reward.txt = 1
```

To check it doesn't double-publish, run `node publisher/release-publisher.mjs --report`
twice inside the container and diff the two outputs — should be exactly the
same, and no second publication should get created on the gateway.

## Task info

- Author: Kumar Prakash
- Difficulty: medium
- Category: security (api_integration, db_interaction)
- Languages: JavaScript, SQL
- Tags: openssl, cms-signature, key-rotation, duckdb, reconciliation, idempotency
- Internet access inside the task container: off

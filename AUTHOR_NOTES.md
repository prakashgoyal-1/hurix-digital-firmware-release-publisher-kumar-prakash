
# Author Notes

## 1. Task Summary

**What's the task?**
Candidate has to write `release-publisher.mjs` that: reads the firmware
manifest, reconciles it correctly, builds a bundle descriptor, signs it,
publishes it, stores the publication, handles repeated runs properly, and
prints a report.

**What's the main goal?**
Build a firmware release publisher that actually signs things securely.

**What the publisher does, step by step:**
Read the firmware manifest → find the valid bundles → build a release
descriptor → sign it with the current signing key → publish it to the
gateway → save the publication state → handle repeated runs without
duplicating anything → print a report that's the same every time.

**How the original bug happens:**
Old publisher signs with the revoked key → gateway checks the signature
against the current certificate → it doesn't match → `UNTRUSTED_SIGNATURE`.

## 2. Design

1. Read the manifest
2. Remove duplicates
3. Apply the withdrawals
4. Build the descriptor
5. Sign it
6. Publish to the gateway
7. Save to DuckDB

## 3. Important Rules

**Duplicates**
If every column in two manifest rows matches, that's one record, not two —
treat it as one.

**Withdrawals**
Drop any `BUILD` row whose `entry_id` is referenced as a `supersedes_id` by
some other row with `record_type = "WITHDRAWAL"`.

**Canonical JSON**
One descriptor per bundle, with `bundle_id`, `artifact_count`, `total_bytes`.

**Current key**
Always fetch the current signing key first. Before signing, check: does the
key exist, does the certificate exist, is `status` `"current"`, is the
algorithm supported. Never use the revoked key.

**Idempotency**
If a bundle is already published, don't publish it again — reuse the saved
receipt and request token on repeat runs.

## 4. Verifier Design

**What does `test.sh` do?**
Sets up the test environment before the actual test cases run.

**Gateway check**
Before the Python tests run, the verifier checks the distribution gateway is
up and waits until it's ready to accept requests. Every check runs against
the live gateway. Once verification finishes, the gateway process gets
stopped.

**Pytest check**
Tests run through pytest, and they check *behavior*, not implementation —
so any correct implementation can pass, not just this one.

**Reward**
Writes `1` if everything passes, `0` otherwise.

**What the Python tests actually check**
Manifest processing, report output, gateway publication, and database
state. They also check that repeated runs give the same output and don't
create duplicate publications (idempotency).

## 5. Gateway Test Result

Ran the gateway's own test suite — all 5 passed. Gateway itself is fine,
nothing wrong there.

### Before Proof A

Command:
```
docker build -t hurix-firmware-task .\environment
```

Output (trimmed):
```
[+] Building 2.7s (20/20) FINISHED                                       docker:desktop-linux
 => [internal] load build definition from Dockerfile                                     0.1s
 => [internal] load metadata for docker.io/library/node:20-slim                          2.0s
 => CACHED [ 5/14] RUN mkdir -p /app/keys/current /app/keys/revoked && openssl req -x5   0.0s
 => CACHED [ 7/14] RUN npm install --no-audit --no-fund                                  0.0s
 => CACHED [10/14] RUN npm install --no-audit --no-fund                                  0.0s
 => CACHED [13/14] COPY fixtures/build_manifest.csv /app/fixtures/build_manifest.csv     0.0s
 => CACHED [14/14] COPY reports/publications.expected.txt /app/reports/...               0.0s
 => exporting to image                                                                   0.2s
 => => naming to docker.io/library/hurix-firmware-task:latest                            0.0s
```

Evidence: `=> naming to docker.io/library/hurix-firmware-task:latest`

Conclusion: image built fine, environment is set up correctly.

## 6. Proof A — Missing Publisher

1. Remove the publisher.
2. Run the verifier.
3. Verification fails, as expected.
4. Reward = 0.

Command:
```
docker run --rm -it `
  --name hurix-proof-a `
  -v "${PWD}\tests:/tests:ro" `
  hurix-firmware-task bash
```
then:
```
bash /tests/test.sh
```

Evidence:
```
...
4 failed, 2 warnings, 9 errors in 0.75s
pytest exit code: 1
```

Reward check:
```
cat /logs/verifier/reward.txt
```
Output: `0`

Conclusion: verification fails as expected because
`release-publisher.mjs` isn't installed. Confirms the verifier correctly
rejects an incomplete solution.

## 7. Proof B — Correct Publisher and Idempotency

1. Install the publisher.
2. Run the verifier.
3. All 13 tests pass.
4. Reward = 1.
5. Repeated run reuses the existing publication.
6. No duplicate publication gets created.

Start a fresh container:
```
docker run --rm -it `
  --name hurix-proof-b `
  -v "${PWD}\solution:/solution:ro" `
  -v "${PWD}\tests:/tests:ro" `
  hurix-firmware-task bash
```

Install the solution:
```
bash /solution/publish.sh
```
Output: `Installed reference publisher at /app/publisher/release-publisher.mjs`

Check it landed:
```
ls /app/publisher
```
Output: `release-publisher.mjs`

Run the verifier:
```
bash /tests/test.sh
```
Evidence: `13 passed`, `pytest exit code: 0`

Reward check:
```
cat /logs/verifier/reward.txt
```
Output: `1`

Conclusion: all verifier tests pass, reward is 1.

## 8. Idempotency Proof

1. Run the publisher twice.
2. Both runs produce the same output.
3. Existing receipt gets reused.
4. No duplicate publication gets created.

Command:
```
node publisher/release-publisher.mjs --report > first.txt
node publisher/release-publisher.mjs --report > second.txt
diff -u first.txt second.txt
```

Evidence: no output (the diff is empty).

Conclusion: repeated runs give byte-identical reports, so there's no
difference to show.

## 9. Resubmission Fix — Reference Publisher Install Path

**What was wrong**

`solution/publish.sh` originally had a hardcoded path:
`SOURCE="/solution/release-publisher.mjs"`. That matched the example mount
path in the submission handbook (`-v "$PWD/../solution":/solution:ro`), but
the real grading harness doesn't necessarily mount `solution/` at
`/solution`. If it mounts the folder somewhere else, the hardcoded path
never resolves, `publish.sh` exits before copying the file, and the
reference implementation never lands at
`/app/publisher/release-publisher.mjs` — so Proof B can't pass, even though
the solution itself is correct.

**The fix**

`solution/publish.sh` now resolves the source file relative to its own
script location instead of a fixed path:

```
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="${SCRIPT_DIR}/release-publisher.mjs"
```

Since `release-publisher.mjs` always ships alongside `publish.sh` inside
`solution/`, this resolves correctly no matter where that folder gets
mounted at grading time.

**Re-verification** (fresh, no-cache image, same two proofs)

- `docker build --no-cache -t hurix-verify environment/`
- Proof A (no solution mounted): `bash /tests/test.sh` → 4 failed, 9 errors
  → `reward.txt` = `0`.
- Proof B, run twice with two different mount points to confirm the fix
  isn't tied to one specific path:
  - `-v .../solution:/solution:ro` (the handbook's own example path) →
    `bash /solution/publish.sh && bash /tests/test.sh` → 13 passed →
    `reward.txt` = `1`.
  - `-v .../solution:/mnt/weird-solution-path:ro` (an arbitrary different
    path) → `bash /mnt/weird-solution-path/publish.sh && bash /tests/test.sh`
    → 13 passed → `reward.txt` = `1`.

**Conclusion**

The empty run still scores 0, and the reference solution now scores 1 no
matter where `solution/` gets mounted — which is exactly what the earlier
review flagged as broken.

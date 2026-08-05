# Firmware Release Publisher

## 1. Task and command
### Main problem
1. Publisher is not completed.
2. Candidate will make the publisher.


### What should be implemented by Candidate
1. Publisher read manifes, build bundle, do sign, publish gateway and Save state in DuckDB.


### What command he will use
`
cd /app
npm run report
`



## 2. Manifest reconciliation rules
### Business rules
1. Read Manifest CSV.
2. Remove duplicate rows.
3. A duplicate is a row identical across every column (entry_id, bundle_id, component_id, version, size_bytes, record_type, supersedes_id, recorded_at). Collapse to one.
4. Apply WITHDRAWAL record.
5. A WITHDRAWAL row's supersedes_id equals the entry_id of the BUILD it cancels; that build is excluded. If every build in a bundle is cancelled, skip the bundle entirely (no report lines for it)
6. Cound only valid BUILD.
7. Calulate artifact_count, total_bytes.
8. Process build_id in order



## 3. Descriptor and Signing
1. read current key from metadata gateway
2. Status should be current
3. Algorithm should be corrected.
4. Not used Revoked key
6. Generate a canonical JSON descriptor with keys sorted lexicographically.
7. Sign the descriptor using the current signing key with detached CMS signature



## 4. Gateway publication
1. Use gateway endpoint.
2. Sent descriptor, signature, request_token
3. Got pulication_id in response
4. Status should be PUBLISHED


## 5. Database and idempotency
1. Save successful publication.
2. Persist state at /app/releases.duckdb (created at runtime, do not pre-create)   3. npm run report must reproduce reports/publications.expected.txt exactly (RECEIPT value is masked by the grader)
4. Save Build_id, Publication, Token, Descriptor
5. Duplicate pulish should not be come on repeated run 
6. Use old receipt



## 6. Report output 
1. In Report - print 2 line for every bundle


## 7. Restrictions
1. Restrictions
2. Do not modify the provided gateway.
3. Use HTTP only.
4. Do not read the gateway private ledger.
5. Do not hardcode expected output.
6. Do not use revoked signing key.
7. Core reconciliation must use DuckDB SQL.


## 8. Success condition
### Publisher should:
- publish only valid bundles
- save publication state
- support idempotent reruns
- produce deterministic report
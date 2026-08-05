
# Author Notes

## 1. Task Summary
1. What is the task?
- The actual assignment tasks is: Candidate -> Implement release-publisher.mjs -> Read firmware manifest -> Reconcile data correctly -> Generate bundle descriptor -> Sign descriptor -> Publish descriptor -> Store publication -> Support repeated execution -> Generate report.

2. What is the main objective?
- Implement a secure firmwae release publisher.


3. What would be done by Publisher?
- Read the firmware manifest -> Find valid firmware bundles -> Create release descriptor -> Sign the descriptor using current signing key -> Publish it to the gateway -> Store successful publication state -> Support idempotent reruns -> Print deterministic report.


4. Assignment flow:- Old publisher -> Sign in using Revoked key -> GateWay-> Verify using current certificate -> Signature doesn't match -> Untrusted Signature.



## 2. Design
1. Read manifest

2. Remove duuplicate
3. Apply the withdrawal
4. Make descriptor
5. Sign in kiya?
6. Publish gateway or not?
7. Save DuckDB or not?


## 3. Important Rules
1. Duplicate
- Two manifest rows are exactly the same. means, If every column in two manifest rows is identical - treat them as one record.

2. Withdrawal
- Exclude Build records, which referenced by supersedes_id. Meaning exclude records whoseentry_id same as supersedes_id of anthor record with record_type="WITHDRAWAL"

3. Canonical JSON
- Create one descriptor per bundle with bundle_id, artifact_count, total_bytes

4. Current key
- Always fetch the current signing key.
- Before signing verify - check this:
    - Key exists or not
    - certificate exists or not
    - Status is "current" or not
    - algorithm is supported or not
- Don't use revoked signing key.

5. Idempotency
- If bundles was already published successfully:
    - Don't publish it again
    - Re-use the saved recipt & request_token on repeated runs


## 4. Verifier design
1. What does test.sh do?
- It prepare the verification environments before running the tests cases.

2. Gateway Verification
- Before python test cases, verifiewer checks provided distribution gateway.
- Verifier waits till the gateway becomes available to accept request. All requests verified via gateway. After verification completes and gateway process stopped.

3. Pytest Verification
- Verifier verify Python test cases using pytest.
- The test cases validate given behaviour of publisher instead of verifying its implemententation and these allows different correct implementations to pass if it's full fills the required behaviour.

4. Reward Generation
- Write reward as 1 else as 0.


5. Python tests check
- The Python tests verify manifest processing, report generation, gateway publication, and database state.

- They also verify repeated runs produce the same output without creating duplicate publications (idempotency).



## 5. Gateway Test result
### Write Command + Output + Conclusion

- Gateway tests run kiye.
- 5 tests pass hue.
- Gateway sahi tha.

### Before Proof A
- Command:
`
docker build -t hurix-firmware-task .\environment
`

- Output:
[+] Building 2.7s (20/20) FINISHED                                       docker:desktop-linux
 => [internal] load build definition from Dockerfile                                     0.1s
 => => transferring dockerfile: 3.65kB                                                   0.0s
 => [internal] load metadata for docker.io/library/node:20-slim@sha256:2cf067cfed83d5ea  2.0s
 => [auth] library/node:pull token for registry-1.docker.io                              0.0s
 => [internal] load .dockerignore                                                        0.0s
 => => transferring context: 147B                                                        0.0s
 => [ 1/14] FROM docker.io/library/node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191  0.0s
 => => resolve docker.io/library/node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a9  0.0s
 => [internal] load build context                                                        0.0s
 => => transferring context: 1.27kB                                                      0.0s
 => CACHED [ 2/14] RUN apt-get update     && apt-get install -y --no-install-recommends  0.0s
 => CACHED [ 3/14] RUN pip install --no-cache-dir --break-system-packages         pytes  0.0s
 => CACHED [ 4/14] WORKDIR /app                                                          0.0s
 => CACHED [ 5/14] RUN mkdir -p /app/keys/current /app/keys/revoked  && openssl req -x5  0.0s
 => CACHED [ 6/14] COPY package.json /app/package.json                                   0.0s
 => CACHED [ 7/14] RUN npm install --no-audit --no-fund                                  0.0s
 => CACHED [ 8/14] COPY distribution-gateway/package.json /app/distribution-gateway/pac  0.0s
 => CACHED [ 9/14] WORKDIR /app/distribution-gateway                                     0.0s
 => CACHED [10/14] RUN npm install --no-audit --no-fund                                  0.0s
 => CACHED [11/14] WORKDIR /app                                                          0.0s
 => CACHED [12/14] COPY distribution-gateway/ /app/distribution-gateway/                 0.0s
 => CACHED [13/14] COPY fixtures/build_manifest.csv /app/fixtures/build_manifest.csv     0.0s
 => CACHED [14/14] COPY reports/publications.expected.txt /app/reports/publications.exp  0.0s
 => exporting to image                                                                   0.2s
 => => exporting layers                                                                  0.0s
 => => exporting manifest sha256:d0444367eb1eb1097dd585bcd57fe741c50f5b03f0bea5df09bf44  0.0s
 => => exporting config sha256:314f694a2e58244f658a69d88abe09a4bead9b35821b48aff1ff68ce  0.0s
 => => exporting attestation manifest sha256:5698f436fe2896eb826dd3610a03f469f012ca72cc  0.1s
 => => exporting manifest list sha256:c10feceade51f3b5387559be529a4465db6f8acb4cf1e0251  0.0s
 => => naming to docker.io/library/hurix-firmware-task:latest                            0.0s
 => => unpacking to docker.io/library/hurix-firmware-task:latest                         0.0s

- Evidence:
=> naming to docker.io/library/hurix-firmware-task:latest

- Conclusion: Docker image built successfully and the assignment environment was created.


## 6. Proof A - missing publisher
1. Remove the publisher.
2. Run the verifier.
3. Verification failed as expected.
4. Reward = 0.

- Command: 
`
docker run --rm -it `
  --name hurix-proof-a `
  -v "${PWD}\tests:/tests:ro" `
  hurix-firmware-task bash
`
+
`
bash /tests/test.sh
`

- Evidence
...
========================== 4 failed, 2 warnings, 9 errors in 0.75s ===========================
pytest exit code: 1

- Reward
`
cat /logs/verifier/reward.txt
`

- Output:
0

- Conclusion:Verification failed as expected because release-publisher.mjs was not installed. It proves the verifier correctly rejects an incomplete solution.


## 7. Proof B - correct publisher and idempotency
1. Installed the publisher.
2. Run the verifier.
3. All 13 tests passed.
4. Reward = 1.
5. Repeated execution reused the existing publication
6. No duplicate publication was created.

### Start new container and run this command:
` 
docker run --rm -it `
  --name hurix-proof-b `
  -v "${PWD}\solution:/solution:ro" `
  -v "${PWD}\tests:/tests:ro" `
  hurix-firmware-task bash
`

### Install solution 
- command:
`
bash /solution/publish.sh
`

- Output: Installed reference publisher at /app/publisher/release-publisher.mjs

### Verify  
- command:
`
ls /app/publisher
`
- 

- Output: release-publisher.ms

### Verifier
- command:
`
bash /tests/test.sh
`

- Evidence:
13 passed
pytest exit code: 0


## Reward
- Command: cat /logs/verifier/reward.txt

- Output: 1

## Conclusion: All verifier tests passed successfully and reward value became 1.


## 8. Idempotency Proof
1. Run the publisher twice
2. Both runs produces same output.
3. Existing receipt was reused
4. No duplicate publication created


- Command
`
node publisher/release-publisher.mjs --report > first.txt
node publisher/release-publisher.mjs --report > second.txt
diff -u first.txt second.txt
`

- Evidence: no output

- Conclusion: Repeated execution gives identical bytes reports Therefor no difference found.

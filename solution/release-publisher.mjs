import duckdb from "duckdb";

const REPORT_FLAG = "--report";

const BASE_URL = "http://127.0.0.1:7070";
const SIGNIN_ENDPOINT = `${BASE_URL}/v1/signing-key/current`;

// Validates that the CLI
function validate(args = process.argv.slice(2)) {
    const [flag] = args;

    if (args.length !== 1 || flag !== REPORT_FLAG) {
        throw new Error(`Expected argument: ${REPORT_FLAG}`);
    }
}


// Retrieve published bundles and return an array of object of bundli_id, artifact_count, and total_bytes for each bundle
async function getBundles(db) {
    const query = `
        WITH unique_entries AS (
            SELECT distinct entry_id, bundle_id, component_id, version, size_bytes, record_type, supersedes_id, recorded_at
            
            FROM manifest_raw
        ),

        withdrawn_ids AS (
            SELECT DISTINCT supersedes_id FROM unique_entries

            WHERE record_type = 'WITHDRAWAL'
                AND supersedes_id IS NOT NULL
                AND supersedes_id <> ''
        ),

        active_builds AS (
            SELECT build.* FROM unique_entries AS build
            
            WHERE build.record_type = 'BUILD'
                AND NOT EXISTS (
                    SELECT 1 FROM withdrawn_ids AS withdrawal

                    WHERE withdrawal.supersedes_id = build.entry_id
                )
        )

        SELECT bundle_id, CAST(COUNT(*) AS INTEGER) AS artifact_count, CAST(SUM(size_bytes) AS BIGINT) AS total_bytes

        FROM active_builds
        GROUP BY bundle_id
        ORDER BY bundle_id ASC;
    `;


    const rows = await new Promise((res, rej) => {
        db.all(query, (err, rows) => {
            if (err) {
                rej(err);
                return;
            }

            res(rows);
        });
    });

    return rows.map((row) => ({
        artifact_count: Number(row?.artifact_count || 0),
        bundle_id: row?.bundle_id,
        total_bytes: Number(row?.total_bytes || 0),
    }));
}


// Loads the manifest CSV into a temporary table
async function loadData(db) {
    const query = `
        CREATE OR REPLACE TABLE manifest_raw AS

        SELECT * FROM read_csv('${"/app/fixtures/build_manifest.csv"}', header = true, nullstr = '',
            columns = {
                'entry_id': 'VARCHAR',
                'bundle_id': 'VARCHAR',
                'component_id': 'VARCHAR',
                'version': 'VARCHAR',
                'size_bytes': 'BIGINT',
                'record_type': 'VARCHAR',
                'supersedes_id': 'VARCHAR',
                'recorded_at': 'TIMESTAMP'
            }
        );
    `;

    await new Promise((res, rej) => {
        db.run(query, (err, result) => {
            if (err) {
                rej(err);
                return;
            }
            
            res(result);
        });
    });
}


// Fetches signing key from gateway
async function fetchKey() {
    const response = await fetch(SIGNIN_ENDPOINT);

    if (!response.ok) {
        throw new Error(`fetchKey failed with status ${response.status}.`);
    }

    try {
        return await response.json();
    } catch {
        throw new Error("fetchKey: Invalid JSON response.");
    }
}


async function main() {
    validate();

    const db = new duckdb.Database("/app/releases.duckdb");

    try {
        await loadData(db);

        const bundles = await getBundles(db);
        console.log('bundles: ', bundles);

        const signin_key = await fetchKey();

        // validate signin_key
        if (!signin_key || typeof signin_key !== "object") {
            throw new Error("Signing-key must be an object.");
        } else if (typeof signin_key.key_id !== "string" || signin_key.key_id.length === 0) {
            throw new Error("Signing-key id missing.");
        } else if (typeof signin_key.certificate_ref !== "string" || signin_key.certificate_ref.length === 0) {
            throw new Error("Signing-key certificate missing.");
        }

        console.log('signin_key: ',signin_key)
    } finally {
        await new Promise((res, rej) => {
            db.close((error) => {
                if (error) {
                    rej(error);
                    return;
                }

                res();
            });
        });
    }
}

main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
});
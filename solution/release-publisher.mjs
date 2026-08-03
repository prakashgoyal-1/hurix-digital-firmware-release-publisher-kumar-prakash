import duckdb from "duckdb";

const REPORT_FLAG = "--report";

// Validates that the CLI
function validate(args = process.argv.slice(2)) {
    const [flag] = args;

    if (args.length !== 1 || flag !== REPORT_FLAG) {
        throw new Error(`Expected argument: ${REPORT_FLAG}`);
    }
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



async function main() {
    validate();

    const db = new duckdb.Database("/app/releases.duckdb");

    try {
        await loadData(db);
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
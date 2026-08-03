import duckdb from "duckdb";

const REPORT_FLAG = "--report";

// Validates that the CLI
function validate(args = process.argv.slice(2)) {
    const [flag] = args;

    if (args.length !== 1 || flag !== REPORT_FLAG) {
        throw new Error(`Expected argument: ${REPORT_FLAG}`);
    }
}



async function main() {
    validate();

    const db = new duckdb.Database("/app/releases.duckdb");

    try {
        // Features will be added in later
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
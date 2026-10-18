# Task 04C — PostgreSQL Integration Test Setup Readiness

## Scope and changes

This was a read-only environment and test-setup inspection. No software was installed; no service, container, database, role, schema, DSN, or system setting was created or changed. No connection to an unknown database was attempted. Raw filings, manifest, parser artifacts, and evidence artifacts were not modified.

## Available options actually detected

| Option | Result | Suitability |
| --- | --- | --- |
| Native PostgreSQL | Not detected: no `psql`, `pg_ctl`, `initdb`, PostgreSQL service, Program Files installation, or registry entry | Not currently usable |
| Docker / Podman | Not detected: no command, service, or installation | Not currently usable |
| WSL | `wsl.exe` is available; default distribution is Ubuntu and WSL version 2 is configured | Best available foundation for an isolated local setup after approval |
| Windows Package Manager | `winget.exe` is available | Can install native PostgreSQL after approval, but is a larger Windows-wide change than WSL |
| Python PostgreSQL driver | `psycopg` is not installed | Install the project `storage` extra after approval |
| Test DSN | `TEST_POSTGRES_DSN` and `DATABASE_URL` are unset | No database connection should be attempted |

## Integration-test safety review

`tests/integration/test_postgres_evidence_storage.py` is appropriate for a dedicated disposable test database:

- It is opt-in: it skips without `psycopg` or `TEST_POSTGRES_DSN`.
- Each test generates an `evidence_test_<uuid>` schema, sets that schema as the connection `search_path`, and drops only that exact generated schema in fixture cleanup.
- The test never targets `public` explicitly and does not manipulate raw SEC inputs or processed artifacts.

The cleanup uses `DROP SCHEMA ... CASCADE`, so the supplied DSN **must** target a dedicated, disposable database and a narrowly privileged test role. The test does not itself verify database identity or reject a production-looking DSN. That makes operator discipline and a dedicated database prerequisite, not optional safeguards.

## Configuration and command review

The documented driver installation matches `pyproject.toml`: `psycopg[binary]==3.2.10` is declared as the `storage` optional dependency. The project uses `requirements.txt` only for `.[dev]`, so it does not install the storage driver. The correct approved installation is therefore:

```powershell
python -m pip install -e ".[dev,storage]"
```

The documented test command is correct:

```powershell
$env:TEST_POSTGRES_DSN = "postgresql://<test-role>:<password>@localhost:5432/financial_rag_test"
python -m pytest tests/integration/test_postgres_evidence_storage.py -q
```

Use a session-only environment variable; do not place the DSN in tracked files or print the password. The final validation sequence should then run the complete test suite, Ruff, compileall, and the immutable manifest validator.

## Recommendation

Use the already-present **WSL2 Ubuntu** environment to install PostgreSQL locally after explicit approval. This is the simplest currently available option because it avoids installing Docker Desktop or a Windows PostgreSQL service. Create one dedicated database (for example `financial_rag_test`) solely for these tests and a non-production test role that owns it. Run the integration suite against that database only.

An approved WSL-oriented setup can use PostgreSQL peer authentication without exposing a password by running the integration command as the local `postgres` OS user. It will need a WSL Python environment with the project’s `dev` and `storage` extras. Alternatively, a restricted test role plus a session-only DSN can be configured for an ordinary WSL user. The choice should be made during approved setup, not inferred now.

Native PostgreSQL through `winget` is a viable fallback if WSL is not acceptable, but it installs and configures a Windows service and is therefore more intrusive. Docker/Podman cannot be used until installed.

## Exact WSL setup commands (run only after approval)

Open an Ubuntu WSL shell with `wsl -d Ubuntu`, then run these commands interactively. They install packages, start or use the local PostgreSQL service, create a database, and install Python dependencies; none were run during this task.

```bash
sudo apt update
sudo apt install -y postgresql postgresql-client python3-venv
sudo -u postgres createdb financial_rag_test

cd "/mnt/d/Financial Research RAG Assistant"
python3 -m venv /tmp/financial-rag-pgtest-venv
/tmp/financial-rag-pgtest-venv/bin/python -m pip install -e ".[dev,storage]"

sudo -u postgres env \
  TEST_POSTGRES_DSN='postgresql:///financial_rag_test?user=postgres' \
  /tmp/financial-rag-pgtest-venv/bin/python -m pytest \
  tests/integration/test_postgres_evidence_storage.py -q
```

The `postgres` OS user uses local peer authentication and owns the disposable database, so the DSN above contains no password. Before the first test command, confirm that the `postgres` user can read the project path and execute the virtual-environment Python; if it cannot, use a dedicated password-authenticated test role instead, retaining its DSN only in the current shell session. Once PostgreSQL integration passes, run the same WSL Python executable for `python -m pytest -q`, `python -m ruff check app scripts tests`, `python -m compileall -q app scripts tests`, and `python scripts/validate_sec_registration_manifest.py`.

## Approval required

Before any setup work, approve all of the following:

1. Installing PostgreSQL packages inside the existing WSL Ubuntu distribution and creating a dedicated disposable `financial_rag_test` database and least-privileged test role (recommended); **or** installing native PostgreSQL with `winget` and creating the equivalent dedicated database.
2. Installing the project’s declared `dev` and `storage` Python extras in the chosen test environment.
3. Starting the local PostgreSQL process and executing the integration suite against the new dedicated test database.

No PostgreSQL integration test has executed yet, and no integration pass is claimed.

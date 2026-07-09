from __future__ import annotations

import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .config import Settings
from .generator import OpenAIShortDramaGenerator
from .ingest import read_jsonl
from .pipeline import run_once
from .scheduler import start_scheduler
from .storage import Storage

load_dotenv()

app = typer.Typer(help="Vidiom short-drama generation pipeline.")
console = Console()


def _storage() -> Storage:
    settings = Settings.from_env()
    return Storage(settings.database_path)


@app.command("init-db")
def init_db() -> None:
    storage = _storage()
    storage.migrate()
    console.print(f"Initialized database at {storage.db_path}")


@app.command("ingest-text")
def ingest_text(
    text: str,
    source_type: str = typer.Option("manual", help="Source category."),
    source_ref: str | None = typer.Option(None, help="External source reference."),
) -> None:
    storage = _storage()
    storage.migrate()
    row_id = storage.add_inspiration(text=text, source_type=source_type, source_ref=source_ref)
    console.print(f"Queued inspiration {row_id}")


@app.command("ingest-file")
def ingest_file(path: Path) -> None:
    storage = _storage()
    storage.migrate()
    count = storage.add_inspirations(read_jsonl(path))
    console.print(f"Queued {count} inspirations")


@app.command("run-once")
def run_once_command(
    limit: int = typer.Option(None, help="Maximum inspirations to process."),
) -> None:
    settings = Settings.from_env()
    storage = Storage(settings.database_path)
    storage.migrate()
    generator = OpenAIShortDramaGenerator(settings.language_model)
    result = run_once(storage, generator, limit or settings.batch_size)
    console.print(
        f"processed={result.processed} succeeded={result.succeeded} failed={result.failed}"
    )


@app.command("list-productions")
def list_productions(limit: int = typer.Option(10, help="Maximum rows to show.")) -> None:
    storage = _storage()
    storage.migrate()
    table = Table(title="Productions")
    table.add_column("ID", justify="right")
    table.add_column("Inspiration", justify="right")
    table.add_column("Title")
    table.add_column("Created")
    for production in storage.list_productions(limit):
        table.add_row(
            str(production.id),
            str(production.inspiration_id),
            production.title,
            production.created_at,
        )
    console.print(table)


@app.command("export-production")
def export_production(production_id: int, output: Path) -> None:
    storage = _storage()
    production = storage.get_production(production_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(production.payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    console.print(f"Exported production {production_id} to {output}")


@app.command("scheduler")
def scheduler_command() -> None:
    start_scheduler(Settings.from_env())


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    import uvicorn

    uvicorn.run("vidiom.web:app", host=host, port=port, reload=False)

from __future__ import annotations

from pathlib import Path

from vidiom.ingest import read_jsonl


def test_read_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "input.jsonl"
    path.write_text(
        '{"text":"第一条"}\n\n{"text":"第二条","source_type":"seed"}\n',
        encoding="utf-8",
    )

    rows = list(read_jsonl(path))

    assert [row["text"] for row in rows] == ["第一条", "第二条"]

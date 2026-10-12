"""CSV export helpers."""
import csv
import io
from collections.abc import Iterable, Iterator
from datetime import datetime

from fastapi.responses import StreamingResponse

MAX_EXPORT_ROWS = 100_000

# Spreadsheet programs run cells that start with these as formulas. Usernames and
# messages come from logs an attacker can influence, so neutralize them ("CSV injection").
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds") + "Z"  # stored as naive UTC
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def csv_response(filename: str, header: list[str], rows: Iterable[Iterable]) -> StreamingResponse:
    def generate() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        buffer.write("﻿")  # BOM so Excel opens the file as UTF-8
        writer.writerow(header)
        for row in rows:
            writer.writerow([_cell(v) for v in row])
            if buffer.tell() > 64_000:
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

"""CSV import: upload -> validate -> preview -> import -> analyse -> store."""

from __future__ import annotations

import csv
import io
import re
import time
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Report, Site

REQUIRED_COLUMNS = ["report_id", "report_type", "date", "site", "location", "activity", "equipment", "description"]
OPTIONAL_COLUMNS = ["worker_role", "contractor", "injury_severity", "shift", "weather"]
MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024
TYPE_ALIASES = {
    "unsafe act": "Unsafe Act", "ua": "Unsafe Act",
    "unsafe condition": "Unsafe Condition", "uc": "Unsafe Condition",
    "near miss": "Near Miss", "near-miss": "Near Miss", "nm": "Near Miss", "nearmiss": "Near Miss",
    "incident": "Incident", "inc": "Incident",
}
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%d %b %Y", "%d %B %Y")

_PENDING: dict[str, tuple[float, list[dict[str, Any]]]] = {}
TTL_SECONDS = 1800


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def validate_csv(db: Session, content: bytes) -> dict[str, Any]:
    if len(content) > MAX_BYTES:
        return {"ok": False, "error": f"File exceeds {MAX_BYTES // (1024 * 1024)} MB limit"}
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    headers = [_norm_header(h) for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        return {"ok": False, "error": f"Missing required column(s): {', '.join(missing)}", "columns_found": headers, "required_columns": REQUIRED_COLUMNS}

    existing_ids = set(db.scalars(select(Report.report_id)).all())
    sites = {s.name.lower(): s for s in db.scalars(select(Site)).all()} | {s.code.lower(): s for s in db.scalars(select(Site)).all()}
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    new_sites: set[str] = set()
    rows_detected = 0
    for line_no, raw in enumerate(reader, start=2):
        rows_detected += 1
        if rows_detected > MAX_ROWS:
            return {"ok": False, "error": f"File has more than {MAX_ROWS} rows"}
        row = {_norm_header(k): (v or "").strip() for k, v in raw.items() if k}
        errors: list[str] = []
        for c in REQUIRED_COLUMNS:
            if not row.get(c):
                errors.append(f"{c} is empty")
        rid = row.get("report_id", "")
        if rid and not re.fullmatch(r"[A-Za-z0-9_\-/.]{3,40}", rid):
            errors.append("report_id must be 3-40 chars (letters, digits, - _ / .)")
        if rid in existing_ids:
            errors.append("report_id already exists")
        if rid in seen:
            errors.append("duplicate report_id in file")
        seen.add(rid)
        rtype = TYPE_ALIASES.get(row.get("report_type", "").lower())
        if row.get("report_type") and not rtype:
            errors.append("report_type must be Unsafe Act / Unsafe Condition / Near Miss / Incident")
        d = parse_date(row.get("date", ""))
        if row.get("date") and d is None:
            errors.append("date not recognised (use YYYY-MM-DD)")
        if d and d > date.today():
            errors.append("date is in the future")
        if row.get("description") and len(row["description"]) < 15:
            errors.append("description shorter than 15 characters")
        site_key = row.get("site", "").lower()
        if site_key and site_key not in sites:
            new_sites.add(row["site"])
        rec = {c: row.get(c) or None for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}
        rec.update({"report_type": rtype, "date": d.isoformat() if d else None})
        if errors:
            invalid.append({"line": line_no, "report_id": rid or None, "errors": errors})
        else:
            valid.append(rec)

    token = uuid.uuid4().hex
    now = time.time()
    for k in [k for k, (t, _) in _PENDING.items() if now - t > TTL_SECONDS]:
        _PENDING.pop(k, None)
    _PENDING[token] = (now, valid)
    return {
        "ok": True,
        "token": token,
        "rows_detected": rows_detected,
        "valid_rows": len(valid),
        "invalid_rows": len(invalid),
        "errors": invalid[:100],
        "preview": valid[:15],
        "new_sites": sorted(new_sites),
        "columns_found": headers,
        "optional_columns_present": [c for c in OPTIONAL_COLUMNS if c in headers],
    }


def take_pending(token: str) -> list[dict[str, Any]] | None:
    item = _PENDING.pop(token, None)
    if not item or time.time() - item[0] > TTL_SECONDS:
        return None
    return item[1]


def get_or_create_site(db: Session, name: str) -> Site:
    key = name.strip().lower()
    for s in db.scalars(select(Site)).all():
        if s.name.lower() == key or s.code.lower() == key:
            return s
    code = re.sub(r"[^A-Z0-9]", "", name.upper())[:6] or "SITE"
    base, i = code, 1
    while db.scalars(select(Site).where(Site.code == code)).first():
        i += 1
        code = f"{base[:5]}{i}"
    s = Site(code=code, name=name.strip(), region=None, site_type="Imported", exposure_hours=None, is_synthetic=False)
    db.add(s)
    db.flush()
    return s

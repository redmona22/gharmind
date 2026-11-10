import io
import re
from typing import Any

from openpyxl import load_workbook
from pydantic import ValidationError

from app.schemas.listing import ListingIn

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000
MAX_ERRORS_SHOWN = 100
PREVIEW_ROWS = 15


class ImportFileError(ValueError):
    """The file as a whole cannot be used."""


# Header names (lowercase, letters and digits only) that map to each listing field.
ALIASES: dict[str, list[str]] = {
    "listing_type": ["type", "listingtype", "saleorrent", "category", "salerent"],
    "project": ["project", "projectname", "property", "propertyname", "title", "name"],
    "price": ["price", "rent", "monthlyrent", "pricerent", "saleprice", "amount", "pricerupees"],
    "deposit": ["deposit", "securitydeposit"],
    "bhk": ["bhk", "bedrooms", "beds"],
    "area_sqft": ["area", "areasqft", "sqft", "areasqfeet", "size"],
    "location": ["location", "locality", "address", "city"],
    "furnishing": ["furnishing", "furnished"],
    "status": ["status", "availability"],
    "rera_number": ["rera", "reranumber", "rerano", "reraregistration", "reraid", "reraregistrationnumber"],
}
_LOOKUP = {alias: field for field, names in ALIASES.items() for alias in names}

_TYPES = {
    "sale": "sale", "sell": "sale", "sales": "sale", "buy": "sale", "resale": "sale",
    "rent": "rent", "rental": "rent", "rentals": "rent", "lease": "rent",
}

_LABELS = {
    "listing_type": "Type", "project": "Project", "price": "Price / rent", "deposit": "Deposit",
    "bhk": "BHK", "area_sqft": "Area", "location": "Location", "furnishing": "Furnishing",
    "status": "Status", "rera_number": "RERA number",
}


def _norm(header: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).lower())


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _text(v: Any) -> str | None:
    if _blank(v):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _number(v: Any, label: str) -> int | None:
    if _blank(v):
        return None
    if isinstance(v, bool):
        raise ValueError(f"{label} must be a number")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v.is_integer():
            return int(v)
        raise ValueError(f"{label} must be a whole number")
    text = re.sub(r"(₹|rs\.?|inr|,|\s)", "", str(v).strip().lower())
    if re.fullmatch(r"\d+", text):
        return int(text)
    if re.fullmatch(r"\d+\.0+", text):
        return int(float(text))
    raise ValueError(f"{label} must be a whole number in rupees, like 6500000 (no 'lakh' or 'crore')")


def _bhk(v: Any) -> int | None:
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d+)\s*(bhk|bed|beds|bedroom|bedrooms)?\s*", v.lower())
        if m:
            return int(m.group(1))
    return _number(v, "BHK")


def _convert(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    out: dict[str, Any] = {}

    type_text = _text(raw.get("listing_type"))
    if type_text is None:
        errors.append("Type is empty. Use sale or rent.")
    elif type_text.lower() not in _TYPES:
        errors.append(f"Type '{type_text}' is not recognised. Use sale or rent.")
    else:
        out["listing_type"] = _TYPES[type_text.lower()]

    project = _text(raw.get("project"))
    if project is None:
        errors.append("Project name is empty.")
    else:
        out["project"] = project

    for field, conv, label in (
        ("price", lambda v: _number(v, "Price / rent"), "Price / rent"),
        ("deposit", lambda v: _number(v, "Deposit"), "Deposit"),
        ("bhk", _bhk, "BHK"),
        ("area_sqft", lambda v: _number(v, "Area"), "Area"),
    ):
        try:
            out[field] = conv(raw.get(field))
        except ValueError as e:
            errors.append(str(e))

    out["location"] = _text(raw.get("location"))
    furnishing = _text(raw.get("furnishing"))
    out["furnishing"] = furnishing.lower() if furnishing else None
    status = _text(raw.get("status"))
    out["status"] = status.lower() if status else "available"
    out["rera_number"] = _text(raw.get("rera_number"))
    return out, errors


def parse_workbook(data: bytes) -> dict[str, Any]:
    """Read an .xlsx file and check every row. Nothing is written to the database here."""
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise ImportFileError("Could not read this file. Upload an Excel .xlsx file.")

    columns: dict[int, str] = {}
    unrecognised: list[str] = []
    errors: list[dict] = []
    error_count = 0
    items: list[dict] = []
    preview: list[dict] = []
    rows_total = 0
    header_found = False
    missing: list[str] = []

    try:
        ws = wb.worksheets[0]
        for row_no, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if not header_found:
                if all(_blank(c) for c in row):
                    continue
                header_found = True
                taken: set[str] = set()
                for idx, h in enumerate(row):
                    if _blank(h):
                        continue
                    field = _LOOKUP.get(_norm(h))
                    if field and field not in taken:
                        columns[idx] = field
                        taken.add(field)
                    else:
                        unrecognised.append(str(h).strip())
                missing = [_LABELS[f] for f in ("listing_type", "project") if f not in taken]
                if missing:
                    break
                continue

            if all(_blank(c) for c in row):
                continue
            rows_total += 1
            if rows_total > MAX_ROWS:
                raise ImportFileError(f"Too many rows. Import at most {MAX_ROWS} at a time.")

            raw = {field: (row[idx] if idx < len(row) else None) for idx, field in columns.items()}
            payload, problems = _convert(raw)
            if not problems:
                try:
                    items.append(ListingIn(**payload).model_dump())
                    if len(preview) < PREVIEW_ROWS:
                        preview.append(items[-1])
                except ValidationError as e:
                    for err in e.errors():
                        field = str(err["loc"][0]) if err["loc"] else ""
                        problems.append(f"{_LABELS.get(field, field)}: {err['msg']}")
            if problems:
                error_count += 1
                if len(errors) < MAX_ERRORS_SHOWN:
                    errors.append({"row": row_no, "messages": problems})
    finally:
        wb.close()

    if not header_found:
        raise ImportFileError("The file is empty.")

    not_promotable = sum(
        1 for i in items if i["listing_type"] == "sale" and not (i["rera_number"] or "").strip()
    )
    return {
        "rows_total": rows_total,
        "valid_count": len(items),
        "error_count": error_count,
        "errors": errors,
        "preview": preview,
        "missing_columns": missing,
        "unrecognised_columns": unrecognised,
        "not_promotable_count": not_promotable,
        "items": items,
    }
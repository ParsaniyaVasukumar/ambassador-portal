from __future__ import annotations
import io, logging, re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import pandas as pd
import requests
from app.config import GOOGLE_SHEET_CSV_URL, SAMPLE_DATA_PATH, STATE_NAME_TO_GEOJSON

logger = logging.getLogger("ambassador_portal.data")

EXPECTED_COLUMNS = [
    "sr_no", "name", "brand_name", "billing_name", "ambassador_code",
    "city", "state", "contact_number", "email", "profile",
]

_COLUMN_ALIASES = {
    "sr. no.": "sr_no", "sr no": "sr_no", "name": "name",
    "brand name": "brand_name", "billing name": "billing_name",
    "ambassador code": "ambassador_code", "city": "city", "state": "state",
    "contact number": "contact_number", "e-mail": "email", "email": "email",
    "profile": "profile",
}


@dataclass
class DataCache:
    df: "pd.DataFrame | None" = None
    last_refreshed: "datetime | None" = None
    last_error: "str | None" = None
    source: str = "unknown"
    raw_columns: "list | None" = None
    raw_row_count: int = 0
    raw_sample: "list | None" = None


_cache = DataCache()


def _fetch_csv_text():
    if GOOGLE_SHEET_CSV_URL:
        try:
            resp = requests.get(GOOGLE_SHEET_CSV_URL, timeout=15)
            resp.raise_for_status()
            return resp.text, "google_sheet"
        except Exception as exc:
            logger.warning("Failed to fetch Google Sheet CSV, using sample data: %s", exc)
            _cache.last_error = f"Live sheet fetch failed ({exc}); showing sample data."
    return SAMPLE_DATA_PATH.read_text(encoding="utf-8"), "sample_data"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for col in df.columns:
        key = str(col).strip().lower()
        rename_map[col] = _COLUMN_ALIASES.get(key, key.replace(" ", "_"))
    df = df.rename(columns=rename_map)
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[EXPECTED_COLUMNS]


def _clean_phone(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\D", "", str(value))


def _title_case(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _clean_dataframe(raw: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(raw)
    for col in ["name", "brand_name", "billing_name", "ambassador_code",
                "city", "state", "email", "profile"]:
        df[col] = df[col].apply(_title_case)

    df["contact_number"] = df["contact_number"].apply(_clean_phone)
    df["sr_no"] = pd.to_numeric(df["sr_no"], errors="coerce")

    df = df[~((df["name"] == "") & (df["brand_name"] == "") & (df["ambassador_code"] == ""))]
    df = df.reset_index(drop=True)
    df["sr_no"] = df["sr_no"].fillna(pd.Series(range(1, len(df) + 1)))

    df["state_display"] = df["state"].apply(lambda s: s.title() if s else "Unspecified")
    df["geo_state"] = df["state_display"].apply(
        lambda s: STATE_NAME_TO_GEOJSON.get(s.strip().lower(), s)
    )

    key_fields = ["name", "brand_name", "city", "state", "contact_number", "email"]
    df["completeness"] = df[key_fields].apply(
        lambda row: round(sum(1 for v in row if v) / len(key_fields) * 100), axis=1
    )
    df["is_incomplete"] = df["completeness"] < 60

    df["ambassador_code"] = df["ambassador_code"].replace("", "N/A")
    df["profile"] = df["profile"].replace("", "Unclassified")
    return df


def refresh(force: bool = False) -> DataCache:
    csv_text, source = _fetch_csv_text()
    try:
        raw = pd.read_csv(io.StringIO(csv_text), engine="python", on_bad_lines="skip")
        _cache.raw_columns = [str(c) for c in raw.columns.tolist()]
        _cache.raw_row_count = len(raw)
        _cache.raw_sample = raw.head(3).fillna("").astype(str).to_dict(orient="records")
        cleaned = _clean_dataframe(raw)
        _cache.df = cleaned
        _cache.source = source
        _cache.last_refreshed = datetime.now(timezone.utc)
        if source == "google_sheet":
            _cache.last_error = None
        logger.info("Data refreshed from %s: %d rows", source, len(cleaned))
    except Exception as exc:
        logger.error("Failed to parse/clean data: %s", exc)
        _cache.last_error = f"Failed to parse data: {exc}"
        if _cache.df is None:
            _cache.df = pd.DataFrame(columns=EXPECTED_COLUMNS + [
                "state_display", "geo_state", "completeness", "is_incomplete"
            ])
    return _cache


def get_cache() -> DataCache:
    from datetime import datetime, timezone
    from app.config import REFRESH_INTERVAL_MINUTES
    stale = (
        _cache.last_refreshed is None
        or (datetime.now(timezone.utc) - _cache.last_refreshed).total_seconds() > REFRESH_INTERVAL_MINUTES * 60
    )
    if stale:
        refresh()
    return _cache


def get_dataframe() -> pd.DataFrame:
    return get_cache().df.copy()


def get_ambassadors(search: str = "", state: str = "", city: str = "", profile: str = "",
                     sort_by: str = "sr_no", sort_dir: str = "asc"):
    df = get_dataframe()
    if search:
        s = search.strip().lower()
        mask = (
            df["name"].str.lower().str.contains(s, na=False)
            | df["brand_name"].str.lower().str.contains(s, na=False)
            | df["city"].str.lower().str.contains(s, na=False)
            | df["ambassador_code"].str.lower().str.contains(s, na=False)
            | df["state_display"].str.lower().str.contains(s, na=False)
        )
        df = df[mask]
    if state:
        df = df[df["state_display"].str.lower() == state.strip().lower()]
    if city:
        df = df[df["city"].str.lower() == city.strip().lower()]
    if profile:
        df = df[df["profile"].str.lower() == profile.strip().lower()]

    valid_sort_cols = {"sr_no", "name", "brand_name", "city", "state_display", "profile", "completeness", "ambassador_code"}
    sort_col = sort_by if sort_by in valid_sort_cols else "sr_no"
    ascending = sort_dir != "desc"
    return df.sort_values(sort_col, ascending=ascending).to_dict(orient="records")


def get_profiles() -> list[str]:
    df = get_dataframe()
    if df.empty:
        return []
    return sorted(p for p in df["profile"].unique().tolist() if p)


def get_states_summary():
    df = get_dataframe()
    if df.empty:
        return []
    grouped = (
        df.groupby(["state_display", "geo_state"]).size().reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    return grouped.to_dict(orient="records")


def get_cities_for_state(state: str):
    df = get_dataframe()
    df = df[df["state_display"].str.lower() == state.strip().lower()]
    if df.empty:
        return []
    grouped = df.groupby("city").size().reset_index(name="count")
    grouped = grouped[grouped["city"] != ""]
    return grouped.sort_values("count", ascending=False).to_dict(orient="records")


def get_analytics_summary():
    df = get_dataframe()
    total = len(df)
    if total == 0:
        return {"total_ambassadors": 0, "total_states": 0, "total_cities": 0,
                "by_state": [], "by_profile": [], "avg_completeness": 0, "incomplete_count": 0}

    by_state = (df.groupby("state_display").size().reset_index(name="count")
                .sort_values("count", ascending=False).to_dict(orient="records"))
    by_profile = (df.groupby("profile").size().reset_index(name="count")
                  .sort_values("count", ascending=False).to_dict(orient="records"))

    return {
        "total_ambassadors": total,
        "total_states": df["state_display"].nunique(),
        "total_cities": df[df["city"] != ""]["city"].nunique(),
        "by_state": by_state,
        "by_profile": by_profile,
        "avg_completeness": round(df["completeness"].mean(), 1),
        "incomplete_count": int(df["is_incomplete"].sum()),
    }
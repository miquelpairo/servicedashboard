import json
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter, defaultdict

import pandas as pd


# =========================
# Config
# =========================
CACHE_FILE = Path("coordinates_cache.json")
OUT_CSV = Path("geocode_cache_audit.csv")
OUT_XLSX = Path("geocode_cache_audit.xlsx")

# Umbrales
SIMILARITY_THRESHOLD = 0.65     # por debajo -> sospechoso
COORD_CLUSTER_THRESHOLD = 8     # coords repetidas >= N -> sospechoso (capital-fallback típico)


# =========================
# Helpers
# =========================
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    # quitar acentos
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.upper()

def similarity(a: str, b: str) -> float:
    a_n = normalize_text(a)
    b_n = normalize_text(b)
    if not a_n and not b_n:
        return 1.0
    if not a_n or not b_n:
        return 0.0
    return SequenceMatcher(None, a_n, b_n).ratio()

def parse_cache_key(key: str):
    """
    Soporta 2 estrategias que has usado:
    - postal-first: "{postal_norm}_{country}"
    - legacy/otros: "POSTAL_CITY_COUNTRY" (lo intentamos inferir)
    """
    parts = key.split("_")
    if len(parts) >= 2 and parts[-1] in {"es", "pt", "ad"}:
        country = parts[-1]
        postal_guess = "_".join(parts[:-1])
        return postal_guess, country
    return key, None


# =========================
# Load cache
# =========================
if not CACHE_FILE.exists():
    raise FileNotFoundError(f"No existe {CACHE_FILE.resolve()}")

with CACHE_FILE.open("r", encoding="utf-8") as f:
    cache = json.load(f)

rows = []
coords_list = []

for key, val in cache.items():
    postal_guess, country_from_key = parse_cache_key(key)

    # Puede ser None, dict (nuevo), o (lat, lon) legacy
    if val is None:
        rows.append({
            "cache_key": key,
            "postal_guess": postal_guess,
            "country": country_from_key,
            "coords": None,
            "lat": None,
            "lon": None,
            "input_city": None,
            "resolved_city": None,
            "display_name": None,
            "query_used": None,
            "validated": False,
            "low_confidence": False,
            "timestamp": None,
            "status": "FAILED_NONE",
        })
        continue

    if isinstance(val, (list, tuple)) and len(val) == 2:
        lat, lon = val
        rows.append({
            "cache_key": key,
            "postal_guess": postal_guess,
            "country": country_from_key,
            "coords": f"{lat},{lon}",
            "lat": lat,
            "lon": lon,
            "input_city": None,
            "resolved_city": None,
            "display_name": None,
            "query_used": "legacy_tuple",
            "validated": True,
            "low_confidence": False,
            "timestamp": None,
            "status": "OK_LEGACY",
        })
        coords_list.append((lat, lon))
        continue

    if isinstance(val, dict):
        coords = val.get("coords")
        lat = coords[0] if isinstance(coords, (list, tuple)) and len(coords) == 2 else None
        lon = coords[1] if isinstance(coords, (list, tuple)) and len(coords) == 2 else None

        country = val.get("country") or country_from_key
        input_city = val.get("input_city") or ""
        resolved_city = val.get("resolved_city") or ""
        display_name = val.get("display_name") or ""
        query_used = val.get("query_used") or val.get("query") or ""
        validated = bool(val.get("validated")) if val.get("validated") is not None else True
        low_conf = bool(val.get("low_confidence")) if val.get("low_confidence") is not None else False
        ts = val.get("timestamp")

        status = "OK"
        if coords is None:
            status = "FAILED_META"

        rows.append({
            "cache_key": key,
            "postal_guess": postal_guess,
            "country": country,
            "coords": f"{lat},{lon}" if lat is not None and lon is not None else None,
            "lat": lat,
            "lon": lon,
            "input_city": input_city,
            "resolved_city": resolved_city,
            "display_name": display_name,
            "query_used": query_used,
            "validated": validated,
            "low_confidence": low_conf,
            "timestamp": ts,
            "status": status,
        })
        if lat is not None and lon is not None:
            coords_list.append((lat, lon))
        continue

    # formato raro
    rows.append({
        "cache_key": key,
        "postal_guess": postal_guess,
        "country": country_from_key,
        "coords": None,
        "lat": None,
        "lon": None,
        "input_city": None,
        "resolved_city": None,
        "display_name": None,
        "query_used": None,
        "validated": False,
        "low_confidence": False,
        "timestamp": None,
        "status": f"UNKNOWN_TYPE_{type(val)}",
    })


df = pd.DataFrame(rows)

# =========================
# Quality metrics
# =========================
# City similarity
df["city_similarity"] = df.apply(
    lambda r: similarity(r.get("input_city", ""), r.get("resolved_city", "")),
    axis=1
)

# Coords clustering
coord_counts = Counter(coords_list)
df["coords_cluster_count"] = df.apply(
    lambda r: coord_counts.get((r["lat"], r["lon"]), 0) if pd.notna(r["lat"]) and pd.notna(r["lon"]) else 0,
    axis=1
)

# Flags
df["flag_city_mismatch"] = (df["city_similarity"] < SIMILARITY_THRESHOLD) & df["status"].str.startswith("OK")
df["flag_clustered_coords"] = (df["coords_cluster_count"] >= COORD_CLUSTER_THRESHOLD) & df["status"].str.startswith("OK")
df["flag_low_confidence"] = df["low_confidence"] & df["status"].str.startswith("OK")
df["flag_not_validated"] = (~df["validated"]) & df["status"].str.startswith("OK")
df["flag_failed"] = df["status"].str.startswith("FAILED")

# Simple suspect score
df["suspect_score"] = 0
df.loc[df["flag_low_confidence"], "suspect_score"] += 3
df.loc[df["flag_not_validated"], "suspect_score"] += 2
df.loc[df["flag_clustered_coords"], "suspect_score"] += 2
df.loc[df["flag_city_mismatch"], "suspect_score"] += 2
df.loc[df["flag_failed"], "suspect_score"] += 4

# Sort
df_sorted = df.sort_values(["suspect_score", "coords_cluster_count", "city_similarity"], ascending=[False, False, True])

# =========================
# Summary prints
# =========================
print("\n=== SUMMARY ===")
print(f"Total cache entries: {len(df)}")
print(f"OK entries: {(df['status'].str.startswith('OK')).sum()}")
print(f"Failed entries: {df['flag_failed'].sum()}")
print(f"City mismatch (<{SIMILARITY_THRESHOLD}): {df['flag_city_mismatch'].sum()}")
print(f"Low confidence: {df['flag_low_confidence'].sum()}")
print(f"Not validated: {df['flag_not_validated'].sum()}")
print(f"Clustered coords (>= {COORD_CLUSTER_THRESHOLD}): {df['flag_clustered_coords'].sum()}")

print("\nTop 20 suspects:")
cols_show = [
    "suspect_score", "country", "postal_guess",
    "input_city", "resolved_city", "city_similarity",
    "lat", "lon", "coords_cluster_count",
    "validated", "low_confidence", "query_used", "status"
]
print(df_sorted[cols_show].head(20).to_string(index=False))

# =========================
# Save reports
# =========================
df_sorted.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
    df_sorted.to_excel(writer, index=False, sheet_name="audit_sorted")

    # Hojas “listas” rápidas
    df_sorted[df_sorted["flag_failed"]].to_excel(writer, index=False, sheet_name="failed")
    df_sorted[df_sorted["flag_city_mismatch"]].to_excel(writer, index=False, sheet_name="city_mismatch")
    df_sorted[df_sorted["flag_clustered_coords"]].to_excel(writer, index=False, sheet_name="coord_clusters")
    df_sorted[df_sorted["flag_low_confidence"]].to_excel(writer, index=False, sheet_name="low_confidence")
    df_sorted[df_sorted["flag_not_validated"]].to_excel(writer, index=False, sheet_name="not_validated")

print(f"\n✅ Saved:\n- {OUT_CSV.resolve()}\n- {OUT_XLSX.resolve()}")

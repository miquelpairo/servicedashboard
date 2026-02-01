"""
Service Dashboard HTML Report Generator (Jinja2-based, Modular)
Generates standalone HTML dashboards with interactive filters and maps
OPTIMIZED FOR LARGE DATASETS (300k+ rows) with columnar format + gzip

CRITICAL FIXES:
- Country normalization to ISO2 BEFORE columnar export
- Available lists extracted FROM processed data (not raw)
- Date format ISO (YYYY-MM-DD)
"""

import json
import os
import gzip
import base64
from datetime import datetime
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from core.report_utils import load_buchi_css, get_sidebar_styles, get_common_report_styles
from app_config.plotting import BUCHI_COLORS
from core.account_linker import AccountLinker


def _has_any_link_column(df) -> bool:
    """Detect if dataframe already contains usable links (AccountURL or SFDC Link variants)."""
    if df is None or df.empty:
        return False

    if "AccountURL" in df.columns:
        s = df["AccountURL"]
        non_empty = s.notna() & (s.astype(str).str.strip() != "") & (s.astype(str).str.lower().str.strip() != "nan")
        if int(non_empty.sum()) > 0:
            return True

    for c in ["SFDC Link", "SFDC_Link", "SFDC URL", "SFDC_URL", "SFDCLink", "SFDCURL"]:
        if c in df.columns:
            s = df[c]
            non_empty = s.notna() & (s.astype(str).str.strip() != "") & (s.astype(str).str.lower().str.strip() != "nan")
            if int(non_empty.sum()) > 0:
                return True

    return False


# ============================================================================
# SAFE STRING CLEANER (CATEGORICAL-SAFE)
# ============================================================================

def s_clean(series: pd.Series, lower: bool = False) -> pd.Series:
    """
    Safe string cleaner for any dtype (including Categorical).
    - Converts to pandas string dtype
    - fillna("")
    - strip
    - optional lower()
    """
    s = series
    try:
        s = s.astype("string")
    except Exception:
        s = series.astype(str)
    s = s.fillna("").str.strip()
    if lower:
        s = s.str.lower()
    return s


# ============================================================================
# JSON SERIALIZATION HELPERS
# ============================================================================

def _json_default(o):
    """
    JSON serialization handler for numpy/pandas types.
    Converts non-serializable types to Python native types.
    """
    # numpy scalars (np.bool_, np.int64, np.float32, etc.)
    if isinstance(o, np.generic):
        return o.item()

    # pandas NA / NaT
    try:
        if pd.isna(o):
            return None
    except Exception:
        pass

    # sets -> list
    if isinstance(o, set):
        return list(o)

    # fallback
    return str(o)


def gzip_b64(obj: Dict[str, Any]) -> str:
    """
    Serialize dict to JSON, gzip it, and return base64 string.
    Robust against numpy/pandas dtypes.
    """
    raw = json.dumps(
        obj,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default
    ).encode("utf-8")

    print(f"  📦 Raw JSON size: {len(raw):,} bytes", flush=True)

    gz = gzip.compress(raw, compresslevel=9)
    print(f"  🗜️ Gzipped size: {len(gz):,} bytes ({len(gz)/len(raw)*100:.1f}%)", flush=True)

    b64 = base64.b64encode(gz).decode("ascii")
    print(f"  📝 Base64 size: {len(b64):,} bytes", flush=True)

    return b64


# ============================================================================
# COLUMNAR FORMAT FUNCTIONS
# ============================================================================

def _build_string_dict(series: pd.Series, name: str):
    """
    Build string dictionary for interning.
    Returns: (dict_list, id_array)
    """
    s = s_clean(series, lower=False)
    
    unique_vals = s.unique().tolist()
    unique_vals = [v for v in unique_vals if v != ""]
    
    val_to_id = {val: idx for idx, val in enumerate(unique_vals)}
    
    EMPTY_ID = -1
    
    id_array = s.map(val_to_id).fillna(EMPTY_ID).astype(int).tolist()
    
    print(f"  📚 {name}: {len(unique_vals)} unique values", flush=True)
    
    return unique_vals, id_array


def build_columnar_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Build columnar dataset with string interning for efficiency.
    
    CRITICAL: df must have Country already normalized to ISO2 lower
    
    Returns:
      {
        "dict": { "country": [...], "rep": [...], "type": [...], ... },
        "cols": { "date": [...], "country": [...], "eur": [...], ... },
        "meta": { "n": N, "has_city": bool, "has_segment": bool, ... }
      }
    """
    print("🔧 Building columnar dataset...", flush=True)
    
    n = len(df)
    
    # ========================================================================
    # BUILD DICTIONARIES (string interning)
    # ========================================================================
    
    dicts = {}
    col_ids = {}
    
    # ⚠️ CRITICAL: Country debe estar NORMALIZADO a ISO2 en df ANTES de llegar aquí
    if 'Country' in df.columns:
        dicts['country'], col_ids['country'] = _build_string_dict(df['Country'], 'Country')
    else:
        dicts['country'] = ['es']
        col_ids['country'] = [0] * n
    
    # Sales Representative
    if 'SalesRepresentative' in df.columns:
        dicts['rep'], col_ids['rep'] = _build_string_dict(df['SalesRepresentative'], 'SalesRep')
    else:
        dicts['rep'] = ['']
        col_ids['rep'] = [0] * n
    
    # Product Type
    if 'ProductType' in df.columns:
        dicts['type'], col_ids['type'] = _build_string_dict(df['ProductType'], 'ProductType')
    else:
        dicts['type'] = ['']
        col_ids['type'] = [0] * n
    
    # Set
    if 'Set' in df.columns:
        dicts['set'], col_ids['set'] = _build_string_dict(df['Set'], 'Set')
    else:
        dicts['set'] = ['']
        col_ids['set'] = [0] * n
    
    # End User Segment (optional)
    has_segment = 'End User Segment' in df.columns
    if has_segment:
        dicts['segment'], col_ids['segment'] = _build_string_dict(df['End User Segment'], 'Segment')
    else:
        dicts['segment'] = ['']
        col_ids['segment'] = [0] * n
    
    # Market Organization (optional)
    has_market_org = 'Market Organization Name' in df.columns
    if has_market_org:
        dicts['marketOrg'], col_ids['marketOrg'] = _build_string_dict(df['Market Organization Name'], 'MarketOrg')
    else:
        dicts['marketOrg'] = ['']
        col_ids['marketOrg'] = [0] * n
    
    # Client (Business Partner Name)
    if 'Business Partner Name' in df.columns:
        dicts['client'], col_ids['client'] = _build_string_dict(df['Business Partner Name'], 'Client')
    else:
        dicts['client'] = ['']
        col_ids['client'] = [0] * n
    
    # Service (ItemIdAndName)
    if 'ItemIdAndName' in df.columns:
        dicts['service'], col_ids['service'] = _build_string_dict(df['ItemIdAndName'], 'Service')
    else:
        dicts['service'] = ['']
        col_ids['service'] = [0] * n
    
    # Account URL (optional)
    if 'AccountURL' in df.columns:
        dicts['accountUrl'], col_ids['accountUrl'] = _build_string_dict(df['AccountURL'], 'AccountURL')
    else:
        dicts['accountUrl'] = ['']
        col_ids['accountUrl'] = [0] * n
    
    # City (optional)
    has_city = 'City' in df.columns and df['City'].notna().sum() > 0
    if has_city:
        dicts['city'], col_ids['city'] = _build_string_dict(df['City'], 'City')
    else:
        dicts['city'] = ['']
        col_ids['city'] = [0] * n
    
    # PostalCode
    if 'PostalCode' in df.columns:
        dicts['postal'], col_ids['postal'] = _build_string_dict(df['PostalCode'], 'PostalCode')
    else:
        dicts['postal'] = ['']
        col_ids['postal'] = [0] * n
    
    # ========================================================================
    # BUILD NUMERIC/DATE COLUMNS
    # ========================================================================
    
    cols = {}
    
    # ⚠️ CRITICAL FIX: Date as ISO string (YYYY-MM-DD)
    if 'Date' in df.columns:
        try:
            date_series = pd.to_datetime(df['Date'], errors='coerce')
            cols['date'] = date_series.dt.strftime('%Y-%m-%d').fillna('').tolist()
        except:
            cols['date'] = s_clean(df['Date'], lower=False).tolist()
    else:
        cols['date'] = [''] * n
    
    # EUR (float32)
    if 'EUR' in df.columns:
        cols['eur'] = df['EUR'].fillna(0).astype('float32').tolist()
    else:
        cols['eur'] = [0.0] * n
    
    # Add all the ID columns
    cols.update(col_ids)
    
    # ========================================================================
    # METADATA (ENSURE PYTHON NATIVE TYPES)
    # ========================================================================
    
    meta = {
        'n': int(n),
        'has_city': bool(has_city),
        'has_segment': bool(has_segment),
        'has_market_org': bool(has_market_org),
    }
    
    print(f"✅ Columnar dataset built: {n:,} rows", flush=True)
    print(f"   Dictionaries: {len(dicts)} types", flush=True)
    print(f"   Columns: {len(cols)} arrays", flush=True)
    print(f"   DEBUG - Sample countries from dict: {dicts['country'][:5]}", flush=True)
    
    return {
        'dict': dicts,
        'cols': cols,
        'meta': meta
    }


def build_map_points_columnar(map_data: pd.DataFrame) -> Dict[str, Any]:
    """
    Build columnar map data (minimal, just coordinates + locKey).
    
    CRITICAL: map_data must have Country already normalized to ISO2 lower
    
    Returns:
      {
        "dict": { "locKey": [...], "resolvedCity": [...] },
        "cols": { "locId": [...], "lat": [...], "lon": [...], "cityId": [...], "validated": [...] },
        "meta": { "n": N }
      }
    """
    print("🗺️ Building map points columnar...", flush=True)
    
    n = len(map_data)
    
    # Build location key (CATEGORICAL-SAFE)
    if 'PostalCode' in map_data.columns and 'Country' in map_data.columns:
        postal = s_clean(map_data['PostalCode'], lower=False)
        country = s_clean(map_data['Country'], lower=True)
        loc_keys = postal + "__" + country
    else:
        loc_keys = pd.Series(['__'] * n)
    
    # Dictionaries
    dicts = {}
    dicts['locKey'], loc_ids = _build_string_dict(loc_keys, 'MapLocKey')
    
    # Resolved City
    if 'ResolvedCity' in map_data.columns:
        dicts['resolvedCity'], city_ids = _build_string_dict(map_data['ResolvedCity'], 'ResolvedCity')
    else:
        dicts['resolvedCity'] = ['Unknown']
        city_ids = [0] * n
    
    # Columns
    cols = {
        'locId': loc_ids,
        'lat': map_data['Latitude'].fillna(0).astype('float32').tolist(),
        'lon': map_data['Longitude'].fillna(0).astype('float32').tolist(),
        'cityId': city_ids,
        'validated': map_data['GeoValidated'].fillna(True).astype(bool).astype(int).tolist() if 'GeoValidated' in map_data.columns else [1] * n
    }
    
    # METADATA (ENSURE PYTHON NATIVE TYPES)
    meta = {'n': int(n)}
    
    print(f"✅ Map points built: {n:,} locations", flush=True)
    print(f"   DEBUG - Sample locKeys: {dicts['locKey'][:5]}", flush=True)
    
    return {
        'dict': dicts,
        'cols': cols,
        'meta': meta
    }


# ============================================================================
# MAIN GENERATOR FUNCTION
# ============================================================================

def generate_service_dashboard_html(
    df_original,
    map_data_with_coords,
    available_years,
    available_months,
    available_reps,
    available_types,
    available_sets,
    geocode_cache,
    account_mapping_file: Optional[str] = None,
    export_mode: str = "legacy"
):
    print(f"🔧 Starting HTML generation (mode={export_mode})...", flush=True)
    print(f"📊 Input df: {len(df_original)} rows", flush=True)
    print(f"📊 Input map: {len(map_data_with_coords)} rows", flush=True)

    # ========================================================================
    # VALIDACIÓN DE DATOS DEL MAPA
    # ========================================================================
    
    if map_data_with_coords is None or len(map_data_with_coords) == 0:
        print("❌ No map data provided!", flush=True)
        return ""
    
    # Validar columnas críticas
    required_map_cols = ['PostalCode', 'Country', 'Latitude', 'Longitude']
    missing_cols = [col for col in required_map_cols if col not in map_data_with_coords.columns]
    
    if missing_cols:
        print(f"❌ Missing critical map columns: {missing_cols}", flush=True)
        return ""
    
    # Filtrar filas sin coordenadas
    map_data_clean = map_data_with_coords.copy()
    before_filter = len(map_data_clean)
    map_data_clean = map_data_clean.dropna(subset=['Latitude', 'Longitude'])
    after_filter = len(map_data_clean)
    
    print(f"🧹 Filtered map data: {before_filter} → {after_filter}", flush=True)
    
    if len(map_data_clean) == 0:
        print("❌ No valid coordinates in map data!", flush=True)
        return ""

    # ========================================================================
    # DETECT POSTAL CODE COLUMN IN MAIN DATA
    # ========================================================================
    
    postal_col = None
    for col in df_original.columns:
        if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
            postal_col = col
            break

    if not postal_col:
        print("❌ No postal code column found in main data", flush=True)
        return ""

    # ========================================================================
    # ⚠️ CRITICAL FIX #1: NORMALIZE COUNTRY TO ISO2 BEFORE EXPORT
    # ========================================================================
    
    df_for_export = df_original.copy()
    
    # Normalize Country to ISO2 lower (CATEGORICAL-SAFE)
    if 'Country' in df_for_export.columns:
        print("🌍 Normalizing Country to ISO2 lower...", flush=True)
        df_for_export['Country'] = s_clean(df_for_export['Country'], lower=True)
        
        # Ensure all are valid ISO2 (2 chars)
        invalid_mask = df_for_export['Country'].str.len() != 2
        if invalid_mask.sum() > 0:
            print(f"⚠️ Found {invalid_mask.sum()} invalid country codes, setting to 'es'", flush=True)
            df_for_export.loc[invalid_mask, 'Country'] = 'es'
        
        print(f"✅ Country normalized. Unique values: {df_for_export['Country'].unique().tolist()}", flush=True)
    else:
        print("⚠️ No Country column, defaulting to 'es'", flush=True)
        df_for_export['Country'] = 'es'

    # ========================================================================
    # ⚠️ CRITICAL FIX #2: EXTRACT AVAILABLE LISTS FROM PROCESSED DATA
    # ========================================================================
    
    print("📋 Extracting filter lists from PROCESSED data...", flush=True)
    
    # Country (already normalized to ISO2)
    available_countries = sorted(df_for_export['Country'].dropna().unique().tolist())
    print(f"   Countries: {available_countries}", flush=True)
    
    # Years (from passed parameter or calculate)
    if not available_years:
        if 'Year' in df_for_export.columns:
            available_years = sorted(df_for_export['Year'].dropna().unique().astype(int).tolist())
        else:
            available_years = []
    else:
        available_years = list(available_years)
    
    # Months
    if not available_months:
        available_months = list(range(1, 13))
    else:
        available_months = list(available_months)
    
    # Reps
    if not available_reps:
        if 'SalesRepresentative' in df_for_export.columns:
            available_reps = sorted(df_for_export['SalesRepresentative'].dropna().unique().tolist())
        else:
            available_reps = []
    else:
        available_reps = list(available_reps)
    
    # Types
    if not available_types:
        if 'ProductType' in df_for_export.columns:
            available_types = sorted(df_for_export['ProductType'].dropna().unique().tolist())
        else:
            available_types = []
    else:
        available_types = list(available_types)
    
    # Sets
    if not available_sets:
        if 'Set' in df_for_export.columns:
            available_sets = sorted(df_for_export['Set'].dropna().unique().tolist())
        else:
            available_sets = []
    else:
        available_sets = list(available_sets)
    
    # Segments
    has_segment = 'End User Segment' in df_for_export.columns
    if has_segment:
        available_segments = sorted(df_for_export['End User Segment'].dropna().unique().tolist())
    else:
        available_segments = []
    
    # Market Orgs
    has_market_org = 'Market Organization Name' in df_for_export.columns
    if has_market_org:
        available_market_orgs = sorted(df_for_export['Market Organization Name'].dropna().unique().tolist())
    else:
        available_market_orgs = []

    # ========================================================================
    # CONVERT DATES TO ISO FORMAT
    # ========================================================================
    
    if "Date" in df_for_export.columns:
        try:
            df_for_export["Date"] = pd.to_datetime(df_for_export["Date"], errors='coerce')
            df_for_export["Date"] = df_for_export["Date"].dt.strftime('%Y-%m-%d')
            print("✅ Dates converted to YYYY-MM-DD", flush=True)
        except Exception as e:
            print(f"⚠️ Date conversion error: {e}", flush=True)
            df_for_export["Date"] = s_clean(df_for_export["Date"], lower=False)

    # ========================================================================
    # STANDARDIZE POSTALCODE COLUMN
    # ========================================================================
    
    if postal_col != 'PostalCode':
        df_for_export['PostalCode'] = s_clean(df_for_export[postal_col], lower=False)

    # ========================================================================
    # ACCOUNT LINKING
    # ========================================================================
    
    print("🔗 Account linking step...", flush=True)

    if _has_any_link_column(df_for_export):
        print("✅ DF already has links. Normalizing...", flush=True)
        linker = AccountLinker()
        df_for_export = linker.enrich_dataframe(df_for_export, account_col='Business Partner Name')
    else:
        print("ℹ️ No links in DF. Using empty columns.", flush=True)
        df_for_export["AccountURL"] = None

    # ========================================================================
    # FEATURE FLAGS
    # ========================================================================
    
    has_city = 'City' in df_for_export.columns and df_for_export['City'].notna().sum() > 0

    # ========================================================================
    # PREPARE MAP DATA FOR EXPORT
    # ========================================================================
    
    map_data_for_export = map_data_clean.copy()
    
    # Normalize Country in map data too
    print("🗺️ Normalizing map Country to ISO2 lower...", flush=True)
    map_data_for_export['Country'] = s_clean(map_data_for_export['Country'], lower=True)
    
    # Ensure valid ISO2
    invalid_mask = map_data_for_export['Country'].str.len() != 2
    if invalid_mask.sum() > 0:
        print(f"⚠️ Map: Found {invalid_mask.sum()} invalid country codes", flush=True)
        map_data_for_export.loc[invalid_mask, 'Country'] = 'es'
    
    if 'City' not in map_data_for_export.columns:
        map_data_for_export['City'] = ''
    
    if 'ResolvedCity' not in map_data_for_export.columns:
        map_data_for_export['ResolvedCity'] = map_data_for_export.get('City', 'Unknown').fillna('Unknown')
    
    if 'GeoValidated' not in map_data_for_export.columns:
        map_data_for_export['GeoValidated'] = True
    
    # Convert types
    map_data_for_export['Latitude'] = pd.to_numeric(map_data_for_export['Latitude'], errors='coerce')
    map_data_for_export['Longitude'] = pd.to_numeric(map_data_for_export['Longitude'], errors='coerce')

    # ========================================================================
    # EXPORT MODE SELECTION
    # ========================================================================
    
    if export_mode == "columnar_gzip":
        print("🚀 Using COLUMNAR + GZIP export mode", flush=True)
        
        # Build columnar datasets
        dataset = build_columnar_dataset(df_for_export)
        map_points = build_map_points_columnar(map_data_for_export)
        
        # Gzip + base64
        dataset_gz_b64 = gzip_b64(dataset)
        map_points_gz_b64 = gzip_b64(map_points)
        
        # Legacy variables (empty for new mode)
        full_data_json = "[]"
        map_data_json = "[]"
        coords_cache_json = "{}"
        
        use_columnar_mode = True
        
    else:
        print("📦 Using LEGACY export mode", flush=True)
        
        # Legacy JSON export
        full_data_json = df_for_export.to_json(orient='records')
        
        export_columns = [
            'PostalCode', 'Country', 'City', 'ResolvedCity',
            'Latitude', 'Longitude', 'Total_EUR', 'Num_Services',
            'Representatives', 'Main_Type', 'GeoValidated'
        ]
        export_columns = [col for col in export_columns if col in map_data_for_export.columns]
        map_data_json = map_data_for_export[export_columns].to_json(orient='records')
        coords_cache_json = json.dumps(geocode_cache)
        
        dataset_gz_b64 = ""
        map_points_gz_b64 = ""
        use_columnar_mode = False

    # ========================================================================
    # LOAD STYLES
    # ========================================================================
    
    buchi_css = load_buchi_css()
    sidebar_styles = get_sidebar_styles()
    common_styles = get_common_report_styles()

    sidebar_items = """
        <h2>📋 Índice</h2>
        <ul>
            <li><a href="#dashboard-section">Dashboard</a></li>
            <li><a href="#map-section">Mapa Geográfico</a></li>
            <li><a href="#trends-section">Multi-Year Trends</a></li>
            <li><a href="#table-section">Tabla de Datos</a></li>
        </ul>
    """

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    year = datetime.now().year

    # ========================================================================
    # JINJA2 SETUP
    # ========================================================================
    
    template_dir = os.path.join(os.path.dirname(__file__), 'core', 'templates')
    if not os.path.exists(template_dir):
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    if not os.path.exists(template_dir):
        template_dir = os.path.join(os.getcwd(), 'core', 'templates')

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )

    template = env.get_template('dashboard_template.html')

    # ========================================================================
    # ⚠️ CRITICAL: DEBUG PRINT ANTES DE RENDER
    # ========================================================================
    
    print(f"\n🔍 DEBUG - Template variables:", flush=True)
    print(f"   use_columnar_mode: {use_columnar_mode}", flush=True)
    print(f"   available_countries: {available_countries}", flush=True)
    print(f"   available_years: {available_years}", flush=True)
    print(f"   available_reps (first 3): {available_reps[:3] if available_reps else []}", flush=True)
    print(f"   available_types (first 3): {available_types[:3] if available_types else []}", flush=True)
    print(f"   has_city: {has_city}", flush=True)
    print(f"   has_segment: {has_segment}", flush=True)
    print(f"   has_market_org: {has_market_org}\n", flush=True)

    # ========================================================================
    # RENDER TEMPLATE
    # ========================================================================
    
    html_content = template.render(
        # CSS / STYLES
        buchi_css=buchi_css,
        sidebar_styles=sidebar_styles,
        common_styles=common_styles,
        colors=BUCHI_COLORS,

        # MODE FLAGS
        use_columnar_mode=bool(use_columnar_mode),

        # COLUMNAR + GZIP DATA
        full_data_b64_gz=dataset_gz_b64 or "",
        map_data_b64_gz=map_points_gz_b64 or "",

        # LEGACY DATA (VACÍO EN COLUMNAR)
        full_data_json=Markup(full_data_json),
        map_data_json=Markup(map_data_json),
        coords_cache_json=Markup(coords_cache_json),

        # ⚠️ CRITICAL: FILTER LISTS (FROM PROCESSED DATA)
        available_years=available_years,
        available_months=available_months,
        available_reps=available_reps,
        available_types=available_types,
        available_sets=available_sets,
        available_countries=available_countries,
        available_segments=available_segments,
        available_market_orgs=available_market_orgs,

        # product_types_list (alias for available_types)
        product_types_list=available_types,

        # FEATURE FLAGS (FORZAR BOOL PYTHON)
        has_city=bool(has_city),
        has_segment=bool(has_segment),
        has_market_org=bool(has_market_org),

        # META / INFO
        timestamp=str(timestamp),
        year=int(year),
        sidebar_items=sidebar_items,
        total_records=int(len(df_original)),
        total_map_points=int(len(map_data_for_export)),
        generation_date=str(datetime.now().strftime('%Y-%m-%d'))
    )

    print(f"✅ HTML generated! Size: {len(html_content):,} bytes ({len(html_content)/1024**2:.2f} MB)", flush=True)

    return html_content
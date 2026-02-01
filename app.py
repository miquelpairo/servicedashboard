# ============================================================================
# IMPORTS - CORE
# ============================================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# ============================================================================
# IMPORTS - BUCHI THEME & TOOLS
# ============================================================================
from buchi_streamlit_theme import apply_buchi_styles
from service_report_generator import generate_service_dashboard_html
from core.account_linker import AccountLinker

# ============================================================================
# IMPORTS - GLOBAL GEOCODING UTILITIES (CRITICAL FIX)
# ============================================================================
from core.global_geocoding_service import (
    normalize_country_code as normalize_country_code_global,
    normalize_postal_code as normalize_postal_code_global,
    build_cache_key as build_cache_key_global,
)

# ============================================================================
# IMPORTS - COLUMN MAPPING SYSTEM
# ============================================================================
from column_mappings import (
    detect_format, 
    get_mapping_for_format, 
    get_additional_columns,
    validate_format,
    get_format_info,
    REQUIRED_COLUMNS
)

# ============================================================================
# IMPORTS - GEOCODING SERVICES
# ============================================================================

# Legacy geocoding service (for old format with City column)
from core.geocoding_service import (
    GeocodingService as LegacyGeocodingService,
    detect_country_from_postal,
    extract_postal_clean,
    normalize_postal_code,
    validate_coordinates,
    build_cache_key,
    normalize_triplet_inputs,
)

# Global geocoding service (for new format with Country column, no City required)
try:
    from core.global_geocoding_service import GlobalGeocodingService
    GLOBAL_GEOCODING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Global geocoding service not available: {e}")
    GLOBAL_GEOCODING_AVAILABLE = False

ACCOUNT_MAPPING_FILE = os.path.join("core", "accounts_URL.xlsx")
ACCOUNT_CACHE_FILE = os.path.join("core", "account_link_cache.json")
ACCOUNT_MIN_SCORE = 80

# Page configuration
st.set_page_config(
    page_title="Service Planning Dashboard", 
    layout="wide",
    page_icon="🗺️"
)

# Apply BUCHI corporate styles
apply_buchi_styles()

# Title
st.markdown('<div class="main-header">🗺️ Service Planning Dashboard</div>', unsafe_allow_html=True)

# Initialize session state
if 'geocoding_service' not in st.session_state:
    st.session_state.geocoding_service = None
    st.session_state.geocoding_service_type = None

if "account_linker" not in st.session_state:
    st.session_state.account_linker = None

if "df_enriched" not in st.session_state:
    st.session_state.df_enriched = None

if "account_cache_dirty" not in st.session_state:
    st.session_state.account_cache_dirty = False

if 'selected_city' not in st.session_state:
    st.session_state.selected_city = None

if 'selected_quick_filters' not in st.session_state:
    st.session_state.selected_quick_filters = []

if 'quick_filter_mode' not in st.session_state:
    st.session_state.quick_filter_mode = 'AND'

if "loaded_file_fingerprint" not in st.session_state:
    st.session_state.loaded_file_fingerprint = None

if "loaded_file_result" not in st.session_state:
    st.session_state.loaded_file_result = None


# ============================================================================
# GEOCODING SERVICE FACTORIES (CACHED RESOURCES)
# ============================================================================

@st.cache_resource
def get_global_geocoder():
    """Create and cache GlobalGeocodingService instance."""
    print("🌍 [cache_resource] Creating GlobalGeocodingService()", flush=True)
    return GlobalGeocodingService()


@st.cache_resource
def get_legacy_geocoder():
    """Create and cache LegacyGeocodingService instance."""
    print("🗺️ [cache_resource] Creating LegacyGeocodingService()", flush=True)
    return LegacyGeocodingService()


# ============================================================================
# GEOCODING SERVICE SELECTOR
# ============================================================================

def select_geocoding_service(df):
    """
    Select appropriate geocoding service based on available columns.
    
    Returns:
        tuple: (service_type, service_instance, description)
        - service_type: 'global' or 'legacy'
        - service_instance: initialized service
        - description: human-readable description
    """
    has_country = 'Country' in df.columns and df['Country'].notna().sum() > 0
    has_city = 'City' in df.columns and df['City'].notna().sum() > 0
    
    # Priority 1: NEW FORMAT (Country + PostalCode, no City required)
    if has_country and GLOBAL_GEOCODING_AVAILABLE:
        service = get_global_geocoder()
        return (
            'global',
            service,
            f"🌍 Global Geocoding (200+ countries, postal-only, GeoNames DB)"
        )
    
    # Priority 2: OLD FORMAT (City + PostalCode, country detection)
    else:
        service = get_legacy_geocoder()
        if has_city:
            desc = "🗺️ Legacy Geocoding (ES/PT/AD/GR/DE, city+postal, Nominatim)"
        else:
            desc = "🗺️ Legacy Geocoding (postal-only fallback, Nominatim)"
        
        return (
            'legacy',
            service,
            desc
        )


# ============================================================================
# FILE LOADER (PURE DATA PROCESSING - NO SESSION STATE MUTATION)
# ============================================================================

def load_file(file):
    """
    Load file and apply format detection and mapping.
    Returns tuple: (df, format_type, format_info) or None
    """
    if file is not None:
        try:
            # 1. CARGAR DATOS RAW
            print("📂 Loading file...", flush=True)
            file.seek(0)  # Reset file pointer
            if file.name.endswith(".csv"):
                df_raw = pd.read_csv(file, encoding='utf-8')
            else:
                df_raw = pd.read_excel(file)
            
            original_rows = len(df_raw)
            
            # 2. LIMPIAR FILAS BASURA
            df = df_raw.copy()
            df = df.dropna(how='all')
            
            if len(df.columns) > 0:
                first_col = df.columns[0]
                df = df[~df[first_col].astype(str).str.strip().str.lower().str.startswith('total', na=False)]
            
            for col in df.columns:
                if df[col].dtype == 'object':
                    mask = df[col].astype(str).str.contains('Applied filters:', case=False, na=False)
                    df = df[~mask]
            
            if len(df.columns) > 0:
                first_col = df.columns[0]
                df = df[df[first_col].notna()]
            
            df = df.reset_index(drop=True)
            cleaned_rows = len(df)
            
            print(f"✅ Loaded {original_rows} rows, cleaned to {cleaned_rows}", flush=True)
            
            # 3. DETECTAR FORMATO
            format_type = detect_format(df.columns.tolist())
            
            if format_type == 'unknown':
                print(f"❌ Unknown format. Columns: {', '.join(df.columns.tolist())}", flush=True)
                return None
            
            # 4. GET FORMAT INFO
            format_info = get_format_info(format_type)
            print(f"✅ Format detected: {format_info['name']}", flush=True)
            
            # 5. VALIDAR FORMATO
            is_valid, missing_cols = validate_format(df, format_type)
            if not is_valid:
                print(f"❌ Missing required columns: {', '.join(missing_cols)}", flush=True)
                return None
            
            # 6. APLICAR MAPEO DE COLUMNAS
            mapping = get_mapping_for_format(format_type)
            reverse_mapping = {}
            
            for standard_name, actual_name in mapping.items():
                if actual_name and actual_name in df.columns:
                    reverse_mapping[actual_name] = standard_name
            
            df = df.rename(columns=reverse_mapping)
            
            # 7. PROCESAR FECHAS
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df[df['Date'].notna()]
            df = df.reset_index(drop=True)
            
            df['Year'] = df['Date'].dt.year
            df['Month'] = df['Date'].dt.month
            df['Month_Name'] = df['Date'].dt.strftime('%B')
            
            # ========================================================================
            # 8. CRITICAL FIX #1: NORMALIZE COUNTRY TO ISO2 (LOWER)
            # ========================================================================
            if 'Country' in df.columns and df['Country'].notna().sum() > 0:
                print("🌍 Normalizing Country column to ISO2 lower...", flush=True)
                
                # Apply normalize_country_code to convert "Spain" → "es", "Netherlands" → "nl", etc.
                df['Country'] = df['Country'].apply(normalize_country_code_global)
                
                # ⚠️ CRITICAL: Convert to lowercase (JS expects "es", not "ES")
                df['Country'] = df['Country'].astype(str).str.lower().str.strip()
                
                # Ensure all are valid ISO2 (2 chars lowercase)
                invalid_mask = df['Country'].str.len() != 2
                if invalid_mask.sum() > 0:
                    print(f"⚠️ Found {invalid_mask.sum()} invalid country codes, setting to 'es'", flush=True)
                    df.loc[invalid_mask, 'Country'] = 'es'
                
                print(f"✅ Country normalized to ISO2 lower: {df['Country'].unique().tolist()}", flush=True)
            else:
                print("🔍 Detecting Country from postal codes", flush=True)
                postal_col = None
                for col in df.columns:
                    if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
                        postal_col = col
                        break
                
                if postal_col:
                    if 'City' in df.columns:
                        df['Country'] = [
                            detect_country_from_postal(p, c)
                            for p, c in zip(df[postal_col], df['City'])
                        ]
                    else:
                        df['Country'] = [
                            detect_country_from_postal(p, None)
                            for p in df[postal_col]
                        ]
                    
                    # ⚠️ CRITICAL: También normalizar a lowercase después de detectar
                    df['Country'] = df['Country'].astype(str).str.lower().str.strip()
                    invalid_mask = df['Country'].str.len() != 2
                    if invalid_mask.sum() > 0:
                        print(f"⚠️ Detected: {invalid_mask.sum()} invalid countries → 'es'", flush=True)
                        df.loc[invalid_mask, 'Country'] = 'es'
                else:
                    df['Country'] = 'es'
            
            # 9. CREAR COLUMNA CITY VACÍA SI NO EXISTE
            if 'City' not in df.columns:
                df['City'] = ''
                print("📍 No City column - using Postal Code only", flush=True)
            
            print(f"✅ File processing complete: {len(df)} records", flush=True)
            
            # RETURN DATA ONLY (no session state mutation)
            return df, format_type, format_info
            
        except Exception as e:
            print(f"❌ Error loading file: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            return None
    return None


# ============================================================================
# FILE UPLOAD
# ============================================================================
st.sidebar.markdown("## 📁 Data Upload")

with st.sidebar.form("upload_form", clear_on_submit=False):
    uploaded_file = st.file_uploader(
        "Upload Service Data (Excel/CSV)",
        type=["xlsx", "csv"],
    )
    do_load = st.form_submit_button("🚀 Load file")

if do_load and uploaded_file:
    file_fingerprint = f"{uploaded_file.name}:{uploaded_file.size}"

    if st.session_state.get("loaded_file_fingerprint") != file_fingerprint:
        st.session_state.loaded_file_fingerprint = file_fingerprint
        st.session_state.loaded_file_result = None

    if st.session_state.loaded_file_result is None:
        with st.spinner("📂 Loading & processing file..."):
            st.session_state.loaded_file_result = load_file(uploaded_file)

# A partir de aquí, usa el resultado si existe
if st.session_state.get("loaded_file_result") is None:
    st.info("👆 **Upload your service data file to get started**")
    st.markdown("""
    ### 📋 Supported Formats:
    - **Original Format**: EUR, ProductType, SalesRepresentative, City
    - **New Format**: LC, Product Type, Sales Representative, Country, SFDC Link
    - **Mixed Format**: Combination of both

    ### 🎯 Features:
    - **Multi-Format Support** - Automatic detection
    - **Global Geocoding** - 200+ countries with GeoNames DB
    - **Native SFDC Links** - Direct from data file
    - **Segment Filters** - End User Segment & Market Organization
    - **Interactive Map** - Valid (●) + Suspicious (▲) locations
    - **Export HTML** - Standalone dashboard
    """)
    st.stop()

df, format_type, format_info = st.session_state.loaded_file_result
file_key = st.session_state.loaded_file_fingerprint  # "name:size"
file_fingerprint = (file_key or "").replace(":", "_")

# ========================================================================
# DEBUG / CACHE CONTROL
# ========================================================================
if st.sidebar.button("🧹 Clear file cache", use_container_width=True):
    st.session_state.loaded_file_result = None
    st.session_state.loaded_file_fingerprint = None
    st.success("✅ File cache cleared")
    st.rerun()

    
# ========================================================================
# SELECT GEOCODING SERVICE (OUTSIDE CACHE)
# ========================================================================
print("\n🔍 Selecting geocoding service...", flush=True)
service_type, service_instance, service_desc = select_geocoding_service(df)
print(f"✅ Selected geocoder: {service_type}", flush=True)

# Store in session state
st.session_state.geocoding_service = service_instance
st.session_state.geocoding_service_type = service_type
st.session_state.file_format = format_type
st.session_state.format_info = format_info

# ========================================================================
# DISPLAY FORMAT INFO IN SIDEBAR
# ========================================================================
st.sidebar.success(f"✅ **{format_info['name']}** detected")
st.sidebar.info(f"📊 {format_info['description']}")
st.sidebar.caption(f"💰 Currency: {format_info['currency']}")
st.sidebar.success(service_desc)

# SFDC Link info
if 'SFDC Link' in df.columns and df['SFDC Link'].notna().sum() > 0:
    st.sidebar.success(f"🔗 SFDC Links available: {df['SFDC Link'].notna().sum()} records")

# Cache info
geo = st.session_state.get("geocoding_service")
cache_len = len(getattr(geo, "cache", {}) or {})
st.sidebar.info(f"📍 Cached coordinates: {cache_len}")

st.sidebar.success(f"✅ {len(df)} records loaded")

file_key = f"{uploaded_file.name}:{uploaded_file.size}"

# ========================================================================
# ACCOUNT LINKER
# ========================================================================
mapping_file = ACCOUNT_MAPPING_FILE if os.path.exists(ACCOUNT_MAPPING_FILE) else None
# Usa el fingerprint ya guardado (no depende de uploaded_file en reruns)
file_fingerprint = (st.session_state.get("loaded_file_fingerprint") or "unknown").replace(":", "_")

if st.session_state.get("account_file_fingerprint") != file_fingerprint:
    st.session_state.account_file_fingerprint = file_fingerprint
    st.session_state.df_enriched = None
    st.session_state.account_linker = None

has_sfdc_link = format_info.get('has_sfdc_link', False) and 'SFDC Link' in df.columns

if has_sfdc_link:
    st.sidebar.success("🔗 Using SFDC Links from data file")
    df_enriched = df.copy()
    df_enriched['account_url'] = df_enriched['SFDC Link']
    df_enriched['url_source'] = 'data_file'
    df_enriched['match_score'] = 100.0
    st.session_state.df_enriched = df_enriched
else:
    st.sidebar.info("🔍 Linking accounts from external mapping")
    if st.session_state.account_linker is None:
        linker = AccountLinker(mapping_file, min_score=ACCOUNT_MIN_SCORE, debug=False) if mapping_file else AccountLinker(min_score=ACCOUNT_MIN_SCORE)
        try:
            linker.load_cache(ACCOUNT_CACHE_FILE)
        except Exception:
            pass
        st.session_state.account_linker = linker

    if st.session_state.df_enriched is None:
        with st.spinner("🔗 Linking accounts (cached) ..."):
            st.session_state.df_enriched = st.session_state.account_linker.enrich_dataframe(
                df,
                account_col="Business Partner Name"
            )
            st.session_state.account_cache_dirty = True

df_base = st.session_state.df_enriched if st.session_state.df_enriched is not None else df

# ========================================================================
# GET AVAILABLE OPTIONS (FROM df_base AFTER ENRICHMENT)
# ========================================================================

# ⚠️ CRITICAL: Extract from df_base (enriched data), not df (raw)
available_years = sorted(df_base['Year'].dropna().unique().astype(int).tolist())
available_reps = sorted(df_base['SalesRepresentative'].dropna().unique().tolist())
available_types = sorted(df_base['ProductType'].dropna().unique().tolist())
available_sets = sorted(df_base['Set'].dropna().unique().tolist())

# ⚠️ CRITICAL: Countries are already ISO2 lower from load_file()
available_countries = sorted(df_base['Country'].dropna().unique().tolist())

print(f"🔍 DEBUG - Available countries for filters: {available_countries}", flush=True)

available_segments = []
available_market_orgs = []

if 'End User Segment' in df_base.columns:
    available_segments = sorted(df_base['End User Segment'].dropna().unique().tolist())

if 'Market Organization Name' in df_base.columns:
    available_market_orgs = sorted(df_base['Market Organization Name'].dropna().unique().tolist())

month_options = list(range(1, 13))
month_labels = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April',
    5: 'May', 6: 'June', 7: 'July', 8: 'August',
    9: 'September', 10: 'October', 11: 'November', 12: 'December'
}

# Reset function
def reset_all_filters():
    st.session_state["year_filter"] = available_years
    st.session_state["month_filter"] = []
    st.session_state["rep_filter"] = available_reps
    st.session_state["type_filter"] = available_types
    st.session_state["set_filter"] = available_sets
    st.session_state["country_filter"] = available_countries
    if available_segments:
        st.session_state["segment_filter"] = available_segments
    if available_market_orgs:
        st.session_state["market_org_filter"] = available_market_orgs
    st.session_state.selected_quick_filters = []
    st.session_state["search_filter"] = ""
    st.session_state["client_filter"] = ""
    st.session_state.selected_city = None

# ========================================================================
# FILTERS - SIDEBAR
# ========================================================================
st.sidebar.markdown("---")
st.sidebar.markdown("## 🎛️ Filters")

# Country filter
with st.sidebar.expander("🌍 Country", expanded=False):
    col_country1, col_country2 = st.columns(2)
    with col_country1:
        st.button("✅ All", key="country_all", use_container_width=True,
                    on_click=lambda: st.session_state.update({"country_filter": available_countries}))
    with col_country2:
        st.button("❌ None", key="country_none", use_container_width=True,
                    on_click=lambda: st.session_state.update({"country_filter": []}))
    
    country_format_map = {
        'es': '🇪🇸 Spain',
        'pt': '🇵🇹 Portugal',
        'ad': '🇦🇩 Andorra',
        'gr': '🇬🇷 Greece',
        'de': '🇩🇪 Germany',
        'nl': '🇳🇱 Netherlands',
        'be': '🇧🇪 Belgium',
        'fr': '🇫🇷 France',
        'it': '🇮🇹 Italy',
        'uk': '🇬🇧 United Kingdom',
        'gb': '🇬🇧 United Kingdom',
        'us': '🇺🇸 United States',
    }
    
    selected_countries = st.multiselect(
        "Select countries",
        available_countries,
        default=available_countries,
        key="country_filter",
        format_func=lambda x: country_format_map.get(x.lower(), x.upper()),
        label_visibility="collapsed"
    )

# Year filter
with st.sidebar.expander("📅 Year", expanded=False):
    col_year1, col_year2 = st.columns(2)
    with col_year1:
        st.button("✅ All", key="year_all", use_container_width=True,
                    on_click=lambda: st.session_state.update({"year_filter": available_years}))
    with col_year2:
        st.button("❌ None", key="year_none", use_container_width=True,
                    on_click=lambda: st.session_state.update({"year_filter": []}))
    
    selected_years = st.multiselect(
        "Select years",
        available_years,
        default=available_years,
        key="year_filter",
        label_visibility="collapsed"
    )

# Month filter
with st.sidebar.expander("📆 Month", expanded=False):
    col_month1, col_month2 = st.columns(2)
    with col_month1:
        st.button("✅ All", key="month_all", use_container_width=True,
                    on_click=lambda: st.session_state.update({"month_filter": month_options}))
    with col_month2:
        st.button("❌ None", key="month_none", use_container_width=True,
                    on_click=lambda: st.session_state.update({"month_filter": []}))
    
    selected_months = st.multiselect(
        "Select months (empty = all)",
        month_options,
        default=[],
        format_func=lambda x: month_labels[x],
        key="month_filter",
        label_visibility="collapsed"
    )

# Sales Representative filter
with st.sidebar.expander("👤 Sales Representative", expanded=False):
    col_rep1, col_rep2 = st.columns(2)
    with col_rep1:
        st.button("✅ All", key="rep_all", use_container_width=True,
                    on_click=lambda: st.session_state.update({"rep_filter": available_reps}))
    with col_rep2:
        st.button("❌ None", key="rep_none", use_container_width=True,
                    on_click=lambda: st.session_state.update({"rep_filter": []}))
    
    selected_reps = st.multiselect(
        "Select representatives",
        available_reps,
        default=available_reps,
        key="rep_filter",
        label_visibility="collapsed"
    )

# Product Type filter
with st.sidebar.expander("🏷️ Product Type", expanded=False):
    col_type1, col_type2 = st.columns(2)
    with col_type1:
        st.button("✅ All", key="type_all", use_container_width=True,
                    on_click=lambda: st.session_state.update({"type_filter": available_types}))
    with col_type2:
        st.button("❌ None", key="type_none", use_container_width=True,
                    on_click=lambda: st.session_state.update({"type_filter": []}))
    
    selected_types = st.multiselect(
        "Select product types",
        available_types,
        default=available_types,
        key="type_filter",
        label_visibility="collapsed"
    )

# Set filter
with st.sidebar.expander("📦 Set", expanded=False):
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        st.button("✅ All", key="set_all", use_container_width=True,
                    on_click=lambda: st.session_state.update({"set_filter": available_sets}))
    with col_set2:
        st.button("❌ None", key="set_none", use_container_width=True,
                    on_click=lambda: st.session_state.update({"set_filter": []}))
    
    selected_sets = st.multiselect(
        "Select sets",
        available_sets,
        default=available_sets,
        key="set_filter",
        label_visibility="collapsed"
    )

# End User Segment filter
if available_segments:
    with st.sidebar.expander("🎯 End User Segment", expanded=False):
        col_seg1, col_seg2 = st.columns(2)
        with col_seg1:
            st.button("✅ All", key="segment_all", use_container_width=True,
                        on_click=lambda: st.session_state.update({"segment_filter": available_segments}))
        with col_seg2:
            st.button("❌ None", key="segment_none", use_container_width=True,
                        on_click=lambda: st.session_state.update({"segment_filter": []}))
        
        selected_segments = st.multiselect(
            "Select segments",
            available_segments,
            default=available_segments,
            key="segment_filter",
            label_visibility="collapsed"
        )
else:
    selected_segments = []

# Market Organization filter
if available_market_orgs:
    with st.sidebar.expander("🏢 Market Organization", expanded=False):
        col_org1, col_org2 = st.columns(2)
        with col_org1:
            st.button("✅ All", key="market_org_all", use_container_width=True,
                        on_click=lambda: st.session_state.update({"market_org_filter": available_market_orgs}))
        with col_org2:
            st.button("❌ None", key="market_org_none", use_container_width=True,
                        on_click=lambda: st.session_state.update({"market_org_filter": []}))
        
        selected_market_orgs = st.multiselect(
            "Select market organizations",
            available_market_orgs,
            default=available_market_orgs,
            key="market_org_filter",
            label_visibility="collapsed"
        )
else:
    selected_market_orgs = []

# Search filter
with st.sidebar.expander("🔍 Search Service", expanded=False):
    quick_mode = st.radio(
        "Quick filter mode:",
        options=['AND', 'OR'],
        horizontal=True,
        key="quick_filter_mode",
        help="AND = All keywords must match | OR = Any keyword matches"
    )
    
    quick_filter_keywords = ['CARE', 'Exact', 'Start', 'Circle', 'Maintain', 'IQ/OQ', 'OQ', 'Install', 'Plus', 'Academy']
    
    cols = st.columns(3)
    for idx, keyword in enumerate(quick_filter_keywords):
        col = cols[idx % 3]
        if col.button(
            keyword, 
            key=f"quick_{keyword}",
            use_container_width=True,
            type="primary" if keyword in st.session_state.selected_quick_filters else "secondary"
        ):
            if keyword in st.session_state.selected_quick_filters:
                st.session_state.selected_quick_filters.remove(keyword)
            else:
                st.session_state.selected_quick_filters.append(keyword)
            st.rerun()
    
    search_text = st.text_input(
        "Or type custom search",
        placeholder="e.g., 'maintenance', 'calibration'...",
        key="search_filter",
        help="Filter services containing this text (case insensitive)",
        label_visibility="collapsed"
    )

# Client filter
with st.sidebar.expander("👥 Client", expanded=False):
    client_search = st.text_input(
        "Filter by Client Name",
        placeholder="e.g., 'Universidad', 'Hospital'...",
        key="client_filter",
        help="Filter by client name (case insensitive)",
        label_visibility="collapsed"
    )

# RESET BUTTON
st.sidebar.markdown("---")
st.sidebar.button(
    "🔄 Reset All Filters",
    type="primary",
    use_container_width=True,
    on_click=reset_all_filters,
    key="reset_btn"
)

# ========================================================================
# APPLY FILTERS
# ========================================================================

df_filtered = df_base.copy()

if selected_countries:
    df_filtered = df_filtered[df_filtered['Country'].isin(selected_countries)]

if selected_years:
    df_filtered = df_filtered[df_filtered['Year'].isin(selected_years)]

if selected_months:
    df_filtered = df_filtered[df_filtered['Month'].isin(selected_months)]

if selected_reps:
    df_filtered = df_filtered[df_filtered['SalesRepresentative'].isin(selected_reps)]

if selected_types:
    df_filtered = df_filtered[df_filtered['ProductType'].isin(selected_types)]

if selected_sets:
    df_filtered = df_filtered[df_filtered['Set'].isin(selected_sets)]

if selected_segments and 'End User Segment' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['End User Segment'].isin(selected_segments)]

if selected_market_orgs and 'Market Organization Name' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['Market Organization Name'].isin(selected_market_orgs)]

# Quick filters with AND/OR mode
if st.session_state.selected_quick_filters:
    if quick_mode == 'AND':
        mask = pd.Series([True] * len(df_filtered), index=df_filtered.index)
        for keyword in st.session_state.selected_quick_filters:
            mask &= df_filtered['ItemIdAndName'].str.contains(keyword, case=False, na=False)
        df_filtered = df_filtered[mask]
    else:
        mask = pd.Series([False] * len(df_filtered), index=df_filtered.index)
        for keyword in st.session_state.selected_quick_filters:
            mask |= df_filtered['ItemIdAndName'].str.contains(keyword, case=False, na=False)
        df_filtered = df_filtered[mask]
elif search_text:
    df_filtered = df_filtered[
        df_filtered['ItemIdAndName'].str.contains(search_text, case=False, na=False)
    ]

if client_search:
    df_filtered = df_filtered[
        df_filtered['Business Partner Name'].str.contains(client_search, case=False, na=False)
    ]

# ========================================================================
# METRICS
# ========================================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_eur = df_filtered['EUR'].sum()
    st.metric("💰 Total EUR", f"€{total_eur:,.2f}")

with col2:
    num_services = len(df_filtered)
    st.metric("📊 Services", f"{num_services:,}")

with col3:
    if 'City' in df_filtered.columns and df_filtered['City'].notna().sum() > 0:
        num_cities = df_filtered['City'].nunique()
        st.metric("📍 Cities", f"{num_cities:,}")
    else:
        postal_col = None
        for col in df_filtered.columns:
            if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
                postal_col = col
                break
        if postal_col:
            num_locations = df_filtered[postal_col].nunique()
            st.metric("📍 Locations", f"{num_locations:,}")
        else:
            st.metric("📍 Locations", "N/A")

with col4:
    num_clients = df_filtered['Business Partner Name'].nunique()
    st.metric("👥 Clients", f"{num_clients:,}")

st.markdown("---")

# ========================================================================
# MAP PREPARATION
# ========================================================================

if len(df_filtered) == 0:
    st.warning("⚠️ No records found with the selected filters. Try adjusting your filters.")
    st.stop()

postal_col = None
for col in df_filtered.columns:
    if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
        postal_col = col
        break

if postal_col is None:
    st.error("❌ Could not find PostalCode column.")
    st.stop()

st.markdown("### 🗺️ Geographic Distribution")

# Group by POSTAL + COUNTRY
agg_dict = {
    'EUR': 'sum',
    'Business Partner Name': 'count',
    'SalesRepresentative': lambda x: ', '.join(x.unique()[:3]),
    'ProductType': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'Mixed'
}

if 'City' in df_filtered.columns:
    agg_dict['City'] = lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]

map_data = df_filtered.groupby([postal_col, 'Country']).agg(agg_dict).reset_index()

if 'City' in df_filtered.columns:
    map_data.columns = ['PostalCode', 'Country', 'City', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']
else:
    map_data.columns = ['PostalCode', 'Country', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']
    map_data['City'] = ''

# ========================================================================
# GEOCODING - ADAPTIVE (CRITICAL FIX #2 + FIX #3)
# ========================================================================

print(f"\n🌍 === STARTING GEOCODING SECTION ===", flush=True)
print(f"Service type: {st.session_state.geocoding_service_type}", flush=True)
print(f"Service instance: {st.session_state.geocoding_service}", flush=True)
print(f"Map data to geocode: {len(map_data)} locations", flush=True)

service_type = st.session_state.geocoding_service_type

if service_type == 'global':
    # ========================================================================
    # GLOBAL GEOCODING SERVICE (Country + PostalCode)
    # CRITICAL FIX #2: Use proper key construction functions
    # CRITICAL FIX #3: Proper validation using source field
    # ========================================================================
    
    st.session_state.geocoding_service.stats.reset()
    st.session_state.geocoding_service.new_coords_added = 0
    
    if len(map_data) > 0:
        unique_postals = map_data[['PostalCode', 'Country']].drop_duplicates()
        
        postals_to_geocode = []
        
        # A) CALCULATE POSTALS TO GEOCODE (USING PROPER FUNCTIONS)
        for _, row in unique_postals.iterrows():
            # 1. Normalize country (already ISO2 lower from load_file)
            cc = normalize_country_code_global(row['Country'])
            pc_raw = row['PostalCode']
            
            # 2. Apply corrections using normalized country
            pc_corr, _ = st.session_state.geocoding_service.corrections.get_corrected_postal(
                "", pc_raw, cc
            )
            
            # 3. Normalize postal code
            pc_norm = normalize_postal_code_global(pc_corr, cc)
            if not pc_norm or not cc:
                continue
            
            # 4. Build cache key using the SAME function as the service
            cache_key = build_cache_key_global(pc_norm, cc)
            
            # 5. Check if we need to geocode
            if cache_key not in st.session_state.geocoding_service.cache:
                postals_to_geocode.append((pc_raw, cc))  # Pass normalized country
        
        if postals_to_geocode:
            st.info(
                f"🌍 Need to geocode {len(postals_to_geocode)} unique postal codes "
                f"(already cached: {len(unique_postals) - len(postals_to_geocode)})"
            )
            
            with st.spinner(f"Geocoding {len(postals_to_geocode)} postal codes..."):
                progress_bar = st.progress(0)
                
                for i, (postal, country) in enumerate(postals_to_geocode):
                    st.session_state.geocoding_service.geocode_location(
                        postal_code=postal,
                        country_code=country,  # Already normalized
                        client_id=None
                    )
                    progress_bar.progress((i + 1) / len(postals_to_geocode))
                
                progress_bar.empty()
            
            saved = st.session_state.geocoding_service.save_cache()
            
            if saved:
                if st.session_state.geocoding_service.new_coords_added > 0:
                    st.success(
                        f"✅ Added {st.session_state.geocoding_service.new_coords_added} new coordinates to cache"
                    )
                else:
                    st.warning(
                        "⚠️ No new coordinates added (all failed), but failures were saved to cache."
                    )
            else:
                st.error("❌ Could not save cache to file.")
        else:
            st.success(f"✅ All {len(unique_postals)} unique postal codes already cached!")
        
        # ========================================================================
        # B) BUILD COORDINATES FOR MAP (USING PROPER FUNCTIONS + SOURCE TRACKING)
        # ========================================================================
        coords_list = []
        resolved_city_list = []
        source_list = []
        reason_list = []
        
        for _, row in map_data.iterrows():
            # 1. Normalize country (already ISO2 lower)
            cc = normalize_country_code_global(row['Country'])
            pc_raw = row['PostalCode']
            
            # 2. Apply corrections using normalized country
            pc_corr, _ = st.session_state.geocoding_service.corrections.get_corrected_postal(
                "", pc_raw, cc
            )
            
            # 3. Normalize postal code
            pc_norm = normalize_postal_code_global(pc_corr, cc)
            
            # 4. Build cache key using the SAME function as the service
            cache_key = build_cache_key_global(pc_norm, cc) if pc_norm and cc else None
            
            # 5. Get cached value
            cached = st.session_state.geocoding_service.cache.get(cache_key) if cache_key else None
            
            if isinstance(cached, dict):
                coords = cached.get('coords')
                source = cached.get('source', 'unknown')
                reason = cached.get('reason', '')
                
                if coords:
                    # Valid coordinates
                    coords_list.append(coords)
                    resolved_city_list.append(cached.get('city') or row.get('City', 'Unknown'))
                    source_list.append(source)
                    reason_list.append(reason)
                else:
                    # Failed geocoding - use centroid for visualization
                    centroid = st.session_state.geocoding_service.get_country_centroid(cc)
                    if centroid:
                        coords_list.append(centroid)
                        resolved_city_list.append(f"⚠️ {row.get('City', 'Unknown')} (centroid)")
                        source_list.append(f"{source}_centroid")
                        reason_list.append(reason)
                    else:
                        coords_list.append((None, None))
                        resolved_city_list.append(row.get('City', 'Unknown'))
                        source_list.append('missing')
                        reason_list.append(reason)
            else:
                coords_list.append((None, None))
                resolved_city_list.append(row.get('City', 'Unknown'))
                source_list.append('missing')
                reason_list.append('')
        
        map_data['Coordinates'] = coords_list
        map_data['ResolvedCity'] = resolved_city_list
        map_data['GeoSource'] = source_list
        map_data['GeoReason'] = reason_list
        
        map_data['Latitude'] = map_data['Coordinates'].apply(
            lambda x: x[0] if x and x[0] is not None else None
        )
        map_data['Longitude'] = map_data['Coordinates'].apply(
            lambda x: x[1] if x and x[1] is not None else None
        )
        
        # ========================================================================
        # CRITICAL FIX #3: PROPER VALIDATION USING SOURCE
        # ========================================================================
        # Valid: geonames or nominatim (successful geocoding)
        # Suspicious: anything with "centroid", "outside_bbox", "mismatch", "no_country_code"
        # Missing: coords = None and no centroid
        
        map_data['GeoValidated'] = map_data['GeoSource'].isin(['geonames', 'nominatim'])

else:
    # LEGACY GEOCODING SERVICE (City + PostalCode)
    
    st.session_state.geocoding_service.stats.reset()
    st.session_state.geocoding_service.new_coords_added = 0
    
    if len(map_data) > 0:
        if 'City' in map_data.columns:
            unique_postals = map_data[['PostalCode', 'City', 'Country']].drop_duplicates()
        else:
            unique_postals = map_data[['PostalCode', 'Country']].copy()
            unique_postals['City'] = ''
        
        postals_to_geocode = []
        
        for _, row in unique_postals.iterrows():
            city_val = row['City'] if 'City' in row and pd.notna(row['City']) else ""
            
            postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
                row['PostalCode'], city_val, row['Country']
            )
            
            cache_key = build_cache_key(postal_fixed, city_fixed, country_fixed)
            cached = st.session_state.geocoding_service.cache.get(cache_key)
            
            if (cached is None) or (isinstance(cached, dict) and cached.get("coords") is None):
                postals_to_geocode.append((postal_fixed, city_fixed, country_fixed))
        
        if postals_to_geocode:
            st.info(
                f"🌍 Need to geocode {len(postals_to_geocode)} unique postal codes "
                f"(already cached: {len(unique_postals) - len(postals_to_geocode)})"
            )
            
            with st.spinner(f"Geocoding {len(postals_to_geocode)} postal codes..."):
                progress_bar = st.progress(0)
                
                for i, (postal_fixed, city_fixed, country_fixed) in enumerate(postals_to_geocode):
                    st.session_state.geocoding_service.geocode_location(
                        postal_fixed, city_fixed, country_fixed
                    )
                    progress_bar.progress((i + 1) / len(postals_to_geocode))
                
                progress_bar.empty()
            
            saved = st.session_state.geocoding_service.save_cache()
            
            if saved:
                if st.session_state.geocoding_service.new_coords_added > 0:
                    st.success(
                        f"✅ Added {st.session_state.geocoding_service.new_coords_added} new coordinates to cache"
                    )
                else:
                    st.warning(
                        "⚠️ No new coordinates added (all failed), but failures were saved to cache."
                    )
            else:
                st.error("❌ Could not save cache to file.")
        else:
            st.success(f"✅ All {len(unique_postals)} unique postal codes already cached!")
        
        # Build coordinates for map
        coords_list = []
        resolved_city_list = []
        
        for _, row in map_data.iterrows():
            city_val = row['City'] if 'City' in row and pd.notna(row['City']) else ""
            
            postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
                row['PostalCode'], city_val, row['Country']
            )
            
            cache_key = build_cache_key(postal_fixed, city_fixed, country_fixed)
            cached = st.session_state.geocoding_service.cache.get(cache_key)
            
            if isinstance(cached, dict):
                coords = cached.get('coords', (None, None))
                coords_list.append(coords)
                resolved_city_list.append(
                    cached.get('resolved_city') or 
                    cached.get('input_city') or 
                    city_fixed or 
                    "Unknown"
                )
            else:
                coords_list.append((None, None))
                resolved_city_list.append(city_fixed or "Unknown")
        
        map_data['Coordinates'] = coords_list
        map_data['ResolvedCity'] = resolved_city_list
        map_data['Latitude'] = map_data['Coordinates'].apply(
            lambda x: x[0] if x and x[0] is not None else None
        )
        map_data['Longitude'] = map_data['Coordinates'].apply(
            lambda x: x[1] if x and x[1] is not None else None
        )

# ========================================================================
# VALIDATE COORDINATES
# ========================================================================

map_data_geocoded = map_data.dropna(subset=['Latitude', 'Longitude']).copy()

if service_type == 'global':
    # Already set GeoValidated in the loop above
    # Suspicious = anything NOT validated (centroid, outside_bbox, etc.)
    pass
else:
    # Legacy service - use validate_coordinates
    map_data_geocoded['GeoValidated'] = map_data_geocoded.apply(
        lambda r: validate_coordinates(r['Latitude'], r['Longitude'], r['Country']),
        axis=1
    )

map_data_valid = map_data_geocoded[map_data_geocoded['GeoValidated'] == True].copy()
map_data_suspicious = map_data_geocoded[map_data_geocoded['GeoValidated'] == False].copy()

# ========================================================================
# RENDER MAP
# ========================================================================

if len(map_data_geocoded) == 0:
    st.warning("⚠️ Could not geocode any postal codes.")
else:
    map_data_valid['Size_Display'] = map_data_valid['Total_EUR'].abs().fillna(0)
    map_data_suspicious['Size_Display'] = map_data_suspicious['Total_EUR'].abs().fillna(0)

    fig = go.Figure()

    # Valid locations (blue circles)
    if len(map_data_valid) > 0:
        sizes = map_data_valid['Size_Display'].fillna(0)
        max_size = sizes.max()
        if max_size > 0:
            normalized_sizes = (sizes / max_size * 30).tolist()
        else:
            normalized_sizes = [10] * len(sizes)
        
        fig.add_trace(go.Scattermapbox(
            lat=map_data_valid['Latitude'],
            lon=map_data_valid['Longitude'],
            mode='markers',
            marker=dict(
                size=normalized_sizes,
                sizemode='diameter',
                sizemin=5,
                color='#2E86C1',
                opacity=0.7,
            ),
            text=map_data_valid['ResolvedCity'],
            customdata=map_data_valid[['PostalCode', 'Country', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']],
            hovertemplate=(
                '<b>%{text}</b><br>'
                'PostalCode: %{customdata[0]}<br>'
                'Country: %{customdata[1]}<br>'
                'Total EUR: €%{customdata[2]:,.2f}<br>'
                'Services: %{customdata[3]}<br>'
                'Reps: %{customdata[4]}<br>'
                'Type: %{customdata[5]}<br>'
                '<extra></extra>'
            ),
            name='✅ Valid',
            showlegend=True
        ))

    # Suspicious locations (red triangles)
    if len(map_data_suspicious) > 0:
        sizes = map_data_suspicious['Size_Display'].fillna(0)
        max_size = sizes.max()
        if max_size > 0:
            normalized_sizes = (sizes / max_size * 30).tolist()
        else:
            normalized_sizes = [10] * len(sizes)
        
        fig.add_trace(go.Scattermapbox(
            lat=map_data_suspicious['Latitude'],
            lon=map_data_suspicious['Longitude'],
            mode='markers',
            marker=dict(
                size=normalized_sizes,
                sizemode='diameter',
                sizemin=5,
                symbol='triangle',
                color='#E74C3C',
                opacity=0.8,
            ),
            text=map_data_suspicious['ResolvedCity'],
            customdata=map_data_suspicious[['PostalCode', 'Country', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']],
            hovertemplate=(
                '<b>⚠️ %{text}</b><br>'
                'PostalCode: %{customdata[0]}<br>'
                'Country: %{customdata[1]}<br>'
                'Total EUR: €%{customdata[2]:,.2f}<br>'
                'Services: %{customdata[3]}<br>'
                'Reps: %{customdata[4]}<br>'
                'Type: %{customdata[5]}<br>'
                '<i>Fallback/suspicious location</i><br>'
                '<extra></extra>'
            ),
            name='⚠️ Suspicious',
            showlegend=True
        ))
    
    fig.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=600,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="rgba(0,0,0,0.2)",
            borderwidth=1
        )
    )
    
    # Auto-zoom
    if len(map_data_geocoded) > 0:
        lat_center = map_data_geocoded['Latitude'].mean()
        lon_center = map_data_geocoded['Longitude'].mean()
        
        lat_range = map_data_geocoded['Latitude'].max() - map_data_geocoded['Latitude'].min()
        lon_range = map_data_geocoded['Longitude'].max() - map_data_geocoded['Longitude'].min()
        max_range = max(lat_range, lon_range)
        
        if max_range < 1:
            zoom_level = 10
        elif max_range < 3:
            zoom_level = 8
        elif max_range < 7:
            zoom_level = 6
        else:
            zoom_level = 5
        
        fig.update_layout(
            mapbox=dict(
                center=dict(lat=lat_center, lon=lon_center),
                zoom=zoom_level
            )
        )
    
    # Display map
    selected_points = st.plotly_chart(
        fig, 
        use_container_width=True,
        key="main_map",
        on_select="rerun"
    )
    
    # Location details panel
    if selected_points and selected_points.selection and selected_points.selection.points:
        selected_indices = [p['point_index'] for p in selected_points.selection.points]
        if selected_indices:
            point_info = selected_points.selection.points[0]
            curve_number = point_info.get('curve_number', 0)
            
            if curve_number == 0 and len(map_data_valid) > 0:
                selected_row = map_data_valid.iloc[selected_indices[0]]
            elif curve_number == 1 and len(map_data_suspicious) > 0:
                selected_row = map_data_suspicious.iloc[selected_indices[0]]
            else:
                selected_row = None
            
            if selected_row is not None:
                selected_postal = selected_row['PostalCode']
                selected_country = selected_row['Country']
                display_city = selected_row['ResolvedCity']
                
                location_data = df_filtered[
                    (df_filtered[postal_col] == selected_postal) &
                    (df_filtered['Country'] == selected_country)
                ].copy()
                
                with st.expander(f"📌 {display_city} ({selected_postal}) — {selected_country.upper()} ({len(location_data)} lines)", expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("💰 Total EUR", f"€{location_data['EUR'].sum():,.2f}")
                    with col2:
                        st.metric("📊 Services", len(location_data))
                    with col3:
                        st.metric("👥 Customers", location_data['Business Partner Name'].nunique())
                    with col4:
                        reps = location_data['SalesRepresentative'].unique()
                        st.metric("👤 Reps", len(reps))
                        if len(reps) <= 3:
                            st.caption(", ".join(reps))
                        else:
                            st.caption(f"{', '.join(reps[:3])} (+{len(reps)-3} more)")
                    
                    st.markdown("---")
                    st.markdown("### 📋 Service Lines")
                    location_data_sorted = location_data.sort_values('Date', ascending=False)
                    
                    all_possible_columns = [
                        'Date', 'City', 'Business Partner Name', 
                        'ItemIdAndName', 'Set', 'ProductType', 'EUR', 'SalesRepresentative'
                    ]
                    
                    table_columns = [col for col in all_possible_columns if col in location_data_sorted.columns]
                    
                    st.dataframe(
                        location_data_sorted[table_columns],
                        use_container_width=True,
                        height=400,
                        hide_index=True
                    )
                    
                    if len(location_data) > 100:
                        st.info(f"ℹ️ Showing all {len(location_data)} services for this location")
    
    st.caption(f"📍 Showing {len(map_data_valid)} valid + {len(map_data_suspicious)} suspicious postal codes")
    
    # Suspicious coordinates expander
    if len(map_data_suspicious) > 0:
        with st.expander(f"⚠️ {len(map_data_suspicious)} postal codes with suspicious/fallback coordinates"):
            susp_display = map_data_suspicious[['PostalCode', 'Country', 'ResolvedCity', 'Latitude', 'Longitude']]
            if 'GeoSource' in map_data_suspicious.columns:
                susp_display = map_data_suspicious[['PostalCode', 'Country', 'ResolvedCity', 'GeoSource', 'GeoReason', 'Latitude', 'Longitude']]
            st.dataframe(susp_display, use_container_width=True)
    
    # Missing coordinates expander
    postals_without_coords = len(map_data) - len(map_data_geocoded)
    if postals_without_coords > 0:
        with st.expander(f"❌ {postals_without_coords} postal codes could not be geocoded"):
            missing_data = map_data[
                map_data['Coordinates'].apply(lambda x: x == (None, None) or x is None)
            ][['PostalCode', 'Country', 'City']]
            st.dataframe(missing_data, use_container_width=True)

st.markdown("---")

# ========================================================================
# SERVICE DETAILS TABLE
# ========================================================================

st.markdown("### 📋 Service Details")

df_table = df_filtered.copy()

all_possible_columns = [
    'Date', 'City', 'Business Partner Name', 
    'ItemIdAndName', 'Set', 'ProductType', 'EUR', 'SalesRepresentative'
]

table_columns = [col for col in all_possible_columns if col in df_table.columns]

st.dataframe(
    df_table[table_columns].sort_values('Date', ascending=False),
    use_container_width=True,
    height=400,
    hide_index=True
)

st.caption(f"📊 Showing {len(df_table)} services")

# ========================================================================
# ACCOUNT LINKING ANALYSIS
# ========================================================================

st.markdown("---")
st.markdown("## 🔗 Account Linking Analysis")

default_account_mapping = os.path.join("core", "accounts_URL.xlsx")

if "account_linking" not in st.session_state:
    st.session_state.account_linking = {}

if has_sfdc_link:
    with st.expander("🔗 SFDC Links Status (from data file)", expanded=False):
        total_records = len(df)
        records_with_link = df['SFDC Link'].notna().sum()
        records_without_link = total_records - records_with_link
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Total Records", total_records)
        with col2:
            st.metric("✅ With SFDC Link", records_with_link)
        with col3:
            st.metric("❌ Without Link", records_without_link)
        
        if records_with_link > 0:
            st.success(f"🎉 {(records_with_link/total_records*100):.1f}% of records have SFDC links")
        
        if records_without_link > 0:
            st.markdown("### ⚠️ Accounts without SFDC Link")
            accounts_without_link = df[df['SFDC Link'].isna()]['Business Partner Name'].unique()
            st.dataframe(
                pd.DataFrame({'Account Name': accounts_without_link}),
                use_container_width=True,
                height=300
            )
elif os.path.exists(default_account_mapping):
    if file_key not in st.session_state.account_linking:
        with st.spinner("🔍 Calculating account linking analysis..."):
            linker = AccountLinker(default_account_mapping, min_score=85, debug=True)

            unique_accounts = df['Business Partner Name'].dropna().unique().tolist()

            for account in unique_accounts:
                linker.get_url_fuzzy(account, top_n=5)

            stats = linker.get_stats()
            match_report = linker.get_match_report()

            st.session_state.account_linking[file_key] = {
                "stats": stats,
                "match_report": match_report,
                "min_score": 85,
                "mapping_file": default_account_mapping,
                "n_unique_accounts": len(unique_accounts),
            }

    data = st.session_state.account_linking[file_key]
    stats = data["stats"]
    match_report = data["match_report"]

    with st.expander("📊 Account URL Matching Statistics (from external mapping)", expanded=False):
        st.caption(
            f"Mapping: {data['mapping_file']} | "
            f"Unique accounts: {data['n_unique_accounts']} | "
            f"Min score: {data['min_score']}"
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📚 Available Mappings", stats['total_mappings'])
        with col2:
            st.metric("🔍 Queries", stats['total_queries'])
        with col3:
            st.metric("✅ Matches", stats['exact_matches'] + stats['fuzzy_matches'])
        with col4:
            st.metric("📊 Match Rate", stats['match_rate'])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎯 Exact Matches", stats['exact_matches'])
        with col2:
            st.metric("🔀 Fuzzy Matches", stats['fuzzy_matches'])
        with col3:
            st.metric("❌ No Matches", stats['no_matches'])

        st.markdown("### 🔍 Detailed Match Report")
        st.dataframe(match_report, use_container_width=True, height=400)

        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("♻️ Recompute analysis", use_container_width=True):
                st.session_state.account_linking.pop(file_key, None)
                st.rerun()
else:
    st.info(f"ℹ️ Account mapping file not found: {default_account_mapping}")

# Save Account Linking Cache
if st.session_state.account_cache_dirty and st.session_state.account_linker is not None:
    ok = st.session_state.account_linker.save_cache(ACCOUNT_CACHE_FILE)
    if ok:
        st.session_state.account_cache_dirty = False

st.session_state.geocoding_service.save_cache()

# ========================================================================
# EXPORT HTML - OPTIMIZED FOR LARGE DATASETS
# ========================================================================

st.markdown("---")
st.markdown("## 📥 Export Dashboard")

col1, col2 = st.columns([2, 1])

with col1:
    st.info("💡 Generate a standalone HTML file with interactive filters and account links!")

with col2:
    if st.button("🌐 Generate HTML", type="primary", use_container_width=True):
        if len(map_data_geocoded) > 0:
            with st.spinner("🔄 Generating HTML file..."):
                mapping_file = default_account_mapping if os.path.exists(default_account_mapping) else None
                
                if mapping_file:
                    st.info(f"🔗 Using account mappings from: {mapping_file}")
                
                # ================================================================
                # OPTIMIZATION: Prepare minimal dataset with optimized dtypes
                # ================================================================
                
                # Define essential columns for export
                export_cols = [
                    "Date", "Year", "Month", "Country", "City",
                    "PostalCode", "Business Partner Name", "ItemIdAndName",
                    "Set", "ProductType", "EUR", "SalesRepresentative",
                    "End User Segment", "Market Organization Name",
                    "SFDC Link", "account_url"
                ]
                
                # Keep only existing columns
                export_cols = [c for c in export_cols if c in df_base.columns]
                df_export = df_base[export_cols].copy()
                
                # Standardize PostalCode column name
                if postal_col and postal_col != "PostalCode" and postal_col in df_export.columns:
                    df_export = df_export.rename(columns={postal_col: "PostalCode"})
                elif "PostalCode" not in df_export.columns:
                    # Create empty PostalCode if missing
                    df_export["PostalCode"] = ""
                
                # ================================================================
                # NORMALIZE COUNTRY BEFORE EXPORT (ENSURE ISO2 LOWER)
                # ================================================================
                if 'Country' in df_export.columns:
                    print("🌍 Final Country normalization before export...", flush=True)
                    df_export['Country'] = df_export['Country'].astype(str).str.lower().str.strip()
                    invalid_mask = df_export['Country'].str.len() != 2
                    if invalid_mask.sum() > 0:
                        print(f"⚠️ Export: {invalid_mask.sum()} invalid countries → 'es'", flush=True)
                        df_export.loc[invalid_mask, 'Country'] = 'es'
                    print(f"✅ Export Country: {df_export['Country'].unique().tolist()}", flush=True)
                
                # ================================================================
                # OPTIMIZE DTYPES - Reduce memory footprint
                # ================================================================
                
                # Numeric columns: reduce precision
                df_export["Year"] = df_export["Year"].astype("int16")
                df_export["Month"] = df_export["Month"].astype("int8")
                
                # EUR: float32 is sufficient for most use cases
                df_export["EUR"] = pd.to_numeric(
                    df_export["EUR"], 
                    errors="coerce"
                ).fillna(0).astype("float32")
                
                # Categorical columns: massive memory savings for repeated values
                categorical_cols = [
                    "Country", "SalesRepresentative", "ProductType", 
                    "Set", "End User Segment", "Market Organization Name"
                ]
                
                for col in categorical_cols:
                    if col in df_export.columns:
                        df_export[col] = df_export[col].astype("category")
                
                st.info(f"📊 Optimized dataset: {len(df_export):,} rows × {len(df_export.columns)} cols")
                st.caption(f"Memory usage: {df_export.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
                
                # ================================================================
                # PREPARE MAP DATA
                # ================================================================
                map_export = map_data_geocoded.copy()
                
                # Ensure essential columns
                required_cols = ['PostalCode', 'Country', 'Latitude', 'Longitude', 'Total_EUR', 'Num_Services']
                for col in required_cols:
                    if col not in map_export.columns:
                        st.error(f"❌ Missing required column: {col}")
                        st.stop()
                
                # Ensure optional columns
                if 'City' not in map_export.columns:
                    map_export['City'] = ''
                if 'ResolvedCity' not in map_export.columns:
                    map_export['ResolvedCity'] = map_export.get('City', 'Unknown')
                if 'Representatives' not in map_export.columns:
                    map_export['Representatives'] = ''
                if 'Main_Type' not in map_export.columns:
                    map_export['Main_Type'] = ''
                if 'GeoValidated' not in map_export.columns:
                    map_export['GeoValidated'] = True
                
                # Convert data types
                map_export['Latitude'] = pd.to_numeric(map_export['Latitude'], errors='coerce')
                map_export['Longitude'] = pd.to_numeric(map_export['Longitude'], errors='coerce')
                map_export['Total_EUR'] = pd.to_numeric(map_export['Total_EUR'], errors='coerce')
                map_export['Num_Services'] = pd.to_numeric(map_export['Num_Services'], errors='coerce').fillna(0).astype(int)
                
                # Normalize Country (ensure ISO2 lower)
                map_export['Country'] = map_export['Country'].astype(str).str.lower().str.strip()
                invalid_mask = map_export['Country'].str.len() != 2
                if invalid_mask.sum() > 0:
                    print(f"⚠️ Map export: {invalid_mask.sum()} invalid countries → 'es'", flush=True)
                    map_export.loc[invalid_mask, 'Country'] = 'es'
                
                st.info(f"📍 Exporting {len(map_export)} map points ({len(map_data_valid)} valid + {len(map_data_suspicious)} suspicious)")
                
                # ================================================================
                # GENERATE HTML WITH COLUMNAR+GZIP MODE
                # ================================================================
                html_content = generate_service_dashboard_html(
                    df_export,  # Optimized dataframe
                    map_export,
                    available_years,
                    month_options,
                    available_reps,
                    available_types,
                    available_sets,
                    st.session_state.geocoding_service.cache,
                    account_mapping_file=mapping_file,
                    export_mode="columnar_gzip"  # ← CRITICAL: Enable columnar format
                )
                
                if html_content and len(html_content) > 1000:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"service_dashboard_{timestamp}.html"
                    
                    # Display size info
                    size_mb = len(html_content) / 1024**2
                    st.success(f"✅ HTML generated successfully! ({size_mb:.2f} MB)")
                    
                    st.download_button(
                        label="📥 Download HTML Dashboard",
                        data=html_content,
                        file_name=filename,
                        mime="text/html",
                        use_container_width=True
                    )
                    
                    # Show compression stats if available
                    st.caption(f"💾 File size: {len(html_content):,} bytes ({size_mb:.2f} MB)")
                else:
                    st.error("❌ HTML generation failed - output too small")
        else:
            st.error("❌ Cannot generate HTML: no geocoded coordinates available")

st.markdown("---")

# ========================================================================
# DEBUG EXPANDER
# ========================================================================

with st.expander("🧭 Geocoding Debug & Statistics"):
    st.markdown("### 📊 Current Session Stats")
    
    stats = st.session_state.geocoding_service.stats
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🎯 Cache Hits", stats.cache_hits)
        st.metric("📡 API Calls", stats.api_calls if hasattr(stats, 'api_calls') else stats.nominatim_calls)
    with col2:
        st.metric("✅ Validated", stats.validated if hasattr(stats, 'validated') else 0)
        st.metric("⚠️ Suspicious", stats.suspicious if hasattr(stats, 'suspicious') else 0)
    with col3:
        st.metric("❌ Failed", stats.failed)
        st.metric("💾 Cache Rate", f"{stats.get_cache_rate():.1f}%")
    
    st.markdown("---")
    st.markdown("### 🔍 Failed Geocoding Attempts")
    
    failed_entries = st.session_state.geocoding_service.get_failed_entries()
    
    if failed_entries:
        df_failed = pd.DataFrame(failed_entries)
        st.dataframe(df_failed, use_container_width=True)
        
        st.markdown("### 🔄 Retry Actions")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("♻️ Retry ALL Failed", use_container_width=True):
                st.session_state.geocoding_service.cache = {
                    k: v for k, v in st.session_state.geocoding_service.cache.items()
                    if not (isinstance(v, dict) and v.get('coords') is None)
                }
                st.session_state.geocoding_service.save_cache()
                st.success("✅ Failed entries cleared.")
                st.rerun()
        with col2:
            if st.button("🗑️ Clear Failed Entries", use_container_width=True):
                # Remove all failed entries from cache
                cleared = 0
                for key in list(st.session_state.geocoding_service.cache.keys()):
                    cached = st.session_state.geocoding_service.cache[key]
                    if isinstance(cached, dict) and cached.get('coords') is None:
                        del st.session_state.geocoding_service.cache[key]
                        cleared += 1
                st.session_state.geocoding_service.save_cache()
                st.success(f"✅ Cleared {cleared} failed entries")
                st.rerun()
    else:
        st.success("✅ No failed geocoding attempts!")

# ========================================================================
# CACHE MANAGEMENT
# ========================================================================

with st.expander("📊 Cache Management"):
    st.write(f"**Total cached locations:** {len(st.session_state.geocoding_service.cache)}")
    st.write(f"**New coordinates added:** {st.session_state.geocoding_service.new_coords_added}")
    st.write(f"**Cache file:** `{st.session_state.geocoding_service.cache_file}`")
    
    st.markdown("### 🔧 Cache Actions")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🗑️ Clear ALL", use_container_width=True, key="clear_all"):
            st.session_state.geocoding_service.clear_cache()
            st.success("✅ Cache cleared!")
            st.rerun()
    with col2:
        if st.button("💾 Save Cache", use_container_width=True, key="save_cache"):
            saved = st.session_state.geocoding_service.save_cache()
            if saved:
                st.success("✅ Cache saved!")
            else:
                st.error("❌ Failed to save cache")
    with col3:
        if st.button("🔄 Reload Cache", use_container_width=True, key="reload_cache"):
            st.session_state.geocoding_service.load_cache()
            st.success("✅ Cache reloaded!")
            st.rerun()

# ========================================================================
# HOW TO USE
# ========================================================================

with st.expander("ℹ️ How to use this dashboard"):
    st.markdown("""
    ### 🎯 Quick Guide:
    
    **Multi-Format Support** 🎯
    - Automatic format detection (Original, New, Mixed)
    - Column name mapping
    - Native SFDC Links in new format
    - Native Country column
    - City column optional
    
    **Global Geocoding** 🌍
    - 200+ countries supported
    - GeoNames database (offline)
    - Postal code corrections
    - Nominatim fallback
    - Smart validation (valid/suspicious/missing)
    
    **Map Legend:**
    - **Blue circles (●)** = Successfully geocoded locations
    - **Red triangles (▲)** = Fallback/suspicious locations (country centroid)
    
    **Features:**
    - Interactive map with filters
    - Quick filter tags (AND/OR mode)
    - Export to standalone HTML
    - Account linking analysis
    - Comprehensive debug tools
    """)

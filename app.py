import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from buchi_streamlit_theme import apply_buchi_styles
from service_report_generator import generate_service_dashboard_html

# Page configuration
st.set_page_config(
    page_title="Service Planning Dashboard", 
    layout="wide",
    page_icon="🗺️"
)

# Apply BUCHI corporate styles
apply_buchi_styles()

# File path for persistent geocoding cache
CACHE_FILE = "coordinates_cache.json"

# ⭐ COUNTRY OVERRIDES - Outliers reales fuera de ES/PT/AD
COUNTRY_OVERRIDES = {
    ("11635", "ATHENS"): "gr",
    ("69469", "WEINHEIM"): "de",
}

# ⭐ LIMPIEZA REAL DE CÓDIGO POSTAL (CRÍTICO)
def extract_postal_clean(postal_code):
    """
    Extrae un código postal real de strings sucios:
    - '195 0256' -> '19502-56' o '19502'
    - '2829-516 Caparica' -> '2829-516'
    - 'CELRÀ 17460' -> '17460'
    """
    if postal_code is None or pd.isna(postal_code):
        return ""
    
    s = str(postal_code).strip().upper()
    
    # Buscar patrones válidos: PT (1234-567) o ES (12345)
    m = re.search(r"\d{4}-\d{3}|\d{5}", s)
    postal_clean = m.group(0) if m else s
    
    # Limpiar espacios internos que deberían ser guiones (PT format)
    postal_clean = postal_clean.replace(" ", "-")
    
    return postal_clean

# ⭐ NORMALIZACIÓN DE TEXTOS
def normalize_text(text):
    """Normalize text for consistent cache keys"""
    if not text or pd.isna(text):
        return ""
    text = str(text).strip()
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Uppercase for consistency
    text = text.upper()
    return text

# ⭐ DETECCIÓN DE PAÍS POR CÓDIGO POSTAL + CIUDAD (ACTUALIZADO)
def detect_country_from_postal(postal_code, city=None):
    """
    Detect country code from postal code format + city overrides.
    - Portugal (pt): ^\d{4}-\d{3}$
    - Andorra (ad): ^AD[- ]?\d{3}$
    - España (es): ^\d{5}$
    - Greece (gr): hardcoded override
    - Germany (de): hardcoded override
    - Default: es
    """
    postal_clean = extract_postal_clean(postal_code)
    city_norm = normalize_text(city) if city else ""
    
    # 1️⃣ Overrides explícitos (outliers reales)
    forced = COUNTRY_OVERRIDES.get((postal_clean, city_norm))
    if forced:
        return forced
    
    # 2️⃣ Reglas normales por patrón
    # Portugal: 1234-567
    if re.match(r'^\d{4}-\d{3}$', postal_clean):
        return 'pt'
    
    # Andorra: AD123 o AD-123 o AD 123
    if re.match(r'^AD[- ]?\d{3}$', postal_clean):
        return 'ad'
    
    # España: 12345
    if re.match(r'^\d{5}$', postal_clean):
        return 'es'
    
    # Default
    return 'es'

# ⭐ NORMALIZACIÓN DE CÓDIGO POSTAL PARA CACHE KEY
def normalize_postal_code(postal_code):
    """Normalize postal code removing spaces and hyphens for cache key"""
    if not postal_code or pd.isna(postal_code):
        return ""
    postal = str(postal_code).strip().upper()
    # Remover espacios y guiones
    postal = re.sub(r'[\s-]+', '', postal)
    return postal

# ⭐ BOUNDING BOX VALIDATION (ACTUALIZADO CON GR Y DE)
def validate_coordinates(lat, lon, country_code):
    """Validate if coordinates are within expected boundaries (incl. islands)."""
    if lat is None or lon is None:
        return False

    # Multiple bounding boxes per country (mainland + islands)
    bboxes = {
        "es": [
            # España peninsular (aprox)
            {"lat": (35.5, 44.2), "lon": (-10.5, 5.5)},
            # Canarias (aprox)
            {"lat": (27.3, 29.8), "lon": (-18.5, -13.0)},
            # Baleares (aprox)
            {"lat": (38.6, 40.2), "lon": (1.0, 4.6)},
        ],
        "pt": [
            # Portugal continental (aprox)
            {"lat": (36.8, 42.3), "lon": (-9.6, -6.0)},
            # Madeira + Porto Santo
            {"lat": (32.0, 33.6), "lon": (-17.5, -16.0)},
            # Azores
            {"lat": (36.6, 39.9), "lon": (-31.7, -24.5)},
        ],
        "ad": [
            # Andorra (pequeño)
            {"lat": (42.4, 42.7), "lon": (1.4, 1.8)},
        ],
        "gr": [
            # Greece (mainland + islands)
            {"lat": (34.5, 41.8), "lon": (19.0, 29.8)},
        ],
        "de": [
            # Germany
            {"lat": (47.2, 55.2), "lon": (5.5, 15.5)},
        ],
    }

    if country_code not in bboxes:
        return True  # si no sabemos el país, no invalidamos

    for bb in bboxes[country_code]:
        if bb["lat"][0] <= lat <= bb["lat"][1] and bb["lon"][0] <= lon <= bb["lon"][1]:
            return True

    return False


# Function to load cache from file
def load_cache_from_file():
    """Load geocoding cache from JSON file"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                return cache
        except Exception as e:
            st.warning(f"⚠️ Could not load cache file: {e}")
            return {}
    return {}

# Function to save cache to file
def save_cache_to_file(cache_dict):
    """Save geocoding cache to JSON file"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"❌ Could not save cache file: {e}")
        return False

# Title
st.markdown('<div class="main-header">🗺️ Service Planning Dashboard</div>', unsafe_allow_html=True)

# Initialize session state
if 'geocode_cache' not in st.session_state:
    st.session_state.geocode_cache = load_cache_from_file()

if 'selected_city' not in st.session_state:
    st.session_state.selected_city = None

if 'new_coords_added' not in st.session_state:
    st.session_state.new_coords_added = 0

if 'selected_quick_filters' not in st.session_state:
    st.session_state.selected_quick_filters = []

if 'quick_filter_mode' not in st.session_state:
    st.session_state.quick_filter_mode = 'AND'

if 'geocode_stats' not in st.session_state:
    st.session_state.geocode_stats = {
        'api_calls': 0,
        'cache_hits': 0,
        'failed': 0,
        'validated': 0,
        'suspicious': 0,
        'postcode_mismatch': 0,
        'low_confidence': 0
    }

# Function to load file
@st.cache_data
def load_file(file):
    if file is not None:
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file, encoding='utf-8')
            else:
                df = pd.read_excel(file)
            
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Year'] = df['Date'].dt.year
            df['Month'] = df['Date'].dt.month
            df['Month_Name'] = df['Date'].dt.strftime('%B')
            
            # ⭐ DETECTAR PAÍS POR CÓDIGO POSTAL + CIUDAD (ACTUALIZADO)
            postal_col = None
            for col in df.columns:
                if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
                    postal_col = col
                    break
            
            if postal_col:
                # Usar postal + ciudad para detección (NO solo postal)
                df['Country'] = [
                    detect_country_from_postal(p, c)
                    for p, c in zip(df[postal_col], df['City'])
                ]
            else:
                df['Country'] = 'es'  # Default España
            
            return df
        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            return None
    return None

# ⭐ CREAR GEOLOCATOR UNA SOLA VEZ
_geolocator = Nominatim(user_agent="service_planning_dashboard")
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1)

# ⭐ FUNCIÓN DE GEOCODIFICACIÓN (POSTAL-FIRST MEJORADO)
def geocode_location(postal_code, city, country_code='es'):
    """
    Geocode a location using POSTAL-FIRST strategy.
    The postal code is the source of truth, city is only for display/fallback.
    """
    
    # ⭐ Limpiar código postal ANTES de todo
    postal_clean = extract_postal_clean(postal_code)
    
    # ⭐ Normalizar código postal para cache key
    postal_norm = normalize_postal_code(postal_clean)
    
    # ⭐ CACHE KEY: postal + country (SIN ciudad)
    cache_key = f"{postal_norm}_{country_code}"
    
    # Check cache
    if cache_key in st.session_state.geocode_cache:
        cached = st.session_state.geocode_cache[cache_key]
        st.session_state.geocode_stats['cache_hits'] += 1
        
        if cached is None:
            return None
        elif isinstance(cached, dict):
            return cached.get('coords')
        return None

    # ⭐ No está en caché, geocodificar
    st.session_state.geocode_stats['api_calls'] += 1
    
    # Mapeo de códigos de país (ACTUALIZADO CON GR Y DE)
    country_names = {
        'es': ('Spain', 'es'),
        'pt': ('Portugal', 'pt'),
        'ad': ('Andorra', 'ad'),
        'gr': ('Greece', 'gr'),
        'de': ('Germany', 'de'),
    }
    
    country_name, cc = country_names.get(country_code, ('Spain', 'es'))
    
    try:
        # ⭐ QUERIES EN ORDEN (POSTAL-FIRST)
        queries = [
            # 1️⃣ Primario: Solo postal limpio + país
            (f"{postal_clean}, {country_name}", cc, False),
            # 2️⃣ Alternativo: Solo postal con country_codes
            (f"{postal_clean}", cc, False),
            # 3️⃣ Fallback controlado: postal + ciudad + país
            (f"{postal_clean} {city}, {country_name}", cc, False),
            # 4️⃣ Último recurso: ciudad + país (low confidence)
            (f"{city}, {country_name}", cc, True),
        ]
        
        location = None
        used_query = None
        low_confidence = False
        
        for query, country_codes, is_low_conf in queries:
            if query is None:
                continue
            
            # Geocodificar con addressdetails para validar postcode
            location = _geocode(query, country_codes=country_codes, addressdetails=True)
            
            if location:
                # ⭐ VALIDACIÓN MEJORADA: No descartar si postcode viene vacío
                returned_postcode = location.raw.get("address", {}).get("postcode", "")
                returned_postcode_norm = normalize_postal_code(returned_postcode)
                
                # ❌ Descartar SOLO si:
                # - Devuelve postcode NO vacío Y
                # - Es diferente al nuestro
                if returned_postcode_norm and returned_postcode_norm != postal_norm:
                    # No descartes todavía: valida por bbox y marca mismatch
                    coords_tmp = (location.latitude, location.longitude)
                    if validate_coordinates(coords_tmp[0], coords_tmp[1], country_code):
                        used_query = f"{query} (postcode mismatch: {returned_postcode} != {postal_clean})"
                        low_confidence = True
                        st.session_state.geocode_stats['postcode_mismatch'] += 1
                        break
                    else:
                        # Fuera de bbox Y postcode diferente → siguiente query
                        st.session_state.geocode_stats['postcode_mismatch'] += 1
                        location = None
                        continue
                
                # ✅ Postcode coincide o viene vacío → ACEPTAR
                used_query = f"{query} (country={country_codes})"
                low_confidence = is_low_conf
                
                if is_low_conf:
                    st.session_state.geocode_stats['low_confidence'] += 1
                
                break

        if location:
            coords = (location.latitude, location.longitude)
            
            # ⭐ Validar coordenadas con bbox (WARNING, no filtro duro)
            is_valid = validate_coordinates(coords[0], coords[1], country_code)
            
            if not is_valid:
                st.session_state.geocode_stats['suspicious'] += 1
            else:
                st.session_state.geocode_stats['validated'] += 1
            
            # ⭐ Extraer ciudad resuelta de Nominatim
            address = location.raw.get("address", {})
            resolved_city = (
                address.get("city") or 
                address.get("town") or 
                address.get("village") or 
                address.get("municipality") or
                ""
            )
            
            # ⭐ Guardar con metadata
            metadata = {
                'coords': coords,
                'country': country_code,
                'input_city': city,  # Ciudad del Excel
                'resolved_city': resolved_city,  # Ciudad devuelta por Nominatim
                'display_name': location.address,
                'query_used': used_query,
                'validated': is_valid,
                'low_confidence': low_confidence,
                'timestamp': datetime.now().isoformat()
            }
            
            st.session_state.geocode_cache[cache_key] = metadata
            st.session_state.new_coords_added += 1
            return coords
        
        # ⭐ Guardar fallo con metadata
        st.session_state.geocode_stats['failed'] += 1
        st.session_state.geocode_cache[cache_key] = {
            'coords': None,
            'country': country_code,
            'input_city': city,
            'resolved_city': None,
            'display_name': None,
            'query_used': f"Failed after trying {len(queries)} queries",
            'validated': False,
            'low_confidence': False,
            'timestamp': datetime.now().isoformat()
        }
        return None

    except Exception as e:
        st.session_state.geocode_stats['failed'] += 1
        st.session_state.geocode_cache[cache_key] = {
            'coords': None,
            'country': country_code,
            'input_city': city,
            'resolved_city': None,
            'display_name': None,
            'query_used': f"Exception: {str(e)}",
            'validated': False,
            'low_confidence': False,
            'timestamp': datetime.now().isoformat()
        }
        return None

# ============================================================================
# FILE UPLOAD
# ============================================================================
st.sidebar.markdown("## 📁 Data Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload Service Data (Excel/CSV)", 
    type=["xlsx", "csv"],
    help="Upload your service data file with Date, Business Partner Name, etc."
)

if uploaded_file:
    df = load_file(uploaded_file)
    
    if df is None:
        st.stop()
    
    st.sidebar.success(f"✅ {len(df)} records loaded")
    st.sidebar.info(f"📍 Cached coordinates: {len(st.session_state.geocode_cache)}")
    
    # Get available options
    available_years = sorted(df['Year'].dropna().unique().astype(int).tolist())
    available_reps = sorted(df['SalesRepresentative'].dropna().unique().tolist())
    available_types = sorted(df['ProductType'].dropna().unique().tolist())
    available_sets = sorted(df['Set'].dropna().unique().tolist())
    available_countries = sorted(df['Country'].dropna().unique().tolist())
    month_options = list(range(1, 13))
    month_labels = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    
    # ⭐ FUNCIÓN RESET
    def reset_all_filters():
        st.session_state["year_filter"] = available_years
        st.session_state["month_filter"] = []
        st.session_state["rep_filter"] = available_reps
        st.session_state["type_filter"] = available_types
        st.session_state["set_filter"] = available_sets
        st.session_state["country_filter"] = available_countries
        st.session_state.selected_quick_filters = []
        st.session_state["search_filter"] = ""
        st.session_state["client_filter"] = ""
        st.session_state.selected_city = None
    
    # ============================================================================
    # FILTERS - COLAPSABLES
    # ============================================================================
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎛️ Filters")
    
    # ⭐ Country filter - COLAPSABLE
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
            'de': '🇩🇪 Germany'
        }
        
        selected_countries = st.multiselect(
            "Select countries",
            available_countries,
            default=available_countries,
            key="country_filter",
            format_func=lambda x: country_format_map.get(x, x),
            label_visibility="collapsed"
        )
    
    # ⭐ Year filter - COLAPSABLE
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
    
    # ⭐ Month filter - COLAPSABLE
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
    
    # ⭐ Sales Representative filter - COLAPSABLE
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
    
    # ⭐ Product Type filter - COLAPSABLE
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
    
    # ⭐ Set filter - COLAPSABLE
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
    
    # ⭐ Search filter - COLAPSABLE
    with st.sidebar.expander("🔍 Search Service", expanded=False):
        # AND/OR selector
        quick_mode = st.radio(
            "Quick filter mode:",
            options=['AND', 'OR'],
            horizontal=True,
            key="quick_filter_mode",
            help="AND = All keywords must match | OR = Any keyword matches"
        )
        
        quick_filter_keywords = ['CARE', 'Exact', 'Start', 'Circle', 'Maintain', 'IQ/OQ', 'OQ', 'Install']
        
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

        client_search = st.text_input(
            "Filter by Client",
            placeholder="e.g., 'Universidad', 'Hospital'...",
            key="client_filter",
            help="Filter by client name (case insensitive)"
        )
    
    # ⭐ RESET BUTTON
    st.sidebar.markdown("---")
    st.sidebar.button(
        "🔄 Reset All Filters",
        type="primary",
        use_container_width=True,
        on_click=reset_all_filters,
        key="reset_btn"
    )
    
    # ============================================================================
    # APPLY FILTERS
    # ============================================================================
    
    df_filtered = df.copy()
    
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

    # ⭐ Quick filters con modo AND/OR
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

    # ============================================================================
    # METRICS
    # ============================================================================
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_eur = df_filtered['EUR'].sum()
        st.metric("💰 Total EUR", f"€{total_eur:,.2f}")
    
    with col2:
        num_services = len(df_filtered)
        st.metric("📊 Services", f"{num_services:,}")
    
    with col3:
        num_cities = df_filtered['City'].nunique()
        st.metric("📍 Cities", f"{num_cities:,}")
    
    with col4:
        num_clients = df_filtered['Business Partner Name'].nunique()
        st.metric("👥 Clients", f"{num_clients:,}")
    
    st.markdown("---")
    
    # ============================================================================
    # MAP AND TABLE
    # ============================================================================
    
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
    
    # ⭐ Agrupar por POSTAL + COUNTRY (no city)
    map_data = df_filtered.groupby([postal_col, 'Country']).agg({
        'City': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],  # Ciudad más frecuente
        'EUR': 'sum',
        'Business Partner Name': 'count',
        'SalesRepresentative': lambda x: ', '.join(x.unique()[:3]),
        'ProductType': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'Mixed'
    }).reset_index()
    
    map_data.columns = ['PostalCode', 'Country', 'City', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']
    
    # ⭐ DEDUPLICAR antes de geocodificar
    st.session_state.new_coords_added = 0
    st.session_state.geocode_stats = {
        'api_calls': 0,
        'cache_hits': 0,
        'failed': 0,
        'validated': 0,
        'suspicious': 0,
        'postcode_mismatch': 0,
        'low_confidence': 0
    }
    
    if len(map_data) > 0:
        # Crear lista de códigos postales únicos a geocodificar
        unique_postals = map_data[['PostalCode', 'City', 'Country']].drop_duplicates()
        
        postals_to_geocode = []
        for idx, row in unique_postals.iterrows():
            postal_clean = extract_postal_clean(row['PostalCode'])
            postal_norm = normalize_postal_code(postal_clean)
            cache_key = f"{postal_norm}_{row['Country']}"
            
            if cache_key not in st.session_state.geocode_cache:
                postals_to_geocode.append((idx, row))
        
        if postals_to_geocode:
            st.info(f"🌍 Need to geocode {len(postals_to_geocode)} unique postal codes (already cached: {len(unique_postals) - len(postals_to_geocode)})")
            
            with st.spinner(f"Geocoding {len(postals_to_geocode)} postal codes..."):
                progress_bar = st.progress(0)
                
                for progress_idx, (idx, row) in enumerate(postals_to_geocode):
                    coord = geocode_location(row['PostalCode'], row['City'], row['Country'])
                    progress_bar.progress((progress_idx + 1) / len(postals_to_geocode))
                
                progress_bar.empty()
            
            if st.session_state.new_coords_added > 0:
                if save_cache_to_file(st.session_state.geocode_cache):
                    st.success(f"✅ Added {st.session_state.new_coords_added} new coordinates to cache")
        else:
            st.success(f"✅ All {len(unique_postals)} unique postal codes already cached!")
        
        # ⭐ Obtener coordenadas del caché
        coords_list = []
        resolved_city_list = []
        
        for idx, row in map_data.iterrows():
            postal_clean = extract_postal_clean(row['PostalCode'])
            postal_norm = normalize_postal_code(postal_clean)
            cache_key = f"{postal_norm}_{row['Country']}"
            
            cached = st.session_state.geocode_cache.get(cache_key)
            
            if cached is None:
                coords_list.append((None, None))
                resolved_city_list.append(None)
            elif isinstance(cached, dict):
                coords = cached.get('coords', (None, None))
                coords_list.append(coords)
                # Usar resolved_city si existe, sino input_city
                resolved_city_list.append(cached.get('resolved_city') or cached.get('input_city') or row['City'])
            else:
                coords_list.append((None, None))
                resolved_city_list.append(None)
        
        map_data['Coordinates'] = coords_list
        map_data['ResolvedCity'] = resolved_city_list
        
        map_data['Latitude'] = map_data['Coordinates'].apply(lambda x: x[0] if x and x[0] is not None else None)
        map_data['Longitude'] = map_data['Coordinates'].apply(lambda x: x[1] if x and x[1] is not None else None)
        
        # ⭐ Separar geocoded
        map_data_geocoded = map_data.dropna(subset=['Latitude', 'Longitude']).copy()
        
        # ⭐ RECALCULAR GeoValidated con bbox ACTUAL (WARNING, no filtro duro)
        map_data_geocoded['GeoValidated'] = map_data_geocoded.apply(
            lambda row: validate_coordinates(row['Latitude'], row['Longitude'], row['Country']),
            axis=1
        )
        
        map_data_valid = map_data_geocoded[map_data_geocoded['GeoValidated'] == True].copy()
        map_data_suspicious = map_data_geocoded[map_data_geocoded['GeoValidated'] == False].copy()
        
        if len(map_data_geocoded) == 0:
            st.warning("⚠️ Could not geocode any postal codes.")
        else:
            # Preparar ambos datasets con Size_Display
            map_data_valid['Size_Display'] = map_data_valid['Total_EUR'].abs()
            map_data_suspicious['Size_Display'] = map_data_suspicious['Total_EUR'].abs()
            
            # Crear figura con 2 traces
            fig = go.Figure()
            
            # Trace 1: Valid (círculos azules)
            if len(map_data_valid) > 0:
                fig.add_trace(go.Scattermapbox(
                    lat=map_data_valid['Latitude'],
                    lon=map_data_valid['Longitude'],
                    mode='markers',
                    marker=dict(
                        size=map_data_valid['Size_Display'] / map_data_valid['Size_Display'].max() * 30,
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
            
            # Trace 2: Suspicious (triángulos rojos)
            if len(map_data_suspicious) > 0:
                fig.add_trace(go.Scattermapbox(
                    lat=map_data_suspicious['Latitude'],
                    lon=map_data_suspicious['Longitude'],
                    mode='markers',
                    marker=dict(
                        size=map_data_suspicious['Size_Display'] / map_data_suspicious['Size_Display'].max() * 30,
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
                        '<i>Outside expected boundaries</i><br>'
                        '<extra></extra>'
                    ),
                    name='⚠️ Suspicious',
                    showlegend=True
                ))
            
            # Configurar layout
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
            
            # ⭐ Capturar clicks en el mapa
            selected_points = st.plotly_chart(
                fig, 
                use_container_width=True,
                key="main_map",
                on_select="rerun"
            )
            
            # ⭐ Panel de detalles de localización seleccionada
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
                        
                        # ⭐ Filtrar datos originales por POSTAL + COUNTRY
                        location_data = df_filtered[
                            (df_filtered[postal_col] == selected_postal) &
                            (df_filtered['Country'] == selected_country)
                        ].copy()
                        
                        # ⭐ Mostrar panel de detalles
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
                            
                            table_columns = [
                                'Date', 'City', 'Business Partner Name', 
                                'ItemIdAndName', 'Set', 'ProductType', 'EUR', 'SalesRepresentative'
                            ]
                            
                            st.dataframe(
                                location_data_sorted[table_columns],
                                use_container_width=True,
                                height=400,
                                hide_index=True
                            )
                            
                            if len(location_data) > 100:
                                st.info(f"ℹ️ Showing all {len(location_data)} services for this location")
            
            st.caption(f"📍 Showing {len(map_data_valid)} valid + {len(map_data_suspicious)} suspicious postal codes")
            
            # Expander de suspicious
            if len(map_data_suspicious) > 0:
                with st.expander(f"⚠️ {len(map_data_suspicious)} postal codes with suspicious coordinates (outside country boundaries)"):
                    st.dataframe(
                        map_data_suspicious[['PostalCode', 'Country', 'ResolvedCity', 'Latitude', 'Longitude']],
                        use_container_width=True
                    )
            
            postals_without_coords = len(map_data) - len(map_data_geocoded)
            if postals_without_coords > 0:
                with st.expander(f"❌ {postals_without_coords} postal codes could not be geocoded"):
                    missing_data = map_data[
                        map_data['Coordinates'].apply(lambda x: x == (None, None) or x is None)
                    ][['PostalCode', 'Country', 'City']]
                    st.dataframe(missing_data, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📋 Service Details")
    
    df_table = df_filtered.copy()
    
    table_columns = [
        'Date', 'City', 'Business Partner Name', 
        'ItemIdAndName', 'Set', 'ProductType', 'EUR', 'SalesRepresentative'
    ]
    
    st.dataframe(
        df_table[table_columns].sort_values('Date', ascending=False),
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    st.caption(f"📊 Showing {len(df_table)} services")
    
    # ============================================================================
    # GENERATE HTML
    # ============================================================================
    
    st.markdown("---")
    st.markdown("## 📥 Export Dashboard")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("💡 Generate a standalone HTML file with interactive filters. It includes all data and works offline!")
    
    with col2:
        if st.button("🌐 Generate HTML", type="primary", use_container_width=True):
            if len(map_data_geocoded) > 0:
                with st.spinner("🔄 Generating HTML file..."):
                    html_content = generate_service_dashboard_html(
                        df,
                        map_data_geocoded,
                        available_years,
                        month_options,
                        available_reps,
                        available_types,
                        available_sets,
                        st.session_state.geocode_cache
                    )
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"service_dashboard_{timestamp}.html"
                    
                    st.download_button(
                        label="📥 Download HTML Dashboard",
                        data=html_content,
                        file_name=filename,
                        mime="text/html",
                        use_container_width=True
                    )
                    
                    st.success(f"✅ HTML generated successfully!")
            else:
                st.error("❌ Cannot generate HTML: no valid coordinates available")
    
    st.markdown("---")
    
    # ============================================================================
    # EXPANDER DEBUG COMPLETO
    # ============================================================================
    with st.expander("🧭 Geocoding Debug & Statistics"):
        st.markdown("### 📊 Current Session Stats")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎯 Cache Hits", st.session_state.geocode_stats['cache_hits'])
            st.metric("📡 API Calls", st.session_state.geocode_stats['api_calls'])
        with col2:
            st.metric("✅ Validated", st.session_state.geocode_stats['validated'])
            st.metric("⚠️ Suspicious", st.session_state.geocode_stats['suspicious'])
        with col3:
            st.metric("❌ Failed", st.session_state.geocode_stats['failed'])
            st.metric("🔀 Postcode Mismatch", st.session_state.geocode_stats['postcode_mismatch'])
            st.metric("⚠️ Low Confidence", st.session_state.geocode_stats['low_confidence'])
            cache_rate = (st.session_state.geocode_stats['cache_hits'] / 
                         max(1, st.session_state.geocode_stats['cache_hits'] + st.session_state.geocode_stats['api_calls'])) * 100
            st.metric("💾 Cache Rate", f"{cache_rate:.1f}%")
        
        st.markdown("---")
        st.markdown("### 🔍 Failed Geocoding Attempts")
        
        failed_entries = []
        for key, value in st.session_state.geocode_cache.items():
            if isinstance(value, dict) and value.get('coords') is None:
                parts = key.split('_')
                if len(parts) >= 2:
                    country = parts[-1]
                    postal = '_'.join(parts[:-1])
                    
                    failed_entries.append({
                        'PostalCode': postal,
                        'Country': country,
                        'Input City': value.get('input_city', 'N/A'),
                        'Query Used': value.get('query_used', 'N/A'),
                        'Timestamp': value.get('timestamp', 'N/A')
                    })
        
        if failed_entries:
            df_failed = pd.DataFrame(failed_entries)
            st.dataframe(df_failed, use_container_width=True)
            
            st.markdown("### 🔄 Retry Actions")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("♻️ Retry ALL Failed Geocodes", use_container_width=True):
                    # Limpiar solo los fallidos
                    st.session_state.geocode_cache = {
                        k: v for k, v in st.session_state.geocode_cache.items()
                        if not (isinstance(v, dict) and v.get('coords') is None)
                    }
                    save_cache_to_file(st.session_state.geocode_cache)
                    st.success("✅ Failed entries cleared. Refresh to retry geocoding.")
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear Failed by Country", use_container_width=True):
                    # Selector de país
                    st.info("Use the country filter above and click Retry ALL to clear specific countries")
        else:
            st.success("✅ No failed geocoding attempts!")
    
    with st.expander("ℹ️ How to use this dashboard"):
        st.markdown("""
        ### 🎯 Quick Guide:
        
        **NEW: Enhanced Postal-First Geocoding** 🎯
        - **Postal code cleaning**: Handles dirty formats like `"195 0256"`, `"2829-516 Caparica"`, `"CELRÀ 17460"`
        - **Country detection**: Automatic ES/PT/AD detection + explicit overrides for GR/DE
        - **Flexible validation**: Accepts results when postcode is empty (common in Nominatim)
        - **Outlier support**: Athens (GR) and Weinheim (DE) properly handled
        
        **Filters:** Collapsible sections including Country filter (🇪🇸 🇵🇹 🇦🇩 🇬🇷 🇩🇪)
        
        **Reset Filters:** Click the "Reset All Filters" button to return to defaults
        
        **Quick Filters:** Click tags to toggle. Use AND mode (all match) or OR mode (any match)
        
        **Map:** Valid locations shown as blue circles ●, suspicious as red triangles ▲
        
        **Click on bubbles:** Opens a detail panel with all services for that postal code
        
        **Export HTML:** Standalone file with all data and interactive filters
        
        **Geocoding Strategy:**
        1. **Clean postal code** first (extract valid format)
        2. Primary: `{postal_clean}, {country}` 🎯
        3. Alternative: `{postal_clean}` with country restriction
        4. Fallback: `{postal_clean} {city}, {country}`
        5. Last resort: `{city}, {country}` (marked as low confidence)
        
        **Validation:**
        - Returned postcode compared to requested (if not empty)
        - Bounding box check (warning only, not filter)
        - Failed geocodes tracked and can be retried
        - Dirty postal codes automatically cleaned
        """)
    
    with st.expander("📊 Cache Management"):
        st.write(f"**Total cached locations:** {len(st.session_state.geocode_cache)}")
        st.write(f"**New coordinates added:** {st.session_state.new_coords_added}")
        st.write(f"**Cache file:** `{os.path.abspath(CACHE_FILE)}`")
        
        st.markdown("### 🔧 Cache Actions")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🗑️ Clear ALL cache", use_container_width=True):
                st.session_state.geocode_cache = {}
                if os.path.exists(CACHE_FILE):
                    os.remove(CACHE_FILE)
                st.success("✅ Cache cleared!")
                st.rerun()
        with col2:
            if st.button("🔄 Clear PT failed", use_container_width=True):
                st.session_state.geocode_cache = {
                    k: v for k, v in st.session_state.geocode_cache.items()
                    if not (k.endswith("_pt") and isinstance(v, dict) and v.get('coords') is None)
                }
                save_cache_to_file(st.session_state.geocode_cache)
                st.success("✅ PT failed cleared!")
                st.rerun()
        with col3:
            if st.button("🔄 Clear ES failed", use_container_width=True):
                st.session_state.geocode_cache = {
                    k: v for k, v in st.session_state.geocode_cache.items()
                    if not (k.endswith("_es") and isinstance(v, dict) and v.get('coords') is None)
                }
                save_cache_to_file(st.session_state.geocode_cache)
                st.success("✅ ES failed cleared!")
                st.rerun()
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("♻️ Reset Cache (Enhanced)", use_container_width=True, type="primary", help="⚠️ Clear old cache to use enhanced postal-first strategy with cleaning"):
                st.session_state.geocode_cache = {}
                if os.path.exists(CACHE_FILE):
                    os.remove(CACHE_FILE)
                st.success("✅ Cache reset! Enhanced postal-first strategy with cleaning will be used on next geocoding.")
                st.rerun()
        with col2:
            if st.button("🔄 Clear AD failed", use_container_width=True):
                st.session_state.geocode_cache = {
                    k: v for k, v in st.session_state.geocode_cache.items()
                    if not (k.endswith("_ad") and isinstance(v, dict) and v.get('coords') is None)
                }
                save_cache_to_file(st.session_state.geocode_cache)
                st.success("✅ AD failed cleared!")
                st.rerun()

else:
    st.info("👆 **Upload your service data file to get started**")
    
    st.markdown("""
    ### 📋 Required columns:
    - `Date`, `Business Partner Name`, `ItemIdAndName`, `ProductType`, `Set`
    - `EUR`, `SalesRepresentative`, `City`, `PostalCode`
    
    ### 🎯 Features:
    - **NEW: Enhanced Postal Cleaning** 🧹 - Handles dirty formats automatically
    - **NEW: Multi-country Support** 🌍 - ES, PT, AD, GR, DE
    - **NEW: Flexible Validation** ✅ - Accepts results when postcode is empty
    - **Postal-First Geocoding** 🎯 - Postal code is source of truth
    - **Andorra Support** 🇦🇩 - Properly detects Andorra postal codes (AD123)
    - **Postcode Validation** - Prevents incorrect geocoding
    - Interactive map with service distribution
    - Country filter (🇪🇸 Spain / 🇵🇹 Portugal / 🇦🇩 Andorra / 🇬🇷 Greece / 🇩🇪 Germany)
    - Quick filter tags with AND/OR mode
    - Collapsible filter sections in sidebar
    - All/None buttons for each filter group
    - Reset all filters with one click
    - Click on map bubbles to see detailed service breakdown
    - Export to standalone HTML with filters
    - Two-layer map: valid (blue circles ●) + suspicious (red triangles ▲)
    - Comprehensive debug tools for geocoding issues
    - Low confidence flagging for city-based geocoding
    - Cache management with country-specific clearing
    
    ### 🔄 Migration Note:
    If you have an existing cache, use the **"Reset Cache (Enhanced)"** button to clear the old cache and use the enhanced postal-first strategy with automatic cleaning.
    """)
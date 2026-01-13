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

# ⭐ DICCIONARIO DE TYPOS CONOCIDOS
CITY_CORRECTIONS = {
    'CARDANAJIMENO': 'CARDENAJIMENO',
    'CARDAÑAJIMENO': 'CARDEÑAJIMENO',
    # Añade más según los vayas encontrando
}

# ⭐ NUEVA FUNCIÓN: Extraer variantes de ciudad (sin paréntesis)
def extract_city_candidates(city_text):
    """
    Extract city name variants, prioritizing content in parentheses.
    Example: "CAPARICA (MONTE DE CAPARICA )" -> ["MONTE DE CAPARICA", "CAPARICA"]
    """
    if not city_text or pd.isna(city_text):
        return []
    
    city_text = str(city_text).strip()
    
    # Buscar patrón X (Y)
    match = re.match(r'^(.+?)\s*\((.+?)\)\s*$', city_text)
    
    if match:
        outside = match.group(1).strip()  # X
        inside = match.group(2).strip()   # Y
        # Priorizar lo que está DENTRO de paréntesis
        candidates = [inside, outside]
    else:
        # No hay paréntesis, usar texto limpio
        candidates = [city_text]
    
    # Limpiar cada candidato: quitar paréntesis residuales, espacios extra
    cleaned_candidates = []
    for candidate in candidates:
        # Remover paréntesis residuales
        cleaned = re.sub(r'[()]', '', candidate)
        # Normalizar espacios
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if cleaned:
            cleaned_candidates.append(cleaned)
    
    return cleaned_candidates

# ⭐ FASE 1: NORMALIZACIÓN DE TEXTOS
def normalize_text(text):
    """Normalize text for consistent cache keys"""
    if not text or pd.isna(text):
        return ""
    text = str(text).strip()
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Normalize unicode (á -> a, ñ -> n, etc.) para cache más eficiente
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    # Uppercase for consistency
    text = text.upper()
    return text

# ⭐ FASE 2: BOUNDING BOX VALIDATION (AMPLIADOS PARA PT)
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
            # Madeira + Porto Santo (MÁS AMPLIO)
            {"lat": (32.0, 33.6), "lon": (-17.5, -16.0)},
            # Azores (MÁS AMPLIO)
            {"lat": (36.6, 39.9), "lon": (-31.7, -24.5)},
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
                
                # ⭐ FASE 2: Convertir cache antiguo (coords) a nuevo formato (metadata)
                migrated_cache = {}
                for key, value in cache.items():
                    if value is None:
                        migrated_cache[key] = value
                    elif isinstance(value, dict):
                        # Ya está en nuevo formato
                        migrated_cache[key] = value
                    elif isinstance(value, (list, tuple)) and len(value) == 2:
                        # Formato antiguo (lat, lon) -> migrar a metadata
                        migrated_cache[key] = {
                            'coords': value,
                            'query': 'legacy',
                            'timestamp': datetime.now().isoformat(),
                            'display_name': None,
                            'validated_at_geocode': True
                        }
                    else:
                        migrated_cache[key] = value
                
                return migrated_cache
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
    
    # ⭐ FASE 2: Limpiar entradas fallidas antiguas (>7 días)
    now = datetime.now()
    cleaned_cache = {}
    for key, value in st.session_state.geocode_cache.items():
        if value is None:
            # Entry fallida - no la guardamos para reintentarla
            continue
        elif isinstance(value, dict) and value.get('coords') is None:
            # Entry fallida con metadata - verificar timestamp
            try:
                ts = datetime.fromisoformat(value.get('timestamp', now.isoformat()))
                if (now - ts).days < 7:
                    cleaned_cache[key] = value  # Menos de 7 días, mantener
                # Si >7 días, no la incluimos para reintentarla
            except:
                pass  # Si hay error en timestamp, no la incluimos
        else:
            cleaned_cache[key] = value
    
    st.session_state.geocode_cache = cleaned_cache

if 'selected_city' not in st.session_state:
    st.session_state.selected_city = None

if 'new_coords_added' not in st.session_state:
    st.session_state.new_coords_added = 0

if 'selected_quick_filters' not in st.session_state:
    st.session_state.selected_quick_filters = []

# ⭐ FASE 1: Initialize quick filter mode
if 'quick_filter_mode' not in st.session_state:
    st.session_state.quick_filter_mode = 'AND'

if 'geocode_stats' not in st.session_state:
    st.session_state.geocode_stats = {
        'api_calls': 0,
        'cache_hits': 0,
        'failed': 0,
        'validated': 0,
        'suspicious': 0,
        'corrected': 0,
        'fallback': 0
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
            
            # ⭐ FASE 1: Añadir columna Country al cargar archivo
            postal_col = None
            for col in df.columns:
                if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
                    postal_col = col
                    break
            
            if postal_col:
                df['Country'] = df[postal_col].apply(
                    lambda x: 'pt' if re.match(r'^\d{4}-\d{3}$', str(x).strip()) else 'es'
                )
            else:
                df['Country'] = 'es'  # Default España
            
            return df
        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            return None
    return None

# ⭐ CREAR GEOLOCATOR UNA SOLA VEZ (fuera de la función)
_geolocator = Nominatim(user_agent="service_planning_dashboard")
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1)

# ⭐ FUNCIÓN DE GEOCODIFICACIÓN MEJORADA (sin paréntesis, con candidatos)
def geocode_location(postal_code, city, country_code='es'):
    """Geocode a location with normalization, metadata, validation and fallback"""
    # ⭐ FASE 1: Normalizar inputs
    postal_norm = normalize_text(postal_code)
    city_norm = normalize_text(city)
    
    # ⭐ FASE 3: Aplicar correcciones de typos conocidos
    city_corrected = city_norm
    if city_norm in CITY_CORRECTIONS:
        city_corrected = CITY_CORRECTIONS[city_norm]
        st.session_state.geocode_stats['corrected'] += 1
    
    # Crear cache key con textos normalizados (usando city corregida)
    cache_key = f"{postal_norm}_{city_corrected}_{country_code}"
    
    # Check cache
    if cache_key in st.session_state.geocode_cache:
        cached = st.session_state.geocode_cache[cache_key]
        st.session_state.geocode_stats['cache_hits'] += 1
        
        if cached is None:
            return None
        elif isinstance(cached, dict):
            return cached.get('coords')
        elif isinstance(cached, (list, tuple)):
            return cached  # Formato antiguo
        return None

    # ⭐ No está en caché, geocodificar
    st.session_state.geocode_stats['api_calls'] += 1
    
    try:
        # ⭐ NUEVO: Extraer candidatos de ciudad (sin paréntesis)
        city_candidates = extract_city_candidates(city)
        
        if not city_candidates:
            city_candidates = [city_corrected]
        
        # ⭐ Build queries con múltiples candidatos
        queries = []
        
        if country_code == "pt":
            country_name = "Portugal"
            cc = "pt"
            
            for city_candidate in city_candidates:
                city_upper = city_candidate.upper()
                
                # Queries básicas
                queries.append(f"{postal_code} {city_candidate}, {country_name}")
                queries.append(f"{city_candidate}, {country_name}")
                
                # Variantes especiales para Caparica
                if "CAPARICA" in city_upper:
                    queries.extend([
                        f"{postal_code} Monte da Caparica, Almada, {country_name}",
                        f"Monte da Caparica, Almada, {country_name}",
                        f"{postal_code} Costa da Caparica, Almada, {country_name}",
                        f"Costa da Caparica, Almada, {country_name}",
                        f"{city_candidate}, Almada, {country_name}",
                    ])
            
            # Postal solo al final (menos prioritario para PT)
            if postal_code:
                queries.append(f"{postal_code}, {country_name}")
            
        else:
            country_name = "Spain"
            cc = "es"
            
            for city_candidate in city_candidates:
                queries.append(f"{postal_code} {city_candidate}, {country_name}")
                queries.append(f"{city_candidate}, {country_name}")
            
            if postal_code:
                queries.append(f"{postal_code}, {country_name}")
        
        location = None
        used_query = None
        
        # ⭐ Intentar primero con country_codes
        for query in queries:
            if query is None:
                continue
            location = _geocode(query, country_codes=cc)
            if location:
                used_query = f"{query} (country={cc})"
                break

        # ⭐ Fallback sin restricción de país si falló
        if location is None:
            st.session_state.geocode_stats['fallback'] += 1
            for query in queries:
                if query is None:
                    continue
                location = _geocode(query)  # Sin country_codes
                if location:
                    # Solo aceptar si pasa validación bbox
                    if validate_coordinates(location.latitude, location.longitude, country_code):
                        used_query = f"{query} (fallback, no country restriction)"
                        break
                    else:
                        location = None  # Descartamos si cae fuera

        if location:
            coords = (location.latitude, location.longitude)
            
            # ⭐ Validar coordenadas AL MOMENTO DE GEOCODIFICAR
            is_valid = validate_coordinates(coords[0], coords[1], country_code)
            
            if not is_valid:
                st.session_state.geocode_stats['suspicious'] += 1
            else:
                st.session_state.geocode_stats['validated'] += 1
            
            # ⭐ Guardar con metadata (validated_at_geocode para referencia histórica)
            metadata = {
                'coords': coords,
                'query': used_query,
                'timestamp': datetime.now().isoformat(),
                'display_name': location.address,
                'validated_at_geocode': is_valid,  # ← Solo referencia histórica
                'original_city': city_norm,
                'corrected_city': city_corrected if city_corrected != city_norm else None
            }
            
            st.session_state.geocode_cache[cache_key] = metadata
            st.session_state.new_coords_added += 1
            return coords
        
        # ⭐ Guardar fallo con timestamp
        st.session_state.geocode_stats['failed'] += 1
        st.session_state.geocode_cache[cache_key] = {
            'coords': None,
            'query': queries[0] if queries else None,
            'timestamp': datetime.now().isoformat(),
            'display_name': None,
            'validated_at_geocode': False,
            'original_city': city_norm,
            'corrected_city': city_corrected if city_corrected != city_norm else None
        }
        return None

    except Exception as e:
        st.session_state.geocode_stats['failed'] += 1
        st.session_state.geocode_cache[cache_key] = {
            'coords': None,
            'query': str(e),
            'timestamp': datetime.now().isoformat(),
            'display_name': None,
            'validated_at_geocode': False,
            'original_city': city_norm,
            'corrected_city': city_corrected if city_corrected != city_norm else None
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
    available_countries = sorted(df['Country'].dropna().unique().tolist())  # ⭐ NUEVO
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
        st.session_state["country_filter"] = available_countries  # ⭐ NUEVO
        st.session_state.selected_quick_filters = []
        st.session_state["search_filter"] = ""
        st.session_state["client_filter"] = ""
        st.session_state.selected_city = None
    
    # ============================================================================
    # FILTERS - COLAPSABLES
    # ============================================================================
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎛️ Filters")
    
    # ⭐ NUEVO: Country filter - COLAPSABLE
    with st.sidebar.expander("🌍 Country", expanded=False):
        col_country1, col_country2 = st.columns(2)
        with col_country1:
            st.button("✅ All", key="country_all", use_container_width=True,
                     on_click=lambda: st.session_state.update({"country_filter": available_countries}))
        with col_country2:
            st.button("❌ None", key="country_none", use_container_width=True,
                     on_click=lambda: st.session_state.update({"country_filter": []}))
        
        selected_countries = st.multiselect(
            "Select countries",
            available_countries,
            default=available_countries,
            key="country_filter",
            format_func=lambda x: "🇵🇹 Portugal" if x == 'pt' else "🇪🇸 Spain" if x == 'es' else x,
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
    
    if selected_countries:  # ⭐ NUEVO
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
            # TODOS los quick filters deben coincidir (AND)
            mask = pd.Series([True] * len(df_filtered), index=df_filtered.index)
            for keyword in st.session_state.selected_quick_filters:
                mask &= df_filtered['ItemIdAndName'].str.contains(keyword, case=False, na=False)
            df_filtered = df_filtered[mask]
        else:  # OR mode
            # CUALQUIER quick filter coincide (OR)
            mask = pd.Series([False] * len(df_filtered), index=df_filtered.index)
            for keyword in st.session_state.selected_quick_filters:
                mask |= df_filtered['ItemIdAndName'].str.contains(keyword, case=False, na=False)
            df_filtered = df_filtered[mask]
    elif search_text:
        # Manual search
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
    
    # ⭐ Usar columna Country ya calculada
    map_data = df_filtered.groupby(['City', postal_col, 'Country']).agg({
        'EUR': 'sum',
        'Business Partner Name': 'count',
        'SalesRepresentative': lambda x: ', '.join(x.unique()[:3]),
        'ProductType': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'Mixed'
    }).reset_index()
    
    map_data.columns = ['City', 'PostalCode', 'Country', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']
    
    # ⭐ DEDUPLICAR antes de geocodificar
    st.session_state.new_coords_added = 0
    st.session_state.geocode_stats = {
        'api_calls': 0,
        'cache_hits': 0,
        'failed': 0,
        'validated': 0,
        'suspicious': 0,
        'corrected': 0,
        'fallback': 0
    }
    
    if len(map_data) > 0:
        # Crear lista de ciudades únicas a geocodificar
        unique_cities = map_data[['City', 'PostalCode', 'Country']].drop_duplicates()
        
        cities_to_geocode = []
        for idx, row in unique_cities.iterrows():
            postal_norm = normalize_text(row['PostalCode'])
            city_norm = normalize_text(row['City'])
            
            # Aplicar corrección si existe
            city_corrected = city_norm
            if city_norm in CITY_CORRECTIONS:
                city_corrected = CITY_CORRECTIONS[city_norm]
            
            cache_key = f"{postal_norm}_{city_corrected}_{row['Country']}"
            
            if cache_key not in st.session_state.geocode_cache:
                cities_to_geocode.append((idx, row))
        
        if cities_to_geocode:
            st.info(f"🌍 Need to geocode {len(cities_to_geocode)} unique cities (already cached: {len(unique_cities) - len(cities_to_geocode)})")
            
            with st.spinner(f"Geocoding {len(cities_to_geocode)} cities..."):
                progress_bar = st.progress(0)
                
                for progress_idx, (idx, row) in enumerate(cities_to_geocode):
                    coord = geocode_location(row['PostalCode'], row['City'], row['Country'])
                    progress_bar.progress((progress_idx + 1) / len(cities_to_geocode))
                
                progress_bar.empty()
            
            if st.session_state.new_coords_added > 0:
                if save_cache_to_file(st.session_state.geocode_cache):
                    st.success(f"✅ Added {st.session_state.new_coords_added} new coordinates to cache")
        else:
            st.success(f"✅ All {len(unique_cities)} unique cities already cached!")
        
        # ⭐ CRÍTICO: Obtener coordenadas del caché y RECALCULAR validación
        coords_list = []
        query_list = []
        display_name_list = []
        
        for idx, row in map_data.iterrows():
            postal_norm = normalize_text(row['PostalCode'])
            city_norm = normalize_text(row['City'])
            
            # Aplicar corrección si existe
            city_corrected = city_norm
            if city_norm in CITY_CORRECTIONS:
                city_corrected = CITY_CORRECTIONS[city_norm]
            
            cache_key = f"{postal_norm}_{city_corrected}_{row['Country']}"
            
            cached = st.session_state.geocode_cache.get(cache_key)
            
            if cached is None:
                coords_list.append((None, None))
                query_list.append(None)
                display_name_list.append(None)
            elif isinstance(cached, dict):
                coords = cached.get('coords', (None, None))
                coords_list.append(coords)
                query_list.append(cached.get('query'))
                display_name_list.append(cached.get('display_name'))
            elif isinstance(cached, (list, tuple)):
                # Formato antiguo (lat, lon)
                coords_list.append(cached)
                query_list.append('legacy')
                display_name_list.append(None)
            else:
                coords_list.append((None, None))
                query_list.append(None)
                display_name_list.append(None)
        
        map_data['Coordinates'] = coords_list
        map_data['GeoQuery'] = query_list
        map_data['GeoDisplayName'] = display_name_list
        
        map_data['Latitude'] = map_data['Coordinates'].apply(lambda x: x[0] if x and x[0] is not None else None)
        map_data['Longitude'] = map_data['Coordinates'].apply(lambda x: x[1] if x and x[1] is not None else None)
        
        # ⭐ Separar geocoded
        map_data_geocoded = map_data.dropna(subset=['Latitude', 'Longitude']).copy()
        
        # ⭐ CRÍTICO: SIEMPRE RECALCULAR GeoValidated con bbox ACTUAL
        map_data_geocoded['GeoValidated'] = map_data_geocoded.apply(
            lambda row: validate_coordinates(row['Latitude'], row['Longitude'], row['Country']),
            axis=1
        )
        
        map_data_valid = map_data_geocoded[map_data_geocoded['GeoValidated'] == True].copy()
        map_data_suspicious = map_data_geocoded[map_data_geocoded['GeoValidated'] == False].copy()
        
        if len(map_data_geocoded) == 0:
            st.warning("⚠️ Could not geocode any cities.")
        else:
            # Preparar ambos datasets con Size_Display
            map_data_valid['Size_Display'] = map_data_valid['Total_EUR'].abs()
            map_data_suspicious['Size_Display'] = map_data_suspicious['Total_EUR'].abs()
            
            # Crear figura con 2 traces usando plotly.graph_objects
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
                        color='#2E86C1',  # Azul
                        opacity=0.7,
                    ),
                    text=map_data_valid['City'],
                    customdata=map_data_valid[['Total_EUR', 'Num_Services', 'Representatives', 'Main_Type', 'Country', 'PostalCode']],
                    hovertemplate=(
                        '<b>%{text}</b><br>'
                        'Total EUR: €%{customdata[0]:,.2f}<br>'
                        'Services: %{customdata[1]}<br>'
                        'Reps: %{customdata[2]}<br>'
                        'Type: %{customdata[3]}<br>'
                        'Country: %{customdata[4]}<br>'
                        'PostalCode: %{customdata[5]}<br>'
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
                        color='#E74C3C',  # Rojo
                        opacity=0.8,
                    ),
                    text=map_data_suspicious['City'],
                    customdata=map_data_suspicious[['Total_EUR', 'Num_Services', 'Representatives', 'Main_Type', 'Country', 'PostalCode']],
                    hovertemplate=(
                        '<b>⚠️ %{text}</b><br>'
                        'Total EUR: €%{customdata[0]:,.2f}<br>'
                        'Services: %{customdata[1]}<br>'
                        'Reps: %{customdata[2]}<br>'
                        'Type: %{customdata[3]}<br>'
                        'Country: %{customdata[4]}<br>'
                        'PostalCode: %{customdata[5]}<br>'
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
            
            # Auto-zoom península ibérica
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
            
            # ⭐ NUEVO: Capturar clicks en el mapa
            selected_points = st.plotly_chart(
                fig, 
                use_container_width=True,
                key="main_map",
                on_select="rerun"
            )
            
            # ⭐ NUEVO: Panel de detalles de localización seleccionada
            if selected_points and selected_points.selection and selected_points.selection.points:
                selected_indices = [p['point_index'] for p in selected_points.selection.points]
                if selected_indices:
                    # Determinar de qué trace viene
                    point_info = selected_points.selection.points[0]
                    curve_number = point_info.get('curve_number', 0)
                    
                    if curve_number == 0 and len(map_data_valid) > 0:
                        selected_row = map_data_valid.iloc[selected_indices[0]]
                    elif curve_number == 1 and len(map_data_suspicious) > 0:
                        selected_row = map_data_suspicious.iloc[selected_indices[0]]
                    else:
                        selected_row = None
                    
                    if selected_row is not None:
                        selected_city = selected_row['City']
                        selected_postal = selected_row['PostalCode']
                        selected_country = selected_row['Country']
                        
                        # ⭐ NUEVO: Filtrar datos originales por esta localización
                        location_data = df_filtered[
                            (df_filtered['City'] == selected_city) & 
                            (df_filtered[postal_col] == selected_postal) &
                            (df_filtered['Country'] == selected_country)
                        ].copy()
                        
                        # ⭐ NUEVO: Mostrar panel de detalles con expander
                        with st.expander(f"📌 {selected_city} ({selected_postal}) — {selected_country.upper()} ({len(location_data)} lines)", expanded=True):
                            # Header con métricas
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
                            
                            # ⭐ Tabla con todas las líneas (ordenadas por fecha descendente)
                            st.markdown("### 📋 Service Lines")
                            location_data_sorted = location_data.sort_values('Date', ascending=False)
                            
                            # Columnas para la tabla
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
            
            st.caption(f"📍 Showing {len(map_data_valid)} valid + {len(map_data_suspicious)} suspicious cities")
            
            # Mantener expander de suspicious
            if len(map_data_suspicious) > 0:
                with st.expander(f"⚠️ {len(map_data_suspicious)} cities with suspicious coordinates (outside country boundaries)"):
                    st.dataframe(
                        map_data_suspicious[['City', 'PostalCode', 'Country', 'Latitude', 'Longitude', 'GeoQuery', 'GeoDisplayName']],
                        use_container_width=True
                    )
            
            cities_without_coords = len(map_data) - len(map_data_geocoded)
            if cities_without_coords > 0:
                with st.expander(f"❌ {cities_without_coords} cities could not be geocoded"):
                    missing_data = map_data[
                        map_data['Coordinates'].apply(lambda x: x == (None, None) or x is None)
                    ][['City', 'PostalCode', 'Country']]
                    st.dataframe(missing_data, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📋 Service Details")
    
    # ⭐ Simplificado - Sin filtro de ciudad
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
    
    # EXPANDER DEBUG MEJORADO
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
            st.metric("🔧 Auto-corrected", st.session_state.geocode_stats['corrected'])
            st.metric("🔄 Fallback Used", st.session_state.geocode_stats['fallback'])
            cache_rate = (st.session_state.geocode_stats['cache_hits'] / 
                         max(1, st.session_state.geocode_stats['cache_hits'] + st.session_state.geocode_stats['api_calls'])) * 100
            st.metric("💾 Cache Rate", f"{cache_rate:.1f}%")
        
        st.markdown("---")
        st.markdown("### 🔍 Failed Geocoding Attempts")
        
        failed_entries = []
        for key, value in st.session_state.geocode_cache.items():
            if value is None or (isinstance(value, dict) and value.get('coords') is None):
                parts = key.split('_')
                if len(parts) >= 3:
                    country = parts[-1]
                    city = '_'.join(parts[1:-1])
                    postal = parts[0]
                    
                    query_used = value.get('query', 'N/A') if isinstance(value, dict) else 'N/A'
                    timestamp = value.get('timestamp', 'N/A') if isinstance(value, dict) else 'N/A'
                    original_city = value.get('original_city', 'N/A') if isinstance(value, dict) else 'N/A'
                    corrected_city = value.get('corrected_city') if isinstance(value, dict) else None
                    
                    failed_entries.append({
                        'City': city,
                        'Original': original_city,
                        'Corrected': corrected_city if corrected_city else '-',
                        'PostalCode': postal,
                        'Country': country,
                        'Query': query_used,
                        'Timestamp': timestamp
                    })
        
        if failed_entries:
            df_failed = pd.DataFrame(failed_entries)
            st.dataframe(df_failed, use_container_width=True)
            
            st.markdown("### 🔄 Retry Actions")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("♻️ Retry ALL Failed Geocodes", use_container_width=True):
                    st.session_state.geocode_cache = {
                        k: v for k, v in st.session_state.geocode_cache.items()
                        if not (v is None or (isinstance(v, dict) and v.get('coords') is None))
                    }
                    save_cache_to_file(st.session_state.geocode_cache)
                    st.success("✅ Failed entries cleared. Refresh to retry geocoding.")
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear OLD Failed (>7 days)", use_container_width=True):
                    now = datetime.now()
                    cleaned = {}
                    for k, v in st.session_state.geocode_cache.items():
                        if isinstance(v, dict) and v.get('coords') is None:
                            try:
                                ts = datetime.fromisoformat(v.get('timestamp', now.isoformat()))
                                if (now - ts).days < 7:
                                    cleaned[k] = v
                            except:
                                pass
                        else:
                            cleaned[k] = v
                    st.session_state.geocode_cache = cleaned
                    save_cache_to_file(st.session_state.geocode_cache)
                    st.success("✅ Old failed entries cleared!")
                    st.rerun()
        else:
            st.success("✅ No failed geocoding attempts!")
    
    with st.expander("ℹ️ How to use this dashboard"):
        st.markdown("""
        ### 🎯 Quick Guide:
        
        **Filters:** Collapsible sections including Country filter (🇪🇸 Spain / 🇵🇹 Portugal)
        
        **Reset Filters:** Click the "Reset All Filters" button to return to defaults
        
        **Quick Filters:** Click tags to toggle. Use AND mode (all match) or OR mode (any match)
        
        **Map:** Valid locations shown as blue circles ●, suspicious as red triangles ▲
        
        **Click on bubbles:** Opens a detail panel with all services for that location
        
        **Export HTML:** Standalone file with all data and interactive filters
        
        **Geocoding:** Automatic city name cleaning (removes parentheses), typo correction, and smart fallback
        """)
    
    with st.expander("📊 Cache Management"):
        st.write(f"**Total cached locations:** {len(st.session_state.geocode_cache)}")
        st.write(f"**New coordinates added:** {st.session_state.new_coords_added}")
        st.write(f"**Cache file:** `{os.path.abspath(CACHE_FILE)}`")
        
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
                    if not (k.endswith("_pt") and (v is None or (isinstance(v, dict) and v.get('coords') is None)))
                }
                save_cache_to_file(st.session_state.geocode_cache)
                st.success("✅ PT failed cleared!")
                st.rerun()
        with col3:
            if st.button("🔄 Clear ES failed", use_container_width=True):
                st.session_state.geocode_cache = {
                    k: v for k, v in st.session_state.geocode_cache.items()
                    if not (k.endswith("_es") and (v is None or (isinstance(v, dict) and v.get('coords') is None)))
                }
                save_cache_to_file(st.session_state.geocode_cache)
                st.success("✅ ES failed cleared!")
                st.rerun()

else:
    st.info("👆 **Upload your service data file to get started**")
    
    st.markdown("""
    ### 📋 Required columns:
    - `Date`, `Business Partner Name`, `ItemIdAndName`, `ProductType`, `Set`
    - `EUR`, `SalesRepresentative`, `City`, `PostalCode`
    
    ### 🎯 Features:
    - Interactive map with service distribution
    - Country filter (🇪🇸 Spain / 🇵🇹 Portugal) based on postal code detection
    - Quick filter tags with AND/OR mode
    - Collapsible filter sections in sidebar
    - All/None buttons for each filter group
    - Reset all filters with one click
    - Click on map bubbles to see detailed service breakdown
    - Export to standalone HTML with filters
    - Intelligent geocoding with city name cleaning (removes parentheses)
    - Typo correction dictionary for known issues
    - Smart fallback when country-restricted search fails
    - Automatic retry for failed locations after 7 days
    - Two-layer map: valid (blue circles ●) + suspicious (red triangles ▲)
    - Always recalculates validation with current bounding boxes
    - Debug tools for geocoding issues
    """)
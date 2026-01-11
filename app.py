import streamlit as st
import pandas as pd
import plotly.express as px
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import json
import os
from datetime import datetime
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

# Function to load cache from file
def load_cache_from_file():
    """Load geocoding cache from JSON file"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
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
            
            return df
        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            return None
    return None

# Geocoding function
def geocode_location(postal_code, city, country_code='es'):
    """Geocode a location using postal code and city"""
    cache_key = f"{postal_code}_{city}_{country_code}"
    if cache_key in st.session_state.geocode_cache:
        return st.session_state.geocode_cache[cache_key]
    
    try:
        geolocator = Nominatim(user_agent="service_planning_dashboard")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        
        location = geocode(f"{postal_code}, {city}, {country_code}")
        
        if location is None:
            location = geocode(f"{city}, {country_code}")
        
        if location:
            coords = (location.latitude, location.longitude)
            st.session_state.geocode_cache[cache_key] = coords
            st.session_state.new_coords_added += 1
            return coords
        else:
            st.session_state.geocode_cache[cache_key] = None
            return None
            
    except Exception as e:
        st.session_state.geocode_cache[cache_key] = None
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
    
    # ============================================================================
    # FILTERS
    # ============================================================================
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎛️ Filters")
    
    # Year filter
    st.sidebar.markdown("### 📅 Year")
    available_years = sorted(df['Year'].dropna().unique().astype(int).tolist())
    selected_years = st.sidebar.multiselect(
        "Select years",
        available_years,
        default=available_years,
        key="year_filter"
    )
    
    # Month filter
    st.sidebar.markdown("### 📆 Month")
    month_options = list(range(1, 13))
    month_labels = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    
    selected_months = st.sidebar.multiselect(
        "Select months (empty = all)",
        month_options,
        default=[],
        format_func=lambda x: month_labels[x],
        key="month_filter"
    )
    
    # Sales Representative filter
    st.sidebar.markdown("### 👤 Sales Representative")
    available_reps = sorted(df['SalesRepresentative'].dropna().unique().tolist())
    selected_reps = st.sidebar.multiselect(
        "Select representatives",
        available_reps,
        default=available_reps,
        key="rep_filter"
    )
    
    # Product Type filter
    st.sidebar.markdown("### 🏷️ Product Type")
    available_types = sorted(df['ProductType'].dropna().unique().tolist())
    selected_types = st.sidebar.multiselect(
        "Select product types",
        available_types,
        default=available_types,
        key="type_filter"
    )
    
    # Search filter with quick filters
    st.sidebar.markdown("### 🔍 Search Service")
    
    quick_filter_keywords = ['CARE', 'Exact', 'Start', 'Circle', 'Maintain', 'IQ/OQ', 'OQ', 'Install']
    
    if 'selected_quick_filters' not in st.session_state:
        st.session_state.selected_quick_filters = []
    
    cols = st.sidebar.columns(3)
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
    
    search_text = st.sidebar.text_input(
        "Or type custom search",
        value="",
        placeholder="e.g., 'maintenance', 'calibration'...",
        key="search_filter",
        help="Filter services containing this text (case insensitive)"
    )

    client_search = st.sidebar.text_input(
        "Filter by Client",
        value="",
        placeholder="e.g., 'Universidad', 'Hospital'...",
        key="client_filter",
        help="Filter by client name (case insensitive)"
    )
    
    # ============================================================================
    # APPLY FILTERS
    # ============================================================================
    
    df_filtered = df.copy()
    
    if selected_years:
        df_filtered = df_filtered[df_filtered['Year'].isin(selected_years)]
    
    if selected_months:
        df_filtered = df_filtered[df_filtered['Month'].isin(selected_months)]
    
    if selected_reps:
        df_filtered = df_filtered[df_filtered['SalesRepresentative'].isin(selected_reps)]
    
    if selected_types:
        df_filtered = df_filtered[df_filtered['ProductType'].isin(selected_types)]
    
    if st.session_state.selected_quick_filters:
        # TODOS los quick filters deben coincidir (AND)
        mask = pd.Series([True] * len(df_filtered), index=df_filtered.index)
        for keyword in st.session_state.selected_quick_filters:
            mask &= df_filtered['ItemIdAndName'].str.contains(keyword, case=False, na=False)
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
    
    map_data = df_filtered.groupby(['City', postal_col]).agg({
        'EUR': 'sum',
        'Business Partner Name': 'count',
        'SalesRepresentative': lambda x: ', '.join(x.unique()[:3]),
        'ProductType': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'Mixed'
    }).reset_index()
    
    map_data.columns = ['City', 'PostalCode', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']
    
    st.session_state.new_coords_added = 0
    
    if len(map_data) > 0:
        cities_to_geocode = []
        for idx, row in map_data.iterrows():
            postal = str(row['PostalCode'])
            country = 'pt' if (len(postal) == 7 and '-' in postal) else 'es'
            cache_key = f"{postal}_{row['City']}_{country}"
            if cache_key not in st.session_state.geocode_cache:
                cities_to_geocode.append((idx, row, country))
        
        if cities_to_geocode:
            st.info(f"🌍 Need to geocode {len(cities_to_geocode)} new cities (already cached: {len(map_data) - len(cities_to_geocode)})")
            
            with st.spinner(f"Geocoding {len(cities_to_geocode)} cities..."):
                progress_bar = st.progress(0)
                
                for progress_idx, (idx, row, country) in enumerate(cities_to_geocode):
                    coord = geocode_location(row['PostalCode'], row['City'], country)
                    progress_bar.progress((progress_idx + 1) / len(cities_to_geocode))
                
                progress_bar.empty()
            
            if st.session_state.new_coords_added > 0:
                if save_cache_to_file(st.session_state.geocode_cache):
                    st.success(f"✅ Added {st.session_state.new_coords_added} new coordinates to cache file")
        else:
            st.success(f"✅ All {len(map_data)} cities already cached!")
        
        coords = []
        for idx, row in map_data.iterrows():
            postal = str(row['PostalCode'])
            country = 'pt' if (len(postal) == 7 and '-' in postal) else 'es'
            cache_key = f"{postal}_{row['City']}_{country}"
            coord = st.session_state.geocode_cache.get(cache_key)
            coords.append(coord if coord else (None, None))
        
        map_data['Coordinates'] = coords
        map_data['Latitude'] = map_data['Coordinates'].apply(lambda x: x[0] if x and x[0] is not None else None)
        map_data['Longitude'] = map_data['Coordinates'].apply(lambda x: x[1] if x and x[1] is not None else None)
        
        map_data_valid = map_data.dropna(subset=['Latitude', 'Longitude'])
        
        if len(map_data_valid) == 0:
            st.warning("⚠️ Could not geocode any cities.")
        else:

            map_data_valid = map_data_valid.copy()  # Evitar SettingWithCopyWarning
            map_data_valid['Size_Display'] = map_data_valid['Total_EUR'].abs()

            fig = px.scatter_mapbox(
                map_data_valid,
                lat='Latitude',
                lon='Longitude',
                size='Size_Display',
                color='Main_Type',
                size_max=30,
                hover_name='City',
                hover_data={
                    'Total_EUR': ':,.2f',
                    'Size_Display': False,
                    'Num_Services': True,
                    'Representatives': True,
                    'Latitude': False,
                    'Longitude': False,
                    'Main_Type': True
                },
                labels={
                    'Total_EUR': 'Total EUR',
                    'Num_Services': 'Services',
                    'Representatives': 'Reps',
                    'Main_Type': 'Type'
                },
                zoom=5,
                height=600,
            )
            
            fig.update_layout(
                mapbox_style="open-street-map",
                margin={"r": 0, "t": 0, "l": 0, "b": 0}
            )
            
            if len(map_data_valid) > 0:
                lat_center = map_data_valid['Latitude'].mean()
                lon_center = map_data_valid['Longitude'].mean()
                
                lat_range = map_data_valid['Latitude'].max() - map_data_valid['Latitude'].min()
                lon_range = map_data_valid['Longitude'].max() - map_data_valid['Longitude'].min()
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
            
            selected_points = st.plotly_chart(
                fig, 
                use_container_width=True,
                key="main_map",
                on_select="rerun"
            )
            
            if selected_points and selected_points.selection and selected_points.selection.points:
                selected_indices = [p['point_index'] for p in selected_points.selection.points]
                if selected_indices:
                    selected_city = map_data_valid.iloc[selected_indices[0]]['City']
                    st.session_state.selected_city = selected_city
                    st.info(f"🎯 Selected city: **{selected_city}**")
            
            st.caption(f"📍 Showing {len(map_data_valid)} cities with valid coordinates")
            
            cities_without_coords = len(map_data) - len(map_data_valid)
            if cities_without_coords > 0:
                with st.expander(f"⚠️ {cities_without_coords} cities could not be geocoded"):
                    missing_cities = map_data[map_data['Coordinates'].isna()]['City'].tolist()
                    st.write(missing_cities)
    
    st.markdown("---")
    st.markdown("### 📋 Service Details")
    
    df_table = df_filtered.copy()
    if st.session_state.selected_city:
        df_table = df_table[df_table['City'] == st.session_state.selected_city]
        
        if st.button("🔄 Clear city filter", key="clear_city"):
            st.session_state.selected_city = None
            st.rerun()
    
    table_columns = [
        'Date', 'City', 'Business Partner Name', 
        'ItemIdAndName', 'ProductType', 'EUR', 'SalesRepresentative'
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
            if len(map_data_valid) > 0:
                with st.spinner("🔄 Generating HTML file..."):
                    html_content = generate_service_dashboard_html(
                        df,
                        map_data_valid,
                        available_years,
                        month_options,
                        available_reps,
                        available_types,
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
    
    with st.expander("ℹ️ How to use this dashboard"):
        st.markdown("""
        ### 🎯 Quick Guide:
        
        **Filters:** Select years, months, reps, types, and use quick filter tags
        
        **Quick Filters:** Click tags to toggle (CARE, Exact, Start, Circle, Maintain, IQ/OQ, OQ)
        
        **Map:** Interactive bubble map with auto-zoom. Click bubbles to filter table.
        
        **Export HTML:** Standalone file with all data and interactive filters (works offline)
        """)
    
    with st.expander("📊 Cache Statistics"):
        st.write(f"**Total cached locations:** {len(st.session_state.geocode_cache)}")
        st.write(f"**New coordinates added:** {st.session_state.new_coords_added}")
        st.write(f"**Cache file:** `{os.path.abspath(CACHE_FILE)}`")
        
        if st.button("🗑️ Clear cache"):
            st.session_state.geocode_cache = {}
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            st.success("✅ Cache cleared!")
            st.rerun()

else:
    st.info("👆 **Upload your service data file to get started**")
    
    st.markdown("""
    ### 📋 Required columns:
    - `Date`, `Business Partner Name`, `ItemIdAndName`, `ProductType`
    - `EUR`, `SalesRepresentative`, `City`, `PostalCode`
    
    ### 🎯 Features:
    - Interactive map with service distribution
    - Quick filter tags for common searches
    - Export to standalone HTML with filters
    - Persistent geocoding cache
    """)
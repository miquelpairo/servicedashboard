import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from buchi_streamlit_theme import apply_buchi_styles
from service_report_generator import generate_service_dashboard_html

# Import geocoding service
from core.geocoding_service import (
    GeocodingService,
    detect_country_from_postal,
    extract_postal_clean,
    normalize_postal_code,
    validate_coordinates,
    build_cache_key,
    normalize_triplet_inputs,
)


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
    st.session_state.geocoding_service = GeocodingService()

if 'selected_city' not in st.session_state:
    st.session_state.selected_city = None

if 'selected_quick_filters' not in st.session_state:
    st.session_state.selected_quick_filters = []

if 'quick_filter_mode' not in st.session_state:
    st.session_state.quick_filter_mode = 'AND'

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
            
            # Detect country from postal code + city
            postal_col = None
            for col in df.columns:
                if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
                    postal_col = col
                    break
            
            if postal_col:
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
    st.sidebar.info(f"📍 Cached coordinates: {len(st.session_state.geocoding_service.cache)}")
    
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
    
    # Reset function
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
    # FILTERS - COLLAPSIBLE
    # ============================================================================
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎛️ Filters")
    
    # Country filter - COLLAPSIBLE
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
    
    # Year filter - COLLAPSIBLE
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
    
    # Month filter - COLLAPSIBLE
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
    
    # Sales Representative filter - COLLAPSIBLE
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
    
    # Product Type filter - COLLAPSIBLE
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
    
    # Set filter - COLLAPSIBLE
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
    
    # Search filter - COLLAPSIBLE
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
    
    # Group by POSTAL + COUNTRY (not city)
    map_data = df_filtered.groupby([postal_col, 'Country']).agg({
        'City': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],  # Most frequent city
        'EUR': 'sum',
        'Business Partner Name': 'count',
        'SalesRepresentative': lambda x: ', '.join(x.unique()[:3]),
        'ProductType': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'Mixed'
    }).reset_index()
    
    map_data.columns = ['PostalCode', 'Country', 'City', 'Total_EUR', 'Num_Services', 'Representatives', 'Main_Type']
    
    # Reset geocoding stats for this run
    st.session_state.geocoding_service.stats.reset()
    st.session_state.geocoding_service.new_coords_added = 0
    
    if len(map_data) > 0:
        # Get unique postal codes to geocode
        unique_postals = map_data[['PostalCode', 'City', 'Country']].drop_duplicates()

        # ------------------------------------------------------------------------
        # 1) Decide what needs geocoding (only missing from cache)
        # ------------------------------------------------------------------------
        postals_to_geocode = []

        for _, row in unique_postals.iterrows():
            postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
                row['PostalCode'], row['City'], row['Country']
            )
            cache_key = build_cache_key(postal_fixed, city_fixed, country_fixed)

            cached = st.session_state.geocoding_service.cache.get(cache_key)

            if (cached is None) or (isinstance(cached, dict) and cached.get("coords") is None):
                postals_to_geocode.append((postal_fixed, city_fixed, country_fixed))

        # ------------------------------------------------------------------------
        # 2) Geocode missing ones
        # ------------------------------------------------------------------------
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

            # ✅ GUARDA SIEMPRE (aunque todo haya fallado)
            saved = st.session_state.geocoding_service.save_cache()

            if saved:
                if st.session_state.geocoding_service.new_coords_added > 0:
                    st.success(
                        f"✅ Added {st.session_state.geocoding_service.new_coords_added} new coordinates to cache"
                    )
                else:
                    st.warning(
                        "⚠️ No new coordinates added (all failed), but failures were saved to cache to avoid retry loops."
                    )
            else:
                st.error("❌ Could not save cache to file.")
        else:
            st.success(f"✅ All {len(unique_postals)} unique postal codes already cached!")


        # ------------------------------------------------------------------------
        # 3) ALWAYS build coordinates for map (IMPORTANT: outside the if/else above)
        # ------------------------------------------------------------------------
        coords_list = []
        resolved_city_list = []

        for _, row in map_data.iterrows():
            postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
                row['PostalCode'], row['City'], row['Country']
            )
            cache_key = build_cache_key(postal_fixed, city_fixed, country_fixed)
            cached = st.session_state.geocoding_service.cache.get(cache_key)

            if isinstance(cached, dict):
                coords = cached.get('coords', (None, None))
                coords_list.append(coords)
                resolved_city_list.append(
                    cached.get('resolved_city') or cached.get('input_city') or city_fixed
                )
            else:
                coords_list.append((None, None))
                resolved_city_list.append(city_fixed)

        map_data['Coordinates'] = coords_list
        map_data['ResolvedCity'] = resolved_city_list

        map_data['Latitude'] = map_data['Coordinates'].apply(lambda x: x[0] if x and x[0] is not None else None)
        map_data['Longitude'] = map_data['Coordinates'].apply(lambda x: x[1] if x and x[1] is not None else None)

        map_data_geocoded = map_data.dropna(subset=['Latitude', 'Longitude']).copy()

        # Recalculate GeoValidated with current bbox
        map_data_geocoded['GeoValidated'] = map_data_geocoded.apply(
            lambda r: validate_coordinates(r['Latitude'], r['Longitude'], r['Country']),
            axis=1
        )

        map_data_valid = map_data_geocoded[map_data_geocoded['GeoValidated'] == True].copy()
        map_data_suspicious = map_data_geocoded[map_data_geocoded['GeoValidated'] == False].copy()

        if len(map_data_geocoded) == 0:
            st.warning("⚠️ Could not geocode any postal codes.")
        else:
            # Prepare both datasets with Size_Display
            map_data_valid['Size_Display'] = map_data_valid['Total_EUR'].abs().fillna(0)
            map_data_suspicious['Size_Display'] = map_data_suspicious['Total_EUR'].abs().fillna(0)

            # Create figure with 2 traces
            fig = go.Figure()

            # Trace 1: Valid (blue circles)
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

            # Trace 2: Suspicious (red triangles)
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
                        '<i>Outside expected boundaries</i><br>'
                        '<extra></extra>'
                    ),
                    name='⚠️ Suspicious',
                    showlegend=True
                ))
            
            # Configure layout
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
            
            # Capture map clicks
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
                        
                        # Filter original data by POSTAL + COUNTRY
                        location_data = df_filtered[
                            (df_filtered[postal_col] == selected_postal) &
                            (df_filtered['Country'] == selected_country)
                        ].copy()
                        
                        # Show details panel
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
            
            # ========================================================================
            # 🔥 DEBUG PANEL: Missing Coordinates (solo si hay missing)
            # ========================================================================
            missing_mask = map_data['Coordinates'].apply(lambda x: x == (None, None) or x is None)
            df_missing = map_data[missing_mask][['PostalCode', 'Country', 'City']].copy()

            if not df_missing.empty:
                with st.expander("🧩 Debug missing coords (why some postals not geocoded)", expanded=False):
                    st.write(f"**Missing coords:** {len(df_missing)}")
                    st.dataframe(df_missing, use_container_width=True, hide_index=True)

                    # Show cache details for missing entries
                    st.markdown("---")
                    st.markdown("### 🔍 Cache Analysis")

                    rows = []
                    for _, r in df_missing.iterrows():
                        p_fix, c_fix, k_fix, fix_tag = normalize_triplet_inputs(
                            r['PostalCode'], r['City'], r['Country']
                        )
                        key = build_cache_key(p_fix, c_fix, k_fix)
                        cached = st.session_state.geocoding_service.cache.get(key)

                        rows.append({
                            "PostalCode": r["PostalCode"],
                            "Country": r["Country"],
                            "City": r["City"],
                            "fix_tag": fix_tag,
                            "postal_fixed": p_fix,
                            "city_fixed": c_fix,
                            "country_fixed": k_fix,
                            "cache_key": key,
                            "cached_type": type(cached).__name__ if cached is not None else "None",
                            "cached_coords": (cached.get("coords") if isinstance(cached, dict) else None),
                            "cached_status": (cached.get("status") if isinstance(cached, dict) else None),
                            "cached_query": (cached.get("query_used") if isinstance(cached, dict) else None),
                        })

                    df_cache_analysis = pd.DataFrame(rows)

                    # Summary
                    st.markdown("#### Summary:")
                    failed_count = len([r for r in rows if r["cached_coords"] is None])
                    not_in_cache = len([r for r in rows if r["cached_type"] == "None"])

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("❌ Failed in cache", failed_count)
                    with col2:
                        st.metric("🔍 Not in cache", not_in_cache)
                    with col3:
                        st.metric("🔄 Need retry", len(df_missing))

                    st.dataframe(df_cache_analysis, use_container_width=True, hide_index=True)

                    # Tips
                    st.markdown("---")
                    st.markdown("#### 💡 Common Issues:")
                    st.markdown("""
                    - **cached_coords = None**: Failed geocoding (stored in cache to avoid retrying)
                    - **cached_type = None**: Not in cache (should have been geocoded)
                    - **fix_tag = ROTATE_...**: Column shift detected and corrected
                    - **cached_status = FAILED_...**: Check query_used for error details
                    """)

                    # Retry button
                    st.markdown("---")
                    st.markdown("### ♻️ Retry Missing Coordinates")

                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.info("This will delete failed cache entries and retry geocoding for missing coordinates only.")
                    with col2:
                        if st.button("♻️ Retry ONLY missing coords", use_container_width=True, type="primary", key="retry_missing_btn"):
                            keys_to_delete = []
                            for _, r in df_missing.iterrows():
                                p_fix, c_fix, k_fix, _ = normalize_triplet_inputs(
                                    r['PostalCode'], r['City'], r['Country']
                                )
                                key = build_cache_key(p_fix, c_fix, k_fix)
                                cached = st.session_state.geocoding_service.cache.get(key)
                                if isinstance(cached, dict) and cached.get("coords") is None:
                                    keys_to_delete.append(key)

                            st.info(f"Will delete {len(keys_to_delete)} failed entries from cache")
                            for key in keys_to_delete:
                                st.session_state.geocoding_service.cache.pop(key, None)

                            st.session_state.geocoding_service.save_cache()

                            with st.spinner(f"Retrying {len(df_missing)} missing locations..."):
                                progress_bar = st.progress(0)
                                for idx, (_, r) in enumerate(df_missing.iterrows()):
                                    p_fix, c_fix, k_fix, _ = normalize_triplet_inputs(
                                        r['PostalCode'], r['City'], r['Country']
                                    )
                                    st.session_state.geocoding_service.geocode_location(p_fix, c_fix, k_fix)
                                    progress_bar.progress((idx + 1) / len(df_missing))
                                progress_bar.empty()

                            st.session_state.geocoding_service.save_cache()
                            st.success(f"✅ Retried {len(df_missing)} missing locations. Reloading...")
                            st.rerun()

            
            # Suspicious expander
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
                        map_data_valid,
                        available_years,
                        month_options,
                        available_reps,
                        available_types,
                        available_sets,
                        st.session_state.geocoding_service.cache
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
    # DEBUG EXPANDER
    # ============================================================================
    with st.expander("🧭 Geocoding Debug & Statistics"):
        st.markdown("### 📊 Current Session Stats")
        
        stats = st.session_state.geocoding_service.stats
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎯 Cache Hits", stats.cache_hits)
            st.metric("📡 API Calls", stats.api_calls)
        with col2:
            st.metric("✅ Validated", stats.validated)
            st.metric("⚠️ Suspicious", stats.suspicious)
        with col3:
            st.metric("❌ Failed", stats.failed)
            st.metric("🔀 Postcode Mismatch", stats.postcode_mismatch)
            st.metric("⚠️ Low Confidence", stats.low_confidence)
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
                if st.button("♻️ Retry ALL Failed Geocodes", use_container_width=True):
                    # Clear only failed entries
                    st.session_state.geocoding_service.cache = {
                        k: v for k, v in st.session_state.geocoding_service.cache.items()
                        if not (isinstance(v, dict) and v.get('coords') is None)
                    }
                    st.session_state.geocoding_service.save_cache()
                    st.success("✅ Failed entries cleared. Refresh to retry geocoding.")
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear Failed by Country", use_container_width=True):
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
        - **Modular architecture**: Geocoding logic is now in a separate module for better maintainability
        
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
        st.write(f"**Total cached locations:** {len(st.session_state.geocoding_service.cache)}")
        st.write(f"**New coordinates added:** {st.session_state.geocoding_service.new_coords_added}")
        st.write(f"**Cache file:** `{st.session_state.geocoding_service.cache_file}`")
        
        st.markdown("### 🔧 Cache Actions")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🗑️ Clear ALL cache", use_container_width=True):
                st.session_state.geocoding_service.clear_cache()
                st.success("✅ Cache cleared!")
                st.rerun()
        with col2:
            if st.button("🔄 Clear PT failed", use_container_width=True):
                st.session_state.geocoding_service.clear_failed_by_country('pt')
                st.success("✅ PT failed cleared!")
                st.rerun()
        with col3:
            if st.button("🔄 Clear ES failed", use_container_width=True):
                st.session_state.geocoding_service.clear_failed_by_country('es')
                st.success("✅ ES failed cleared!")
                st.rerun()
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("♻️ Reset Cache (Enhanced)", use_container_width=True, type="primary", help="⚠️ Clear old cache to use enhanced postal-first strategy with cleaning"):
                st.session_state.geocoding_service.clear_cache()
                st.success("✅ Cache reset! Enhanced postal-first strategy with cleaning will be used on next geocoding.")
                st.rerun()
        with col2:
            if st.button("🔄 Clear AD failed", use_container_width=True):
                st.session_state.geocoding_service.clear_failed_by_country('ad')
                st.success("✅ AD failed cleared!")
                st.rerun()

else:
    st.info("👆 **Upload your service data file to get started**")
    
    st.markdown("""
    ### 📋 Required columns:
    - `Date`, `Business Partner Name`, `ItemIdAndName`, `ProductType`, `Set`
    - `EUR`, `SalesRepresentative`, `City`, `PostalCode`
    
    ### 🎯 Features:
    - **NEW: Modular Architecture** 🏗️ - Geocoding logic in separate module
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
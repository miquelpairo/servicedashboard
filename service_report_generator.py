"""
Service Dashboard HTML Report Generator (Jinja2-based, Modular)
Generates standalone HTML dashboards with interactive filters and maps
"""

import json
import os
from datetime import datetime
from typing import Optional
import pandas as pd

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from core.report_utils import load_buchi_css, get_sidebar_styles, get_common_report_styles
from app_config.plotting import BUCHI_COLORS
from core.account_linker import AccountLinker


def _has_any_link_column(df) -> bool:
    """Detect if dataframe already contains usable links (AccountURL or SFDC Link variants)."""
    if df is None or df.empty:
        return False

    # If AccountURL exists and has any non-empty values
    if "AccountURL" in df.columns:
        s = df["AccountURL"]
        non_empty = s.notna() & (s.astype(str).str.strip() != "") & (s.astype(str).str.lower().str.strip() != "nan")
        if int(non_empty.sum()) > 0:
            return True

    # SFDC variants
    for c in ["SFDC Link", "SFDC_Link", "SFDC URL", "SFDC_URL", "SFDCLink", "SFDCURL"]:
        if c in df.columns:
            s = df[c]
            non_empty = s.notna() & (s.astype(str).str.strip() != "") & (s.astype(str).str.lower().str.strip() != "nan")
            if int(non_empty.sum()) > 0:
                return True

    return False


def generate_service_dashboard_html(
    df_original,
    map_data_with_coords,  # RENOMBRADO: ya no es "valid", es "geocoded completo"
    available_years,
    available_months,
    available_reps,
    available_types,
    available_sets,
    geocode_cache,
    account_mapping_file: Optional[str] = None
):
    print("🔧 Starting HTML generation...", flush=True)

    # ========================================================================
    # VALIDACIÓN DE DATOS DEL MAPA
    # ========================================================================
    
    if map_data_with_coords is None or len(map_data_with_coords) == 0:
        print("❌ No map data provided!", flush=True)
        return ""
    
    print(f"📊 Map data received: {len(map_data_with_coords)} rows", flush=True)
    print(f"📋 Map data columns: {map_data_with_coords.columns.tolist()}", flush=True)
    
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
    
    print(f"🧹 Filtered map data: {before_filter} → {after_filter} (removed {before_filter - after_filter} without coords)", flush=True)
    
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

    print(f"✅ Postal column: {postal_col}", flush=True)

    # ========================================================================
    # PREPARE COUNTRIES
    # ========================================================================
    
    try:
        available_countries = sorted(df_original['Country'].dropna().unique().tolist())
    except Exception:
        available_countries = []
    print(f"✅ Available countries: {available_countries}", flush=True)

    # ========================================================================
    # PREPARE MAIN DATAFRAME
    # ========================================================================
    
    df_for_export = df_original.copy()

    # Convert dates to strings
    print("📅 Converting dates...", flush=True)
    if "Date" in df_for_export.columns:
        try:
            df_for_export["Date"] = pd.to_datetime(df_for_export["Date"], errors='coerce')
            df_for_export["Date"] = df_for_export["Date"].dt.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"⚠️ Date conversion error: {e}", flush=True)
            df_for_export["Date"] = df_for_export["Date"].astype(str)
    else:
        df_for_export["Date"] = ""

    df_for_export['PostalCode'] = df_for_export[postal_col].astype(str).str.strip()

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
        df_for_export["AccountMatchScore"] = None
        df_for_export["AccountMatchedName"] = None

    print(f"✅ Records ready: {len(df_for_export)}", flush=True)

    # ========================================================================
    # FEATURE FLAGS
    # ========================================================================
    
    has_city = 'City' in df_for_export.columns and df_for_export['City'].notna().sum() > 0
    has_segment = 'End User Segment' in df_for_export.columns
    has_market_org = 'Market Organization Name' in df_for_export.columns
    print(f"📊 Features: City={has_city}, Segment={has_segment}, MarketOrg={has_market_org}", flush=True)

    available_segments = []
    available_market_orgs = []

    if has_segment:
        available_segments = sorted(df_for_export['End User Segment'].dropna().unique().tolist())
        print(f"✅ Segments: {len(available_segments)}", flush=True)

    if has_market_org:
        available_market_orgs = sorted(df_for_export['Market Organization Name'].dropna().unique().tolist())
        print(f"✅ Market Orgs: {len(available_market_orgs)}", flush=True)

    # ========================================================================
    # PREPARE MAP DATA FOR EXPORT
    # ========================================================================
    
    print("🗺️ Preparing map data for export...", flush=True)
    
    map_data_for_export = map_data_clean.copy()
    
    # Asegurar todas las columnas necesarias
    if 'City' not in map_data_for_export.columns:
        map_data_for_export['City'] = ''
    
    if 'ResolvedCity' not in map_data_for_export.columns:
        if 'City' in map_data_for_export.columns:
            map_data_for_export['ResolvedCity'] = map_data_for_export['City'].fillna('Unknown')
        else:
            map_data_for_export['ResolvedCity'] = 'Unknown'
    
    if 'Representatives' not in map_data_for_export.columns:
        map_data_for_export['Representatives'] = ''
    
    if 'Main_Type' not in map_data_for_export.columns:
        map_data_for_export['Main_Type'] = 'Mixed'
    
    if 'GeoValidated' not in map_data_for_export.columns:
        map_data_for_export['GeoValidated'] = True
    
    # Convertir tipos
    try:
        map_data_for_export['Latitude'] = pd.to_numeric(map_data_for_export['Latitude'], errors='coerce')
        map_data_for_export['Longitude'] = pd.to_numeric(map_data_for_export['Longitude'], errors='coerce')
        map_data_for_export['Total_EUR'] = pd.to_numeric(map_data_for_export['Total_EUR'], errors='coerce').fillna(0)
        map_data_for_export['Num_Services'] = pd.to_numeric(map_data_for_export['Num_Services'], errors='coerce').fillna(0).astype(int)
        
        # Normalizar Country
        map_data_for_export['Country'] = map_data_for_export['Country'].astype(str).str.lower().str.strip()
        
        print(f"✅ Map data types converted successfully", flush=True)
    except Exception as e:
        print(f"❌ Error converting map data types: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return ""
    
    # Serializar a JSON
    try:
        # Seleccionar solo columnas necesarias para evitar problemas
        export_columns = [
            'PostalCode', 'Country', 'City', 'ResolvedCity',
            'Latitude', 'Longitude', 'Total_EUR', 'Num_Services',
            'Representatives', 'Main_Type', 'GeoValidated'
        ]
        
        # Filtrar columnas que existen
        export_columns = [col for col in export_columns if col in map_data_for_export.columns]
        
        map_data_json = map_data_for_export[export_columns].to_json(orient='records')
        print(f"✅ Map JSON created: {len(map_data_json):,} bytes, {len(map_data_for_export)} points", flush=True)
        
        # Validar que no esté vacío
        if map_data_json == "[]" or len(map_data_json) < 10:
            print("⚠️ WARNING: Map JSON is empty or too small!", flush=True)
            print(f"Map data sample:\n{map_data_for_export.head()}", flush=True)
            
    except Exception as e:
        print(f"❌ Error serializing map data: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return ""

    # ========================================================================
    # SERIALIZE FULL DATA
    # ========================================================================
    
    print("💾 Serializing full data...", flush=True)
    try:
        full_data_json = df_for_export.to_json(orient='records')
        print(f"✅ Full data JSON: {len(full_data_json):,} bytes", flush=True)
    except Exception as e:
        print(f"❌ Error serializing full data: {e}", flush=True)
        return ""

    # ========================================================================
    # SERIALIZE CACHE (OPCIONAL - ya no es crítico)
    # ========================================================================
    
    print("🔑 Serializing cache...", flush=True)
    try:
        coords_cache_json = json.dumps(geocode_cache)
        print(f"✅ Cache JSON: {len(coords_cache_json):,} bytes", flush=True)
    except Exception as e:
        print(f"⚠️ Warning: Could not serialize cache: {e}", flush=True)
        coords_cache_json = "{}"

    # ========================================================================
    # PRODUCT TYPES
    # ========================================================================
    
    product_types_list = list(df_original['ProductType'].dropna().unique()) if "ProductType" in df_original.columns else []
    print(f"✅ Product types: {len(product_types_list)}", flush=True)

    # ========================================================================
    # LOAD STYLES
    # ========================================================================
    
    print("🎨 Loading styles...", flush=True)
    try:
        buchi_css = load_buchi_css()
        sidebar_styles = get_sidebar_styles()
        common_styles = get_common_report_styles()
        print("✅ Styles loaded", flush=True)
    except Exception as e:
        print(f"❌ Error loading styles: {e}", flush=True)
        return ""

    sidebar_items = """
        <h2>📋 Índice</h2>
        <ul>
            <li><a href="#dashboard-section">Dashboard</a></li>
            <li><a href="#map-section">Mapa Geográfico</a></li>
            <li><a href="#table-section">Tabla de Datos</a></li>
        </ul>
    """

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    year = datetime.now().year

    # ========================================================================
    # JINJA2 SETUP
    # ========================================================================
    
    print("📁 Setting up Jinja2 environment...", flush=True)
    template_dir = os.path.join(os.path.dirname(__file__), 'core', 'templates')

    if not os.path.exists(template_dir):
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')

    if not os.path.exists(template_dir):
        print(f"⚠️ Template dir not found: {template_dir}", flush=True)
        template_dir = os.path.join(os.getcwd(), 'core', 'templates')
        print(f"🔍 Trying: {template_dir}", flush=True)

        if not os.path.exists(template_dir):
            print("❌ Template directory not found!", flush=True)
            return ""

    print(f"✅ Template directory: {template_dir}", flush=True)

    try:
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        print("✅ Jinja2 environment created", flush=True)
    except Exception as e:
        print(f"❌ Error creating Jinja2 environment: {e}", flush=True)
        return ""

    # ========================================================================
    # RENDER TEMPLATE
    # ========================================================================
    
    print("📄 Loading template...", flush=True)
    try:
        template = env.get_template('dashboard_template.html')
        print("✅ Template loaded", flush=True)
    except Exception as e:
        print(f"❌ Could not load template: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return ""

    print("🎨 Rendering template...", flush=True)
    try:
        html_content = template.render(
            buchi_css=buchi_css,
            sidebar_styles=sidebar_styles,
            common_styles=common_styles,
            colors=BUCHI_COLORS,

            # Markup => no escaping
            full_data_json=Markup(full_data_json),
            map_data_json=Markup(map_data_json),
            coords_cache_json=Markup(coords_cache_json),

            product_types_list=product_types_list,

            available_years=available_years,
            available_months=available_months,
            available_reps=available_reps,
            available_types=available_types,
            available_sets=available_sets,
            available_countries=available_countries,
            available_segments=available_segments,
            available_market_orgs=available_market_orgs,

            has_city=has_city,
            has_segment=has_segment,
            has_market_org=has_market_org,

            timestamp=timestamp,
            year=year,
            sidebar_items=sidebar_items,
            total_records=len(df_original),
            total_map_points=len(map_data_for_export),
            total_cache=len(geocode_cache),
            generation_date=datetime.now().strftime('%Y-%m-%d')
        )

        print(f"✅ Template rendered! Size: {len(html_content):,} bytes", flush=True)

        if len(html_content) < 1000:
            print("⚠️ WARNING: HTML too small!", flush=True)
            print(f"First 500 chars:\n{html_content[:500]}", flush=True)

        return html_content

    except Exception as e:
        print(f"❌ Error rendering template: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return ""
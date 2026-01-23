"""
Service Dashboard HTML Report Generator (Jinja2-based)
Generates standalone HTML dashboards with interactive filters and maps
"""

import json
import os
from datetime import datetime
from typing import Optional
from jinja2 import Template
from core.report_utils import load_buchi_css, get_sidebar_styles, get_common_report_styles
from app_config.plotting import BUCHI_COLORS
from core.account_linker import AccountLinker


def generate_service_dashboard_html(df_original, map_data_valid, available_years, 
                                    available_months, available_reps, available_types,
                                    available_sets,
                                    geocode_cache,
                                    account_mapping_file: Optional[str] = None):
    """
    Generate standalone HTML file with embedded data, map, and interactive filters
    
    Args:
        df_original: Full dataset DataFrame
        map_data_valid: Map data with valid coordinates
        available_years: List of available years
        available_months: List of available months
        available_reps: List of sales representatives
        available_types: List of product types
        available_sets: List of sets
        geocode_cache: Dictionary with geocoding cache
        account_mapping_file: Optional path to Excel/CSV with Account Name and Account URL columns
        
    Returns:
        str: Complete HTML content
    """
    
    # Detect postal code column
    postal_col = None
    for col in df_original.columns:
        if col.lower() in ['postalcode', 'postal code', 'postal_code', 'zipcode', 'zip_code', 'cp', 'codigo postal']:
            postal_col = col
            break
    
    if not postal_col:
        return ""
    
    # Linker + enrich
    linker = AccountLinker(account_mapping_file, min_score=80) if account_mapping_file else AccountLinker()

    available_countries = sorted(df_original['Country'].unique().tolist())
    df_for_export = df_original.copy()

    # Convert dates to strings
    df_for_export['Date'] = df_for_export['Date'].dt.strftime('%Y-%m-%d')
    df_for_export['PostalCode'] = df_for_export[postal_col].astype(str).str.strip()

    # Enrich with account URLs
    df_for_export = linker.enrich_dataframe(df_for_export, account_col='Business Partner Name')

    # ⭐ NUEVO: Detectar columnas disponibles
    has_city = 'City' in df_for_export.columns and df_for_export['City'].notna().sum() > 0
    has_segment = 'End User Segment' in df_for_export.columns
    has_market_org = 'Market Organization Name' in df_for_export.columns
    
    # ⭐ NUEVO: Obtener valores únicos de nuevos filtros
    available_segments = []
    available_market_orgs = []
    
    if has_segment:
        available_segments = sorted(df_for_export['End User Segment'].dropna().unique().tolist())
    
    if has_market_org:
        available_market_orgs = sorted(df_for_export['Market Organization Name'].dropna().unique().tolist())

    # Serialize data
    full_data_json = df_for_export.to_json(orient='records')
    map_data_json = map_data_valid.to_json(orient='records')
    coords_cache_json = json.dumps(geocode_cache)
    product_types_list = list(df_original['ProductType'].unique())
    
    # Load styles
    buchi_css = load_buchi_css()
    sidebar_styles = get_sidebar_styles()
    common_styles = get_common_report_styles()
    
    # Build sidebar items
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
    
    # ⭐ NUEVO: Cargar template Jinja2
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard_template.html')
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    template = Template(template_content)
    
    # ⭐ NUEVO: Renderizar con contexto
    html_content = template.render(
        # Styles
        buchi_css=buchi_css,
        sidebar_styles=sidebar_styles,
        common_styles=common_styles,
        colors=BUCHI_COLORS,
        
        # Data
        full_data_json=full_data_json,
        map_data_json=map_data_json,
        coords_cache_json=coords_cache_json,
        product_types_list=product_types_list,
        
        # Filters
        available_years=available_years,
        available_months=available_months,
        available_reps=available_reps,
        available_types=available_types,
        available_sets=available_sets,
        available_countries=available_countries,
        available_segments=available_segments,
        available_market_orgs=available_market_orgs,
        
        # Feature flags
        has_city=has_city,
        has_segment=has_segment,
        has_market_org=has_market_org,
        
        # Metadata
        timestamp=timestamp,
        year=year,
        sidebar_items=sidebar_items,
        total_records=len(df_original),
        total_cache=len(geocode_cache),
        generation_date=datetime.now().strftime('%Y-%m-%d')
    )
    
    return html_content
"""
Service Dashboard HTML Report Generator
Generates standalone HTML dashboards with interactive filters and maps
"""

import json
from datetime import datetime
from core.report_utils import load_buchi_css, get_sidebar_styles, get_common_report_styles
from app_config.plotting import BUCHI_COLORS


def generate_service_dashboard_html(df_original, map_data_valid, available_years, 
                                    available_months, available_reps, available_types,
                                    geocode_cache):
    """
    Generate standalone HTML file with embedded data, map, and interactive filters
    
    Args:
        df_original: Full dataset DataFrame
        map_data_valid: Map data with valid coordinates
        available_years: List of available years
        available_months: List of available months
        available_reps: List of sales representatives
        available_types: List of product types
        geocode_cache: Dictionary with geocoding cache
        
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
    
    # Prepare data for export
    df_for_export = df_original.copy()
    df_for_export['Date'] = df_for_export['Date'].dt.strftime('%Y-%m-%d')
    df_for_export['PostalCode'] = df_for_export[postal_col].astype(str).str.strip()
    
    full_data_json = df_for_export.to_json(orient='records')
    map_data_json = map_data_valid.to_json(orient='records')
    coords_cache_json = json.dumps(geocode_cache)
    product_types_list = list(df_original['ProductType'].unique())
    
    # Load BUCHI styles
    buchi_css = load_buchi_css()
    sidebar_styles = get_sidebar_styles()
    common_styles = get_common_report_styles()
    
    # Build sidebar
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
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Service Planning Dashboard - {datetime.now().strftime('%Y-%m-%d')}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    
    <style>
{buchi_css}
{sidebar_styles}
{common_styles}

        .main-content {{
            margin-left: 400px !important;
        }}
        
        /* Sidebar más ancho */
        .sidebar {{
            width: 400px !important;
        }}
        
        /* Ocultar scrollbars del sidebar */
        .sidebar {{
            scrollbar-width: none; /* Firefox */
            -ms-overflow-style: none; /* IE/Edge */
        }}
        
        .sidebar::-webkit-scrollbar {{
            display: none; /* Chrome/Safari/Opera */
        }}

        .filter-group label {{
            display: block;
            font-weight: bold;
            margin-bottom: 8px;
            color: white !important;
            font-size: 0.95rem;
        }}
        
        /* Estilos para details colapsables */
        .filter-group details {{
            margin-bottom: 10px;
        }}
        
        .filter-group summary {{
            cursor: pointer;
            font-weight: bold;
            color: white;
            padding: 10px 12px;
            user-select: none;
            list-style: none;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .filter-group summary::-webkit-details-marker {{
            display: none;
        }}
        
        .filter-group summary::before {{
            content: '▶';
            display: inline-block;
            transition: transform 0.2s;
            margin-right: 8px;
            font-size: 0.8em;
        }}
        
        .filter-group details[open] summary {{
            background: rgba(255, 255, 255, 0.12);
        }}
        
        .filter-group details[open] summary::before {{
            transform: rotate(90deg);
        }}
        
        .filter-group summary:hover {{
            background: rgba(255, 255, 255, 0.15);
            color: {BUCHI_COLORS['accent']};
        }}
        
        .summary-text {{
            flex: 1;
        }}
        
        /* Botones All/None en summary */
        .filter-actions {{
            display: inline-flex;
            gap: 4px;
            align-items: center;
            margin-left: 8px;
        }}
        
        .mini-btn {{
            background: rgba(255,255,255,0.15);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 10px;
            cursor: pointer;
            line-height: 1.2;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.2s;
        }}
        
        .mini-btn:hover {{
            background: {BUCHI_COLORS['accent']};
            border-color: {BUCHI_COLORS['accent']};
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        
        .mini-btn:active {{
            transform: translateY(0);
        }}

        .quick-filters {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
        }}
        
        .quick-filter-tag {{
            background-color: #e9ecef;
            border: 1px solid #adb5bd;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
            user-select: none;
        }}
        
        .quick-filter-tag:hover {{
            background-color: #d3d3d8;
        }}
        
        .quick-filter-tag.active {{
            background-color: {BUCHI_COLORS['accent']};
            color: white;
            border-color: {BUCHI_COLORS['accent']};
        }}
        
        .checkbox-group {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 200px;
            overflow-y: auto;
            padding: 10px;
            margin-top: 8px;
            background-color: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            /* Scrollbar sutil */
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.3) transparent;
        }}
        
        .checkbox-group::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .checkbox-group::-webkit-scrollbar-track {{
            background: transparent;
        }}
        
        .checkbox-group::-webkit-scrollbar-thumb {{
            background-color: rgba(255, 255, 255, 0.3);
            border-radius: 3px;
        }}
        
        .checkbox-group::-webkit-scrollbar-thumb:hover {{
            background-color: rgba(255, 255, 255, 0.5);
        }}
        
        .checkbox-group label {{
            display: flex;
            align-items: center;
            font-weight: normal !important;
            cursor: pointer;
            padding: 5px;
            border-radius: 3px;
            transition: background-color 0.2s;
            color: white !important;
        }}
        
        .checkbox-group label:hover {{
            background-color: rgba(255, 255, 255, 0.15);
        }}
        
        .checkbox-group input[type="checkbox"] {{
            width: auto;
            margin-right: 8px;
            cursor: pointer;
        }}
        
        .filter-group {{
            margin-bottom: 20px;
        }}
        
        .filter-group input[type="text"] {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
        
        .apply-filters-btn {{
            background: {BUCHI_COLORS['success']};
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            margin-top: 20px;
            transition: all 0.2s;
        }}
        
        .apply-filters-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            background: {BUCHI_COLORS['accent']};
        }}
        
        .reset-filters-btn {{
            background: #6c757d;
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            margin-top: 10px;
            transition: all 0.2s;
        }}
        
        .reset-filters-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            background: #5a6268;
        }}
        
        /* Active filters section */
        .active-filters-section {{
            margin-top: 20px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        
        .active-filters-section h3 {{
            color: white;
            font-size: 0.9rem;
            margin: 0 0 10px 0;
            opacity: 0.9;
        }}
        
        #resultCount {{
            color: #fff;
            font-size: 13px;
            opacity: 0.9;
            margin-bottom: 10px;
        }}
        
        #activeChips {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        
        .active-chip {{
            background: rgba(255, 255, 255, 0.2);
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }}
        
        /* Quick mode toggle */
        .quick-mode-toggle {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.15);
        }}
        
        .quick-mode-toggle label {{
            color: #fff !important;
            font-size: 12px !important;
            opacity: 0.9;
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            font-weight: normal !important;
        }}
        
        .quick-mode-toggle input[type="checkbox"] {{
            cursor: pointer;
        }}
        
        #map {{
            width: 100%;
            height: 600px;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .table-container {{
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 8px;
            /* Scrollbar sutil */
            scrollbar-width: thin;
            scrollbar-color: #ccc transparent;
        }}
        
        .table-container::-webkit-scrollbar {{
            width: 8px;
        }}
        
        .table-container::-webkit-scrollbar-track {{
            background: transparent;
        }}
        
        .table-container::-webkit-scrollbar-thumb {{
            background-color: #ccc;
            border-radius: 4px;
        }}
        
        .table-container::-webkit-scrollbar-thumb:hover {{
            background-color: #999;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
        }}
        
        th {{
            background-color: {BUCHI_COLORS['primary']};
            color: white;
            padding: 12px;
            text-align: left;
            position: sticky;
            top: 0;
            z-index: 10;
            cursor: pointer;
            user-select: none;
            transition: background-color 0.2s;
        }}
        
        th:hover {{
            background-color: {BUCHI_COLORS['secondary']};
        }}
        
        th::after {{
            content: ' ⇅';
            opacity: 0.3;
            font-size: 0.8em;
        }}
        
        th.sort-asc::after {{
            content: ' ↑';
            opacity: 1;
        }}
        
        th.sort-desc::after {{
            content: ' ↓';
            opacity: 1;
        }}
        
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
        }}
        
        tr:hover {{
            background-color: #f5f5f5;
        }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .metric-card.blue {{
            background: linear-gradient(135deg, {BUCHI_COLORS['kashmir_blue']} 0%, {BUCHI_COLORS['sky_blue']} 100%);
        }}
        
        .metric-card.green {{
            background: linear-gradient(135deg, {BUCHI_COLORS['teal_blue']} 0%, {BUCHI_COLORS['accent']} 100%);
        }}
        
        .metric-card.orange {{
            background: linear-gradient(135deg, {BUCHI_COLORS['sky_blue']} 0%, {BUCHI_COLORS['accent']} 100%);
        }}
        
        .metric-card.purple {{
            background: linear-gradient(135deg, {BUCHI_COLORS['primary']} 0%, {BUCHI_COLORS['secondary']} 100%);
        }}
        
        .metric-card .label {{
            font-size: 0.9rem;
            opacity: 0.9;
            margin-bottom: 10px;
        }}
        
        .metric-card .value {{
            font-size: 2rem;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <!-- SIDEBAR -->
    <div class="sidebar">
{sidebar_items}
        
        <div style="padding: 20px;">
            <div class="filter-group">
                <details>
                    <summary>
                        <span class="summary-text">📅 Years</span>
                        <span class="filter-actions">
                            <button type="button" class="mini-btn" onclick="setGroupChecked('year', true); event.preventDefault(); event.stopPropagation();">All</button>
                            <button type="button" class="mini-btn" onclick="setGroupChecked('year', false); event.preventDefault(); event.stopPropagation();">None</button>
                        </span>
                    </summary>
                    <div class="checkbox-group" id="yearFilters"></div>
                </details>
            </div>
            
            <div class="filter-group">
                <details>
                    <summary>
                        <span class="summary-text">📆 Months</span>
                        <span class="filter-actions">
                            <button type="button" class="mini-btn" onclick="setGroupChecked('month', true); event.preventDefault(); event.stopPropagation();">All</button>
                            <button type="button" class="mini-btn" onclick="setGroupChecked('month', false); event.preventDefault(); event.stopPropagation();">None</button>
                        </span>
                    </summary>
                    <div class="checkbox-group" id="monthFilters"></div>
                </details>
            </div>
            
            <div class="filter-group">
                <details>
                    <summary>
                        <span class="summary-text">👤 Sales Representatives</span>
                        <span class="filter-actions">
                            <button type="button" class="mini-btn" onclick="setGroupChecked('rep', true); event.preventDefault(); event.stopPropagation();">All</button>
                            <button type="button" class="mini-btn" onclick="setGroupChecked('rep', false); event.preventDefault(); event.stopPropagation();">None</button>
                        </span>
                    </summary>
                    <div class="checkbox-group" id="repFilters"></div>
                </details>
            </div>
            
            <div class="filter-group">
                <details>
                    <summary>
                        <span class="summary-text">🏷️ Product Types</span>
                        <span class="filter-actions">
                            <button type="button" class="mini-btn" onclick="setGroupChecked('type', true); event.preventDefault(); event.stopPropagation();">All</button>
                            <button type="button" class="mini-btn" onclick="setGroupChecked('type', false); event.preventDefault(); event.stopPropagation();">None</button>
                        </span>
                    </summary>
                    <div class="checkbox-group" id="typeFilters"></div>
                </details>
            </div>
            
            <div class="filter-group">
                <details open>
                    <summary>
                        <span class="summary-text">🔍 Search Service</span>
                    </summary>
                    <div class="quick-filters">
                        <span class="quick-filter-tag" data-keyword="CARE" onclick="toggleQuickFilter(this)">CARE</span>
                        <span class="quick-filter-tag" data-keyword="Exact" onclick="toggleQuickFilter(this)">Exact</span>
                        <span class="quick-filter-tag" data-keyword="Start" onclick="toggleQuickFilter(this)">Start</span>
                        <span class="quick-filter-tag" data-keyword="Circle" onclick="toggleQuickFilter(this)">Circle</span>
                        <span class="quick-filter-tag" data-keyword="Maintain" onclick="toggleQuickFilter(this)">Maintain</span>
                        <span class="quick-filter-tag" data-keyword="IQ/OQ" onclick="toggleQuickFilter(this)">IQ/OQ</span>
                        <span class="quick-filter-tag" data-keyword="OQ" onclick="toggleQuickFilter(this)">OQ</span>
                        <span class="quick-filter-tag" data-keyword="Install" onclick="toggleQuickFilter(this)">Install</span>
                    </div>
                    <input type="text" id="searchInput" placeholder="Or type custom search..." style="margin-top: 8px;">
                    
                    <div class="quick-mode-toggle">
                        <label>
                            <input type="checkbox" id="quickModeOr" onchange="setQuickMode(this.checked ? 'OR' : 'AND')">
                            Quick filters en modo OR (si no, AND)
                        </label>
                    </div>
                </details>
            </div>
            
            <div class="filter-group">
                <label>👥 Filter by Client</label>
                <input type="text" id="clientInput" placeholder="e.g., 'Universidad', 'Hospital'...">
            </div>
            
            <button class="apply-filters-btn" onclick="applyFilters()">🔄 Apply Filters</button>
            <button class="reset-filters-btn" onclick="resetFilters()">♻ Reset Filters</button>
            
            <!-- Active filters section -->
            <div class="active-filters-section">
                <h3>📌 Active Filters</h3>
                <div id="resultCount"></div>
                <div id="activeChips"></div>
            </div>
        </div>
    </div>
    
    <!-- MAIN CONTENT -->
    <div class="main-content">
        <h1>🗺️ Service Planning Dashboard</h1>
        
        <!-- INFO GENERAL -->
        <div class="info-box" id="dashboard-section">
            <h2>Información General</h2>
            <table>
                <tr>
                    <th>Fecha de generación</th>
                    <td>{timestamp}</td>
                </tr>
                <tr>
                    <th>Total de registros</th>
                    <td>{len(df_original)}</td>
                </tr>
                <tr>
                    <th>Coordenadas en caché</th>
                    <td>{len(geocode_cache)}</td>
                </tr>
            </table>
        </div>
        
        <!-- METRICS -->
        <div class="metrics">
            <div class="metric-card blue">
                <div class="label">💰 Total EUR</div>
                <div class="value" id="metricEUR">€0.00</div>
            </div>
            <div class="metric-card green">
                <div class="label">📊 Services</div>
                <div class="value" id="metricServices">0</div>
            </div>
            <div class="metric-card orange">
                <div class="label">📍 Cities</div>
                <div class="value" id="metricCities">0</div>
            </div>
            <div class="metric-card purple">
                <div class="label">👥 Clients</div>
                <div class="value" id="metricClients">0</div>
            </div>
        </div>
        
        <!-- MAP SECTION -->
        <div class="info-box" id="map-section">
            <h2>🗺️ Geographic Distribution</h2>
            <p class="text-caption">
                <em>Mapa interactivo mostrando la distribución geográfica de servicios. El tamaño de las burbujas representa el volumen de facturación.</em>
            </p>
            <div id="map"></div>
        </div>
        
        <!-- TABLE SECTION -->
        <div class="info-box" id="table-section">
            <h2>📋 Service Details</h2>
            <p class="text-caption">
                <em>Tabla detallada de todos los servicios filtrados. Haz clic en los encabezados para ordenar las columnas.</em>
            </p>
            <div class="table-container">
                <table id="serviceTable">
                    <thead>
                        <tr>
                            <th onclick="sortTable(0)" data-col="0">Date</th>
                            <th onclick="sortTable(1)" data-col="1">City</th>
                            <th onclick="sortTable(2)" data-col="2">Client</th>
                            <th onclick="sortTable(3)" data-col="3">Service</th>
                            <th onclick="sortTable(4)" data-col="4">Type</th>
                            <th onclick="sortTable(5)" data-col="5">EUR</th>
                            <th onclick="sortTable(6)" data-col="6">Rep</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody"></tbody>
                </table>
            </div>
        </div>
        
        <!-- FOOTER -->
        <div style="margin-top: 50px; padding-top: 20px; border-top: 2px solid #eee; text-align: center; color: #666; font-size: 12px;">
            <p>Dashboard generado automáticamente por Service Planning Tool</p>
            <p>Fecha: {timestamp}</p>
            <p>© {year} BÜCHI Labortechnik AG</p>
        </div>
    </div>
    
    <script>
        // =============================
        // EMBEDDED DATA
        // =============================
        const fullData = {full_data_json};
        const coordsCache = {coords_cache_json};
        const productTypes = {json.dumps(product_types_list)};
        const availableYears = {json.dumps(available_years)};
        const availableMonths = {json.dumps(available_months)};
        const availableReps = {json.dumps(available_reps)};
        const availableTypes = {json.dumps(available_types)};
        const monthNames = ['January','February','March','April','May','June',
                            'July','August','September','October','November','December'];

        // =============================
        // STATE
        // =============================
        let filteredData = [...fullData];
        let filteredMapData = [];
        let activeQuickFilters = [];
        let quickMode = 'AND';  // AND (default) | OR
        let sortState = {{ column: 0, ascending: false }};
        const STORAGE_KEY = 'service_dashboard_filters_v1';

        // =============================
        // HELPERS
        // =============================
        function $(id) {{ return document.getElementById(id); }}

        function safeLower(v) {{
            return String(v ?? '').toLowerCase();
        }}

        function uniq(arr) {{
            return Array.from(new Set(arr));
        }}

        function escapeHtml(str) {{
            return String(str ?? '')
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#39;');
        }}

        function getCheckedValues(selector, mapFn) {{
            return Array.from(document.querySelectorAll(selector + ':checked'))
                .map(cb => mapFn ? mapFn(cb) : cb.value);
        }}

        function setAll(selector, checked) {{
            document.querySelectorAll(selector).forEach(cb => cb.checked = checked);
        }}

        // =============================
        // ALL/NONE GROUP BUTTONS
        // =============================
        function setGroupChecked(group, checked) {{
            const map = {{
                year: '.year-filter',
                month: '.month-filter',
                rep: '.rep-filter',
                type: '.type-filter'
            }};
            const selector = map[group];
            if (!selector) return;

            setAll(selector, checked);
            saveFilterState();
            applyFilters();
        }}

        // =============================
        // QUICK FILTERS
        // =============================
        function toggleQuickFilter(el) {{
            const key = el.getAttribute('data-keyword');
            el.classList.toggle('active');

            if (el.classList.contains('active')) {{
                activeQuickFilters.push(key);
            }} else {{
                activeQuickFilters = activeQuickFilters.filter(k => k !== key);
            }}

            saveFilterState();
        }}

        function setQuickMode(mode) {{
            quickMode = mode;
            saveFilterState();
            applyFilters();
        }}

        // =============================
        // DEBOUNCE HELPER
        // =============================
        function debounce(fn, ms) {{
            let t = null;
            return function() {{
                clearTimeout(t);
                t = setTimeout(() => fn(), ms);
            }};
        }}

        // =============================
        // INITIALIZE FILTER UI
        // =============================
        function initializeFilters() {{
            const yearBox = $('yearFilters');
            availableYears.forEach(y => {{
                const l = document.createElement('label');
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = y;
                cb.checked = true;
                cb.className = 'year-filter';
                l.appendChild(cb);
                l.append(' ' + y);
                yearBox.appendChild(l);
            }});

            const monthBox = $('monthFilters');
            availableMonths.forEach(m => {{
                const l = document.createElement('label');
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = m;
                cb.checked = false; // ninguno = todos
                cb.className = 'month-filter';
                l.appendChild(cb);
                l.append(' ' + monthNames[m - 1]);
                monthBox.appendChild(l);
            }});

            const repBox = $('repFilters');
            availableReps.forEach(r => {{
                const l = document.createElement('label');
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = r;
                cb.checked = true;
                cb.className = 'rep-filter';
                l.appendChild(cb);
                l.append(' ' + r);
                repBox.appendChild(l);
            }});

            const typeBox = $('typeFilters');
            availableTypes.forEach(t => {{
                const l = document.createElement('label');
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = t;
                cb.checked = true;
                cb.className = 'type-filter';
                l.appendChild(cb);
                l.append(' ' + t);
                typeBox.appendChild(l);
            }});

            // Auto-apply filters on checkbox change with debounce
            const applyDebounced = debounce(applyFilters, 200);
            document.querySelectorAll('.year-filter, .month-filter, .rep-filter, .type-filter')
                .forEach(cb => cb.addEventListener('change', applyDebounced));
        }}

        // =============================
        // APPLY FILTERS (CORE)
        // =============================
        function applyFilters() {{
            const years = getCheckedValues('.year-filter', cb => parseInt(cb.value));
            let months = getCheckedValues('.month-filter', cb => parseInt(cb.value));
            const reps = getCheckedValues('.rep-filter');
            const types = getCheckedValues('.type-filter');
            const manualSearch = safeLower($('searchInput')?.value);
            const clientSearch = safeLower($('clientInput')?.value);

            // Si no hay meses seleccionados → TODOS
            if (months.length === 0) {{
                months = [...availableMonths];
            }}

            filteredData = fullData.filter(row => {{
                const d = new Date(row.Date);
                const y = d.getFullYear();
                const m = d.getMonth() + 1;

                if (!years.includes(y)) return false;
                if (!months.includes(m)) return false;
                if (!reps.includes(row.SalesRepresentative)) return false;
                if (!types.includes(row.ProductType)) return false;

                const item = safeLower(row.ItemIdAndName);

                if (activeQuickFilters.length > 0) {{
                    const matches = (quickMode === 'AND')
                        ? activeQuickFilters.every(k => item.includes(k.toLowerCase()))
                        : activeQuickFilters.some(k => item.includes(k.toLowerCase()));
                    if (!matches) return false;
                }} else if (manualSearch) {{
                    if (!item.includes(manualSearch)) return false;
                }}

                if (clientSearch) {{
                    const client = safeLower(row['Business Partner Name']);
                    if (!client.includes(clientSearch)) return false;
                }}

                return true;
            }});

            updateMetrics();
            updateMapData();
            renderMap();
            renderTable();
            updateStatusUI();
            saveFilterState();
        }}

        // =============================
        // STATUS UI (X / Y + CHIPS)
        // =============================
        function updateStatusUI() {{
            const total = fullData.length;
            const shown = filteredData.length;

            if ($('resultCount')) {{
                $('resultCount').textContent = `Showing ${{shown}} of ${{total}} records`;
            }}

            if (!$('activeChips')) return;

            const chips = [];

            activeQuickFilters.forEach(k => chips.push(`Service:${{k}}`));
            
            const selectedYears = getCheckedValues('.year-filter');
            if (selectedYears.length > 0 && selectedYears.length < availableYears.length) {{
                selectedYears.forEach(v => chips.push(`Year:${{v}}`));
            }}
            
            const selectedMonths = getCheckedValues('.month-filter');
            if (selectedMonths.length > 0) {{
                selectedMonths.forEach(v => {{
                    const monthName = monthNames[parseInt(v) - 1];
                    chips.push(`Month:${{monthName}}`);
                }});
            }}
            
            const selectedReps = getCheckedValues('.rep-filter');
            if (selectedReps.length > 0 && selectedReps.length < availableReps.length) {{
                selectedReps.forEach(v => chips.push(`Rep:${{v}}`));
            }}
            
            const selectedTypes = getCheckedValues('.type-filter');
            if (selectedTypes.length > 0 && selectedTypes.length < availableTypes.length) {{
                selectedTypes.forEach(v => chips.push(`Type:${{v}}`));
            }}

            $('activeChips').innerHTML = '';
            chips.forEach(c => {{
                const span = document.createElement('span');
                span.className = 'active-chip';
                span.textContent = c;
                $('activeChips').appendChild(span);
            }});
        }}

        // =============================
        // RESET / SELECT ALL / NONE
        // =============================
        function resetFilters() {{
            setAll('.year-filter', true);
            setAll('.month-filter', false);
            setAll('.rep-filter', true);
            setAll('.type-filter', true);

            activeQuickFilters = [];
            document.querySelectorAll('.quick-filter-tag')
                .forEach(el => el.classList.remove('active'));

            if ($('searchInput')) $('searchInput').value = '';
            if ($('clientInput')) $('clientInput').value = '';

            quickMode = 'AND';
            if ($('quickModeOr')) $('quickModeOr').checked = false;
            
            localStorage.removeItem(STORAGE_KEY);
            applyFilters();
        }}

        // =============================
        // LOCAL STORAGE
        // =============================
        function saveFilterState() {{
            const state = {{
                years: getCheckedValues('.year-filter'),
                months: getCheckedValues('.month-filter'),
                reps: getCheckedValues('.rep-filter'),
                types: getCheckedValues('.type-filter'),
                quick: activeQuickFilters,
                quickMode: quickMode,
                search: $('searchInput')?.value || '',
                client: $('clientInput')?.value || ''
            }};
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }}

        function restoreFilterState() {{
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;

            try {{
                const s = JSON.parse(raw);

                const yearsSet  = new Set((s.years  || []).map(String));
                const monthsSet = new Set((s.months || []).map(String));
                const repsSet   = new Set((s.reps   || []).map(String));
                const typesSet  = new Set((s.types  || []).map(String));

                setAll('.year-filter', false);
                setAll('.month-filter', false);
                setAll('.rep-filter', false);
                setAll('.type-filter', false);

                document.querySelectorAll('.year-filter').forEach(cb => cb.checked = yearsSet.has(String(cb.value)));
                document.querySelectorAll('.month-filter').forEach(cb => cb.checked = monthsSet.has(String(cb.value)));
                document.querySelectorAll('.rep-filter').forEach(cb => cb.checked = repsSet.has(String(cb.value)));
                document.querySelectorAll('.type-filter').forEach(cb => cb.checked = typesSet.has(String(cb.value)));

                activeQuickFilters = s.quick || [];
                quickMode = s.quickMode || 'AND';

                if ($('quickModeOr')) {{
                    $('quickModeOr').checked = (quickMode === 'OR');
                }}

                document.querySelectorAll('.quick-filter-tag').forEach(el => {{
                    if (activeQuickFilters.includes(el.dataset.keyword)) {{
                        el.classList.add('active');
                    }} else {{
                        el.classList.remove('active');
                    }}
                }});

                if ($('searchInput')) $('searchInput').value = s.search || '';
                if ($('clientInput')) $('clientInput').value = s.client || '';
            }} catch (e) {{
                console.warn('Failed to restore filter state', e);
                try {{ localStorage.removeItem(STORAGE_KEY); }} catch (err) {{}}
            }}
        }}

        // =============================
        // ORIGINAL FUNCTIONS (RESTORED)
        // =============================
        function updateMapData() {{
            const cityGroups = {{}};

            filteredData.forEach(row => {{
                const postalStr = String(row.PostalCode || '').trim();
                const cityStr = String(row.City || '').trim();
                const key = cityStr + '_' + postalStr;

                if (!cityGroups[key]) {{
                    cityGroups[key] = {{
                        City: cityStr,
                        PostalCode: postalStr,
                        Total_EUR: 0,
                        Num_Services: 0,
                        Representatives: new Set(),
                        ProductTypes: {{}}
                    }};
                }}

                cityGroups[key].Total_EUR += row.EUR || 0;
                cityGroups[key].Num_Services += 1;
                cityGroups[key].Representatives.add(row.SalesRepresentative);

                const type = row.ProductType;
                cityGroups[key].ProductTypes[type] = (cityGroups[key].ProductTypes[type] || 0) + 1;
            }});

            filteredMapData = Object.values(cityGroups).map(group => {{
                const postal = String(group.PostalCode).trim();
                const city = String(group.City).trim();
                const country = /^\\d{{4}}-\\d{{3}}$/.test(postal) ? 'pt' : 'es';

                const cacheKey = `${{postal}}_${{city}}_${{country}}`;
                const coords = coordsCache[cacheKey];

                const types = Object.entries(group.ProductTypes);
                const mainType = types.length > 0
                    ? types.reduce((a, b) => a[1] > b[1] ? a : b)[0]
                    : 'Mixed';

                return {{
                    City: group.City,
                    PostalCode: group.PostalCode,
                    Total_EUR: group.Total_EUR,
                    Num_Services: group.Num_Services,
                    Representatives: Array.from(group.Representatives).slice(0, 3).join(', '),
                    Main_Type: mainType,
                    Latitude: coords ? coords[0] : null,
                    Longitude: coords ? coords[1] : null
                }};
            }}).filter(item => item.Latitude && item.Longitude);
        }}

        function updateMetrics() {{
            const totalEUR = filteredData.reduce((sum, row) => sum + (row.EUR || 0), 0);
            const numServices = filteredData.length;
            const numCities = new Set(filteredData.map(row => row.City)).size;
            const numClients = new Set(filteredData.map(row => row['Business Partner Name'])).size;

            if ($('metricEUR')) {{
                $('metricEUR').textContent = '€' + totalEUR.toLocaleString('es-ES', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
            }}
            if ($('metricServices')) $('metricServices').textContent = numServices.toLocaleString();
            if ($('metricCities')) $('metricCities').textContent = numCities.toLocaleString();
            if ($('metricClients')) $('metricClients').textContent = numClients.toLocaleString();
        }}

        function renderMap() {{
            if (filteredMapData.length === 0) {{
                $('map').innerHTML = '<p style="text-align:center; padding:50px; color:#999;">No data to display</p>';
                return;
            }}

            const trace = {{
                type: 'scattermapbox',
                lon: filteredMapData.map(d => d.Longitude),
                lat: filteredMapData.map(d => d.Latitude),
                mode: 'markers',
                marker: {{
                    size: filteredMapData.map(d => Math.max(10, Math.sqrt(Math.abs(d.Total_EUR)) / 5)),
                    color: filteredMapData.map(d => productTypes.indexOf(d.Main_Type)),
                    colorscale: 'Viridis',
                    showscale: true,
                    sizemode: 'diameter'
                }},
                text: filteredMapData.map(d =>
                    `${{d.City}}<br>Total: €${{d.Total_EUR.toFixed(2)}}<br>Services: ${{d.Num_Services}}<br>Reps: ${{d.Representatives}}<br>Type: ${{d.Main_Type}}`
                ),
                hoverinfo: 'text'
            }};

            const lats = filteredMapData.map(d => d.Latitude);
            const lons = filteredMapData.map(d => d.Longitude);
            const latCenter = lats.reduce((a, b) => a + b, 0) / lats.length;
            const lonCenter = lons.reduce((a, b) => a + b, 0) / lons.length;

            const latRange = Math.max(...lats) - Math.min(...lats);
            const lonRange = Math.max(...lons) - Math.min(...lons);
            const maxRange = Math.max(latRange, lonRange);

            let zoom = 5;
            if (maxRange < 1) zoom = 10;
            else if (maxRange < 3) zoom = 8;
            else if (maxRange < 7) zoom = 6;

            const layout = {{
                mapbox: {{
                    style: 'open-street-map',
                    center: {{ lon: lonCenter, lat: latCenter }},
                    zoom: zoom
                }},
                margin: {{ r: 0, t: 0, l: 0, b: 0 }},
                height: 600
            }};

            Plotly.newPlot('map', [trace], layout, {{ responsive: true }});
        }}

        function sortTable(colIndex) {{
            if (sortState.column === colIndex) {{
                sortState.ascending = !sortState.ascending;
            }} else {{
                sortState.column = colIndex;
                sortState.ascending = true;
            }}

            document.querySelectorAll('th').forEach((th, idx) => {{
                th.classList.remove('sort-asc', 'sort-desc');
                if (idx === colIndex) {{
                    th.classList.add(sortState.ascending ? 'sort-asc' : 'sort-desc');
                }}
            }});

            const sortedData = [...filteredData].sort((a, b) => {{
                let aVal, bVal;

                switch (colIndex) {{
                    case 0:
                        aVal = new Date(a.Date);
                        bVal = new Date(b.Date);
                        break;
                    case 1:
                        aVal = a.City;
                        bVal = b.City;
                        break;
                    case 2:
                        aVal = a['Business Partner Name'];
                        bVal = b['Business Partner Name'];
                        break;
                    case 3:
                        aVal = a.ItemIdAndName;
                        bVal = b.ItemIdAndName;
                        break;
                    case 4:
                        aVal = a.ProductType;
                        bVal = b.ProductType;
                        break;
                    case 5:
                        aVal = a.EUR || 0;
                        bVal = b.EUR || 0;
                        break;
                    case 6:
                        aVal = a.SalesRepresentative;
                        bVal = b.SalesRepresentative;
                        break;
                }}

                if (typeof aVal === 'string') {{
                    return sortState.ascending ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                }} else {{
                    return sortState.ascending ? aVal - bVal : bVal - aVal;
                }}
            }});

            const tbody = $('tableBody');
            tbody.innerHTML = '';

            sortedData.forEach(row => {{
                const tr = document.createElement('tr');
                const date = new Date(row.Date).toLocaleDateString();
                tr.innerHTML = `
                    <td>${{date}}</td>
                    <td>${{escapeHtml(row.City)}}</td>
                    <td>${{escapeHtml(row['Business Partner Name'])}}</td>
                    <td>${{escapeHtml(row.ItemIdAndName)}}</td>
                    <td>${{escapeHtml(row.ProductType)}}</td>
                    <td>€${{(row.EUR || 0).toFixed(2)}}</td>
                    <td>${{escapeHtml(row.SalesRepresentative)}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function renderTable() {{
            sortTable(sortState.column);
        }}
        
        // =============================
        // BOOT
        // =============================
        initializeFilters();
        restoreFilterState();
        applyFilters();
    </script>

</body>
</html>
"""
    
    return html_content
"""
Report Utils - Shared Functions
================================
Funciones compartidas para generadores de informes HTML.
Usado por: validation_kit_report_generator y offset_adjustment_report_generator

Author: Miquel
Date: December 2024
"""

from typing import Dict, List
import pandas as pd
import numpy as np
from datetime import datetime


def wrap_chart_in_expandable(chart_html: str, title: str, chart_id: str, 
                             default_open: bool = False) -> str:
    """
    Envuelve un gráfico en un elemento expandible HTML.
    
    Args:
        chart_html: HTML del gráfico
        title: Título del expandible
        chart_id: ID único para el expandible
        default_open: Si debe estar abierto por defecto
        
    Returns:
        str: HTML con el gráfico en un expandible
    """
    open_attr = "open" if default_open else ""
    
    return f"""
    <details class="chart-expandable" {open_attr}>
        <summary style="cursor: pointer; font-weight: bold; padding: 10px; background-color: #f8f9fa; border-radius: 5px; user-select: none; color: #333;">
            📊 {title}
        </summary>
        <div style="padding: 15px; margin-top: 10px;">
            {chart_html}
        </div>
    </details>
    """


def load_buchi_css() -> str:
    """
    Carga y consolida todos los archivos CSS corporativos de Buchi.
    
    Returns:
        str: Contenido CSS completo
    """
    css_files = [
        'css/base.css',
        'css/sidebar.css',
        'css/tables.css',
        'css/buttons.css',
        'css/boxes.css',
        'css/plots.css',
        'css/tabs.css',
        'css/consolidator.css',
        'css/tsv_validation.css',
        'css/prediction_reports.css',
        'css/responsive.css'
        'css/carousel.css'
    ]
    
    consolidated_css = ""
    
    for css_file in css_files:
        try:
            with open(css_file, 'r', encoding='utf-8') as f:
                consolidated_css += f"\n/* ===== {css_file} ===== */\n"
                consolidated_css += f.read()
                consolidated_css += "\n"
        except FileNotFoundError:
            print(f"Warning: CSS file not found: {css_file}")
            continue
    
    # Fallback si no se cargó nada
    if not consolidated_css:
        consolidated_css = """
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            h1, h2, h3 { color: #2c5f3f; }
            table { width: 100%; border-collapse: collapse; margin: 15px 0; }
            th { background-color: #2c5f3f; color: white; padding: 10px; text-align: left; }
            td { padding: 8px; border-bottom: 1px solid #ddd; }
            .info-box { background-color: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 5px; }
            .warning-box { background-color: #fff3cd; padding: 20px; margin: 20px 0; border-radius: 5px; border-left: 4px solid #ffc107; }
            .success-box { background-color: #d4edda; padding: 20px; margin: 20px 0; border-radius: 5px; border-left: 4px solid #28a745; }
            .status-good { color: #4caf50; font-weight: bold; }
            .status-warning { color: #ff9800; font-weight: bold; }
            .status-bad { color: #f44336; font-weight: bold; }
        """
    
    return consolidated_css

def get_sidebar_styles() -> str:
    """
    Retorna los estilos CSS para el sidebar del informe.
    CORREGIDO: Usa selectores específicos para evitar conflictos con main-content.
    
    Returns:
        str: CSS del sidebar
    """
    return """
        .sidebar {
            position: fixed; left: 0; top: 0; width: 250px; height: 100%;
            background-color: #093A34; padding: 20px; overflow-y: auto; z-index: 1000;
        }
        .sidebar h2 {
            color: white; font-size: 16px; margin-bottom: 20px; text-align: center;
        }
        .sidebar ul { list-style: none; padding: 0; }
        .sidebar ul li { margin-bottom: 10px; }
        .sidebar ul li a {
            color: white; text-decoration: none; display: block; padding: 8px;
            border-radius: 5px; transition: background-color 0.3s; font-weight: bold;
            font-size: 14px;
        }
        .sidebar ul li a:hover { background-color: #289A93; }
        
        /* Estilos ESPECÍFICOS para details del menú del sidebar */
        .sidebar .sidebar-menu-details {
            margin-bottom: 10px;
        }
        .sidebar .sidebar-menu-details summary {
            color: white;
            list-style: none;
            user-select: none;
            cursor: pointer;
            padding: 8px;
            border-radius: 5px;
            font-weight: bold;
            font-size: 14px;
            font: helvetica;
        }
        .sidebar .sidebar-menu-details summary::-webkit-details-marker {
            display: none;
        }
        .sidebar .sidebar-menu-details summary:hover {
            background-color: #289A93;
        }
        .sidebar .sidebar-menu-details[open] summary {
            background-color: #289A93;
        }
        .sidebar .sidebar-menu-details ul li a {
            font-size: 12px;
            font-weight: normal;
            padding: 6px 8px;
        }
    """


def get_common_report_styles() -> str:
    """
    Retorna estilos CSS comunes para todos los informes.
    
    Returns:
        str: CSS común
    """
    return """
        .main-content { margin-left: 270px; padding: 20px; }
        
        /* Estilos específicos para expandibles de gráficos en main-content */
        .main-content .chart-expandable {
            margin: 20px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
            background-color: white;
        }
        
        .main-content .chart-expandable summary {
            cursor: pointer;
            font-weight: bold;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 5px;
            user-select: none;
            color: #333;
            list-style: none;
        }
        
        .main-content .chart-expandable summary::-webkit-details-marker {
            display: none;
        }
        
        .main-content .chart-expandable summary:hover {
            background-color: #e9ecef;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .metric-card {
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .metric-card.ok {
            background-color: #e8f5e9;
            border-left: 4px solid #4caf50;
        }
        
        .metric-card.warning {
            background-color: #fff3e0;
            border-left: 4px solid #ff9800;
        }
        
        .metric-card.fail {
            background-color: #ffebee;
            border-left: 4px solid #f44336;
        }
        
        .metric-card.total {
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
        }
        
        .metric-card.offset {
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
        }
        
        .metric-card.standards {
            background-color: #f3e5f5;
            border-left: 4px solid #9c27b0;
        }
        
        .metric-card.improvement {
            background-color: #e8f5e9;
            border-left: 4px solid #4caf50;
        }
        
        .metric-value {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .metric-label {
            font-size: 14px;
            color: #666;
        }
        
        .comparison-table {
            margin: 20px 0;
        }
        
        .comparison-table th {
            text-align: center;
        }
        
        .improvement {
            color: #4caf50;
            font-weight: bold;
        }
        
        .degradation {
            color: #f44336;
            font-weight: bold;
        }
        
        @media print {
            .sidebar { display: none; }
            .main-content { margin-left: 0; }
        }
    """


def build_sidebar_html(sections: List[tuple], standards_list: List[Dict] = None,
                       show_individual_analysis: bool = True) -> str:
    """
    Construye el HTML del sidebar con índice de navegación.
    
    Args:
        sections: Lista de tuplas (id, label) para secciones principales
        standards_list: Lista de diccionarios con datos de estándares para sub-índice
        show_individual_analysis: Si True, incluye sección de análisis individual
        
    Returns:
        str: HTML del sidebar
    """
    sidebar_items = []
    
    # Secciones principales
    for sid, label in sections:
        sidebar_items.append(f'<li><a href="#{sid}">{label}</a></li>')
    
    # Sub-índice de estándares individuales (si se proporciona)
    if show_individual_analysis and standards_list:
        standards_submenu = []
        for data in standards_list:
            sample_id = data.get('id', 'Unknown')
            
            # Determinar icono según estado (si está disponible)
            if 'validation_results' in data:
                val_res = data['validation_results']
                has_shift = data.get('has_shift', False)
                
                if val_res.get('pass', False) and not has_shift:
                    icon = "✅"
                elif val_res.get('pass', False) and has_shift:
                    icon = "⚠️"
                else:
                    icon = "❌"
            else:
                icon = "📊"
            
            standards_submenu.append(
                f'<li><a href="#standard-{sample_id}">{icon} {sample_id}</a></li>'
            )
        
        standards_html = "\n".join(standards_submenu)
        
        sidebar_items.append(f'''
            <li>
                <details class="sidebar-menu-details">
                    <summary>
                        📊 Análisis Individual
                    </summary>
                    <ul style="padding-left: 15px; margin-top: 5px;">
                        {standards_html}
                    </ul>
                </details>
            </li>
        ''')
    
    return "\n".join(sidebar_items)


def evaluate_offset(offset: float) -> str:
    """
    Evalúa el offset según umbrales y retorna HTML con estilo.
    
    Args:
        offset: Valor del offset
        
    Returns:
        str: HTML con evaluación estilizada
    """
    from app_config import OFFSET_LIMITS
    
    abs_offset = abs(offset)
    
    if abs_offset < OFFSET_LIMITS['negligible']:
        return '<span class="status-good">✅ Despreciable</span>'
    elif abs_offset < OFFSET_LIMITS['acceptable']:
        return '<span class="status-good">✓ Aceptable</span>'
    else:
        return '<span class="status-warning">⚠️ Significativo</span>'


def format_change(delta: float, inverse: bool = False, show_sign: bool = False) -> str:
    """
    Formatea el cambio con color según si es mejora o empeoramiento.
    
    Args:
        delta: Cambio en la métrica
        inverse: Si True, un valor negativo es mejora (para Max Δ, RMS)
        show_sign: Si True, muestra el signo incluso para abs()
    
    Returns:
        str: HTML con cambio formateado y estilizado
    """
    if show_sign:
        text = f"{delta:+.6f}"
    else:
        text = f"{delta:+.6f}"
    
    # Determinar si es mejora
    if inverse:
        is_improvement = delta < 0
    else:
        is_improvement = delta > 0
    
    if abs(delta) < 0.000001:
        return f'<span style="color: #666;">{text}</span>'
    elif is_improvement:
        return f'<span class="improvement">↑ {text}</span>'
    else:
        return f'<span class="degradation">↓ {text}</span>'


def generate_service_info_section(sensor_serial: str, customer_name: str, 
                                  technician_name: str, service_notes: str,
                                  additional_info: Dict = None) -> str:
    """
    Genera la sección de información del servicio.
    
    Args:
        sensor_serial: Número de serie del sensor
        customer_name: Nombre del cliente
        technician_name: Nombre del técnico
        service_notes: Notas del servicio
        additional_info: Diccionario con información adicional a mostrar
        
    Returns:
        str: HTML de la sección de información
    """
    report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    html = f"""
        <div class="info-box" id="info-servicio">
            <h2>Información del Servicio</h2>
            <table>
                <tr><th>Campo</th><th>Valor</th></tr>
                <tr><td><strong>Cliente</strong></td><td>{customer_name}</td></tr>
                <tr><td><strong>Técnico</strong></td><td>{technician_name}</td></tr>
                <tr><td><strong>Número de Serie</strong></td><td>{sensor_serial}</td></tr>
                <tr><td><strong>Fecha del Informe</strong></td><td>{report_date}</td></tr>
    """
    
    # Añadir información adicional si se proporciona
    if additional_info:
        for key, value in additional_info.items():
            html += f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>\n"
    
    html += f"""
                <tr><td><strong>Notas del Servicio</strong></td><td>{service_notes if service_notes else 'N/A'}</td></tr>
            </table>
        </div>
    """
    
    return html


def generate_footer(tool_name: str = "NIR ServiceKit") -> str:
    """
    Genera el footer del informe.
    
    Args:
        tool_name: Nombre de la herramienta que generó el informe
        
    Returns:
        str: HTML del footer
    """
    html = f"""
        <div style="margin-top: 50px; padding-top: 20px; border-top: 2px solid #eee; text-align: center; color: #666; font-size: 12px;">
            <p>Informe generado automáticamente por {tool_name}</p>
            <p>Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>© {datetime.now().year} BÜCHI Labortechnik AG</p>
        </div>
    </body>
    </html>
    """
    return html


def start_html_template(title: str, sidebar_html: str = None, 
                        sidebar_sections: list = None, client_info: dict = None,
                        include_bootstrap: bool = False) -> str:
    """
    Inicia el documento HTML con sidebar y opcionalmente información del cliente.
    
    Args:
        title: Título del informe
        sidebar_html: HTML del sidebar ya construido (DEPRECATED, usar sidebar_sections)
        sidebar_sections: Lista de tuplas (id, label) para construir el sidebar
        client_info: Dict con información del cliente (opcional)
        include_bootstrap: Si True, incluye Bootstrap CSS/JS en el head
    
    Returns:
        str: HTML inicial del documento
    """
    # Cargar CSS
    buchi_css = load_buchi_css()
    sidebar_css = get_sidebar_styles()
    common_css = get_common_report_styles()
    
    # Construir sidebar
    if sidebar_sections is not None:
        sidebar_items = []
        for sid, label in sidebar_sections:
            sidebar_items.append(f'            <li><a href="#{sid}">{label}</a></li>')
        sidebar_content = '\n'.join(sidebar_items)
    elif sidebar_html is not None:
        sidebar_content = sidebar_html
    else:
        sidebar_content = ""
    
    # Bootstrap CDN (opcional)
    bootstrap_head = ""
    bootstrap_scripts = ""
    
    if include_bootstrap:
        bootstrap_head = """
    <!-- Bootstrap CSS -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
"""
        bootstrap_scripts = """
    <!-- Bootstrap JS -->
    <script src="https://code.jquery.com/jquery-3.5.1.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.1/dist/umd/popper.min.js"></script>
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
"""
    
    # HTML base
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
{bootstrap_head}
    <style>
{buchi_css}
{sidebar_css}
{common_css}
    </style>
</head>
<body>
{bootstrap_scripts}
    <div class="sidebar">
        <h2>📋 Índice</h2>
        <ul>
{sidebar_content}
        </ul>
    </div>
    
    <div class="main-content">
        <h1>{title}</h1>
"""
    
    # Si hay info cliente, añadir sección
    if client_info:
        html += generate_client_info_section(client_info)
    
    return html

def calculate_global_metrics(validation_data: List[Dict]) -> Dict:
    """
    Calcula métricas globales de un conjunto de validaciones.
    
    Args:
        validation_data: Lista de diccionarios con datos de validación
        
    Returns:
        Dict con métricas agregadas
    """
    corr_list = [d['validation_results']['correlation'] for d in validation_data]
    max_list = [d['validation_results']['max_diff'] for d in validation_data]
    rms_list = [d['validation_results']['rms'] for d in validation_data]
    offset_list = [d['validation_results']['mean_diff'] for d in validation_data]
    
    return {
        'corr_mean': np.mean(corr_list),
        'corr_std': np.std(corr_list),
        'corr_min': np.min(corr_list),
        'corr_max': np.max(corr_list),
        'max_mean': np.mean(max_list),
        'max_std': np.std(max_list),
        'max_min': np.min(max_list),
        'max_max': np.max(max_list),
        'rms_mean': np.mean(rms_list),
        'rms_std': np.std(rms_list),
        'rms_min': np.min(rms_list),
        'rms_max': np.max(rms_list),
        'offset_mean': np.mean(offset_list),
        'offset_std': np.std(offset_list),
        'offset_min': np.min(offset_list),
        'offset_max': np.max(offset_list),
    }

# ============================================================================
# FUNCIONES NUEVAS PARA AÑADIR AL FINAL DE report_utils.py
# ============================================================================

def generate_client_info_section(client_data: dict) -> str:
    """
    Genera sección de información del cliente (reutilizable en todos los informes).
    
    Args:
        client_data: Dict con datos del cliente
            Keys esperadas: client_name, contact_person, contact_email,
                           sensor_sn, equipment_model, technician,
                           location, date
    
    Returns:
        str: HTML de la sección de información del cliente
    """
    from datetime import datetime
    
    html = f"""
        <div class="info-box" id="info-cliente">
            <h2>Información del Cliente</h2>
            <table>
                <tr><th>Campo</th><th>Valor</th></tr>
                <tr><td><strong>Cliente</strong></td><td>{client_data.get('client_name', 'N/A')}</td></tr>
                <tr><td><strong>Contacto</strong></td><td>{client_data.get('contact_person', 'N/A')}</td></tr>
                <tr><td><strong>Email</strong></td><td>{client_data.get('contact_email', 'N/A')}</td></tr>
                <tr><td><strong>N/S Sensor</strong></td><td>{client_data.get('sensor_sn', 'N/A')}</td></tr>
                <tr><td><strong>Modelo</strong></td><td>{client_data.get('equipment_model', 'N/A')}</td></tr>
                <tr><td><strong>Técnico</strong></td><td>{client_data.get('technician', 'N/A')}</td></tr>
                <tr><td><strong>Ubicación</strong></td><td>{client_data.get('location', 'N/A')}</td></tr>
                <tr><td><strong>Fecha del Proceso</strong></td><td>{client_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</td></tr>
            </table>
        </div>
    """
    return html


def generate_notes_section(notes: str) -> str:
    """
    Genera sección de notas adicionales (reutilizable en todos los informes).
    
    Args:
        notes: Texto de las notas adicionales
        
    Returns:
        str: HTML de la sección de notas
    """
    if not notes:
        return ""
    
    html = f"""
        <div class="info-box">
            <h2>📝 Notas Adicionales</h2>
            <p>{notes}</p>
        </div>
    """
    return html


def df_to_html_table(df, float_fmt="{:.2f}", index=False) -> str:
    """
    Convierte DataFrame a tabla HTML con formato personalizado.
    
    Args:
        df: DataFrame a convertir
        float_fmt: Formato para números flotantes
        index: Si mostrar el índice
        
    Returns:
        str: HTML de la tabla
    """
    if df is None or df.empty:
        return "<p><em>Sin datos</em></p>"
    
    df_fmt = df.copy()
    
    # Formatear columnas numéricas
    for col in df_fmt.select_dtypes(include="number").columns:
        df_fmt[col] = df_fmt[col].apply(
            lambda x: float_fmt.format(x) if pd.notna(x) else ""
        )
    
    return df_fmt.to_html(index=index, classes="table", border=0)


# ============================================================================
# FUNCIÓN ADICIONAL PARA report_utils.py
# Añadir después de df_to_html_table()
# ============================================================================

def generate_evaluated_table(
    data,
    columns,
    evaluation_column=None,
    evaluation_thresholds=None,
    title=None
):
    """
    Genera tabla HTML con evaluación automática por colores según umbrales.
    
    Esta función es útil para tablas comparativas donde las filas deben
    colorearse según la magnitud de algún valor (ej: diferencias, errores, etc.)
    
    Args:
        data (list[dict]): Lista de dicts con datos de cada fila
            Ejemplo: [
                {'param': 'Proteína', 'baseline': 15.2, 'nueva': 15.8, 'delta': 3.9},
                {'param': 'Grasa', 'baseline': 3.5, 'nueva': 3.7, 'delta': 5.7}
            ]
        
        columns (list[dict]): Lista de dicts definiendo cada columna
            Cada dict debe tener:
            - 'key' (str): Clave en data dict
            - 'header' (str): Texto del encabezado
            - 'align' (str, opcional): 'left', 'center', 'right' (default: 'center')
            - 'format' (str, opcional): String format para números (ej: '{:.3f}')
            
            Ejemplo: [
                {'key': 'param', 'header': 'Parámetro', 'align': 'left'},
                {'key': 'baseline', 'header': 'Baseline', 'format': '{:.3f}'},
                {'key': 'nueva', 'header': 'Nueva', 'format': '{:.3f}'},
                {'key': 'delta', 'header': 'Δ %', 'format': '{:+.2f}%'}
            ]
        
        evaluation_column (str, optional): Nombre de la columna que determina 
            el color de la fila (se usa valor absoluto)
        
        evaluation_thresholds (dict, optional): Dict con umbrales de evaluación.
            Cada nivel debe tener 'class' y opcionalmente 'max'.
            El último nivel no debe tener 'max' (es el catch-all).
            
            Ejemplo: {
                'excellent': {'max': 2.0, 'class': 'eval-excellent'},
                'acceptable': {'max': 5.0, 'class': 'eval-acceptable'},
                'review': {'max': 10.0, 'class': 'eval-review'},
                'critical': {'class': 'eval-significant'}
            }
        
        title (str, optional): Título de la tabla
    
    Returns:
        str: HTML de la tabla con clases CSS aplicadas
    
    Example:
        >>> data = [
        ...     {'param': 'Proteína', 'ref': 15.2, 'new': 15.8, 'diff': 3.9},
        ...     {'param': 'Grasa', 'ref': 3.5, 'new': 3.4, 'diff': -2.9}
        ... ]
        >>> 
        >>> columns = [
        ...     {'key': 'param', 'header': 'Parámetro', 'align': 'left'},
        ...     {'key': 'ref', 'header': 'Referencia', 'format': '{:.1f}'},
        ...     {'key': 'new', 'header': 'Nueva', 'format': '{:.1f}'},
        ...     {'key': 'diff', 'header': 'Δ %', 'format': '{:+.1f}%'}
        ... ]
        >>> 
        >>> thresholds = {
        ...     'good': {'max': 3.0, 'class': 'eval-excellent'},
        ...     'warning': {'max': 5.0, 'class': 'eval-acceptable'},
        ...     'bad': {'class': 'eval-review'}
        ... }
        >>> 
        >>> html = generate_evaluated_table(
        ...     data, columns,
        ...     evaluation_column='diff',
        ...     evaluation_thresholds=thresholds,
        ...     title='Comparación de Resultados'
        ... )
    """
    html = '<div class="table-overflow">\n'
    
    if title:
        html += f'<h4>{title}</h4>\n'
    
    html += '<table>\n<thead>\n<tr>\n'
    
    # Generar headers
    for col in columns:
        align = col.get('align', 'center')
        header_text = col['header']
        html += f'<th style="text-align: {align};">{header_text}</th>\n'
    
    html += '</tr>\n</thead>\n<tbody>\n'
    
    # Generar filas
    for row_data in data:
        # Determinar clase CSS para la fila según evaluación
        row_class = ''
        
        if evaluation_column and evaluation_thresholds and evaluation_column in row_data:
            eval_value = abs(row_data[evaluation_column])
            
            # Iterar por los umbrales en orden
            for level_name, threshold_config in evaluation_thresholds.items():
                if 'max' in threshold_config:
                    if eval_value < threshold_config['max']:
                        row_class = threshold_config['class']
                        break
                else:
                    # Último nivel sin 'max' es el catch-all
                    row_class = threshold_config['class']
        
        html += f'<tr class="{row_class}">\n'
        
        # Generar celdas
        for col in columns:
            key = col['key']
            value = row_data.get(key, '-')
            
            # Aplicar formato si está especificado y el valor es numérico
            if 'format' in col and isinstance(value, (int, float)):
                try:
                    value = col['format'].format(value)
                except (ValueError, KeyError):
                    pass  # Mantener valor original si falla el formato
            
            align = col.get('align', 'center')
            html += f'<td style="text-align: {align};">{value}</td>\n'
        
        html += '</tr>\n'
    
    html += '</tbody>\n</table>\n</div>\n'
    
    return html
# -*- coding: utf-8 -*-
"""
Configuración de gráficos y visualizaciones
"""

# ============================================================================
# CONFIGURACIÓN DE GRÁFICOS
# ============================================================================

PLOT_CONFIG = {
    'figsize_default': (12, 6),
    'figsize_large': (12, 8),
    'figsize_report': (14, 7),
    'dpi': 150,
    'alpha_spectrum': 0.85,
    'alpha_grid': 0.3,
    'linewidth_default': 2,
    'linewidth_thin': 1,
}

# ============================================================================
# COLORES CORPORATIVOS BUCHI
# ============================================================================

BUCHI_COLORS = {
    'primary': '#093A34',
    'secondary': '#289A93',
    'accent': '#00BFA5',
    'success': '#28a745',
    'warning': '#ffc107',
    'danger': '#dc3545',
    'info': '#17a2b8',
    'light': '#f8f9fa',
    'dark': '#343a40',
    'kashmir_blue': '#4F719A',
    'sky_blue': '#4DB9D2',
    'teal_blue': '#289A93',
}

# ============================================================================
# PLANTILLA PLOTLY
# ============================================================================

PLOTLY_TEMPLATE = {
    'layout': {
        'colorway': [
            '#4F719A',  # Kashmir Blue
            '#4DB9D2',  # Sky Blue
            '#289A93',  # Teal Blue
            '#093A34',  # Primary (verde oscuro BUCHI)
            '#00BFA5',  # Accent
            '#FF6B6B',  # Rojo (contraste)
        ],
        'font': {'family': 'Segoe UI, Arial, sans-serif'},
        'plot_bgcolor': 'white',
        'paper_bgcolor': 'white',
    }
}
# -*- coding: utf-8 -*-
"""
Umbrales y criterios de validación
"""

# ============================================================================
# UMBRALES DE DIAGNÓSTICO (WSTD)
# ============================================================================

WSTD_THRESHOLDS = {
    'good': 0.015,
    'warning': 0.05,
    'bad': float('inf'),
}

DIAGNOSTIC_STATUS = {
    'good': {
        'icon': '🟢',
        'label': 'Bien ajustado',
        'color': 'green',
    },
    'warning': {
        'icon': '🟡',
        'label': 'Desviación moderada',
        'color': 'warning',
    },
    'bad': {
        'icon': '🔴',
        'label': 'Offset, ajustar a offset inicial',
        'color': 'red',
    },
}

# ============================================================================
# UMBRALES DE VALIDACIÓN
# ============================================================================

VALIDATION_THRESHOLDS = {
    'excellent': 0.001,
    'good': 0.01,
    'acceptable': 0.05,
    'bad': float('inf'),
}

VALIDATION_STATUS = {
    'excellent': {
        'icon': '✅',
        'label': 'Excelente',
        'color': 'green',
    },
    'good': {
        'icon': '✅',
        'label': 'Bueno',
        'color': 'green',
    },
    'acceptable': {
        'icon': '⚠️',
        'label': 'Aceptable',
        'color': 'warning',
    },
    'bad': {
        'icon': '❌',
        'label': 'Requiere atención',
        'color': 'red',
    },
}

# Umbral crítico para decidir si necesita alineamiento en Paso 4
VALIDATION_RMS_THRESHOLD = 0.005

WHITE_REFERENCE_THRESHOLDS = {
    'excellent': {'rms': 0.002, 'max_diff': 0.005, 'color': '#4caf50'},
    'good': {'rms': 0.005, 'max_diff': 0.01, 'color': '#8bc34a'},
    'acceptable': {'rms': 0.01, 'max_diff': 0.02, 'color': '#ffc107'},
    'review': {'color': '#f44336'},
}

DEFAULT_VALIDATION_THRESHOLDS = {
    'correlation': 0.9995,
    'max_diff': 0.015,
    'rms': 0.010,
}

CRITICAL_REGIONS = [(1100, 1200), (1400, 1500), (1600, 1700)]

OFFSET_LIMITS = {
    'negligible': 0.001,
    'acceptable': 0.005,
}
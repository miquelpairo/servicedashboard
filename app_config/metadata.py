# -*- coding: utf-8 -*-
"""
Metadatos y configuraciones por defecto
"""

# ============================================================================
# METADATOS POR DEFECTO PARA CSV
# ============================================================================

DEFAULT_CSV_METADATA = {
    'expires': '',
    'sys_temp': 35.0,
    'tec_temp': 25.0,
    'lamp_time': '0:00:00',
    'count': 1,
    'vis_avg': 32000,
    'vis_max': 65535,
    'vis_int_time': 100,
    'vis_gain': 1,
    'vis_offset': 0,
    'vis_scans': 10,
    'vis_first': 0,
    'vis_pixels': 256,
    'nir_avg': 1000.0,
    'nir_max': 4095,
    'nir_int_time': 10.0,
    'nir_gain': 1.0,
    'nir_offset': 0,
    'nir_scans': 10,
    'nir_first': 0,
    'bounds': '400.0,1000.0',
}

# ============================================================================
# CONFIGURACIÓN DE MUESTRAS DE CONTROL
# ============================================================================

CONTROL_SAMPLES_CONFIG = {
    'min_samples': 1,
    'max_samples': 50,
    'prediction_tolerance': {
        'good': 0.5,
        'warning': 2.0,
        'bad': float('inf'),
    },
}

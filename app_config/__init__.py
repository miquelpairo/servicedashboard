# -*- coding: utf-8 -*-
"""
NIR ServiceKit - Configuración Central
Re-exporta todos los módulos de configuración
"""

# Importar módulos individualmente
import app_config.app
import app_config.paths
import app_config.thresholds
import app_config.plotting
import app_config.messages
import app_config.reports
import app_config.metadata

# Re-exportar todo explícitamente
from app_config.app import PAGE_CONFIG, STEPS, VERSION, VERSION_DATE, VERSION_NOTES
from app_config.paths import BASELINE_PATHS, SUPPORTED_EXTENSIONS
from app_config.thresholds import (
    WSTD_THRESHOLDS, VALIDATION_THRESHOLDS, VALIDATION_RMS_THRESHOLD,
    WHITE_REFERENCE_THRESHOLDS, DEFAULT_VALIDATION_THRESHOLDS,
    CRITICAL_REGIONS, OFFSET_LIMITS, DIAGNOSTIC_STATUS, VALIDATION_STATUS
)
from app_config.plotting import PLOT_CONFIG, BUCHI_COLORS, PLOTLY_TEMPLATE
from app_config.messages import MESSAGES, INSTRUCTIONS, SPECIAL_IDS
from app_config.reports import REPORT_STYLE
from app_config.metadata import DEFAULT_CSV_METADATA, CONTROL_SAMPLES_CONFIG

__all__ = [
    # App
    'PAGE_CONFIG', 'STEPS', 'VERSION', 'VERSION_DATE', 'VERSION_NOTES',
    # Paths
    'BASELINE_PATHS', 'SUPPORTED_EXTENSIONS',
    # Thresholds
    'WSTD_THRESHOLDS', 'VALIDATION_THRESHOLDS', 'VALIDATION_RMS_THRESHOLD',
    'WHITE_REFERENCE_THRESHOLDS', 'DEFAULT_VALIDATION_THRESHOLDS',
    'CRITICAL_REGIONS', 'OFFSET_LIMITS', 'DIAGNOSTIC_STATUS', 'VALIDATION_STATUS',
    # Plotting
    'PLOT_CONFIG', 'BUCHI_COLORS', 'PLOTLY_TEMPLATE',
    # Messages
    'MESSAGES', 'INSTRUCTIONS', 'SPECIAL_IDS',
    # Reports
    'REPORT_STYLE',
    # Metadata
    'DEFAULT_CSV_METADATA', 'CONTROL_SAMPLES_CONFIG',
]
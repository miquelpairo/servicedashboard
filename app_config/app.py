# -*- coding: utf-8 -*-
"""
Configuración general de la aplicación
"""

# ============================================================================
# CONFIGURACIÓN DE LA PÁGINA (STREAMLIT)
# ============================================================================

PAGE_CONFIG = {
    "page_title": "NIR ServiceKit",
    "page_icon": "🏠",
    "layout": "wide",
}

# ============================================================================
# DEFINICIÓN DE PASOS DEL PROCESO
# ============================================================================

STEPS = {
    1: "Datos del cliente",
    2: "Backup de archivos",
    3: "Diagnóstico Inicial",
    4: "Validación",
    5: "Alineamiento de Baseline",
}

# ============================================================================
# INFORMACIÓN DE VERSIÓN
# ============================================================================

VERSION = "3.1.0"
VERSION_DATE = "2025-12-26"
VERSION_NOTES = """
Versión 3.1.0 - Optimización y Refactorización:
- ✅ Mensajes e instrucciones centralizados en config.py
- ✅ Eliminación de duplicación en funciones de visualización
- ✅ Arquitectura modular mejorada (plotly_utils, standards_analysis)
- ✅ CSS centralizado en buchi_streamlit_theme.py
- ✅ Gestión consistente de unsaved_changes en todos los steps
- ✅ Nomenclatura clara para funciones específicas vs genéricas
- 📊 Reducción de ~6,000 líneas de código (-33%)
- 🎨 UI consistente con estilos corporativos BUCHI
"""
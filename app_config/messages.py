# -*- coding: utf-8 -*-
"""
Mensajes de UI, instrucciones y textos
"""

# ============================================================================
# IDENTIFICADORES ESPECIALES
# ============================================================================

SPECIAL_IDS = {
    'wstd': 'WSTD',
}

# ============================================================================
# INSTRUCCIONES POR PASO (UI)
# ============================================================================

INSTRUCTIONS = {
    # CLIENT INFO
    'client_info': """
Por favor, completa los siguientes datos antes de comenzar el proceso de ajuste.
Esta información se incluirá en el informe final.
    """,

    # BACKUP
    'backup': """
### ⚠️ Medición de Referencia Pre-Mantenimiento
**Registra el estado actual del sensor antes de realizar cualquier cambio.**

El objetivo es establecer una línea base de referencia que nos permita alinear el equipo 
después del mantenimiento. Al medir el External White con el baseline actual, documentamos 
cómo está midiendo el sensor ahora, para luego ajustar las mediciones post-mantenimiento 
a este mismo estado de referencia.

**¿Por qué es importante?**
- Esta medida será tu punto de referencia para el ajuste posterior
- Sin esta referencia, no podremos calcular la corrección necesaria
- Permite mantener la continuidad en las mediciones antes y después del cambio de lámpara
    """,

    'backup_procedure': r"""
### Procedimiento para el backup:

**Objetivo:** Identificar la baseline que se usa actualmente y hacer una copia de seguridad.

1. **Localiza la carpeta de baseline según tu versión de software:**
   
   - **SX Suite ≤531**: `C:\ProgramData\NIR-Online\SX-Suite`
     - El archivo tiene un patrón de nombre: `serialnumber.lamp.date.ref` (ej: `316FG103.1.2025-11-21.ref`)
     - La posición de la lámpara: **1** indica primaria, **2** indica secundaria
     - **Copia los archivos .ref de ambas lámparas**
     - **Si no hay archivos .ref**, el equipo está trabajando sin línea base
   
   - **SX Suite ≥554**: `C:\ProgramData\NIR-Online\SX-Suite\Data\Reference`
     - El archivo tiene el nombre: `numerodeserie.baseline.lampara.csv` (ej: `316FG103.Baseline.1.csv')

2. **Haz copia de los archivos**, incluyendo el número de serie en el nombre de la carpeta (ej: `316FG103_Backup_2025-11-21`)

3. **Carga la baseline en el PC de trabajo** para continuar con el proceso

4. **Verifica que la copia se realizó correctamente**
    """,

    # WSTD - DIAGNÓSTICO INICIAL
    'wstd': """
### 📊 Registro del Estado Actual del Sensor
**Objetivo:** Documentar cómo está midiendo el sensor actualmente para usarlo como referencia.

**Procedimiento:**
1. **Comprueba qué archivo de baseline se está usando actualmente** en el equipo y cárgalo
2. **Mide una referencia blanca** (External White) con el baseline que se está usando
3. **Asigna un ID identificable** a la medición (ej: "WHITE"). Usa el mismo ID en todo el proceso
4. **Exporta el archivo TSV** con las mediciones y cárgalo
5. **Selecciona las filas correspondientes a la referencia blanca** usando los checkboxes

**¿Qué registramos?**
Las desviaciones del espectro respecto a cero representan el estado de referencia actual del sensor.
Esta medición servirá como punto de comparación para alinear el equipo tras el mantenimiento.

**IMPORTANTE:** Este archivo TSV se usará en el Paso 5 para calcular la corrección necesaria y alinear la nueva lámpara al mismo estado de referencia.
    """,

    'wstd_file_info': """
📋 **Este archivo TSV se usará como referencia en el Paso 5 (Alineamiento de Baseline)**

Asegúrate de medir con el baseline actual del equipo antes de cualquier ajuste.
    """,

    'wstd_selection_instruction': "✅ Marca las casillas de las mediciones que corresponden al White Standard.",

    'wstd_continue_warning': """
⚠️ **Debes cargar el archivo TSV de External White para continuar**

Este archivo es necesario como referencia para el alineamiento de baseline en el Paso 5.
    """,

    # VALIDATION
    'validation_objective': """
### 🎯 Objetivo
Verificar si el equipo está correctamente alineado al estado de referencia midiendo el White Standard.

**Proceso:**
1. Mide el White Standard con el baseline actual
2. Comparamos con la referencia del Paso 3
3. **Si está bien alineado** (RMS < 0.005) → Generar informe y finalizar ✅
4. **Si necesita ajuste** (RMS ≥ 0.005) → Ir al Paso 5 para alinear ⚙️
    """,

    'validation_first_measurement': """
**Primera medición:**
1. Con el baseline actual del equipo
2. Mide el MISMO White Standard del Paso 3
3. Exporta el TSV y cárgalo aquí
    """,

    'validation_success_title': """
✅ **VALIDACIÓN EXITOSA**

**White Standard ({white_id}):** RMS = {rms:.6f} < 0.005

El equipo está correctamente alineado y listo para usar.
    """,

    'validation_alignment_needed': """
⚠️ **ALINEAMIENTO NECESARIO**

**White Standard ({white_id}):** RMS = {rms:.6f} ≥ 0.005

El equipo necesita alineamiento de baseline.
    """,

    'validation_option_continue': """
**Recomendado**: Ve al Paso 5 para ajustar el baseline.

En el Paso 5 podrás:
1. Cargar el baseline actual
2. Calcular la corrección necesaria
3. Exportar el baseline corregido
4. Volver a este paso para validar
    """,

    'validation_option_force': """
⚠️ **No recomendado**: Genera el informe con el estado actual 
aunque no se cumpla el umbral de RMS < 0.002.

El informe indicará claramente que el alineamiento no fue exitoso.
    """,

    'validation_report_intro': """
El informe incluirá:
- Datos del cliente y equipo
- Métricas del White Standard
- Gráficos comparativos
- Conclusiones
    """,

    # ALIGNMENT
    'alignment_intro': """
### ⚙️ Alineamiento de Baseline

Has llegado aquí porque el RMS del White Standard es ≥ 0.005.

**En este paso:**
1. Cargas el baseline actual del equipo
2. Calculamos la corrección necesaria respecto al estado de referencia
3. Exportas el baseline corregido
4. Lo instalas en el equipo y vuelves a medir la referencia blanca
5. Vuelves al Paso 4 para validar
    """,

    'alignment_procedure': """
### 📋 Procedimiento de Alineamiento

**IMPORTANTE:** El equipo debe estar estabilizado (mínimo 30 minutos encendido) antes de comenzar.

**Pasos a seguir:**

1. **Tomar nueva baseline** en el equipo con la lámpara nueva
   - Asegúrate de que el equipo esté estabilizado (≥30 min)
   - Toma la baseline siguiendo el procedimiento normal del equipo

2. **Medir el White Standard** con la nueva baseline
   - Usa el MISMO White Standard del Paso 3
   - Asigna el mismo ID identificable (ej: "WHITE")
   - Exporta el TSV con esta medición

3. **Cargar los archivos en esta aplicación:**
   - Baseline tomada (archivo .ref o .csv)
   - TSV de referencia (Paso 3) - se carga automáticamente
   - TSV de nueva medición (que acabas de medir)

4. **Generar baseline corregido**
   - La aplicación calculará la corrección necesaria
   - Descarga el archivo baseline corregido

5. **Sustituir el baseline en el equipo:**
   - **SX Suite ≤531**: Copia el archivo .ref corregido a `C:\\ProgramData\\NIR-Online\\SX-Suite`
   - **SX Suite ≥554**: Copia el archivo .csv corregido a `C:\\ProgramData\\NIR-Online\\SX-Suite\\Data\\Reference`
   - Reemplaza el archivo baseline actual con el corregido

**Verificación:** Después de sustituir el baseline, vuelve al Paso 4 para validar el ajuste.
    """,

    'alignment_load_baseline': "### 1️⃣ Cargar Baseline Actual",
    'alignment_baseline_info': "Sube el archivo de baseline actual del equipo (.ref o .csv)",
    'alignment_validation_data': "### 2️⃣ Datos de Validación",

    'alignment_validation_error': """
❌ No hay datos de validación del Paso 4

Vuelve al Paso 4 para realizar la validación primero
    """,

    'alignment_validation_loaded': "✅ Datos de validación cargados (White ID: {white_id})",
    'alignment_apply_correction': "### 3️⃣ Aplicar Corrección al Baseline",
    'alignment_correction_applied': "✅ Corrección aplicada al baseline",

    'alignment_dimension_error': """
❌ Error de dimensiones:
- Baseline: {baseline_points} puntos
- Corrección: {correction_points} puntos
    """,

    'alignment_export': "### 4️⃣ Exportar Baseline Corregido",
    'alignment_export_ref': "**Formato .ref (binario)**",
    'alignment_export_csv': "**Formato .csv (nuevo software)**",
    'alignment_header_preserved': "✅ Cabecera original preservada",
    'alignment_metadata_preserved': "✅ Metadatos originales preservados",
    'alignment_no_header': "⚠️ No hay cabecera original (archivo no era .ref)",
    'alignment_metadata_default': "ℹ️ Usando metadatos por defecto",
    'alignment_return': "### ⬅️ Volver a Validación",

    'alignment_next_steps': """
**⚠️ PRÓXIMOS PASOS:**

1. ✅ Descarga el baseline corregido
2. ✅ Cópialo al equipo (reemplaza el anterior)
3. ✅ Reinicia SX Suite
4. ✅ Haz clic en "Volver a Validación"
5. ✅ Mide de nuevo el White Standard
    """,

    # LEGACY / OTROS
    'control_samples': """
### 🎯 Muestras de Control (Opcional)

**Objetivo:** Validar que el ajuste de baseline mejora las predicciones del equipo.

**¿Qué son muestras de control?**
Muestras reales que medirás **antes** y **después** del ajuste para comparar 
el impacto en las predicciones.
    """,

    'kit': """
### 📦 Archivos para Calcular la Corrección

**La herramienta necesita DOS archivos TSV para calcular el ajuste:**

**Archivo 1 - Referencia (estado deseado):**
- Mediciones del sensor en el estado que quieres replicar

**Archivo 2 - Estado Actual (a corregir):**
- Mediciones del sensor en su estado actual
- Debe contener las **MISMAS muestras** que el archivo de referencia
    """,

    'baseline_load': """
### 📁 Cargar Baseline Actual

**Necesitas el archivo baseline que usaste para medir el "Estado Actual" en el paso anterior.**
    """,
}

# ============================================================================
# MENSAJES DE ÉXITO/ERROR/INFO
# ============================================================================

MESSAGES = {
    # Generales
    'success_file_loaded': "✅ Archivo cargado correctamente",
    'success_dimension_match': "✅ Validación correcta: {n_points} puntos en ambos archivos",
    'success_correction_applied': "✅ Corrección aplicada al baseline",

    # Errores
    'error_no_wstd': "❌ No se encontraron mediciones con ID = 'External White' en el archivo.",
    'error_no_samples': "❌ No se encontraron mediciones de muestras (todas son WSTD).",
    'error_no_common_samples': "❌ No hay muestras comunes entre los dos archivos. Verifica que uses las mismas IDs.",
    'error_dimension_mismatch': "**Error de validación:** El baseline tiene {baseline_points} puntos, pero el TSV tiene {tsv_channels} canales. No coinciden.",
    'error_no_predictions': "❌ El archivo no contiene la columna 'Results' con las predicciones",
    'error_no_common_control': "❌ No se encontraron muestras de control comunes entre las mediciones iniciales y finales",

    # Advertencias
    'warning_no_header': "⚠️ No se puede generar .ref desde CSV: faltan valores de cabecera del sensor",
    'warning_default_metadata': "⚠️ Metadatos generados por defecto",

    # Info
    'info_two_files': "ℹ️ Proceso actualizado: ahora usamos dos archivos TSV separados para mayor flexibilidad",
    'info_control_skipped': "ℹ️ Paso de muestras de control omitido",

    # Muestras de control
    'success_control_initial': "✅ Muestras de control iniciales guardadas correctamente",
    'success_control_final': "✅ Muestras de control finales guardadas correctamente",
}

# ============================================================================
# HOME PAGE - TEXTOS Y CONFIGURACIÓN
# ============================================================================

HOME_PAGE = {
    'title': 'NIR ServiceKit',
    'subtitle': 'Análisis, calibración y validación de espectrómetros NIR',
    'version': '2.0',
    
    'description': """
**NIR ServiceKit** es un conjunto de herramientas diseñadas para el análisis, mantenimiento 
y validación de equipos NIR (Near-Infrared) con detectores dioade-array.

""",
    
    'service_tools': {
        'section_title': '🔧 Service Tools',
        'section_subtitle': 'Herramientas especializadas para mantenimiento y servicio técnico',
        
        'baseline': {
            'title': '📐 Baseline Adjustment',
            'description': 'Ajuste de baseline tras cambio de lámpara. Calcula correcciones basadas en mediciones de referencia blanca externa.',
            'features': [
                'Análisis de diferencias espectrales',
                'Cálculo automático de correcciones',
                'Corrección de forma espectral'
            ],
            'button': '🚀 Abrir Baseline Adjustment',
            'page': 'pages/1_📐_Baseline adjustment.py',
            'card_class': 'card-blue'
        },
        
        'validation': {
            'title': '🎯 Standard Validation',
            'description': 'Validación automática de estándares ópticos post-mantenimiento mediante emparejamiento por ID.',
            'features': [
                'Detección automática de IDs comunes',
                'Validación múltiple simultánea',
                'Análisis de regiones críticas',
                'Detección de offset global'
            ],
            'button': '🚀 Abrir Standard Validation',
            'page': 'pages/2_🎯_Validation_Standards.py',
            'card_class': 'card-red'
        },
        
        'offset': {
            'title': '🎚️ Offset Adjustment',
            'description': 'Ajuste fino de offset vertical al baseline preservando la forma espectral.',
            'features': [
                'Corrección de bias sistemático',
                'Simulación con estándares ópticos',
                'Visualización de impacto'
            ],
            'button': '🚀 Abrir Offset Adjustment',
            'page': 'pages/3_🎚️_Offset_Adjustment.py',
            'card_class': 'card-orange'
        }
    },
    
    'application_tools': {
        'section_title': '🧪 Application Tools',
        'section_subtitle': 'Herramientas de análisis y generación de informes',
        
        'spectrum': {
            'title': '🔍 Spectrum Comparison',
            'description': 'Comparación avanzada de múltiples espectros NIR con análisis estadístico completo.',
            'features': [
                'Overlay de espectros',
                'Análisis de residuales y correlación',
                'Agrupamiento de réplicas',
                'Modo White Reference integrado'
            ],
            'button': '🚀 Abrir Spectrum Comparison',
            'page': 'pages/4_🔍_Comparacion_Espectros.py',
            'card_class': 'card-green'
        },
        
        'predictions': {
            'title': '📊 Prediction Reports',
            'description': 'Comparación de predicciones entre lámparas usando informes <strong>XML</strong> generados desde SX Center.',
            'features': [
                'Cargar reporte XML de SX Center',
                'Comparar predicciones entre lámparas',
                'Analizar diferencias por muestra/parámetro'
            ],
            'button': '🚀 Abrir Prediction Reports',
            'page': 'pages/6_📊_Prediction_Reports.py',
            'card_class': 'card-teal'
        },
        
        'metareports': {
            'title': '📦 Report Consolidator',
            'description': 'Consolida en un <strong>metainforme</strong> único los informes de Baseline, Validación y Predicciones.',
            'features': [
                'Subir 1-3 informes (HTML/XML según módulo)',
                'Resumen ejecutivo y estado global',
                'Navegación lateral e informes embebidos'
            ],
            'button': '🚀 Abrir Report Consolidator',
            'page': 'pages/07_📦_MetaReports.py',
            'card_class': 'card-gray'
        },
        
        'tsv_validation': {
            'title': '📋 TSV Validation Reports',
            'description': 'Genera informes de validación a partir de ficheros <strong>TSV</strong> (journal) y produce un HTML interactivo.',
            'features': [
                'Cargar uno o varios TSV con predicciones y valores de referencia',
                'Limpieza y reorganización automática de datos',
                'Gráficos interactivos y estadísticas'
            ],
            'button': '🚀 Abrir TSV Validation Reports',
            'page': 'pages/08_📋_TSV_Validation_Reports.py',
            'card_class': 'card-lime'
        }
    },
    
    'workflow': {
        'title': '📋 Flujo de trabajo típico',
        'content': """
**Workflow completo de mantenimiento:**

1. **Pre-mantenimiento**: 
   - Medir y guardar referencia blanca (TSV)
   - Medir estándares ópticos certificados (TSV)

2. **Cambio de lámpara** en NIR Online
   - Warm-up 15-30 minutos

3. **Baseline Adjustment** (Corrección de forma):
   - Nueva medición de referencia blanca
   - Cálculo de corrección espectral
   - Exportar baseline corregido

4. **Standard Validation** (Detección de offset):
   - Medir mismos estándares ópticos con baseline nuevo
   - Validar correlación, RMS, Max Δ
   - **Detectar offset global del kit**

5. **Offset Adjustment** (Corrección de bias - OPCIONAL):
   - Si offset global > 0.005 AU
   - Simular impacto del offset en estándares
   - Aplicar corrección al baseline
   - Re-exportar baseline final

6. **Prediction Reports (SX Center)**:
   - Cargar informe XML con predicciones
   - Comparar resultados entre lámparas / configuraciones
   - Detectar sesgos y desviaciones por parámetro

7. **MetaReports**:
   - Consolidar Baseline + Validación + Predicciones
   - Generar un informe único con resumen ejecutivo
   - ✅ Documentación completa para cierre de servicio

8. **TSV Validation Reports**:
   - Cargar TSV(s) desde journal / export
   - Generar informes HTML interactivos (parity, residuum, histograma)
   - Exportar CSV limpio para trazabilidad

---

**Herramientas complementarias:**
- **Spectrum Comparison**: Análisis comparativo general con modo White Reference integrado
"""
    },
    
    'footer': {
        'app_name': 'NIR ServiceKit',
        'support_text': 'Para soporte técnico o consultas, contacta con el departamento de servicio.'
    }
}
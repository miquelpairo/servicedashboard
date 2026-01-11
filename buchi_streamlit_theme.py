# buchi_streamlit_theme.py

import streamlit as st


def load_shared_report_css() -> str:
    """
    Carga CSS compartido de informes HTML (para reports descargables).
    Si no existe el archivo, devuelve string vacío.
    """
    try:
        with open("buchi_report_styles.css", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def apply_buchi_styles() -> None:
    """
    Estilos BUCHI en Streamlit (sin romper nada):
    - Sidebar corporativo (fondo + tipografía)
    - Navigation section headers (Service Tools / Application Tools)
    - Botones PRIMARY verdes (global) → también en form_submit_button
    - Botones SECONDARY: default en main, pero en SIDEBAR gris oscuro para contraste con texto blanco
    - Header Streamlit intacto (Deploy/Settings/Rerun)
    - File uploader dropzone con fondo gris oscuro
    - Expander: icono blanco + estado OPEN con fondo más oscuro (sidebar)
    - (Opcional) inyecta el CSS de reports si existe, pero NO dependemos de él
    """
    shared_css = load_shared_report_css()

    st.markdown(
        f"""
        <style>
        /* ================================
           (Opcional) CSS compartido de reports
           ================================ */
        {shared_css}

        /* =========================================================
           SIDEBAR – FONDO CORPORATIVO
           ========================================================= */
        [data-testid="stSidebar"] {{
            background-color: #093A34 !important;
        }}

        /* Textos del sidebar */
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] small {{
            color: #ffffff !important;
        }}

        /* Inputs del sidebar */
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {{
            background-color: #ffffff !important;
            color: #111111 !important;
        }}

        /* =========================================================
           NAVIGATION SECTION HEADERS (st.navigation)
           Service Tools / Application Tools
           ========================================================= */
        [data-testid="stSidebar"] [data-testid="stNavSectionHeader"] {{
            color: #FFFFFF !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }}

        /* =========================================================
           LISTAS / ITEMS DENTRO DEL SIDEBAR (ul / li)
           ========================================================= */
        [data-testid="stSidebar"] ul,
        [data-testid="stSidebar"] li {{
            color: #ffffff !important;
        }}

        /* =========================================================
           BOTONES PRIMARY – VERDE BUCHI (GLOBAL)
           ========================================================= */
        button[kind="primary"],
        button[kind="primaryFormSubmit"] {{
            background-color: #64B445 !important;
            color: #ffffff !important;
            border: 1px solid #64B445 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }}

        button[kind="primary"]:hover,
        button[kind="primaryFormSubmit"]:hover {{
            background-color: #289A93 !important;
            border-color: #289A93 !important;
        }}

        /* =========================================================
           BOTONES SECONDARY – MAIN CONTENT
           → dejamos el estilo DEFAULT de Streamlit (NO TOCAR)
           ========================================================= */

        /* =========================================================
           BOTONES SECONDARY – SIDEBAR
           Gris medio oscuro para contraste con texto blanco
           ========================================================= */
        [data-testid="stSidebar"] button[kind="secondary"],
        [data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {{
            background-color: #5f6b68 !important;
            color: #ffffff !important;
            border: 1px solid #5f6b68 !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }}

        [data-testid="stSidebar"] button[kind="secondary"]:hover,
        [data-testid="stSidebar"] button[kind="secondaryFormSubmit"]:hover {{
            background-color: #4e5956 !important;
            border-color: #4e5956 !important;
        }}

        /* =========================================================
           HEADER STREAMLIT (Deploy / Settings / Rerun)
           → NO tocar estilos
           ========================================================= */
        header button,
        header [role="button"] {{
            background-color: transparent !important;
            color: inherit !important;
            border: none !important;
            box-shadow: none !important;
            padding: initial !important;
        }}

        /* =========================================================
           EXPANDER – SIDEBAR (icono + open state)
           ========================================================= */

        /* El summary (cabecera) siempre legible */
        [data-testid="stSidebar"] details > summary {{
            color: #FFFFFF !important;
        }}

        /* Por si el texto interno del summary viene en spans/divs */
        [data-testid="stSidebar"] details > summary * {{
            color: #FFFFFF !important;
        }}

        /* Chevron del expander (usa currentColor) */
        [data-testid="stSidebar"] svg[data-testid="stExpanderToggleIcon"] {{
            color: #FFFFFF !important;
            fill: currentColor !important;
        }}

        /* Cuando está ABIERTO: fondo más oscuro */
        [data-testid="stSidebar"] details[open] > summary {{
            background-color: rgba(255, 255, 255, 0.10) !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
        }}

        /* Contenido interno del expander */
        [data-testid="stSidebar"] details[open] > div {{
            background-color: rgba(255, 255, 255, 0.06) !important;
            border-radius: 8px !important;
        }}

        /* Wrapper del expander (evitar fondos raros) */
        [data-testid="stSidebar"] [data-testid="stExpander"] {{
            background-color: transparent !important;
        }}

        /* =========================================================
           FILE UPLOADER DROPZONE – SIDEBAR
           ========================================================= */
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
            background-color: #4a5f5a !important;
            border: 2px dashed rgba(255, 255, 255, 0.4) !important;
            border-radius: 8px !important;
        }}

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {{
            background-color: #5a6f6a !important;
            border-color: rgba(255, 255, 255, 0.6) !important;
        }}

        /* Texto del dropzone en blanco */
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] * {{
            color: #ffffff !important;
        }}

        /* =========================================================
           TARJETAS HOME - NIR ServiceKit
           ========================================================= */
        .card-container {{
            min-height: 400px;
            padding: 20px;
            border-radius: 10px;
            background-color: #f5f5f5;
            display: flex;
            flex-direction: column;
        }}

        .card-blue {{ border: 2px solid #1976d2; }}
        .card-red {{ border: 2px solid #d32f2f; }}
        .card-green {{ border: 2px solid #388e3c; }}
        .card-purple {{ border: 2px solid #7b1fa2; }}
        .card-orange {{ border: 2px solid #f57c00; }}
        .card-teal {{ border: 2px solid #00897b; }}
        .card-gray {{ border: 2px solid #546e7a; }}
        .card-lime {{ border: 2px solid #7CB342; }}

        .card-container h3 {{ margin-top: 0; }}
        .card-blue h3 {{ color: #1976d2; }}
        .card-red h3 {{ color: #d32f2f; }}
        .card-green h3 {{ color: #388e3c; }}
        .card-purple h3 {{ color: #7b1fa2; }}
        .card-orange h3 {{ color: #f57c00; }}
        .card-teal h3 {{ color: #00897b; }}
        .card-gray h3 {{ color: #546e7a; }}
        .card-lime h3 {{ color: #7CB342; }}

        /* =========================================================
           MULTISELECT TAGS - Gris claro con texto negro
           ========================================================= */
        /* Tags seleccionados */
        .stMultiSelect [data-baseweb="tag"] {{
            background-color: #e0e0e0 !important;
            color: #000000 !important;
        }}
        
        .stMultiSelect [data-baseweb="tag"] span {{
            color: #000000 !important;
        }}
        
        /* Botón X de cerrar tag */
        .stMultiSelect [data-baseweb="tag"] svg {{
            fill: #000000 !important;
        }}
        
        /* Hover en tags */
        .stMultiSelect [data-baseweb="tag"]:hover {{
            background-color: #d0d0d0 !important;
        }}
        
        /* =========================================================
           ENCABEZADOS GLOBALES - ESTANDARIZACIÓN
           ========================================================= */
        /* H1 - Título principal */
        h1 {{
            font-size: 2.5rem !important;
            font-weight: 700 !important;
            color: #093A34 !important;
            margin-bottom: 0.5rem !important;
        }}
        
        /* H2 - Subtítulos principales */
        h2 {{
            font-size: 1.75rem !important;
            font-weight: 600 !important;
            color: #093A34 !important;
            margin-top: 1.5rem !important;
            margin-bottom: 0.75rem !important;
        }}
        
        /* H3 - Secciones */
        h3 {{
            font-size: 1.5rem !important;
            font-weight: 600 !important;
            color: #289A93 !important;
            margin-top: 1rem !important;
            margin-bottom: 0.5rem !important;
        }}
        
        /* H4 - Subsecciones */
        h4 {{
            font-size: 1.25rem !important;
            font-weight: 500 !important;
            color: #093A34 !important;
            margin-top: 0.75rem !important;
            margin-bottom: 0.5rem !important;
        }}
        
        /* Markdown headers en main content */
        .main h1 {{
            font-size: 2.5rem !important;
            font-weight: 700 !important;
        }}
        
        .main h2 {{
            font-size: 1.75rem !important;
            font-weight: 600 !important;
        }}
        
        .main h3 {{
            font-size: 1.5rem !important;
            font-weight: 600 !important;
        }}
        
        .main h4 {{
            font-size: 1.25rem !important;
            font-weight: 500 !important;
        }}
        
        /* Headers en sidebar - sobrescribir si es necesario */
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4 {{
            color: #FFFFFF !important;
        }}
        
        </style>
        """,
        unsafe_allow_html=True,
    )
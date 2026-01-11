# -*- coding: utf-8 -*-
"""
Configuración de informes HTML
"""

# ============================================================================
# ESTILOS DE INFORMES HTML
# ============================================================================

REPORT_STYLE = """
body { font-family: Arial, sans-serif; margin: 40px; }
h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
h2 { color: #34495e; margin-top: 30px; }
h3 { color: #5a6c7d; margin-top: 20px; }
.info-box { background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 10px 0; }
.warning-box { background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #ffc107; }
.success-box { background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #28a745; }
.metric { display: inline-block; margin: 10px 20px 10px 0; }
.metric-label { font-weight: bold; color: #7f8c8d; }
.metric-value { color: #2c3e50; font-size: 1.1em; }
table { border-collapse: collapse; width: 100%; margin: 20px 0; }
th, td { border: 1px solid #bdc3c7; padding: 10px; text-align: left; }
th { background-color: #3498db; color: white; }
tr:nth-child(even) { background-color: #f2f2f2; }
.status-good { color: #28a745; font-weight: bold; }
.status-warning { color: #ffc107; font-weight: bold; }
.status-bad { color: #dc3545; font-weight: bold; }
.footer { margin-top: 50px; padding-top: 20px; border-top: 1px solid #bdc3c7; text-align: center; color: #7f8c8d; font-size: 0.9em; }
.tag { display:inline-block; padding:2px 8px; border-radius:12px; font-size:0.85em; margin: 2px; }
.tag-ok { background:#e8f5e9; color:#2e7d32; border:1px solid #c8e6c9; }
.tag-no { background:#fff3e0; color:#e65100; border:1px solid #ffe0b2; }
img { max-width: 100%; height: auto; margin: 20px 0; }
"""
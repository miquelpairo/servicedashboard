"""
Column Mappings for Multi-Format Support
Detects and maps different column naming conventions to standardized names
"""

# =============================================================================
# FORMAT DEFINITIONS
# =============================================================================

# Formato Original (con City)
ORIGINAL_FORMAT = {
    'Date': 'Date',
    'Business Partner Name': 'Business Partner Name',
    'ItemIdAndName': 'ItemIdAndName',
    'ProductType': 'ProductType',
    'Qty': 'Qty',
    'EUR': 'EUR',
    'SalesRepresentative': 'SalesRepresentative',
    'Set': 'Set',
    'Productline': 'Productline',
    'City': 'City',
    'Country': 'Country',
    'PostalCode': 'PostalCode',
    'SFDC Link': None,
    'End User Segment': None,
    'Market Organization Name': None,
}

# ⭐ Formato Nuevo REAL (tu archivo actual - SIN City)
NEW_FORMAT = {
    'Date': 'Date',
    'Business Partner Name': 'End User',
    'ItemIdAndName': 'Id - Name.1',  # ⭐ IMPORTANTE: Usar .1 para segunda columna
    'ProductType': 'Product Type',
    'Qty': 'Qty',
    'EUR': 'LC',
    'SalesRepresentative': 'Sales Representative',
    'Set': 'Set',
    'Productline': 'Product Line',
    'City': None,  # NO EXISTE
    'Country': 'Country',
    'PostalCode': 'Postal Code',
    'SFDC Link': 'SFDC Link',
    'End User Segment': 'End User Segment',
    'Market Organization Name': 'Market Organization Name',
}

# Formato Mixto (si hay casos híbridos)
MIXED_FORMAT = {
    'Date': 'Date',
    'Business Partner Name': 'End User',
    'ItemIdAndName': 'Id - Name.1',  # ⭐ Usar .1 para segunda columna
    'ProductType': 'Product Type',
    'Qty': 'Qty',
    'EUR': 'LC',
    'SalesRepresentative': 'Sales Representative',
    'Set': 'Set',
    'Productline': 'Product Line',
    'City': None,
    'Country': 'Country',
    'PostalCode': 'Postal Code',
    'SFDC Link': 'SFDC Link',
    'End User Segment': 'End User Segment',
    'Market Organization Name': 'Market Organization Name',
}

# Columnas adicionales a preservar
ADDITIONAL_COLUMNS_NEW_FORMAT = [
    'Sales Territory',
    'Segment',
    'FC',
    'CHF',
    'Document Number',
    'Position'
]

# =============================================================================
# REQUIRED COLUMNS (nombres estandarizados internos)
# =============================================================================

REQUIRED_COLUMNS = [
    'Date',
    'Business Partner Name',
    'ItemIdAndName',
    'ProductType',
    'Qty',
    'EUR',
    'SalesRepresentative',
    'Set',
    'Productline',
]

OPTIONAL_COLUMNS = [
    'City',
    'Country',
    'PostalCode',
    'SFDC Link',
    'End User Segment',
    'Market Organization Name',
]

# =============================================================================
# DETECTION FUNCTIONS
# =============================================================================

def detect_format(columns):
    """
    Detect which format the input file uses
    
    Args:
        columns (list): List of column names from the DataFrame
        
    Returns:
        str: 'original', 'new', 'mixed', or 'unknown'
    """
    columns_set = set(columns)
    
    # Columnas EXCLUSIVAS del formato NUEVO
    has_end_user = 'End User' in columns_set
    has_lc = 'LC' in columns_set
    has_product_type_space = 'Product Type' in columns_set
    has_sales_rep_space = 'Sales Representative' in columns_set
    has_postal_code = 'Postal Code' in columns_set
    # ⭐ MEJORADO: Verificar que existe Id - Name.1 (segunda columna)
    has_id_name_dot1 = 'Id - Name.1' in columns_set
    
    # Columnas EXCLUSIVAS del formato ORIGINAL
    has_business_partner = 'Business Partner Name' in columns_set
    has_eur = 'EUR' in columns_set
    has_product_type_no_space = 'ProductType' in columns_set
    has_sales_rep_no_space = 'SalesRepresentative' in columns_set
    has_city = 'City' in columns_set
    
    # LÓGICA DE DETECCIÓN
    
    # Si tiene "End User" → formato NUEVO/MIXED
    if has_end_user:
        new_score = sum([has_lc, has_product_type_space, has_sales_rep_space, has_postal_code])
        if new_score >= 3:
            return 'new'
        else:
            return 'mixed'
    
    # Si tiene "Business Partner Name" + EUR → formato ORIGINAL
    if has_business_partner and has_eur:
        original_score = sum([
            has_product_type_no_space,
            has_sales_rep_no_space,
            has_city
        ])
        if original_score >= 2:
            return 'original'
    
    # Fallback: contar matches
    new_matches = sum([has_end_user, has_lc, has_product_type_space, has_sales_rep_space])
    original_matches = sum([has_business_partner, has_eur, has_product_type_no_space, has_sales_rep_no_space])
    
    if new_matches >= 3:
        return 'new'
    elif original_matches >= 3:
        return 'original'
    
    return 'unknown'

def get_mapping_for_format(format_type):
    """
    Get the column mapping dictionary for a given format
    
    Args:
        format_type (str): 'original', 'new', or 'mixed'
        
    Returns:
        dict: Mapping from standardized names to actual column names
    """
    if format_type == 'original':
        return ORIGINAL_FORMAT
    elif format_type == 'new':
        return NEW_FORMAT
    elif format_type == 'mixed':
        return MIXED_FORMAT
    else:
        return None

def get_additional_columns(format_type):
    """
    Get list of additional columns to preserve
    
    Args:
        format_type (str): 'original', 'new', or 'mixed'
        
    Returns:
        list: List of additional column names to preserve
    """
    if format_type in ['new', 'mixed']:
        return ADDITIONAL_COLUMNS_NEW_FORMAT
    else:
        return []

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_format(df, format_type):
    """
    Validate that DataFrame has all required columns for the detected format
    
    Args:
        df (pd.DataFrame): Input DataFrame
        format_type (str): 'original', 'new', or 'mixed'
        
    Returns:
        tuple: (is_valid (bool), missing_columns (list))
    """
    mapping = get_mapping_for_format(format_type)
    if mapping is None:
        return False, []
    
    missing_columns = []
    for standard_name in REQUIRED_COLUMNS:
        actual_name = mapping.get(standard_name)
        if actual_name and actual_name not in df.columns:
            missing_columns.append(actual_name)
    
    is_valid = len(missing_columns) == 0
    return is_valid, missing_columns

def get_format_info(format_type):
    """
    Get human-readable information about a format
    
    Args:
        format_type (str): 'original', 'new', or 'mixed'
        
    Returns:
        dict: Information about the format
    """
    if format_type == 'original':
        return {
            'name': 'Original Format',
            'description': 'Export with EUR currency and City column',
            'currency': 'EUR',
            'version': 'v1.0-v2.0',
            'has_country': False,
            'has_sfdc_link': False,
            'has_segments': False,
            'has_city': True
        }
    elif format_type == 'new':
        return {
            'name': 'Multi-Currency Format',
            'description': 'Export with LC/FC/CHF and Postal Code (no City)',
            'currency': 'LC (Local Currency)',
            'version': 'v3.0+',
            'has_country': True,
            'has_sfdc_link': True,
            'has_segments': True,
            'has_city': False
        }
    elif format_type == 'mixed':
        return {
            'name': 'Current Format',
            'description': 'Export with End User, LC currency',
            'currency': 'LC (Local Currency)',
            'version': 'v3.0 (Current)',
            'has_country': True,
            'has_sfdc_link': True,
            'has_segments': True,
            'has_city': False
        }
    else:
        return {
            'name': 'Unknown Format',
            'description': 'Format not recognized',
            'currency': 'Unknown',
            'version': 'Unknown',
            'has_country': False,
            'has_sfdc_link': False,
            'has_segments': False,
            'has_city': False
        }
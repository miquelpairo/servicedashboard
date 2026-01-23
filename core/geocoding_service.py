"""
Geocoding Service Module - ADAPTED FOR NO-CITY GEOCODING
=========================================================
Handles all geocoding operations for the Service Planning Dashboard.

NEW ADAPTATIONS:
- ✅ Accepts City=None or empty string (geocodes with postal code only)
- ✅ Uses Country column from DataFrame if available
- ✅ Generates generic city names when City is missing
- ✅ Adapted cache keys for postal-only geocoding

Previous features:
- ✅ Flexible postcode matching for PT (4-digit prefix) and ES (5-digit prefix)
- ✅ Extended PT bbox to include Azores and Madeira
- ✅ Multi-country support (ES, PT, AD, GR, DE)
- ✅ Postal code cleaning and normalization
- ✅ Coordinate validation with bounding boxes
- ✅ Persistent caching system
- ✅ Statistics tracking
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import pandas as pd


# ============================================================================
# DEBUG CONFIGURATION
# ============================================================================

DEBUG_GEOCODE = False  # Set to True to enable debug prints


# ============================================================================
# CONSTANTS
# ============================================================================

# Default cache file path
DEFAULT_CACHE_FILE = "coordinates_cache.json"

# Country overrides for outliers (by postal code + city)
COUNTRY_OVERRIDES = {
    ("11635", "ATHENS"): "gr",
    ("69469", "WEINHEIM"): "de",
}

## Hardcoded coordinates for problematic postal codes
HARDCODED_COORDS = {
    # ES — casos problemáticos
    ("02071", "es"): (38.9943, -1.8564, "Albacete", "HARDCODED"),
    ("05290", "es"): (40.8910, -4.5790, "Sanchidrián", "HARDCODED"),
    ("84450", "es"): (41.6390, 2.4040, "Llinars del Vallès", "HARDCODED"),
    ("88490", "es"): (41.7000, 2.7190, "Tordera", "HARDCODED"),
    ("13000", "es"): (38.9863, -3.9291, "Ciudad Real", "HARDCODED"),
    ("15041", "es"): (43.3623, -8.4115, "A Coruña", "HARDCODED"),
    ("15071A", "es"): (43.3623, -8.4115, "A Coruña", "HARDCODED"),
    ("15071", "es"): (43.3623, -8.4115, "A Coruña", "HARDCODED"),
    ("1950256", "es"): (38.7078, -9.1366, "Lisboa", "HARDCODED"),
    ("2014", "es"): (43.3183, -1.9812, "Donostia / San Sebastián", "HARDCODED"),
    ("22234", "es"): (41.6200, 0.1900, "Ballobar", "HARDCODED"),
    ("23071", "es"): (37.7796, -3.7849, "Jaén", "HARDCODED"),
    ("2805", "es"): (38.6760, -9.1650, "Almada", "HARDCODED"),
    ("29048", "es"): (40.4168, -3.7038, "Madrid", "HARDCODED"),
    ("05644", "es"): (38.0816, -1.2550, "Lorquí", "HARDCODED"),
    ("34071", "es"): (42.0096, -4.5288, "Palencia", "HARDCODED"),
    ("36015", "es"): (42.8125, -1.6458, "Pamplona", "HARDCODED"),
    ("36154", "es"): (42.4347, -8.5760, "Bora (Pontevedra)", "HARDCODED"),
    ("36555", "es"): (42.5920, -8.3500, "Forcarei", "HARDCODED"),
    ("43080", "es"): (41.1189, 1.2445, "Tarragona", "HARDCODED"),
    ("44424", "es"): (40.1410, -0.8160, "Sarrión", "HARDCODED"),
    ("70011", "es"): (41.6523, -4.7245, "Valladolid", "HARDCODED"),
    ("47281", "es"): (41.8099, -4.6932, "Corcos del Valle", "HARDCODED"),
    ("47900", "es"): (41.6523, -4.7245, "Valladolid", "HARDCODED"),
    ("5000", "es"): (41.3006, -7.7441, "Vila Real", "HARDCODED"),
    ("50293", "es"): (41.3270, -1.7170, "Terrer", "HARDCODED"),
    ("50784", "es"): (41.3260, -0.4290, "La Zaida", "HARDCODED"),
    ("E09071", "es"): (42.3310, -3.6200, "Cardeñajimeno", "HARDCODED"),
    ("09071", "es"): (42.3310, -3.6200, "Cardeñajimeno", "HARDCODED"),
    # Swapped cases
    ("48012", "es"): (43.2630, -2.9350, "Bilbao", "HARDCODED"),
    ("17460", "es"): (42.0333, 2.8833, "Celrà", "HARDCODED"),
    ("50360", "es"): (41.1167, -1.4167, "Daroca", "HARDCODED"),
    ("01510", "es"): (42.9167, -2.6667, "Miñano (Araba)", "HARDCODED"),
    # PT
    ("3801501", "pt"): (40.6050, -8.5960, "Eixo", "HARDCODED"),
    ("4761923", "pt"): (41.4078, -8.5198, "Vila Nova de Famalicão", "HARDCODED"),
    ("9560406", "pt"): (37.7800, -25.4970, "Ilha de São Miguel", "HARDCODED"),
    ("9600049", "pt"): (37.8202, -25.5147, "Ribeira Grande", "HARDCODED"),
    ("9600217", "pt"): (37.8130, -25.5140, "Ribeira Seca (Ribeira Grande)", "HARDCODED"),
    # ES additional
    ("45508", "es"): (43.3492, -3.0850, "Zierbana", "HARDCODED"),
}

# Known outlier cities
OUTLIER_CITIES = {
    "ATHENS", "ATENAS", "ATHINA",
    "WEINHEIM",
    "BERLIN", "MUNICH", "MÜNCHEN", "FRANKFURT",
    "PARIS", "LYON", "MARSEILLE",
    "LONDON", "MANCHESTER",
    "ROMA", "MILANO", "NAPOLI"
}

# Generic city names that indicate low-quality results
GENERIC_RESULTS = {
    "LISBOA, PORTUGAL",
    "MADRID, SPAIN", 
    "BARCELONA, SPAIN",
    "PORTO, PORTUGAL"
}

# Spanish provinces by postal code prefix (01-52)
SPAIN_PROVINCES = {
    1: "Álava", 2: "Albacete", 3: "Alicante", 4: "Almería", 5: "Ávila",
    6: "Badajoz", 7: "Baleares", 8: "Barcelona", 9: "Burgos", 10: "Cáceres",
    11: "Cádiz", 12: "Castellón", 13: "Ciudad Real", 14: "Córdoba", 15: "A Coruña",
    16: "Cuenca", 17: "Girona", 18: "Granada", 19: "Guadalajara", 20: "Gipuzkoa",
    21: "Huelva", 22: "Huesca", 23: "Jaén", 24: "León", 25: "Lleida",
    26: "La Rioja", 27: "Lugo", 28: "Madrid", 29: "Málaga", 30: "Murcia",
    31: "Navarra", 32: "Ourense", 33: "Asturias", 34: "Palencia", 35: "Las Palmas",
    36: "Pontevedra", 37: "Salamanca", 38: "Santa Cruz de Tenerife", 39: "Cantabria",
    40: "Segovia", 41: "Sevilla", 42: "Soria", 43: "Tarragona", 44: "Teruel",
    45: "Toledo", 46: "Valencia", 47: "Valladolid", 48: "Bizkaia", 49: "Zamora",
    50: "Zaragoza", 51: "Ceuta", 52: "Melilla"
}

BOUNDING_BOXES = {
    "es": [
        {"lat": (35.5, 44.2), "lon": (-10.5, 5.5)},  # Peninsula
        {"lat": (27.3, 29.8), "lon": (-18.5, -13.0)},  # Canarias
        {"lat": (38.6, 40.2), "lon": (1.0, 4.6)},  # Baleares
    ],
    "pt": [
        {"lat": (36.8, 42.3), "lon": (-9.6, -6.0)},  # Continental
        {"lat": (32.0, 33.6), "lon": (-17.5, -16.0)},  # Madeira
        {"lat": (36.6, 40.0), "lon": (-32.0, -24.5)},  # Azores (extended)
    ],
    "ad": [
        {"lat": (42.4, 42.7), "lon": (1.4, 1.8)},  # Andorra
    ],
    "gr": [
        {"lat": (34.5, 41.8), "lon": (19.0, 29.8)},  # Greece
    ],
    "de": [
        {"lat": (47.2, 55.2), "lon": (5.5, 15.5)},  # Germany
    ],
}

COUNTRY_NAMES = {
    'es': ('Spain', 'es'),
    'pt': ('Portugal', 'pt'),
    'ad': ('Andorra', 'ad'),
    'gr': ('Greece', 'gr'),
    'de': ('Germany', 'de'),
}


# ============================================================================
# STATISTICS TRACKER
# ============================================================================

class GeocodingStats:
    """Track geocoding statistics for debugging and monitoring."""
    
    def __init__(self):
        self.api_calls = 0
        self.cache_hits = 0
        self.failed = 0
        self.validated = 0
        self.suspicious = 0
        self.postcode_mismatch = 0
        self.low_confidence = 0
    
    def reset(self):
        """Reset all statistics to zero."""
        self.__init__()
    
    def to_dict(self) -> Dict[str, int]:
        """Convert statistics to dictionary."""
        return {
            'api_calls': self.api_calls,
            'cache_hits': self.cache_hits,
            'failed': self.failed,
            'validated': self.validated,
            'suspicious': self.suspicious,
            'postcode_mismatch': self.postcode_mismatch,
            'low_confidence': self.low_confidence
        }
    
    def get_cache_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total = self.cache_hits + self.api_calls
        return (self.cache_hits / max(1, total)) * 100


# ============================================================================
# TRIPLET INPUT NORMALIZATION
# ============================================================================

POSTAL_LIKE_RE = re.compile(r"^\s*(\d{5}|\d{4}[-\s]?\d{3})\s*$")
COUNTRY2_RE = re.compile(r"^\s*[a-z]{2}\s*$", re.IGNORECASE)
HAS_LETTERS_RE = re.compile(r"[A-ZÁÉÍÓÚÑÜ]", re.IGNORECASE)


def normalize_triplet_inputs(postal_raw: Any, city_raw: Any, country_raw: Any) -> Tuple[Any, Any, Any, str]:
    """
    Normalize (postal, city, country) triplet.
    
    ⭐ ADAPTED: Now handles city=None or empty
    
    Returns:
        Tuple of (postal_fixed, city_fixed, country_fixed, fix_tag)
    """
    p = "" if postal_raw is None or str(postal_raw).strip() == '' else str(postal_raw).strip()
    c = "" if city_raw is None or str(city_raw).strip() == '' else str(city_raw).strip()
    k = "" if country_raw is None else str(country_raw).strip()
    
    # ⭐ Si city está vacío, no intentamos swap
    if not c:
        return postal_raw, "", country_raw, "NO_CITY"
    
    p_has_letters = bool(HAS_LETTERS_RE.search(p))
    c_looks_postal = bool(POSTAL_LIKE_RE.match(c))
    k_looks_postal = bool(POSTAL_LIKE_RE.match(k))
    
    c_is_country2 = bool(COUNTRY2_RE.match(c))
    k_is_country2 = bool(COUNTRY2_RE.match(k))
    
    # Case A) Classic swap: postal↔city
    if p_has_letters and c_looks_postal and not k_looks_postal:
        return city_raw, postal_raw, country_raw, "SWAP_POSTAL_CITY"
    
    # Case B) 3-column shift
    if p_has_letters and c_is_country2 and k_looks_postal:
        return country_raw, postal_raw, city_raw, "ROTATE_COUNTRY_HAS_POSTAL"
    
    # Case C) Variant shift
    c_has_letters = bool(HAS_LETTERS_RE.search(c))
    p_is_country2 = bool(COUNTRY2_RE.match(p))
    
    if c_has_letters and k_looks_postal and p_is_country2:
        return country_raw, city_raw, postal_raw, "ROTATE_POSTAL_IS_COUNTRY"
    
    return postal_raw, city_raw, country_raw, "OK"


# ============================================================================
# FLEXIBLE POSTAL CODE MATCHING
# ============================================================================

def _extract_digits(s: str) -> str:
    """Extract only digits from a string."""
    return re.sub(r"\D+", "", s or "")


def postcodes_match(requested: str, returned: str, country: str) -> bool:
    """
    Flexible postal code matching with country-specific rules.
    
    Rules:
    - Empty returned postcode: Accept
    - PT: Accept if first 4 digits match
    - ES: Accept if first 5 digits match
    - Exact match: Always accept
    """
    req = _extract_digits(requested)
    ret = _extract_digits(returned)
    
    if not ret:
        return True
    
    if req and ret == req:
        return True
    
    if country.lower() == "pt":
        if len(req) >= 4 and len(ret) >= 4 and ret[:4] == req[:4]:
            return True
    
    if country.lower() == "es":
        if len(req) >= 5 and len(ret) >= 5 and ret[:5] == req[:5]:
            return True
    
    return False


# ============================================================================
# POSTAL CODE CLEANING AND NORMALIZATION
# ============================================================================

def extract_postal_clean(postal_code: Any) -> str:
    """Extract a clean postal code from dirty strings."""
    if postal_code is None or str(postal_code).strip() == '' or str(postal_code).lower() == 'nan':
        return ""

    s = str(postal_code).strip().upper()

    # PT patterns
    m = re.search(r"\b(\d{4})[\s-]?(\d{3})\b", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # ES patterns
    m = re.search(r"\b(\d{5})\b", s)
    if m:
        return m.group(1)

    # ES dirty 6 digits
    m = re.search(r"\b(\d{6})\b", s)
    if m:
        six = m.group(1)
        if six.startswith("0"):
            return six[1:]
        return six[-5:]

    return s


def normalize_text(text: Any) -> str:
    """Normalize text for consistent cache keys."""
    if not text or str(text).strip() == '' or str(text).lower() == 'nan':
        return ""
    
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.upper()
    
    return text


def normalize_postal_code(postal_code: Any) -> str:
    """Normalize postal code for cache key."""
    if not postal_code or str(postal_code).strip() == '' or str(postal_code).lower() == 'nan':
        return ""
    
    postal = str(postal_code).strip().upper()
    postal = re.sub(r'[\s-]+', '', postal)
    
    return postal


def is_incomplete_postal(postal_code: str, country_code: str) -> bool:
    """Check if postal code is incomplete."""
    if not postal_code:
        return True
    
    if country_code == 'es':
        return not re.match(r'^\d{5}$', postal_code)
    
    if country_code == 'pt':
        if re.match(r'^\d{7}$', postal_code):
            return False
        return not re.match(r'^\d{4}-\d{3}$', postal_code)
    
    if country_code == 'ad':
        return not re.match(r'^AD[- ]?\d{3}$', postal_code)
    
    return False


def normalize_portugal_postal(postal_code: str) -> str:
    """Normalize Portuguese postal code."""
    if re.match(r'^\d{7}$', postal_code):
        return f"{postal_code[:4]}-{postal_code[4:]}"
    return postal_code


def is_generic_result(display_name: str, resolved_city: str) -> bool:
    """Check if geocoding result is too generic."""
    if not display_name or not resolved_city:
        return False
    
    display_upper = display_name.upper().strip()
    for generic in GENERIC_RESULTS:
        if display_upper == generic or display_upper.endswith(f", {generic}"):
            return True
    
    parts = [p.strip() for p in display_name.split(',')]
    if len(parts) <= 2:
        return True
    
    return False


# ============================================================================
# COUNTRY DETECTION
# ============================================================================

def detect_country_from_postal(postal_code: Any, city: Optional[str] = None) -> str:
    """Detect country code from postal code format."""
    postal_clean = extract_postal_clean(postal_code)
    city_norm = normalize_text(city) if city else ""
    
    if city_norm in OUTLIER_CITIES:
        return 'other'
    
    forced = COUNTRY_OVERRIDES.get((postal_clean, city_norm))
    if forced:
        return forced
    
    if re.match(r'^\d{4}-\d{3}$', postal_clean) or re.match(r'^\d{7}$', postal_clean):
        return 'pt'
    
    if re.match(r'^AD[- ]?\d{3}$', postal_clean):
        return 'ad'
    
    if re.match(r'^\d{5}$', postal_clean):
        return 'es'
    
    return 'es'


# ============================================================================
# COORDINATE VALIDATION
# ============================================================================

def validate_coordinates(lat: Optional[float], lon: Optional[float], 
                        country_code: str) -> bool:
    """Validate if coordinates are within expected boundaries."""
    if lat is None or lon is None:
        return False

    if country_code not in BOUNDING_BOXES:
        return True

    for bb in BOUNDING_BOXES[country_code]:
        if bb["lat"][0] <= lat <= bb["lat"][1] and bb["lon"][0] <= lon <= bb["lon"][1]:
            return True

    return False


# ============================================================================
# UNIFIED CACHE KEY HELPER
# ============================================================================

def build_cache_key(postal_raw: Any, city_raw: Any, country_raw: str) -> str:
    """
    Build unified cache key.
    
    ⭐ ADAPTED: Handles city=None or empty
    """
    # Triplet normalization
    postal_raw, city_raw, country_raw, fix_tag = normalize_triplet_inputs(postal_raw, city_raw, country_raw)
    
    # Normalize country
    country_raw = (str(country_raw).strip().lower() if country_raw is not None else "es")
    
    # Clean postal code
    postal_clean = extract_postal_clean(postal_raw)
    
    # Normalize Portugal postal
    if country_raw == 'pt':
        postal_clean = normalize_portugal_postal(postal_clean)
    
    # Normalize for cache key
    postal_norm = normalize_postal_code(postal_clean)
    
    # Check if incomplete
    is_incomplete = is_incomplete_postal(postal_clean, country_raw)
    
    # ⭐ ADAPTED: Si no hay city, usar solo postal + country
    if not postal_norm or is_incomplete:
        if city_raw and str(city_raw).strip():
            city_hash = abs(hash(normalize_text(city_raw))) % 1000000
            return f"incomplete_{city_hash}_{country_raw}"
        else:
            # Sin city, usar hash del postal incompleto
            postal_hash = abs(hash(postal_clean)) % 1000000
            return f"incomplete_{postal_hash}_{country_raw}"
    else:
        return f"{postal_norm}_{country_raw}"


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

def load_cache_from_file(cache_file: str = DEFAULT_CACHE_FILE) -> Dict[str, Any]:
    """Load geocoding cache from JSON file."""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                return cache
        except Exception as e:
            print(f"⚠️ Could not load cache file: {e}")
            return {}
    return {}


def save_cache_to_file(cache_dict: Dict[str, Any], 
                       cache_file: str = DEFAULT_CACHE_FILE) -> bool:
    """Save geocoding cache to JSON file."""
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Could not save cache file: {e}")
        return False


# ============================================================================
# GEOCODING SERVICE
# ============================================================================

class GeocodingService:
    """
    Geocoding service with postal-first strategy.
    
    ⭐ ADAPTED: Now handles City=None or empty string
    """
    
    def __init__(self, cache_file: str = DEFAULT_CACHE_FILE):
        """Initialize geocoding service."""
        self.cache_file = cache_file
        self.cache = load_cache_from_file(cache_file)
        self.stats = GeocodingStats()
        
        self._geolocator = Nominatim(
            user_agent="service_planning_dashboard",
            timeout=10
        )
        self._geocode = RateLimiter(
            self._geolocator.geocode, 
            min_delay_seconds=1,
            max_retries=2,
            error_wait_seconds=2.0
        )
        
        self.new_coords_added = 0
    
    def geocode_location(self, postal_code: Any, city: Optional[str] = None, 
                        country_code: str = 'es') -> Optional[Tuple[float, float]]:
        """
        Geocode a location using POSTAL-FIRST strategy.
        
        ⭐ ADAPTED: city can be None or empty string
        
        Args:
            postal_code: Postal code (can be dirty)
            city: City name (can be None or empty)
            country_code: Country code (es, pt, ad, gr, de)
        
        Returns:
            Tuple of (latitude, longitude) or None if failed
        """
        # ⭐ Normalize city to empty string if None
        if city is None or str(city).strip() == '':
            city = ""
        
        # Triplet normalization
        postal_code, city, country_code, fix_tag = normalize_triplet_inputs(postal_code, city, country_code)
        
        if DEBUG_GEOCODE and fix_tag != "OK" and fix_tag != "NO_CITY":
            print(f"[INPUT_FIX:{fix_tag}] postal={postal_code}, city={city}, country={country_code}")
        
        # Normalize country_code
        country_code = (str(country_code).strip().lower() if country_code is not None else "es")
        
        # Clean postal code
        postal_clean = extract_postal_clean(postal_code)
        
        if country_code == 'pt':
            postal_clean = normalize_portugal_postal(postal_clean)
        
        postal_norm = normalize_postal_code(postal_clean)
        
        if DEBUG_GEOCODE:
            print(
                "[DEBUG] raw_postal=", postal_code,
                "city=", city if city else "(empty)",
                "country=", country_code,
                "postal_clean=", postal_clean,
                "postal_norm=", postal_norm
            )
        
        is_incomplete = is_incomplete_postal(postal_clean, country_code)
        
        # Check HARDCODED_COORDS
        hardcoded_key = (postal_norm, country_code)
        
        if hardcoded_key in HARDCODED_COORDS:
            lat, lon, resolved_city, status = HARDCODED_COORDS[hardcoded_key]
            coords = (lat, lon)
            
            metadata = {
                'coords': coords,
                'country': country_code,
                'input_city': city if city else "",
                'input_postal': postal_code,
                'resolved_city': resolved_city,
                'display_name': f"{resolved_city}, {country_code.upper()}",
                'query_used': f"HARDCODED: {hardcoded_key}",
                'validated': validate_coordinates(lat, lon, country_code),
                'low_confidence': False,
                'is_generic': False,
                'status': status,
                'suspect_score': 0,
                'timestamp': datetime.now().isoformat()
            }
            
            cache_key = build_cache_key(postal_code, city, country_code)
            self.cache[cache_key] = metadata
            self.new_coords_added += 1
            self.stats.validated += 1
            
            return coords
        
        # Build cache key
        cache_key = build_cache_key(postal_code, city, country_code)
        
        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            self.stats.cache_hits += 1
            
            if cached is None:
                return None
            elif isinstance(cached, dict):
                return cached.get('coords')
            return None
        
        # Not in cache, geocode
        self.stats.api_calls += 1
        
        # Normal countries (es, pt, ad, gr, de)
        country_name, cc = COUNTRY_NAMES.get(country_code, ('Spain', 'es'))
        
        # ⭐ ADAPTED: Queries sin city
        try:
            if country_code == 'pt':
                queries = [
                    (f"{postal_clean}, {country_name}", cc, False),
                    ({"postalcode": postal_clean, "country": country_name}, cc, False),
                    (f"{postal_clean}", cc, False),
                ]
            elif country_code == 'es':
                province_name = None
                if len(postal_clean) >= 2:
                    try:
                        input_province_code = int(postal_clean[:2])
                        province_name = SPAIN_PROVINCES.get(input_province_code, None)
                    except:
                        pass
                
                queries = [
                    ({"postalcode": postal_clean, "country": country_name}, cc, False),
                    (f"{postal_clean}, {country_name}", cc, False),
                    (f"{postal_clean}", cc, False),
                ]
            else:
                queries = [
                    ({"postalcode": postal_clean, "country": country_name}, cc, False),
                    (f"{postal_clean}, {country_name}", cc, False),
                    (f"{postal_clean}", cc, False),
                ]
            
            location = None
            used_query = None
            low_confidence = False
            
            # Initialize variables
            returned_postcode = ""
            returned_postcode_clean = ""
            returned_postcode_norm = ""
            returned_country = ""
            resolved_city = ""
            
            for query, country_codes, is_low_conf in queries:
                if query is None:
                    continue
                
                # Geocode
                if isinstance(query, dict):
                    location = self._geocode(query, country_codes=country_codes, 
                                            addressdetails=True)
                    query_str = f"structured: {query}"
                else:
                    location = self._geocode(query, country_codes=country_codes, 
                                            addressdetails=True)
                    query_str = f"free-text: {query}"
                
                if location:
                    address = location.raw.get("address", {}) or {}

                    returned_postcode = address.get("postcode", "") or ""
                    returned_country = address.get("country_code", "") or ""

                    ret_digits = _extract_digits(returned_postcode)
                    req_digits = _extract_digits(postal_clean)

                    returned_postcode_clean = extract_postal_clean(returned_postcode)
                    returned_postcode_norm = normalize_postal_code(returned_postcode_clean)

                    resolved_city = (
                        address.get("city") or
                        address.get("town") or
                        address.get("village") or
                        address.get("municipality") or
                        ""
                    )

                    # Postcode validation
                    has_any_postcode_info = bool(ret_digits)

                    if has_any_postcode_info:
                        if not postcodes_match(postal_clean, returned_postcode, country_code):
                            if country_code == 'es':
                                try:
                                    if len(req_digits) >= 2 and len(ret_digits) >= 2:
                                        if int(req_digits[:2]) != int(ret_digits[:2]):
                                            self.stats.postcode_mismatch += 1
                                            location = None
                                            continue
                                        else:
                                            low_confidence = True
                                    else:
                                        self.stats.postcode_mismatch += 1
                                        location = None
                                        continue
                                except:
                                    self.stats.postcode_mismatch += 1
                                    location = None
                                    continue
                            else:
                                self.stats.postcode_mismatch += 1
                                location = None
                                continue
                    else:
                        # No postcode returned
                        coords_tmp = (location.latitude, location.longitude)
                        bbox_valid = validate_coordinates(coords_tmp[0], coords_tmp[1], country_code)
                        if not bbox_valid:
                            location = None
                            continue
                        low_confidence = True
                    
                    # Generic result check
                    if is_generic_result(location.address, resolved_city):
                        coords_tmp = (location.latitude, location.longitude)
                        bbox_valid = validate_coordinates(coords_tmp[0], coords_tmp[1], country_code)
                        
                        if bbox_valid:
                            low_confidence = True
                        else:
                            location = None
                            continue
                    
                    used_query = f"{query_str} (country={country_codes})"
                    
                    if is_low_conf:
                        low_confidence = True
                    
                    if low_confidence:
                        self.stats.low_confidence += 1
                    
                    break
            
            if location:
                coords = (location.latitude, location.longitude)
                
                is_valid = validate_coordinates(coords[0], coords[1], country_code)
                
                if not is_valid:
                    self.stats.suspicious += 1
                else:
                    self.stats.validated += 1
                
                is_generic = is_generic_result(location.address, resolved_city)
                
                if low_confidence:
                    status = 'OK_LOW_CONFIDENCE'
                elif is_generic:
                    status = 'OK_GENERIC'
                else:
                    status = 'OK'
                
                suspect_score = 1 if low_confidence else 0
                
                metadata = {
                    'coords': coords,
                    'country': country_code,
                    'input_city': city if city else "",
                    'input_postal': postal_code,
                    'resolved_city': resolved_city,
                    'display_name': location.address,
                    'query_used': used_query,
                    'validated': is_valid,
                    'low_confidence': low_confidence,
                    'is_generic': is_generic,
                    'status': status,
                    'suspect_score': suspect_score,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.cache[cache_key] = metadata
                self.new_coords_added += 1
                return coords
            
            # Failed
            self.stats.failed += 1
            self.cache[cache_key] = {
                'coords': None,
                'country': country_code,
                'input_city': city if city else "",
                'input_postal': postal_code,
                'resolved_city': None,
                'display_name': None,
                'query_used': f"Failed after trying {len(queries)} queries",
                'validated': False,
                'low_confidence': False,
                'status': 'FAILED_META',
                'timestamp': datetime.now().isoformat()
            }
            return None
        
        except Exception as e:
            self.stats.failed += 1
            self.cache[cache_key] = {
                'coords': None,
                'country': country_code,
                'input_city': city if city else "",
                'input_postal': postal_code,
                'resolved_city': None,
                'display_name': None,
                'query_used': f"Exception: {str(e)}",
                'validated': False,
                'low_confidence': False,
                'status': 'FAILED_EXCEPTION',
                'timestamp': datetime.now().isoformat()
            }
            return None
    
    def save_cache(self) -> bool:
        """Save current cache to file."""
        return save_cache_to_file(self.cache, self.cache_file)
    
    def clear_cache(self) -> bool:
        """Clear all cache."""
        self.cache = {}
        self.new_coords_added = 0
        
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                return True
            except Exception as e:
                print(f"❌ Could not remove cache file: {e}")
                return False
        return True
    
    def clear_failed_by_country(self, country_code: str) -> bool:
        """Clear failed geocoding attempts for a specific country."""
        self.cache = {
            k: v for k, v in self.cache.items()
            if not (k.endswith(f"_{country_code}") and 
                   isinstance(v, dict) and 
                   v.get('coords') is None)
        }
        return self.save_cache()
    
    def get_failed_entries(self) -> list:
        """Get list of failed geocoding attempts."""
        failed_entries = []
        for key, value in self.cache.items():
            if isinstance(value, dict) and value.get('coords') is None:
                parts = key.split('_')
                if len(parts) >= 2:
                    country = parts[-1]
                    postal = '_'.join(parts[:-1])
                    
                    failed_entries.append({
                        'PostalCode': postal,
                        'Country': country,
                        'Input City': value.get('input_city', 'N/A'),
                        'Query Used': value.get('query_used', 'N/A'),
                        'Timestamp': value.get('timestamp', 'N/A')
                    })
        
        return failed_entries


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def geocode_dataframe(df, postal_col: str, city_col: str, country_col: str,
                     geocoding_service: GeocodingService,
                     show_progress: bool = True):
    """
    Geocode a DataFrame with postal codes.
    
    ⭐ ADAPTED: Handles city_col that may be empty or None
    """
    unique_postals = df[[postal_col, city_col, country_col]].drop_duplicates()
    
    postals_to_geocode = []
    for idx, row in unique_postals.iterrows():
        # ⭐ Handle empty city
        city_val = row[city_col] if city_col in row and pd.notna(row[city_col]) else ""
        
        postal_fixed, city_fixed, country_fixed, fix_tag = normalize_triplet_inputs(
            row[postal_col], city_val, row[country_col]
        )
        
        cache_key = build_cache_key(postal_fixed, city_fixed, country_fixed)
        
        if cache_key not in geocoding_service.cache:
            postals_to_geocode.append((idx, row))
    
    # Geocode missing ones
    if postals_to_geocode and show_progress:
        try:
            import streamlit as st
            progress_bar = st.progress(0)
            
            for progress_idx, (idx, row) in enumerate(postals_to_geocode):
                city_val = row[city_col] if city_col in row and pd.notna(row[city_col]) else ""
                
                postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
                    row[postal_col], city_val, row[country_col]
                )
                
                geocoding_service.geocode_location(
                    postal_fixed,
                    city_fixed,
                    country_fixed
                )
                progress_bar.progress((progress_idx + 1) / len(postals_to_geocode))
            
            progress_bar.empty()
        except ImportError:
            for idx, row in postals_to_geocode:
                city_val = row[city_col] if city_col in row and pd.notna(row[city_col]) else ""
                
                postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
                    row[postal_col], city_val, row[country_col]
                )
                
                geocoding_service.geocode_location(
                    postal_fixed,
                    city_fixed,
                    country_fixed
                )
    elif postals_to_geocode:
        for idx, row in postals_to_geocode:
            city_val = row[city_col] if city_col in row and pd.notna(row[city_col]) else ""
            
            postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
                row[postal_col], city_val, row[country_col]
            )
            
            geocoding_service.geocode_location(
                postal_fixed,
                city_fixed,
                country_fixed
            )
    
    # Build results
    coords_list = []
    resolved_city_list = []
    
    for idx, row in df.iterrows():
        city_val = row[city_col] if city_col in row and pd.notna(row[city_col]) else ""
        
        postal_fixed, city_fixed, country_fixed, _ = normalize_triplet_inputs(
            row[postal_col], city_val, row[country_col]
        )
        
        cache_key = build_cache_key(postal_fixed, city_fixed, country_fixed)
        
        cached = geocoding_service.cache.get(cache_key)
        
        if cached is None:
            coords_list.append((None, None))
            resolved_city_list.append(None)
        elif isinstance(cached, dict):
            coords = cached.get('coords', (None, None))
            coords_list.append(coords)
            resolved_city_list.append(
                cached.get('resolved_city') or 
                cached.get('input_city') or 
                city_fixed or
                "Unknown"
            )
        else:
            coords_list.append((None, None))
            resolved_city_list.append(None)
    
    df['Coordinates'] = coords_list
    df['ResolvedCity'] = resolved_city_list
    df['Latitude'] = df['Coordinates'].apply(
        lambda x: x[0] if x and x[0] is not None else None
    )
    df['Longitude'] = df['Coordinates'].apply(
        lambda x: x[1] if x and x[1] is not None else None
    )
    
    return df
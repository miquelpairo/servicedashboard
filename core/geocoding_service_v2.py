"""
Geocoding Service Module - BACKWARD COMPAT + NO-CITY SUPPORT
===========================================================

- ✅ City can be None / empty (postal-only geocoding)
- ✅ Uses Country column if available (handled in app)
- ✅ Backward compatible cache keys (postal_norm + _country for complete postals)
- ✅ Flexible postcode matching (PT 4-digit, ES 5-digit)
- ✅ Hardcoded coords supported
- ✅ Bounding-box validation + suspicious flagging
- ✅ Persistent JSON cache
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


# =============================================================================
# DEBUG
# =============================================================================

DEBUG_GEOCODE = False


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_CACHE_FILE = "coordinates_cache.json"

# Overrides (city-specific) + fallback (postal-only)
COUNTRY_OVERRIDES_CITY = {
    ("11635", "ATHENS"): "gr",
    ("69469", "WEINHEIM"): "de",
}
COUNTRY_OVERRIDES_POSTAL = {
    "11635": "gr",
    "69469": "de",
}

HARDCODED_COORDS = {
    # ES examples
    ("02071", "es"): (38.9943, -1.8564, "Albacete", "HARDCODED"),
    ("05290", "es"): (40.8910, -4.5790, "Sanchidrián", "HARDCODED"),
    ("45508", "es"): (43.3492, -3.0850, "Zierbana", "HARDCODED"),
    ("E09071", "es"): (42.3310, -3.6200, "Cardeñajimeno", "HARDCODED"),
    ("09071", "es"): (42.3310, -3.6200, "Cardeñajimeno", "HARDCODED"),
    # PT examples
    ("3801501", "pt"): (40.6050, -8.5960, "Eixo", "HARDCODED"),
    ("4761923", "pt"): (41.4078, -8.5198, "Vila Nova de Famalicão", "HARDCODED"),
    ("9560406", "pt"): (37.7800, -25.4970, "Ilha de São Miguel", "HARDCODED"),
    ("9600049", "pt"): (37.8202, -25.5147, "Ribeira Grande", "HARDCODED"),
    ("9600217", "pt"): (37.8130, -25.5140, "Ribeira Seca (Ribeira Grande)", "HARDCODED"),
}

GENERIC_RESULTS = {
    "LISBOA, PORTUGAL",
    "MADRID, SPAIN",
    "BARCELONA, SPAIN",
    "PORTO, PORTUGAL",
}

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
        {"lat": (35.5, 44.2), "lon": (-10.5, 5.5)},
        {"lat": (27.3, 29.8), "lon": (-18.5, -13.0)},
        {"lat": (38.6, 40.2), "lon": (1.0, 4.6)},
    ],
    "pt": [
        {"lat": (36.8, 42.3), "lon": (-9.6, -6.0)},
        {"lat": (32.0, 33.6), "lon": (-17.5, -16.0)},
        {"lat": (36.6, 40.0), "lon": (-32.0, -24.5)},
    ],
    "ad": [{"lat": (42.4, 42.7), "lon": (1.4, 1.8)}],
    "gr": [{"lat": (34.5, 41.8), "lon": (19.0, 29.8)}],
    "de": [{"lat": (47.2, 55.2), "lon": (5.5, 15.5)}],
}

COUNTRY_NAMES = {
    'es': ('Spain', 'es'),
    'pt': ('Portugal', 'pt'),
    'ad': ('Andorra', 'ad'),
    'gr': ('Greece', 'gr'),
    'de': ('Germany', 'de'),
}


# =============================================================================
# STATS
# =============================================================================

class GeocodingStats:
    def __init__(self):
        self.api_calls = 0
        self.cache_hits = 0
        self.failed = 0
        self.validated = 0
        self.suspicious = 0
        self.postcode_mismatch = 0
        self.low_confidence = 0

    def reset(self):
        self.__init__()

    def get_cache_rate(self) -> float:
        total = self.cache_hits + self.api_calls
        return (self.cache_hits / max(1, total)) * 100


# =============================================================================
# NORMALIZATION HELPERS
# =============================================================================

POSTAL_LIKE_RE = re.compile(r"^\s*(\d{5}|\d{4}[-\s]?\d{3}|AD[-\s]?\d{3})\s*$", re.IGNORECASE)
COUNTRY2_RE = re.compile(r"^\s*[a-z]{2}\s*$", re.IGNORECASE)
HAS_LETTERS_RE = re.compile(r"[A-ZÁÉÍÓÚÑÜ]", re.IGNORECASE)


def _s(x: Any) -> str:
    if x is None:
        return ""
    t = str(x).strip()
    if not t or t.lower() == "nan":
        return ""
    return t


def normalize_text(text: Any) -> str:
    t = _s(text)
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t).upper()
    return t


def _extract_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def extract_postal_clean(postal_code: Any) -> str:
    s = _s(postal_code).upper()
    if not s:
        return ""

    # PT
    m = re.search(r"\b(\d{4})[\s-]?(\d{3})\b", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # AD
    m = re.search(r"\bAD[\s-]?(\d{3})\b", s, flags=re.IGNORECASE)
    if m:
        return f"AD{m.group(1)}"

    # ES
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


def normalize_postal_code(postal_code: Any) -> str:
    p = _s(postal_code).upper()
    if not p:
        return ""
    return re.sub(r"[\s-]+", "", p)


def normalize_portugal_postal(postal_code: str) -> str:
    if re.match(r"^\d{7}$", postal_code):
        return f"{postal_code[:4]}-{postal_code[4:]}"
    return postal_code


def is_incomplete_postal(postal_clean: str, country_code: str) -> bool:
    if not postal_clean:
        return True
    if country_code == 'es':
        return not re.match(r'^\d{5}$', postal_clean)
    if country_code == 'pt':
        if re.match(r'^\d{7}$', postal_clean):
            return False
        return not re.match(r'^\d{4}-\d{3}$', postal_clean)
    if country_code == 'ad':
        return not re.match(r'^AD\d{3}$', postal_clean)
    return False


def postcodes_match(requested: str, returned: str, country: str) -> bool:
    req = _extract_digits(requested)
    ret = _extract_digits(returned)

    if not ret:
        return True
    if req and ret == req:
        return True

    country = (country or "").lower()
    if country == "pt":
        return len(req) >= 4 and len(ret) >= 4 and ret[:4] == req[:4]
    if country == "es":
        return len(req) >= 5 and len(ret) >= 5 and ret[:5] == req[:5]
    return False


def is_generic_result(display_name: str, resolved_city: str) -> bool:
    if not display_name:
        return False
    dn = normalize_text(display_name)
    if dn in GENERIC_RESULTS:
        return True
    parts = [p.strip() for p in display_name.split(",") if p.strip()]
    # muy corto = genérico
    if len(parts) <= 2 and not normalize_text(resolved_city):
        return True
    return False


# =============================================================================
# TRIPLET NORMALIZATION (SWAP/ROTATE) - BACKWARD COMPAT
# =============================================================================

def normalize_triplet_inputs(postal_raw: Any, city_raw: Any, country_raw: Any) -> Tuple[Any, Any, Any, str]:
    """
    Normalize (postal, city, country) triplet and fix typical column shifts.

    IMPORTANT:
    - If city is empty -> NO_CITY (do not attempt swap/rotate)
    - Backward compatible behaviour for classic swaps
    """
    p = _s(postal_raw)
    c = _s(city_raw)
    k = _s(country_raw)

    if not c:
        return postal_raw, "", country_raw, "NO_CITY"

    p_has_letters = bool(HAS_LETTERS_RE.search(p))
    c_looks_postal = bool(POSTAL_LIKE_RE.match(c))
    k_looks_postal = bool(POSTAL_LIKE_RE.match(k))

    c_is_country2 = bool(COUNTRY2_RE.match(c))
    k_is_country2 = bool(COUNTRY2_RE.match(k))

    # Swap postal<->city
    if p_has_letters and c_looks_postal and not k_looks_postal:
        return city_raw, postal_raw, country_raw, "SWAP_POSTAL_CITY"

    # Rotate 3-col shift
    if p_has_letters and c_is_country2 and k_looks_postal:
        return country_raw, postal_raw, city_raw, "ROTATE_COUNTRY_HAS_POSTAL"

    c_has_letters = bool(HAS_LETTERS_RE.search(c))
    p_is_country2 = bool(COUNTRY2_RE.match(p))
    if c_has_letters and k_looks_postal and p_is_country2:
        return country_raw, city_raw, postal_raw, "ROTATE_POSTAL_IS_COUNTRY"

    return postal_raw, city_raw, country_raw, "OK"


# =============================================================================
# COUNTRY DETECTION (BACKWARD COMPAT, NO 'other')
# =============================================================================

def detect_country_from_postal(postal_code: Any, city: Optional[str] = None) -> str:
    postal_clean = extract_postal_clean(postal_code)
    city_norm = normalize_text(city)

    # city-specific overrides
    forced = COUNTRY_OVERRIDES_CITY.get((postal_clean, city_norm))
    if forced:
        return forced

    # postal-only overrides (works when city missing)
    forced2 = COUNTRY_OVERRIDES_POSTAL.get(postal_clean)
    if forced2:
        return forced2

    if re.match(r'^\d{4}-\d{3}$', postal_clean) or re.match(r'^\d{7}$', postal_clean):
        return 'pt'
    if re.match(r'^AD\d{3}$', postal_clean):
        return 'ad'
    if re.match(r'^\d{5}$', postal_clean):
        return 'es'

    return 'es'


# =============================================================================
# COORD VALIDATION
# =============================================================================

def validate_coordinates(lat: Optional[float], lon: Optional[float], country_code: str) -> bool:
    if lat is None or lon is None:
        return False
    if country_code not in BOUNDING_BOXES:
        return True
    for bb in BOUNDING_BOXES[country_code]:
        if bb["lat"][0] <= lat <= bb["lat"][1] and bb["lon"][0] <= lon <= bb["lon"][1]:
            return True
    return False


# =============================================================================
# CACHE KEY (STABLE + BACKWARD COMPAT)
# =============================================================================

def build_cache_key(postal_raw: Any, city_raw: Any, country_raw: Any) -> str:
    postal_raw, city_raw, country_raw, _ = normalize_triplet_inputs(postal_raw, city_raw, country_raw)

    country = (_s(country_raw) or "es").lower()

    postal_clean = extract_postal_clean(postal_raw)
    if country == "pt":
        postal_clean = normalize_portugal_postal(postal_clean)

    postal_norm = normalize_postal_code(postal_clean)
    incomplete = is_incomplete_postal(postal_clean, country)

    # Complete postal: keep classic key (postal_norm_country)
    if postal_norm and not incomplete:
        return f"{postal_norm}_{country}"

    # Incomplete: use hash, prefer city if present (legacy-safe)
    if _s(city_raw):
        city_hash = abs(hash(normalize_text(city_raw))) % 1_000_000
        return f"incomplete_city_{city_hash}_{country}"

    postal_hash = abs(hash(postal_clean or _s(postal_raw))) % 1_000_000
    return f"incomplete_postal_{postal_hash}_{country}"


# =============================================================================
# CACHE IO
# =============================================================================

def load_cache_from_file(cache_file: str = DEFAULT_CACHE_FILE) -> Dict[str, Any]:
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache_to_file(cache_dict: Dict[str, Any], cache_file: str = DEFAULT_CACHE_FILE) -> bool:
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# =============================================================================
# SERVICE
# =============================================================================

class GeocodingService:
    def __init__(self, cache_file: str = DEFAULT_CACHE_FILE):
        self.cache_file = cache_file
        self.cache: Dict[str, Any] = load_cache_from_file(cache_file)
        self.stats = GeocodingStats()
        self.new_coords_added = 0

        self._geolocator = Nominatim(user_agent="service_planning_dashboard", timeout=10)
        self._geocode = RateLimiter(
            self._geolocator.geocode,
            min_delay_seconds=1,
            max_retries=2,
            error_wait_seconds=2.0
        )

    def save_cache(self) -> bool:
        return save_cache_to_file(self.cache, self.cache_file)

    def clear_cache(self) -> bool:
        self.cache = {}
        self.new_coords_added = 0
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except Exception:
                return False
        return True

    def clear_failed_by_country(self, country_code: str) -> bool:
        cc = (country_code or "").lower()
        self.cache = {
            k: v for k, v in self.cache.items()
            if not (k.endswith(f"_{cc}") and isinstance(v, dict) and v.get("coords") is None)
        }
        return self.save_cache()

    def get_failed_entries(self) -> list:
        failed = []
        for key, value in self.cache.items():
            if isinstance(value, dict) and value.get("coords") is None:
                parts = key.split("_")
                country = parts[-1] if parts else ""
                failed.append({
                    "CacheKey": key,
                    "Country": country,
                    "Input City": value.get("input_city", ""),
                    "Input Postal": value.get("input_postal", ""),
                    "Query Used": value.get("query_used", ""),
                    "Timestamp": value.get("timestamp", ""),
                })
        return failed

    def geocode_location(self, postal_code: Any, city: Optional[str] = None, country_code: str = "es") -> Optional[Tuple[float, float]]:
        city = _s(city)
        postal_code, city, country_code, fix_tag = normalize_triplet_inputs(postal_code, city, country_code)

        country_code = (_s(country_code) or "es").lower()

        postal_clean = extract_postal_clean(postal_code)
        if country_code == "pt":
            postal_clean = normalize_portugal_postal(postal_clean)
        postal_norm = normalize_postal_code(postal_clean)

        if DEBUG_GEOCODE and fix_tag not in ("OK", "NO_CITY"):
            print(f"[INPUT_FIX:{fix_tag}] postal={postal_code}, city={city}, country={country_code}")

        # 1) Hardcoded
        hardcoded_key = (postal_norm, country_code)
        if hardcoded_key in HARDCODED_COORDS:
            lat, lon, resolved_city, status = HARDCODED_COORDS[hardcoded_key]
            coords = (lat, lon)
            cache_key = build_cache_key(postal_code, city, country_code)
            self.cache[cache_key] = {
                "coords": coords,
                "country": country_code,
                "input_city": city,
                "input_postal": postal_code,
                "resolved_city": resolved_city,
                "display_name": f"{resolved_city}, {country_code.upper()}",
                "query_used": f"HARDCODED: {hardcoded_key}",
                "validated": validate_coordinates(lat, lon, country_code),
                "low_confidence": False,
                "is_generic": False,
                "status": status,
                "suspect_score": 0,
                "timestamp": datetime.now().isoformat(),
            }
            self.new_coords_added += 1
            self.stats.validated += 1
            return coords

        # 2) Cache
        cache_key = build_cache_key(postal_code, city, country_code)
        if cache_key in self.cache:
            self.stats.cache_hits += 1
            cached = self.cache.get(cache_key)
            if cached is None:
                return None
            if isinstance(cached, dict):
                return cached.get("coords")
            return None

        # 3) API
        self.stats.api_calls += 1
        country_name, cc = COUNTRY_NAMES.get(country_code, ("Spain", "es"))

        try:
            queries: List[Tuple[Any, str]] = []

            # Structured tends to be best
            queries.append(({"postalcode": postal_clean, "country": country_name}, cc))
            queries.append((f"{postal_clean}, {country_name}", cc))
            queries.append((f"{postal_clean}", cc))

            location = None
            used_query = None
            low_confidence = False
            resolved_city = ""
            returned_postcode = ""

            for query, ccode in queries:
                if isinstance(query, dict):
                    location = self._geocode(query, country_codes=ccode, addressdetails=True)
                    qstr = f"structured: {query}"
                else:
                    location = self._geocode(query, country_codes=ccode, addressdetails=True)
                    qstr = f"free-text: {query}"

                if not location:
                    continue

                address = (location.raw or {}).get("address", {}) or {}
                returned_postcode = address.get("postcode", "") or ""
                resolved_city = (
                    address.get("city")
                    or address.get("town")
                    or address.get("village")
                    or address.get("municipality")
                    or ""
                )

                # postcode check
                if _extract_digits(returned_postcode):
                    if not postcodes_match(postal_clean, returned_postcode, country_code):
                        # ES: allow same province as low confidence
                        if country_code == "es":
                            req = _extract_digits(postal_clean)
                            ret = _extract_digits(returned_postcode)
                            if len(req) >= 2 and len(ret) >= 2 and req[:2] == ret[:2]:
                                low_confidence = True
                            else:
                                self.stats.postcode_mismatch += 1
                                location = None
                                continue
                        else:
                            self.stats.postcode_mismatch += 1
                            location = None
                            continue
                else:
                    # no postcode returned -> bbox validation
                    if not validate_coordinates(location.latitude, location.longitude, country_code):
                        location = None
                        continue
                    low_confidence = True

                # generic result check
                if is_generic_result(location.address, resolved_city):
                    if validate_coordinates(location.latitude, location.longitude, country_code):
                        low_confidence = True
                    else:
                        location = None
                        continue

                used_query = f"{qstr} (country={ccode})"
                break

            if location:
                coords = (location.latitude, location.longitude)
                is_valid = validate_coordinates(coords[0], coords[1], country_code)

                if is_valid:
                    self.stats.validated += 1
                else:
                    self.stats.suspicious += 1

                if low_confidence:
                    self.stats.low_confidence += 1

                metadata = {
                    "coords": coords,
                    "country": country_code,
                    "input_city": city,
                    "input_postal": postal_code,
                    "resolved_city": resolved_city,
                    "display_name": location.address,
                    "query_used": used_query,
                    "validated": is_valid,
                    "low_confidence": low_confidence,
                    "is_generic": is_generic_result(location.address, resolved_city),
                    "status": "OK_LOW_CONFIDENCE" if low_confidence else "OK",
                    "suspect_score": 1 if low_confidence else 0,
                    "timestamp": datetime.now().isoformat(),
                }

                self.cache[cache_key] = metadata
                self.new_coords_added += 1
                return coords

            # Failed
            self.stats.failed += 1
            self.cache[cache_key] = {
                "coords": None,
                "country": country_code,
                "input_city": city,
                "input_postal": postal_code,
                "resolved_city": None,
                "display_name": None,
                "query_used": f"Failed after trying {len(queries)} queries",
                "validated": False,
                "low_confidence": False,
                "status": "FAILED_META",
                "timestamp": datetime.now().isoformat(),
            }
            return None

        except Exception as e:
            self.stats.failed += 1
            self.cache[cache_key] = {
                "coords": None,
                "country": country_code,
                "input_city": city,
                "input_postal": postal_code,
                "resolved_city": None,
                "display_name": None,
                "query_used": f"Exception: {str(e)}",
                "validated": False,
                "low_confidence": False,
                "status": "FAILED_EXCEPTION",
                "timestamp": datetime.now().isoformat(),
            }
            return None

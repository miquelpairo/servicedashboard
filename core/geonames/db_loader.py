"""
GeoNames Postal Code Database Loader
=====================================
Loads and queries the GeoNames postal code database for geocoding.

Database source: https://download.geonames.org/export/zip/
"""

import pandas as pd
import os
from typing import Optional, Dict, Tuple


class GeoNamesDB:
    """
    GeoNames postal code database loader and query interface.
    
    Provides fast O(1) lookup of coordinates by postal code + country.
    """
    
    def __init__(self, db_path: str = "core/geonames/postal_codes_db.csv"):
        """
        Initialize GeoNames database.
        
        Args:
            db_path: Path to the postal codes database CSV file
        """
        self.db_path = db_path
        self.df = None
        self.lookup = {}
        self.loaded = False
        
        # Try to load database
        self._load_database()
    
    def _load_database(self):
        """Load the GeoNames database into memory."""
        if not os.path.exists(self.db_path):
            print(f"⚠️ GeoNames database not found at: {self.db_path}")
            print("   Download from: https://download.geonames.org/export/zip/allCountries.zip")
            return
        
        try:
            print(f"📂 Loading GeoNames database from {self.db_path}...")
            
            # Column names for GeoNames postal code database
            column_names = [
                'country_code',
                'postal_code',
                'place_name',
                'admin_name1',
                'admin_code1',
                'admin_name2',
                'admin_code2',
                'admin_name3',
                'admin_code3',
                'latitude',
                'longitude',
                'accuracy'
            ]
            
            # Load database (tab-separated)
            self.df = pd.read_csv(
                self.db_path,
                sep='\t',
                header=None,
                names=column_names,
                dtype={
                    'country_code': str,
                    'postal_code': str,
                    'place_name': str,
                    'admin_name1': str,
                    'admin_code1': str,
                    'admin_name2': str,
                    'admin_code2': str,
                    'admin_name3': str,
                    'admin_code3': str,
                    'latitude': float,
                    'longitude': float,
                    'accuracy': float
                },
                low_memory=False
            )
            
            print(f"✅ Loaded {len(self.df):,} records from database")
            
            # ⭐ OPTIMIZACIÓN: Preparar datos antes del loop
            print("🔨 Building lookup index (this may take a minute)...")
            
            # Normalizar columnas de una vez (vectorizado = RÁPIDO)
            self.df['postal_normalized'] = (
                self.df['postal_code']
                .astype(str)
                .str.strip()
                .str.upper()
                .str.replace(' ', '_', regex=False)  # ⭐ Normalizar espacios
            )
            
            self.df['country_normalized'] = (
                self.df['country_code']
                .astype(str)
                .str.strip()
                .str.upper()
            )
            
            # Crear keys de una vez
            self.df['lookup_key'] = (
                self.df['postal_normalized'] + '_' + self.df['country_normalized']
            )
            
            # ⭐ OPCIÓN 1: Si quieres el PRIMERO de cada postal (más rápido)
            # Elimina duplicados quedándote con la primera aparición
            df_unique = self.df.drop_duplicates(subset=['lookup_key'], keep='first')
            
            # Construir lookup dictionary con itertuples (100x más rápido que iterrows)
            for row in df_unique.itertuples(index=False):
                self.lookup[row.lookup_key] = {
                    'coords': (row.latitude, row.longitude),
                    'lat': row.latitude,
                    'lon': row.longitude,
                    'city': row.place_name,
                    'admin1': row.admin_name1,
                    'admin2': row.admin_name2,
                    'accuracy': row.accuracy,
                    'country': row.country_normalized,
                    'source': 'geonames'
                }
            
            # ⭐ OPCIÓN 2 (ALTERNATIVA): Si quieres el de MEJOR accuracy
            # Descomenta esto y comenta el bloque de arriba
            """
            # Ordenar por accuracy descendente
            df_sorted = self.df.sort_values('accuracy', ascending=False)
            
            # Quedarse con el de mejor accuracy por key
            df_unique = df_sorted.drop_duplicates(subset=['lookup_key'], keep='first')
            
            # Construir lookup
            for row in df_unique.itertuples(index=False):
                self.lookup[row.lookup_key] = {
                    'coords': (row.latitude, row.longitude),
                    'lat': row.latitude,
                    'lon': row.longitude,
                    'city': row.place_name,
                    'admin1': row.admin_name1,
                    'admin2': row.admin_name2,
                    'accuracy': row.accuracy,
                    'country': row.country_normalized,
                    'source': 'geonames'
                }
            """
            
            self.loaded = True
            print(f"✅ GeoNames database ready:")
            print(f"   📊 Total records: {len(self.df):,}")
            print(f"   🗺️ Unique locations: {len(self.lookup):,}")
            print(f"   🌍 Countries: {self.df['country_code'].nunique()}")
            
        except Exception as e:
            print(f"❌ Error loading GeoNames database: {e}")
            import traceback
            traceback.print_exc()
            self.loaded = False
    
    def get_coords(self, postal_code: str, country_code: str) -> Optional[Dict]:
        """
        Get coordinates for a postal code + country.
        
        Args:
            postal_code: Postal code (should be already normalized from caller)
            country_code: 2-letter ISO country code (uppercase)
        
        Returns:
            Dictionary with coords, city, admin info, or None if not found
        """
        if not self.loaded:
            return None
        
        # ⭐ ASUMIR que viene normalizado desde el caller
        # Solo hacer el .replace(' ', '_') final por consistencia
        key = f"{postal_code}_{country_code}"
        
        return self.lookup.get(key)
    
    def get_coords_batch(self, postal_country_pairs: list) -> Dict[str, Optional[Dict]]:
        """
        Get coordinates for multiple postal codes in one operation (VECTORIZED).
        
        Args:
            postal_country_pairs: List of tuples [(postal1, country1), (postal2, country2), ...]
        
        Returns:
            Dictionary mapping cache_key -> result dict (or None if not found)
        
        Example:
            pairs = [("08001", "ES"), ("1000-001", "PT"), ("SW1A 1AA", "GB")]
            results = db.get_coords_batch(pairs)
            # results = {
            #     "08001_ES": {...coords, city...},
            #     "1000-001_PT": {...coords, city...},
            #     "SW1A_1AA_GB": None  # not found
            # }
        """
        if not self.loaded:
            return {}
        
        results = {}
        
        # Construir keys para todas las búsquedas
        for postal, country in postal_country_pairs:
            postal_clean = str(postal).strip().upper().replace(' ', '_')
            country_clean = str(country).strip().upper()
            key = f"{postal_clean}_{country_clean}"
            
            # Lookup directo en el diccionario (O(1) por key)
            results[key] = self.lookup.get(key)
        
        return results

    
    def search_by_place_name(self, place_name: str, country_code: str, limit: int = 10) -> list:
        """
        Search for postal codes by place name.
        
        Args:
            place_name: City/town name to search
            country_code: 2-letter ISO country code
            limit: Maximum number of results
        
        Returns:
            List of matching records
        """
        if not self.loaded:
            return []
        
        country_clean = str(country_code).strip().upper()
        place_clean = str(place_name).strip().lower()
        
        matches = self.df[
            (self.df['country_code'] == country_clean) &
            (self.df['place_name'].str.lower().str.contains(place_clean, na=False))
        ].head(limit)
        
        return matches.to_dict('records')
    
    def get_stats(self) -> Dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary with stats about the loaded database
        """
        if not self.loaded:
            return {
                'loaded': False,
                'total_records': 0,
                'unique_postal_codes': 0,
                'countries': 0
            }
        
        return {
            'loaded': True,
            'total_records': len(self.df),
            'unique_postal_codes': len(self.lookup),
            'countries': self.df['country_code'].nunique()
        }
"""
Postal Code Correction Manager
===============================
Manages postal code corrections for geocoding accuracy.

Supports:
- Client-specific corrections (by Business Partner Name)
- Pattern-based corrections (regex)
- Global replacements (known errors)
"""

import json
import os
import re
from typing import Tuple, Optional, Dict
from datetime import datetime


class PostalCorrectionManager:
    """
    Manages postal code corrections from a JSON file.
    
    Corrections are applied in order:
    1. Client-specific corrections
    2. Pattern-based corrections
    3. Global replacements
    """
    
    def __init__(self, corrections_file: str = "core/postal_corrections.json"):
        """
        Initialize correction manager.
        
        Args:
            corrections_file: Path to corrections JSON file
        """
        self.corrections_file = corrections_file
        self.corrections = {
            'metadata': {},
            'by_client_id': {},
            'by_postal_pattern': {},
            'global_replacements': {}
        }
        
        # Load corrections from file
        self._load_corrections()
    
    def _load_corrections(self):
        """Load corrections from JSON file."""
        if os.path.exists(self.corrections_file):
            try:
                with open(self.corrections_file, 'r', encoding='utf-8') as f:
                    self.corrections = json.load(f)
                print(f"✅ Loaded postal corrections from {self.corrections_file}")
            except Exception as e:
                print(f"⚠️ Could not load corrections: {e}")
                # Initialize with default structure
                self._init_default_corrections()
        else:
            print(f"ℹ️ No corrections file found, using defaults")
            self._init_default_corrections()
    
    def _init_default_corrections(self):
        """Initialize with default correction structure."""
        self.corrections = {
            'metadata': {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'description': 'Postal code corrections for geocoding'
            },
            'by_client_id': {},
            'by_postal_pattern': {
                # Remove leading 'E' from Spanish postal codes
                '^E0(\\d{4})$': {
                    'replacement': '0\\1',
                    'countries': ['es'],
                    'description': 'Remove leading E from Spanish postal codes'
                },
                # Portuguese 7-digit format
                '^(\\d{7})$': {
                    'replacement': '\\1',
                    'countries': ['pt'],
                    'description': 'Portuguese 7-digit format is valid'
                }
            },
            'global_replacements': {
                # Common OCR errors
                '70011': {
                    'corrected': '47011',
                    'country': 'es',
                    'reason': 'Common OCR error - Valladolid'
                },
                '84450': {
                    'corrected': '08450',
                    'country': 'es',
                    'reason': 'Llinars del Vallès - leading digit error'
                }
            }
        }
    
    def get_corrected_postal(self, client_id: str, postal_code: str, country_code: str) -> Tuple[str, Optional[str]]:
        """
        Get corrected postal code.
        
        Args:
            client_id: Business Partner Name (for client-specific corrections)
            postal_code: Original postal code
            country_code: Country code (lowercase)
        
        Returns:
            Tuple of (corrected_postal, correction_reason)
        """
        postal_original = str(postal_code).strip()
        country = str(country_code).strip().lower()
        
        # 1. Check client-specific corrections
        if client_id and client_id in self.corrections['by_client_id']:
            client_corrections = self.corrections['by_client_id'][client_id]
            if client_corrections.get('original_postal') == postal_original:
                if client_corrections.get('country', '').lower() == country:
                    return (
                        client_corrections['corrected_postal'],
                        f"client_specific: {client_corrections.get('notes', 'N/A')}"
                    )
        
        # 2. Apply pattern-based corrections
        for pattern, config in self.corrections['by_postal_pattern'].items():
            if country in config.get('countries', []):
                match = re.match(pattern, postal_original)
                if match:
                    corrected = re.sub(pattern, config['replacement'], postal_original)
                    if corrected != postal_original:
                        return (
                            corrected,
                            f"pattern: {config.get('description', pattern)}"
                        )
        
        # 3. Apply global replacements
        if postal_original in self.corrections['global_replacements']:
            replacement = self.corrections['global_replacements'][postal_original]
            if replacement.get('country', '').lower() == country:
                return (
                    replacement['corrected'],
                    f"global: {replacement.get('reason', 'N/A')}"
                )
        
        # No correction needed
        return (postal_original, None)
    
    def add_client_correction(self, client_id: str, original_postal: str, 
                             corrected_postal: str, country: str, notes: str = ""):
        """
        Add a client-specific correction.
        
        Args:
            client_id: Business Partner Name
            original_postal: Original postal code
            corrected_postal: Corrected postal code
            country: Country code
            notes: Optional notes about the correction
        """
        self.corrections['by_client_id'][client_id] = {
            'original_postal': original_postal,
            'corrected_postal': corrected_postal,
            'country': country.lower(),
            'notes': notes,
            'corrected_by': 'manual',
            'corrected_date': datetime.now().isoformat()
        }
        
        self._save_corrections()
    
    def add_global_replacement(self, original_postal: str, corrected_postal: str, 
                               country: str, reason: str = ""):
        """
        Add a global replacement.
        
        Args:
            original_postal: Original postal code
            corrected_postal: Corrected postal code
            country: Country code
            reason: Reason for the correction
        """
        self.corrections['global_replacements'][original_postal] = {
            'corrected': corrected_postal,
            'country': country.lower(),
            'reason': reason,
            'added_date': datetime.now().isoformat()
        }
        
        self._save_corrections()
    
    def remove_client_correction(self, client_id: str):
        """
        Remove a client-specific correction.
        
        Args:
            client_id: Business Partner Name
        """
        if client_id in self.corrections['by_client_id']:
            del self.corrections['by_client_id'][client_id]
            self._save_corrections()
    
    def _save_corrections(self):
        """Save corrections to JSON file."""
        try:
            # Update metadata
            self.corrections['metadata']['last_updated'] = datetime.now().isoformat()
            
            with open(self.corrections_file, 'w', encoding='utf-8') as f:
                json.dump(self.corrections, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Saved corrections to {self.corrections_file}")
        except Exception as e:
            print(f"❌ Could not save corrections: {e}")
    
    def get_corrections_summary(self) -> Dict:
        """
        Get summary of loaded corrections.
        
        Returns:
            Dictionary with counts of each correction type
        """
        return {
            'client_specific': len(self.corrections['by_client_id']),
            'patterns': len(self.corrections['by_postal_pattern']),
            'global_replacements': len(self.corrections['global_replacements'])
        }
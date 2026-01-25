"""
Account URL Linker Module
Manages URL mapping for customer accounts in reports using fuzzy matching.

✅ Backwards-compatible with your current integration:
- Class name: AccountLinker
- Methods kept: load_mapping, get_url_exact, get_url_fuzzy, get_url, has_url,
  get_html_link, enrich_dataframe, get_stats, get_match_report, export_match_log
- Singleton helpers kept: get_default_linker, set_default_mapping

NEW (your requirement):
- If df already contains a link column (e.g. 'SFDC Link' / 'AccountURL'), use it and SKIP matching.
- Fallback: if no link present, do NOT attempt fuzzy matching (no link).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from rapidfuzz import fuzz, process

# =============================================================================
# NORMALIZATION HELPERS
# =============================================================================

_LEGAL_SUFFIXES = {
    "SA", "S A", "S.A", "S.A.",
    "SL", "S L", "S.L", "S.L.",
    "SRL", "S R L", "S.R.L", "S.R.L.",
    "SAS", "S A S", "S.A.S", "S.A.S.",
    "BV", "B V", "B.V", "B.V.",
    "NV", "N V", "N.V", "N.V.",
    "AG", "GMBH", "LTD", "LIMITED", "INC", "INC.", "LLC", "PLC",
}

_STOPWORDS = {
    "THE", "GROUP", "HOLDING", "HOLDINGS",
}


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _normalize_name(s: str) -> str:
    """
    Normalizes an account name to improve matching stability.
    - remove accents
    - uppercase
    - replace & -> AND
    - strip punctuation
    - collapse spaces
    - remove trailing legal suffixes (SA/SL/...)
    - remove some stopwords (conservative)
    """
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""

    s = _strip_accents(s)
    s = s.upper()
    s = s.replace("&", " AND ")

    # punctuation -> spaces
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # remove stopwords
    tokens = [t for t in s.split() if t not in _STOPWORDS]

    # remove trailing legal suffix tokens (one or more)
    while tokens:
        tail = tokens[-1]
        if tail in _LEGAL_SUFFIXES:
            tokens = tokens[:-1]
            continue
        if len(tokens) >= 2 and f"{tokens[-2]} {tokens[-1]}" in _LEGAL_SUFFIXES:
            tokens = tokens[:-2]
            continue
        break

    return " ".join(tokens).strip()


def _compact_key(s: str) -> str:
    """Compact key: normalized name without spaces (handles VIDRAFOC vs VIDRA FOC)."""
    return _normalize_name(s).replace(" ", "")


def _safe_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

# =============================================================================
# HARD-CODED OVERRIDES (manual fixes)
# =============================================================================

ACCOUNT_OVERRIDES: Dict[str, str] = {
    # "VIDRAFoc": "https://...",
}

# =============================================================================
# MAIN CLASS
# =============================================================================

class AccountLinker:
    """
    Maps customer/account names to their CRM URLs using exact + fuzzy matching.

    Loads from Excel/CSV with columns:
    - "Account Name", "Account URL"
    (also supports AccountName / AccountURL)
    """

    def __init__(self, mapping_file: Optional[str] = None, min_score: int = 85, debug: bool = False):
        self.min_score = int(min_score)
        self.debug = bool(debug)

        # normalized_key -> url (includes normal + compact keys)
        self.url_map: Dict[str, str] = {}
        # normalized_key -> original_name (from mapping file)
        self.original_names: Dict[str, str] = {}

        self.stats: Dict[str, int] = {
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "no_matches": 0,
            "total_queries": 0,
        }

        self.match_log: List[Dict[str, Any]] = []

        # Persistent cache
        self.cache_file: Optional[str] = None
        self.match_cache: Dict[str, Dict[str, Any]] = {}

        # hardcoded overrides (normalized_key -> url)
        self.overrides: Dict[str, str] = {
            _normalize_name(k): v for k, v in ACCOUNT_OVERRIDES.items()
            if k and v
        }
        self.overrides.update({
            _compact_key(k): v for k, v in ACCOUNT_OVERRIDES.items()
            if k and v
        })

        if mapping_file:
            self.load_mapping(mapping_file)

    # -------------------------------------------------------------------------
    # Loading
    # -------------------------------------------------------------------------
    def load_mapping(self, filepath: str) -> None:
        try:
            if filepath.lower().endswith(".csv"):
                df = pd.read_csv(filepath, encoding="utf-8")
            else:
                df = pd.read_excel(filepath)

            if "Account Name" in df.columns and "Account URL" in df.columns:
                name_col, url_col = "Account Name", "Account URL"
            elif "AccountName" in df.columns and "AccountURL" in df.columns:
                name_col, url_col = "AccountName", "AccountURL"
            else:
                raise ValueError(
                    "Mapping file must contain columns: 'Account Name' and 'Account URL' "
                    "(or 'AccountName' and 'AccountURL'). "
                    f"Found: {df.columns.tolist()}"
                )

            self.url_map.clear()
            self.original_names.clear()

            for _, row in df.iterrows():
                name = row.get(name_col)
                url = row.get(url_col)

                if pd.isna(name) or pd.isna(url):
                    continue

                name_str = str(name).strip()
                url_str = str(url).strip()
                if not name_str or not url_str:
                    continue

                key = _normalize_name(name_str)
                if not key:
                    continue

                key_compact = key.replace(" ", "")

                if key not in self.url_map:
                    self.url_map[key] = url_str
                    self.original_names[key] = name_str

                if key_compact and key_compact not in self.url_map:
                    self.url_map[key_compact] = url_str
                    self.original_names[key_compact] = name_str

            print(f"✅ Loaded {len(self.url_map)} account URL mappings (min_score={self.min_score})")

        except Exception as e:
            print(f"⚠️ Could not load account mapping: {e}")
            self.url_map = {}
            self.original_names = {}

    # -------------------------------------------------------------------------
    # Cache persistence
    # -------------------------------------------------------------------------
    def load_cache(self, cache_filepath: str) -> bool:
        self.cache_file = cache_filepath
        try:
            if not cache_filepath or not os.path.exists(cache_filepath):
                self.match_cache = {}
                return False

            with open(cache_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                self.match_cache = data
                return True

            self.match_cache = {}
            return False

        except Exception:
            self.match_cache = {}
            return False

    def save_cache(self, cache_filepath: Optional[str] = None) -> bool:
        path = cache_filepath or self.cache_file
        if not path:
            return False

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.match_cache, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Matching
    # -------------------------------------------------------------------------
    def get_url_exact(self, account_name: str) -> Optional[str]:
        if not account_name or pd.isna(account_name):
            return None

        key = _normalize_name(str(account_name))
        if not key:
            return None

        url = self.url_map.get(key)
        if url:
            return url

        key_compact = key.replace(" ", "")
        return self.url_map.get(key_compact)

    def _fuzzy_candidates(
        self,
        account_name: str,
        top_n: int = 5,
        scorer=fuzz.token_set_ratio,
    ) -> List[Tuple[str, float, int]]:
        key_query = _normalize_name(account_name)
        if not key_query or not self.url_map:
            return []

        key_query_compact = key_query.replace(" ", "")
        choices = list(self.url_map.keys())

        r1 = process.extract(key_query, choices, scorer=scorer, limit=top_n)
        r2 = process.extract(key_query_compact, choices, scorer=scorer, limit=top_n)

        combined = r1 + r2
        combined.sort(key=lambda x: x[1], reverse=True)

        seen = set()
        out: List[Tuple[str, float, int]] = []
        for k, sc, idx in combined:
            if k in seen:
                continue
            seen.add(k)
            out.append((k, sc, idx))
            if len(out) >= top_n:
                break
        return out

    def _cache_key_for_input(self, account_name: str) -> str:
        return _normalize_name(account_name)

    def get_url_fuzzy(self, account_name: str, top_n: int = 5) -> Optional[Tuple[str, int, str]]:
        if not account_name or pd.isna(account_name):
            return None

        self.stats["total_queries"] += 1
        account_str = str(account_name).strip()
        norm = _normalize_name(account_str)
        comp = _compact_key(account_str)

        # 1) overrides
        override_url = self.overrides.get(norm) or self.overrides.get(comp)
        if override_url:
            self.stats["exact_matches"] += 1
            if self.debug:
                self.match_log.append({
                    "input": account_str,
                    "input_norm": norm,
                    "match_type": "override",
                    "matched_key": norm,
                    "matched_name": account_str,
                    "score": 100,
                    "url": override_url,
                })

            cache_key = self._cache_key_for_input(account_str)
            self.match_cache[cache_key] = {
                "status": "MATCHED",
                "url": override_url,
                "score": 100,
                "matched_name": account_str,
                "source": "override",
            }
            return (override_url, 100, account_str)

        # 2) cache
        cache_key = self._cache_key_for_input(account_str)
        cached = self.match_cache.get(cache_key)
        if cached is None and comp:
            cached = self.match_cache.get(comp)

        if isinstance(cached, dict):
            status = cached.get("status")
            if status == "MATCHED" and cached.get("url"):
                self.stats["exact_matches"] += 1
                if self.debug:
                    self.match_log.append({
                        "input": account_str,
                        "input_norm": norm,
                        "match_type": "cache_hit",
                        "matched_key": cached.get("matched_key", ""),
                        "matched_name": cached.get("matched_name", ""),
                        "score": cached.get("score", 100),
                        "url": cached.get("url"),
                    })
                return (cached["url"], int(cached.get("score", 100)), str(cached.get("matched_name") or account_str))

            if status == "NO_MATCH":
                self.stats["no_matches"] += 1
                if self.debug:
                    self.match_log.append({
                        "input": account_str,
                        "input_norm": norm,
                        "match_type": "cache_no_match",
                        "score": cached.get("score"),
                    })
                return None

        # 3) exact
        exact_url = self.get_url_exact(account_str)
        if exact_url:
            self.stats["exact_matches"] += 1
            matched_name = self.original_names.get(norm, account_str)

            if self.debug:
                self.match_log.append({
                    "input": account_str,
                    "input_norm": norm,
                    "match_type": "exact",
                    "matched_key": norm,
                    "matched_name": matched_name,
                    "score": 100,
                    "url": exact_url,
                })

            self.match_cache[cache_key] = {
                "status": "MATCHED",
                "url": exact_url,
                "score": 100,
                "matched_name": matched_name,
                "matched_key": norm,
                "source": "exact",
            }
            return (exact_url, 100, matched_name)

        # 4) fuzzy
        if not self.url_map:
            self.stats["no_matches"] += 1
            self.match_cache[cache_key] = {
                "status": "NO_MATCH",
                "url": None,
                "score": None,
                "matched_name": None,
                "source": "empty_map",
            }
            return None

        results = self._fuzzy_candidates(account_str, top_n=top_n, scorer=fuzz.token_set_ratio)

        if self.debug:
            log_entry: Dict[str, Any] = {
                "input": account_str,
                "input_norm": norm,
                "input_length": len(account_str),
                "candidates": [],
            }
            for matched_key, score, _ in results:
                log_entry["candidates"].append({
                    "key": matched_key,
                    "name": self.original_names.get(matched_key),
                    "score": int(score),
                    "url": self.url_map.get(matched_key),
                })
            self.match_log.append(log_entry)

        if results:
            best_key, best_score, _ = results[0]
            best_score_int = int(best_score)

            if best_score_int >= self.min_score:
                url = self.url_map.get(best_key)
                if url:
                    self.stats["fuzzy_matches"] += 1
                    matched_name = self.original_names.get(best_key, best_key)

                    self.match_cache[cache_key] = {
                        "status": "MATCHED",
                        "url": url,
                        "score": best_score_int,
                        "matched_name": matched_name,
                        "matched_key": best_key,
                        "source": "fuzzy",
                    }
                    return (url, best_score_int, matched_name)

            self.stats["no_matches"] += 1
            self.match_cache[cache_key] = {
                "status": "NO_MATCH",
                "url": None,
                "score": best_score_int,
                "matched_name": self.original_names.get(best_key),
                "matched_key": best_key,
                "source": "below_threshold",
            }
            return None

        self.stats["no_matches"] += 1
        self.match_cache[cache_key] = {
            "status": "NO_MATCH",
            "url": None,
            "score": None,
            "matched_name": None,
            "source": "no_candidates",
        }
        return None

    def get_url(self, account_name: str) -> Optional[str]:
        result = self.get_url_fuzzy(account_name)
        return result[0] if result else None

    def has_url(self, account_name: str) -> bool:
        return self.get_url(account_name) is not None

    # -------------------------------------------------------------------------
    # Rendering / enrichment
    # -------------------------------------------------------------------------
    def get_html_link(self, account_name: str, css_class: str = "") -> str:
        if not account_name or pd.isna(account_name):
            return ""

        account_str = str(account_name).strip()
        result = self.get_url_fuzzy(account_str)

        if result:
            url, score, matched_name = result
            safe_name = _safe_html(account_str)
            class_attr = f' class="{css_class}"' if css_class else ""
            return f'<a href="{url}" target="_blank"{class_attr}>{safe_name}</a>'

        return account_str

    def enrich_dataframe(self, df: pd.DataFrame, account_col: str = "Business Partner Name") -> pd.DataFrame:
        """
        Adds AccountURL / AccountMatchScore / AccountMatchedName.

        YOUR RULE:
        - If df contains a link column (AccountURL or SFDC Link variants) with real values, use it and SKIP matching.
        - Otherwise fallback is NO LINK (do not run fuzzy).
        """
        df_copy = df.copy()

        # 1) Respect existing AccountURL (if it has values)
        if "AccountURL" in df_copy.columns:
            non_empty = df_copy["AccountURL"].notna() & (df_copy["AccountURL"].astype(str).str.strip() != "")
            if int(non_empty.sum()) > 0:
                df_copy["AccountMatchScore"] = None
                df_copy["AccountMatchedName"] = None
                return df_copy

        # 2) Use SFDC Link if present
        sfdc_cols = ["SFDC Link", "SFDC_Link", "SFDC URL", "SFDC_URL", "SFDCLink", "SFDCURL"]
        sfdc_col = next((c for c in sfdc_cols if c in df_copy.columns), None)

        if sfdc_col:
            url = df_copy[sfdc_col].fillna("").astype(str).str.strip()
            url = url.where((url != "") & (url.str.lower() != "nan"), None)

            df_copy["AccountURL"] = url
            df_copy["AccountMatchScore"] = None
            df_copy["AccountMatchedName"] = None
            return df_copy

        # 3) Fallback: no link, no matching
        df_copy["AccountURL"] = None
        df_copy["AccountMatchScore"] = None
        df_copy["AccountMatchedName"] = None
        return df_copy

    # -------------------------------------------------------------------------
    # Reporting / stats
    # -------------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        unique_domains = set()
        for url in self.url_map.values():
            try:
                if "://" in url:
                    domain = url.split("://", 1)[1].split("/", 1)[0]
                else:
                    domain = url.split("/", 1)[0]
                unique_domains.add(domain)
            except Exception:
                pass

        match_rate = 0.0
        if self.stats["total_queries"] > 0:
            matches = self.stats["exact_matches"] + self.stats["fuzzy_matches"]
            match_rate = (matches / self.stats["total_queries"]) * 100.0

        return {
            "total_mappings": len(self.url_map),
            "unique_domains": len(unique_domains),
            "min_score": self.min_score,
            "total_queries": self.stats["total_queries"],
            "exact_matches": self.stats["exact_matches"],
            "fuzzy_matches": self.stats["fuzzy_matches"],
            "no_matches": self.stats["no_matches"],
            "match_rate": f"{match_rate:.1f}%",
        }

    def get_match_report(self, account_names: list = None, top_n: int = 10) -> pd.DataFrame:
        if account_names is not None:
            results = []
            for name in account_names:
                if not name or pd.isna(name):
                    continue
                result = self.get_url_fuzzy(str(name), top_n=top_n)
                if result:
                    url, score, matched_name = result
                    results.append({
                        "Input Name": name,
                        "Matched Name": matched_name,
                        "Score": score,
                        "URL": url,
                        "Status": "✅ Matched",
                    })
                else:
                    results.append({
                        "Input Name": name,
                        "Matched Name": None,
                        "Score": None,
                        "URL": None,
                        "Status": f"❌ No match (min score: {self.min_score})",
                    })
            return pd.DataFrame(results)

        if not self.match_log:
            return pd.DataFrame()

        out_rows = []
        for entry in self.match_log:
            input_name = entry.get("input", "")
            if entry.get("match_type") == "exact":
                out_rows.append({
                    "Input Name": input_name,
                    "Match Type": "Exact",
                    "Best Match": entry.get("matched_name", ""),
                    "Best Score": 100,
                    "Status": "✅ Exact",
                })
                continue

            candidates = entry.get("candidates", [])
            if candidates:
                best = candidates[0]
                best_score = best.get("score", None)
                status = (
                    "✅ Fuzzy"
                    if (best_score is not None and int(best_score) >= self.min_score)
                    else f"❌ <{self.min_score}"
                )
                out_rows.append({
                    "Input Name": input_name,
                    "Match Type": "Fuzzy" if status.startswith("✅") else "No Match",
                    "Best Match": best.get("name", ""),
                    "Best Score": best_score,
                    "Top 3 Candidates": " | ".join(
                        [f"{c.get('name','')} ({c.get('score','')})" for c in candidates[:3]]
                    ),
                    "Status": status,
                })
            else:
                out_rows.append({
                    "Input Name": input_name,
                    "Match Type": "No Match",
                    "Best Match": None,
                    "Best Score": None,
                    "Status": "❌ No candidates",
                })

        return pd.DataFrame(out_rows)

    def export_match_log(self, filepath: str = "account_matching_log.xlsx") -> None:
        if not self.match_log:
            print("⚠️ No match log available. Enable debug=True when initializing AccountLinker.")
            return

        rows: List[Dict[str, Any]] = []
        for entry in self.match_log:
            input_name = entry.get("input", "")

            if entry.get("match_type") == "exact":
                rows.append({
                    "Input Name": input_name,
                    "Input Norm": entry.get("input_norm", ""),
                    "Match Type": "Exact",
                    "Candidate Key": entry.get("matched_key", ""),
                    "Candidate Name": entry.get("matched_name", ""),
                    "Score": 100,
                    "URL": entry.get("url", ""),
                    "Status": "Matched",
                })
                continue

            candidates = entry.get("candidates", [])
            if candidates:
                for i, c in enumerate(candidates):
                    rows.append({
                        "Input Name": input_name if i == 0 else "",
                        "Input Norm": entry.get("input_norm", "") if i == 0 else "",
                        "Match Type": "Fuzzy",
                        "Rank": i + 1,
                        "Candidate Key": c.get("key", ""),
                        "Candidate Name": c.get("name", ""),
                        "Score": c.get("score", ""),
                        "URL": c.get("url", ""),
                        "Status": "Matched"
                        if (i == 0 and int(c.get("score", 0) or 0) >= self.min_score)
                        else "Below threshold",
                    })
            else:
                rows.append({
                    "Input Name": input_name,
                    "Input Norm": entry.get("input_norm", ""),
                    "Match Type": "None",
                    "Status": "No candidates found",
                })

        pd.DataFrame(rows).to_excel(filepath, index=False)
        print(f"✅ Match log exported to: {filepath}")


# =============================================================================
# SINGLETON HELPERS (backwards-compatible)
# =============================================================================
_default_linker: Optional[AccountLinker] = None


def get_default_linker() -> AccountLinker:
    global _default_linker
    if _default_linker is None:
        _default_linker = AccountLinker()
    return _default_linker


def set_default_mapping(filepath: str, min_score: int = 85, debug: bool = False) -> Tuple[AccountLinker, AccountLinker]:
    global _default_linker
    _default_linker = AccountLinker(filepath, min_score, debug)
    return _default_linker, _default_linker

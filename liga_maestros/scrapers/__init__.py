"""Quiniela15 directo scraper - re-export from root."""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

from SCRAPE_QUINIELA15_DIRECTO import scrape, fetch_page, clean, parse_score, parse_live_minute, has_final_signal, status_for_q15, signo_for_score, parse_match_title, parse_events, parse_probs, parse_main_row, main

__all__ = ["scrape", "main"]

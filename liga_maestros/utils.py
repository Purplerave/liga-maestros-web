"""Wrapper: re-exporta utils del root para el paquete liga_maestros."""
import sys, os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import utils as _root_utils

normalize_team_key = _root_utils.normalize_team_key
short_team_name = _root_utils.short_team_name
team_token = _root_utils.team_token
load_team_logos = _root_utils.load_team_logos
build_team_contract = _root_utils.build_team_contract
load_standings_override = _root_utils.load_standings_override
safe_read_json = _root_utils.safe_read_json
safe_write_json = _root_utils.safe_write_json
strip_html = _root_utils.strip_html
normalize_news_text = _root_utils.normalize_news_text
news_relevance_score = _root_utils.news_relevance_score
parse_rfc822_to_iso = _root_utils.parse_rfc822_to_iso
sanitize_xml_payload = _root_utils.sanitize_xml_payload
parse_score_text = _root_utils.parse_score_text
signo_for_match = _root_utils.signo_for_match
highlightly_status = _root_utils.highlightly_status
highlightly_match_to_panel = _root_utils.highlightly_match_to_panel
parse_db_match_datetime = _root_utils.parse_db_match_datetime
parse_any_match_datetime = _root_utils.parse_any_match_datetime
runtime_data_path = _root_utils.runtime_data_path
clean_team_key = _root_utils.clean_team_key

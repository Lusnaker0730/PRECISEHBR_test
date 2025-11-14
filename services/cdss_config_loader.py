"""
CDSS Configuration Loader
載入並管理 CDSS (Clinical Decision Support System) 配置
"""
import json
import logging

# --- Global Configuration ---
_CDSS_CONFIG = None

def load_cdss_config():
    """
    載入 cdss_config.json 配置檔案
    Returns: dict - 配置字典
    """
    global _CDSS_CONFIG
    
    if _CDSS_CONFIG is not None:
        return _CDSS_CONFIG
    
    try:
        with open('cdss_config.json', 'r', encoding='utf-8') as f:
            _CDSS_CONFIG = json.load(f)
        logging.info("Successfully loaded cdss_config.json")
        return _CDSS_CONFIG
    except FileNotFoundError:
        logging.error("CRITICAL: cdss_config.json not found. Calculations will fail.")
        _CDSS_CONFIG = {}
        return _CDSS_CONFIG
    except json.JSONDecodeError:
        logging.error("CRITICAL: cdss_config.json is not valid JSON. Calculations will fail.")
        _CDSS_CONFIG = {}
        return _CDSS_CONFIG

def get_cdss_config():
    """
    獲取已載入的配置（如未載入則自動載入）
    Returns: dict - 配置字典
    """
    if _CDSS_CONFIG is None:
        return load_cdss_config()
    return _CDSS_CONFIG

def get_loinc_codes():
    """
    從配置中載入 LOINC codes
    Returns: dict - 映射觀察類型到 LOINC code tuples
    """
    config = get_cdss_config()
    if not config:
        return {}
    
    lab_config = config.get('laboratory_value_extraction', {})
    
    return {
        "EGFR": tuple(lab_config.get('egfr_loinc_codes', [])),
        "CREATININE": tuple(lab_config.get('creatinine_loinc_codes', [])),
        "HEMOGLOBIN": tuple(lab_config.get('hemoglobin_loinc_codes', [])),
        "WBC": tuple(lab_config.get('white_blood_cell_loinc_codes', [])),
        "PLATELETS": tuple(lab_config.get('platelet_loinc_codes', [])),
    }

def get_text_search_terms():
    """
    從配置中載入文字搜尋詞彙
    Returns: dict - 映射觀察類型到搜尋詞彙列表
    """
    config = get_cdss_config()
    if not config:
        return {}
    
    lab_config = config.get('laboratory_value_extraction', {})
    
    return {
        "EGFR": lab_config.get('egfr_text_search', []),
        "CREATININE": lab_config.get('creatinine_text_search', []),
        "HEMOGLOBIN": lab_config.get('hemoglobin_text_search', []),
        "WBC": lab_config.get('wbc_text_search', []),
        "PLATELETS": lab_config.get('platelet_text_search', []),
    }

# 初始化時自動載入配置
load_cdss_config()


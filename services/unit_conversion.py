"""
Unit Conversion System for Medical Laboratory Values
醫學實驗室數值的單位轉換系統
"""
import logging

# 定義應用程式內部使用的標準單位
TARGET_UNITS = {
    'HEMOGLOBIN': {
        'unit': 'g/dl',
        # 轉換係數：將來源單位轉換為目標單位 (g/dL)
        'factors': {
            'g/l': 0.1,
            'mmol/l': 1.61135,  # 基於 Hb 分子量 64,458 g/mol
            'mg/dl': 0.001,     # mg/dL to g/dL
        }
    },
    'CREATININE': {
        'unit': 'mg/dl',
        # 轉換係數：將來源單位轉換為目標單位 (mg/dL)
        'factors': {
            'umol/l': 0.0113,   # µmol/L to mg/dL
            'µmol/l': 0.0113,   # 處理 unicode 字符
        }
    },
    'WBC': {
        'unit': '10*9/l',
        # 轉換係數：將來源單位轉換為目標單位 (10^9/L)
        'factors': {
            '10*3/ul': 1.0,     # 10^3/µL = K/µL = 10^9/L
            'k/ul': 1.0,        # K/µL = 10^9/L
            '/ul': 0.001,       # cells/µL ÷ 1000 = 10^9/L
            '/mm3': 0.001,      # cells/mm³ = cells/µL
            '10^9/l': 1.0,      # 已是目標單位
            'giga/l': 1.0       # Giga/L = 10^9/L
        }
    },
    'EGFR': {
        'unit': 'ml/min/1.73m2',
        'factors': {
            'ml/min/1.73m2': 1.0,       # 標準格式
            'ml/min/{1.73_m2}': 1.0,    # Cerner 格式（帶大括號）
            'ml/min/1.73m^2': 1.0,      # 帶 caret
            'ml/min/1.73 m2': 1.0,      # 帶空格
            'ml/min/1.73 m^2': 1.0,     # 空格和 caret
            'ml/min per 1.73m2': 1.0,   # 帶 'per'
            'ml/min/bsa': 1.0,          # 體表面積
            'ml/min': 1.0               # 沒有 BSA 標準化
        } 
    },
    'PLATELETS': {
        'unit': '10*9/l',
        'factors': {
            '10*3/ul': 1.0,     # 10^3/µL = K/µL = 10^9/L
            'k/ul': 1.0,        # K/µL = 10^9/L
            '/ul': 0.001,       # cells/µL ÷ 1000 = 10^9/L
            '10^9/l': 1.0,      # 已是目標單位
            'giga/l': 1.0       # Giga/L = 10^9/L
        }
    }
}

def get_value_from_observation(obs, unit_system):
    """
    安全地從 Observation 資源中提取數值，處理單位轉換
    
    Args:
        obs: FHIR Observation 資源（dict）
        unit_system: 單位系統配置（來自 TARGET_UNITS）
    
    Returns:
        float or None: 轉換後的數值，若無法轉換則返回 None
    """
    if not obs or not isinstance(obs, dict):
        return None

    value_quantity = obs.get('valueQuantity')
    if not value_quantity:
        return None

    value = value_quantity.get('value')
    if value is None or not isinstance(value, (int, float)):
        return None
        
    source_unit = value_quantity.get('unit', '').lower()
    target_unit = unit_system['unit']
    
    # 0. 如果單位缺失/空白，假設數值已經是目標單位
    # 這處理了不提供單位資訊的 FHIR 伺服器
    if not source_unit or source_unit.strip() == '':
        logging.warning(f"No unit provided for Observation value {value}. "
                       f"Assuming it is already in target unit '{target_unit}'.")
        return value
    
    # 1. 直接匹配
    if source_unit == target_unit:
        return value

    # 2. 檢查目標單位的常見替代寫法
    # (例如 "g/dL" vs "g/dl")，簡單的大小寫不敏感檢查
    if source_unit.lower() == target_unit.lower():
        return value

    # 3. 嘗試轉換
    conversion_factors = unit_system.get('factors', {})
    if source_unit in conversion_factors:
        conversion_factor = conversion_factors[source_unit]
        converted_value = value * conversion_factor
        logging.info(f"Converted {value} {source_unit} to {converted_value:.2f} {target_unit}")
        return converted_value

    # 4. 如果無法轉換，記錄警告並返回 None 以防止錯誤計算
    logging.warning(f"Unit mismatch and no conversion rule found for Observation. "
                    f"Received: '{source_unit}', Expected: '{target_unit}'. Cannot proceed with this value.")
    return None

def normalize_unit_string(unit_string):
    """
    標準化單位字串以提高匹配成功率
    
    Args:
        unit_string: 原始單位字串
    
    Returns:
        str: 標準化後的單位字串
    """
    if not unit_string:
        return ''
    
    # 轉換為小寫
    normalized = unit_string.lower().strip()
    
    # 移除多餘的空格
    normalized = ' '.join(normalized.split())
    
    # 常見替換
    replacements = {
        'micromol/l': 'umol/l',
        'μmol/l': 'umol/l',
        'micro': 'u',
        'per': '/',
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    return normalized


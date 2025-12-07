"""
FHIR Utility Functions
FHIR 相關的通用輔助函數
"""
import datetime as dt
import logging
from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

def get_patient_demographics(patient_resource):
    """
    從 patient 資源中提取關鍵人口統計資料
    
    Args:
        patient_resource: FHIR Patient 資源（dict）
    
    Returns:
        dict: 包含 name, gender, age, birthDate 的字典
    """
    demographics = {
        "name": "Unknown",
        "gender": None,
        "age": None,
        "birthDate": None
    }
    
    if not patient_resource:
        return demographics

    # Name
    if patient_resource.get("name"):
        name_data = patient_resource["name"][0]
        # 優先使用 text 欄位（台灣 FHIR 格式），然後回退到 given/family
        if name_data.get("text"):
            demographics["name"] = name_data.get("text")
        else:
            # Handle both given and family as potentially being lists or strings
            given_names = name_data.get("given", [])
            family_name = name_data.get("family", "")
            
            # Ensure given_names is a list
            if isinstance(given_names, str):
                given_names = [given_names]
            
            # Ensure family_name is a string (flatten if it's a list)
            if isinstance(family_name, list):
                family_name = " ".join(family_name) if family_name else ""
            
            # Combine all name parts
            name_parts = list(given_names) + ([family_name] if family_name else [])
            demographics["name"] = " ".join(name_parts).strip()

    # Gender
    demographics["gender"] = patient_resource.get("gender")

    # Age
    if patient_resource.get("birthDate"):
        demographics["birthDate"] = patient_resource["birthDate"]
        try:
            birth_date = dt.datetime.strptime(
                patient_resource["birthDate"], "%Y-%m-%d"
            ).date()
            today = dt.date.today()
            demographics["age"] = (
                today.year - birth_date.year - 
                ((today.month, today.day) < (birth_date.month, birth_date.day))
            )
        except (ValueError, TypeError):
            pass
            
    return demographics

def calculate_egfr(cr_val, age, gender):
    """
    使用 CKD-EPI 2021 公式計算 eGFR
    
    Args:
        cr_val: Creatinine 值 (mg/dL)
        age: 年齡
        gender: 性別 ('male' 或 'female')
    
    Returns:
        tuple: (eGFR 值, 計算方法說明)
    """
    if not all([cr_val, age, gender]) or gender not in ['male', 'female']:
        return None, "Missing data for eGFR calculation"
    
    k = 0.7 if gender == 'female' else 0.9
    alpha = -0.241 if gender == 'female' else -0.302
    
    # CKD-EPI 2021 公式
    egfr = 142 * (min(cr_val / k, 1) ** alpha) * (max(cr_val / k, 1) ** -1.2) * (0.9938 ** age)
    if gender == 'female':
        egfr *= 1.012
        
    return round(egfr), "CKD-EPI 2021"

def resource_has_code(resource, system, code):
    """
    檢查資源的 coding 是否匹配給定的 system 和 code
    
    Args:
        resource: FHIR 資源（dict）
        system: 編碼系統 URL
        code: 編碼值
    
    Returns:
        bool: 是否匹配
    """
    for coding in resource.get('code', {}).get('coding', []):
        if coding.get('system') == system and coding.get('code') == code:
            return True
    return False

def is_within_time_window(resource_date_str, min_months=None, max_months=None):
    """
    檢查資源日期是否在指定的時間窗口內（從今天算起）
    
    Args:
        resource_date_str: 資源日期字串
        min_months: 最小月數（若指定，資源日期必須早於此）
        max_months: 最大月數（若指定，資源日期必須晚於此）
    
    Returns:
        bool: 是否在時間窗口內
    """
    if not resource_date_str:
        return False
    try:
        resource_date = parse_date(resource_date_str).date()
        today = dt.date.today()
        if min_months is not None and resource_date > today - relativedelta(months=min_months):
            return False
        if max_months is not None and resource_date < today - relativedelta(months=max_months):
            return False
        return True
    except (ValueError, TypeError):
        return False

def get_condition_text(condition):
    """
    從 condition 資源中提取所有文字以進行文字匹配
    
    Args:
        condition: FHIR Condition 資源（dict）
    
    Returns:
        str: 合併的條件文字
    """
    text_parts = []
    
    # 獲取 text 欄位
    if condition.get('code', {}).get('text'):
        text_parts.append(condition['code']['text'])
    
    # 獲取 coding 的 display 文字
    for coding in condition.get('code', {}).get('coding', []):
        if coding.get('display'):
            text_parts.append(coding['display'])
    
    return ' '.join(text_parts)

def get_score_from_table(value, score_table, range_key):
    """
    從查找表中獲取分數的輔助函數
    
    Args:
        value: 要查找的值
        score_table: 分數表（list of dicts）
        range_key: 範圍鍵名（如 'age_range', 'hb_range'）
    
    Returns:
        int: 對應的分數
    """
    matched_score = None
    
    for item in score_table:
        if range_key in item:
            range_values = item[range_key]
            if len(range_values) == 2 and range_values[0] <= value <= range_values[1]:
                return item.get('base_score', 0)
    
    # 如果沒有精確匹配，檢查值是否超出最高範圍
    # 在這種情況下，使用可用的最高分數
    if range_key == 'age_range':
        # 對於年齡，如果大於最大範圍，使用最高分數
        max_range_item = max(score_table, key=lambda x: x[range_key][1] if range_key in x else 0)
        if value > max_range_item[range_key][1]:
            logging.info(f"Age {value} exceeds max range {max_range_item[range_key]}, using highest score: {max_range_item.get('base_score', 0)}")
            return max_range_item.get('base_score', 0)
    elif range_key == 'hb_range':
        # 對於血紅蛋白，如果低於最小範圍，使用最高分數（最低 Hb = 最高風險）
        min_range_item = min(score_table, key=lambda x: x[range_key][0] if range_key in x else float('inf'))
        if value < min_range_item[range_key][0]:
            logging.info(f"Hemoglobin {value} below min range {min_range_item[range_key]}, using highest score: {min_range_item.get('base_score', 0)}")
            return min_range_item.get('base_score', 0)
    elif range_key == 'ccr_range':
        # 對於肌酸酐清除率，如果低於最小範圍，使用最高分數（最低 CCr = 最高風險）
        min_range_item = min(score_table, key=lambda x: x[range_key][0] if range_key in x else float('inf'))
        if value < min_range_item[range_key][0]:
            logging.info(f"Creatinine clearance {value} below min range {min_range_item[range_key]}, using highest score: {min_range_item.get('base_score', 0)}")
            return min_range_item.get('base_score', 0)
    elif range_key == 'wbc_range':
        # 對於 WBC，如果高於最大範圍，使用最高分數（更高 WBC = 更高風險）
        max_range_item = max(score_table, key=lambda x: x[range_key][1] if range_key in x else 0)
        if value > max_range_item[range_key][1]:
            logging.info(f"WBC {value} exceeds max range {max_range_item[range_key]}, using highest score: {max_range_item.get('base_score', 0)}")
            return max_range_item.get('base_score', 0)
    
    return 0

def get_active_medications(raw_data, demographics):
    """
    從 FHIR 資源中處理藥物資料以識別活躍藥物
    用於 CDS Hooks 藥物分析
    
    Args:
        raw_data: 原始 FHIR 資料
        demographics: 人口統計資料
    
    Returns:
        list: 活躍藥物資源列表
    """
    medications = raw_data.get('med_requests', [])
    active_medications = []
    
    for med in medications:
        # 檢查藥物是否活躍
        status = med.get('status', '').lower()
        if status in ['active', 'on-hold', 'completed']:
            active_medications.append(med)
    
    logging.info(f"Found {len(active_medications)} active medications")
    return active_medications

def check_medication_interactions_bleeding_risk(medications):
    """
    檢查增加出血風險的藥物組合
    特別查找 DAPT 組合和其他高風險藥物
    
    Args:
        medications: 藥物列表
    
    Returns:
        dict: 包含交互作用詳情的字典
    """
    interactions = {
        'dapt_detected': False,
        'high_risk_combinations': [],
        'bleeding_risk_medications': [],
        'recommendations': []
    }
    
    # 此函數可以擴展以包含除 DAPT 之外更複雜的藥物交互作用檢查
    
    return interactions


"""
PRECISE-HBR Risk Calculator
PRECISE-HBR 出血風險計算器

實作 PRECISE-HBR V5.0 評分系統
"""
import logging
import math

from services.cdss_config_loader import get_cdss_config
from services.unit_conversion import TARGET_UNITS, get_value_from_observation
from services.fhir_utils import calculate_egfr
from services.condition_checkers import (
    check_prior_bleeding_updated,
    check_oral_anticoagulation,
    check_arc_hbr_factors_detailed
)

def calculate_precise_hbr_score(raw_data, demographics):
    """
    使用最終確認的評分指南計算 PRECISE-HBR 出血風險評分 (V5.0)
    
    計算步驟：
    1. 確定有效值：對連續變數應用截斷規則
    2. 基礎分數：從 2 分開始
    3. 添加風險分數：使用有效值計算每個項目的風險分數
    4. 求和：添加基礎分數和所有風險分數
    5. 四捨五入：將總分四捨五入到最接近的整數作為最終分數
    
    連續變數：
    - 年齡：如果有效年齡 > 30: score = (有效年齡 - 30) × 0.25
    - 血紅蛋白：如果有效 Hb < 15: score = (15 - 有效 Hb) × 2.5
    - WBC：如果有效 WBC > 3.0: score = (有效 WBC - 3.0) × 0.8
    - eGFR：如果有效 eGFR < 100: score = (100 - 有效 eGFR) × 0.05
    
    類別變數：
    - 既往出血史：是 = +7 分
    - 長期口服抗凝：是 = +5 分
    - 其他 ARC-HBR 條件：是 = +3 分
    
    Args:
        raw_data: 原始 FHIR 資料
        demographics: 人口統計資料
    
    Returns:
        tuple: (components 列表, 最終分數)
    """
    components = []
    
    # 基礎分數：從 2 分開始
    base_score = 2
    total_score = base_score
    
    # 初始化個別分數
    age_score = 0
    hb_score = 0
    egfr_score = 0
    wbc_score = 0
    bleeding_score = 0
    anticoag_score = 0
    arc_hbr_score = 0
    
    # 截斷限制用於有效值
    MIN_AGE, MAX_AGE = 30, 80
    MIN_HB, MAX_HB = 5.0, 15.0
    MIN_EGFR, MAX_EGFR = 5, 100  # eGFR 截斷低於 5
    MAX_WBC = 15.0  # WBC 截斷高於 15×10³ cells/μL
    
    # 1. 年齡分數 - 如果有效年齡 > 30: score = (有效年齡 - 30) × 0.25
    age = demographics.get('age')
    if age:
        # 應用截斷獲得有效年齡
        effective_age = max(MIN_AGE, min(MAX_AGE, age))
        
        # 計算年齡分數：如果有效年齡 > 30: score = (有效年齡 - 30) × 0.25
        if effective_age > 30:
            age_score_raw = (effective_age - 30) * 0.25
            age_score = round(age_score_raw)
            total_score += age_score_raw  # 使用原始分數進行總計計算
            logging.info(f"Age score: ({effective_age} - 30) × 0.25 = {age_score_raw:.2f} → {age_score}")
        else:
            age_score = 0
            logging.info(f"Age score: effective age {effective_age} ≤ 30, score = 0")
        
        components.append({
            "parameter": "PRECISE-HBR - Age",
            "value": f"{age} years (effective: {effective_age})" if age != effective_age else f"{age} years",
            "score": age_score,
            "raw_value": age,
            "date": "N/A",
            "description": f"Age score: ({effective_age} - 30) × 0.25 = {age_score}" if effective_age > 30 else f"Age {effective_age} ≤ 30, score = 0"
        })
    else:
        components.append({
            "parameter": "PRECISE-HBR - Age", 
            "value": "Unknown",
            "score": 0,
            "raw_value": None,
            "date": "N/A",
            "description": "Age not available"
        })
    
    # 2. 血紅蛋白分數 - 如果有效 Hb < 15: score = (15 - 有效 Hb) × 2.5
    hemoglobin_list = raw_data.get('HEMOGLOBIN', [])
    if hemoglobin_list:
        hemoglobin_obs = hemoglobin_list[0]
        # 使用新的單位感知函數
        hb_val = get_value_from_observation(hemoglobin_obs, TARGET_UNITS['HEMOGLOBIN'])
        
        if hb_val:
            hb_unit = TARGET_UNITS['HEMOGLOBIN']['unit'] # 顯示標準化單位
            hb_date = hemoglobin_obs.get('effectiveDateTime', 'N/A')
            
            # 應用截斷獲得有效 Hb
            effective_hb = max(MIN_HB, min(MAX_HB, hb_val))
            
            # 計算 Hb 分數：如果有效 Hb < 15: score = (15 - 有效 Hb) × 2.5
            if effective_hb < 15:
                hb_score_raw = (15 - effective_hb) * 2.5
                hb_score = round(hb_score_raw)
                total_score += hb_score_raw  # 使用原始分數進行總計計算
                logging.info(f"Hemoglobin score: (15 - {effective_hb}) × 2.5 = {hb_score_raw:.2f} → {hb_score}")
            else:
                hb_score = 0
                logging.info(f"Hemoglobin score: effective Hb {effective_hb} ≥ 15, score = 0")
            
            components.append({
                "parameter": "PRECISE-HBR - Hemoglobin",
                "value": f"{hb_val} {hb_unit} (effective: {effective_hb})" if hb_val != effective_hb else f"{hb_val} {hb_unit}",
                "score": hb_score,
                "raw_value": hb_val,
                "date": hb_date,
                "description": f"Hemoglobin score: (15 - {effective_hb}) × 2.5 = {hb_score}" if effective_hb < 15 else f"Hb {effective_hb} ≥ 15, score = 0"
            })
        else:
            components.append({
                "parameter": "PRECISE-HBR - Hemoglobin",
                "value": "Not available",
                "score": 0,
                "raw_value": None,
                "date": "N/A", 
                "description": "Hemoglobin not available"
            })
    else:
        components.append({
            "parameter": "PRECISE-HBR - Hemoglobin",
            "value": "Not available",
            "score": 0,
            "raw_value": None,
            "date": "N/A", 
            "description": "Hemoglobin not available"
        })
    
    # 3. eGFR 分數 - 如果有效 eGFR < 100: score = (100 - 有效 eGFR) × 0.05
    egfr_list = raw_data.get('EGFR', [])
    creatinine_list = raw_data.get('CREATININE', [])
    
    egfr_val = None
    egfr_source = ""
    egfr_date = "N/A"
    
    if egfr_list:
        egfr_obs = egfr_list[0]
        # 使用新的單位感知函數
        egfr_val = get_value_from_observation(egfr_obs, TARGET_UNITS['EGFR'])
        egfr_source = "Direct eGFR"
        egfr_date = egfr_obs.get('effectiveDateTime', 'N/A')
    elif creatinine_list and age and demographics.get('gender'):
        creatinine_obs = creatinine_list[0]
        # 使用新的單位感知函數獲取 Creatinine（mg/dL）
        creatinine_val = get_value_from_observation(creatinine_obs, TARGET_UNITS['CREATININE'])
        if creatinine_val:
            calculated_egfr, reason = calculate_egfr(creatinine_val, age, demographics.get('gender'))
            if calculated_egfr:
                egfr_val = calculated_egfr
                egfr_source = reason
                egfr_date = creatinine_obs.get('effectiveDateTime', 'N/A')
    
    if egfr_val:
        # 應用截斷獲得有效 eGFR（截斷低於 5 和高於 100）
        effective_egfr = max(MIN_EGFR, min(MAX_EGFR, egfr_val))
        
        # 計算 eGFR 分數：如果有效 eGFR < 100: score = (100 - 有效 eGFR) × 0.05
        if effective_egfr < 100:
            egfr_score_raw = (100 - effective_egfr) * 0.05
            egfr_score = round(egfr_score_raw)
            total_score += egfr_score_raw  # 使用原始分數進行總計計算
            logging.info(f"eGFR score: (100 - {effective_egfr}) × 0.05 = {egfr_score_raw:.2f} → {egfr_score}")
        else:
            egfr_score = 0
            logging.info(f"eGFR score: effective eGFR {effective_egfr} ≥ 100, score = 0")
        
        components.append({
            "parameter": "PRECISE-HBR - eGFR",
            "value": f"{egfr_val} mL/min/1.73m² (effective: {effective_egfr}) ({egfr_source})" if egfr_val != effective_egfr else f"{egfr_val} mL/min/1.73m² ({egfr_source})",
            "score": egfr_score,
            "raw_value": egfr_val,
            "date": egfr_date,
            "description": f"eGFR score: (100 - {effective_egfr}) × 0.05 = {egfr_score}" if effective_egfr < 100 else f"eGFR {effective_egfr} ≥ 100, score = 0"
        })
    else:
        components.append({
            "parameter": "PRECISE-HBR - eGFR",
            "value": "Not available",
            "score": 0,
            "raw_value": None,
            "date": "N/A",
            "description": "eGFR not available"
        })
    
    # 4. 白血球計數分數 - 如果有效 WBC > 3.0: score = (有效 WBC - 3.0) × 0.8
    wbc_list = raw_data.get('WBC', [])
    if wbc_list:
        wbc_obs = wbc_list[0]
        # 使用新的單位感知函數
        wbc_val = get_value_from_observation(wbc_obs, TARGET_UNITS['WBC'])
        
        if wbc_val:
            wbc_unit = TARGET_UNITS['WBC']['unit'] # 顯示標準化單位
            wbc_date = wbc_obs.get('effectiveDateTime', 'N/A')
            
            # 應用截斷獲得有效 WBC（截斷高於 15×10³ cells/μL）
            effective_wbc = min(MAX_WBC, wbc_val)
            
            # 計算 WBC 分數：如果有效 WBC > 3.0: score = (有效 WBC - 3.0) × 0.8
            if effective_wbc > 3.0:
                wbc_score_raw = (effective_wbc - 3.0) * 0.8
                wbc_score = round(wbc_score_raw)
                total_score += wbc_score_raw  # 使用原始分數進行總計計算
                logging.info(f"WBC score: ({effective_wbc} - 3.0) × 0.8 = {wbc_score_raw:.2f} → {wbc_score}")
            else:
                wbc_score = 0
                logging.info(f"WBC score: effective WBC {effective_wbc} ≤ 3.0, score = 0")
            
            components.append({
                "parameter": "PRECISE-HBR - White Blood Cell Count",
                "value": f"{wbc_val} {wbc_unit} (effective: {effective_wbc})" if wbc_val != effective_wbc else f"{wbc_val} {wbc_unit}",
                "score": wbc_score,
                "raw_value": wbc_val,
                "date": wbc_date,
                "description": f"WBC score: ({effective_wbc} - 3.0) × 0.8 = {wbc_score}" if effective_wbc > 3.0 else f"WBC {effective_wbc} ≤ 3.0, score = 0"
            })
        else:
            components.append({
                "parameter": "PRECISE-HBR - White Blood Cell Count",
                "value": "Not available",
                "score": 0,
                "raw_value": None,
                "date": "N/A",
                "description": "WBC count not available"
            })
    else:
        components.append({
            "parameter": "PRECISE-HBR - White Blood Cell Count",
            "value": "Not available",
            "score": 0,
            "raw_value": None,
            "date": "N/A",
            "description": "WBC count not available"
        })
    
    # 5. 既往出血史 - 類別變數：是 = +7 分（更新的 valueset 邏輯）
    conditions = raw_data.get('conditions', [])
    has_bleeding, bleeding_evidence = check_prior_bleeding_updated(conditions)
    
    bleeding_score = 7 if has_bleeding else 0
    total_score += bleeding_score
    
    logging.info(f"Previous bleeding score: {'Yes' if has_bleeding else 'No'} = {bleeding_score} points")
    
    components.append({
        "parameter": "PRECISE-HBR - Prior Bleeding",
        "value": "Yes" if has_bleeding else "No",
        "score": bleeding_score,
        "is_present": has_bleeding,
        "date": "N/A",
        "description": f"Previous bleeding: {'Yes' if has_bleeding else 'No'} = {bleeding_score} points. Found: {', '.join(bleeding_evidence) if bleeding_evidence else 'None detected'}"
    })
    
    # 6. 長期口服抗凝 - 類別變數：是 = +5 分
    medications = raw_data.get('med_requests', [])
    has_anticoagulation = check_oral_anticoagulation(medications)
    
    anticoag_score = 5 if has_anticoagulation else 0
    total_score += anticoag_score
    
    logging.info(f"Oral anticoagulation score: {'Yes' if has_anticoagulation else 'No'} = {anticoag_score} points")
    
    components.append({
        "parameter": "PRECISE-HBR - Oral Anticoagulation",
        "value": "Yes" if has_anticoagulation else "No", 
        "score": anticoag_score,
        "is_present": has_anticoagulation,
        "date": "N/A",
        "description": f"Long-term oral anticoagulation: {'Yes' if has_anticoagulation else 'No'} = {anticoag_score} points"
    })
    
    # 7. 其他 ARC-HBR 條件 - 類別變數：是 = +3 分
    # 獲取個別 ARC-HBR 因素詳情
    arc_hbr_details = check_arc_hbr_factors_detailed(raw_data, medications)
    has_arc_factors = arc_hbr_details['has_any_factor']
    
    arc_hbr_score = 3 if has_arc_factors else 0
    total_score += arc_hbr_score
    
    logging.info(f"ARC-HBR conditions score: {'Yes' if has_arc_factors else 'No'} = {arc_hbr_score} points")
    
    # 添加個別 ARC-HBR 元素作為單獨的組件
    components.append({
        "parameter": "PRECISE-HBR - Platelet Count",
        "value": "Yes" if arc_hbr_details['thrombocytopenia'] else "No",
        "score": 0,  # 個別元素不單獨貢獻分數
        "is_present": arc_hbr_details['thrombocytopenia'],
        "is_arc_hbr_element": True,
        "date": "N/A",
        "description": "Platelet count <100 ×10⁹/L"
    })
    
    components.append({
        "parameter": "PRECISE-HBR - Chronic Bleeding Diathesis",
        "value": "Yes" if arc_hbr_details['bleeding_diathesis'] else "No",
        "score": 0,
        "is_present": arc_hbr_details['bleeding_diathesis'],
        "is_arc_hbr_element": True,
        "date": "N/A",
        "description": "Chronic bleeding diathesis"
    })
    
    components.append({
        "parameter": "PRECISE-HBR - Liver Cirrhosis",
        "value": "Yes" if arc_hbr_details['liver_cirrhosis'] else "No",
        "score": 0,
        "is_present": arc_hbr_details['liver_cirrhosis'],
        "is_arc_hbr_element": True,
        "date": "N/A",
        "description": "Liver cirrhosis with portal hypertension"
    })
    
    components.append({
        "parameter": "PRECISE-HBR - Active Malignancy",
        "value": "Yes" if arc_hbr_details['active_malignancy'] else "No",
        "score": 0,
        "is_present": arc_hbr_details['active_malignancy'],
        "is_arc_hbr_element": True,
        "date": "N/A",
        "description": "Active malignancy"
    })
    
    components.append({
        "parameter": "PRECISE-HBR - NSAIDs/Corticosteroids",
        "value": "Yes" if arc_hbr_details['nsaids_corticosteroids'] else "No",
        "score": 0,
        "is_present": arc_hbr_details['nsaids_corticosteroids'],
        "is_arc_hbr_element": True,
        "date": "N/A",
        "description": "Chronic use of nsaids or corticosteroids"
    })
    
    # 添加 ARC-HBR 摘要組件
    arc_hbr_count = sum([
        arc_hbr_details['thrombocytopenia'],
        arc_hbr_details['bleeding_diathesis'],
        arc_hbr_details['liver_cirrhosis'],
        arc_hbr_details['active_malignancy'],
        arc_hbr_details['nsaids_corticosteroids']
    ])
    
    components.append({
        "parameter": "PRECISE-HBR - ARC-HBR Summary",
        "value": f"{arc_hbr_count} factor(s) present" if has_arc_factors else "None detected",
        "score": arc_hbr_score,
        "is_present": has_arc_factors,
        "date": "N/A",
        "description": f"ARC-HBR Elements ≥1: {'Yes' if has_arc_factors else 'No'} = {arc_hbr_score} points"
    })
    
    # 添加基礎分數組件以增加透明度
    components.insert(0, {
        "parameter": "PRECISE-HBR - Base Score",
        "value": "Fixed base score",
        "score": base_score,
        "date": "N/A",
        "description": f"Base score: {base_score} points (fixed)"
    })
    
    # 將最終分數四捨五入到最接近的整數
    final_score = round(total_score)
    
    logging.info(f"PRECISE-HBR V5.0 calculation complete:")
    logging.info(f"Base score: {base_score}")
    logging.info(f"Age score: {age_score:.2f}")
    logging.info(f"Hemoglobin score: {hb_score:.2f}")
    logging.info(f"eGFR score: {egfr_score:.2f}")
    logging.info(f"WBC score: {wbc_score:.2f}")
    logging.info(f"Bleeding score: {bleeding_score}")
    logging.info(f"Anticoagulation score: {anticoag_score}")
    logging.info(f"ARC-HBR score: {arc_hbr_score}")
    logging.info(f"Total before rounding: {total_score:.2f}")
    logging.info(f"Final score (rounded): {final_score}")
    
    return components, final_score

def calculate_bleeding_risk_percentage(precise_hbr_score):
    """
    根據 PRECISE-HBR 分數計算 1 年出血風險百分比
    基於 PRECISE-HBR 驗證研究的校準曲線
    
    Args:
        precise_hbr_score: PRECISE-HBR 分數
    
    Returns:
        float: 估計的 1 年 BARC 3 或 5 出血事件風險
    """
    # 基於校準曲線的近似風險百分比
    # 這些值來自 PRECISE-HBR 驗證研究
    if precise_hbr_score <= 22:
        # 非 HBR：風險範圍從 ~0.5% 到 ~3.5%
        # 分數 0-22 的線性插值
        risk_percent = 0.5 + (precise_hbr_score / 22) * 3.0
        return min(3.5, risk_percent)
    elif precise_hbr_score <= 26:
        # HBR：風險範圍從 ~3.5% 到 ~5.5%
        # 分數 23-26 的線性插值
        risk_percent = 3.5 + ((precise_hbr_score - 22) / 4) * 2.0
        return min(5.5, risk_percent)
    elif precise_hbr_score <= 30:
        # 非常 HBR：風險範圍從 ~5.5% 到 ~8%
        # 分數 27-30 的線性插值
        risk_percent = 5.5 + ((precise_hbr_score - 26) / 4) * 2.5
        return min(8.0, risk_percent)
    elif precise_hbr_score <= 35:
        # 極高風險：風險範圍從 ~8% 到 ~12%
        risk_percent = 8.0 + ((precise_hbr_score - 30) / 5) * 4.0
        return min(12.0, risk_percent)
    else:
        # 對於非常高的分數（>35），上限為 ~15%
        risk_percent = 12.0 + ((precise_hbr_score - 35) / 10) * 3.0
        return min(15.0, risk_percent)

def get_risk_category_info(precise_hbr_score):
    """
    根據 PRECISE-HBR 分數獲取風險類別資訊
    
    Args:
        precise_hbr_score: PRECISE-HBR 分數
    
    Returns:
        dict: 包含類別標籤、顏色和具體出血風險百分比
    """
    bleeding_risk_percent = calculate_bleeding_risk_percentage(precise_hbr_score)
    
    if precise_hbr_score <= 22:
        return {
            "category": "Not high bleeding risk",
            "color": "success",  # Bootstrap 顏色類別
            "bleeding_risk_percent": f"{bleeding_risk_percent:.1f}%",
            "score_range": f"(score ≤22)"
        }
    elif precise_hbr_score <= 26:
        return {
            "category": "HBR",
            "color": "warning",  # Bootstrap 顏色類別  
            "bleeding_risk_percent": f"{bleeding_risk_percent:.1f}%",
            "score_range": f"(score 23-26)"
        }
    else:  # score >= 27
        return {
            "category": "Very HBR", 
            "color": "danger",  # Bootstrap 顏色類別
            "bleeding_risk_percent": f"{bleeding_risk_percent:.1f}%",
            "score_range": f"(score ≥27)"
        }

def get_precise_hbr_display_info(precise_hbr_score):
    """
    獲取 PRECISE-HBR 分數的完整顯示資訊
    包括風險類別、出血風險百分比和建議
    
    Args:
        precise_hbr_score: PRECISE-HBR 分數
    
    Returns:
        dict: 完整的顯示資訊
    """
    risk_info = get_risk_category_info(precise_hbr_score)
    bleeding_risk_percent = calculate_bleeding_risk_percentage(precise_hbr_score)
    
    return {
        "score": precise_hbr_score,
        "risk_category": risk_info["category"],
        "score_range": risk_info["score_range"],
        "bleeding_risk_percent": f"{bleeding_risk_percent:.2f}%",
        "color_class": risk_info["color"],
        "full_label": f"{risk_info['category']} {risk_info['score_range']}",
        "recommendation": f"1-year risk of major bleeding: {bleeding_risk_percent:.2f}% (Bleeding Academic Research Consortium [BARC] type 3 or 5)"
    }

def calculate_risk_components(raw_data, demographics):
    """
    使用 PRECISE-HBR 計算出血風險分數的主函數
    
    Args:
        raw_data: 原始 FHIR 資料
        demographics: 人口統計資料
    
    Returns:
        tuple: (components 列表, 總分數)
    """
    return calculate_precise_hbr_score(raw_data, demographics)


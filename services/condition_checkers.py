"""
Medical Condition Checkers
檢查各種醫療條件的函數集合
"""
import logging
from services.cdss_config_loader import get_cdss_config
from services.unit_conversion import TARGET_UNITS, get_value_from_observation
from services.fhir_utils import get_condition_text

def check_oral_anticoagulation(medications):
    """
    使用配置中的代碼檢查長期口服抗凝治療
    
    Args:
        medications: 藥物列表
    
    Returns:
        bool: 患者是否正在使用口服抗凝劑
    """
    # 從配置中獲取藥物關鍵詞
    config = get_cdss_config()
    med_config = config.get('medication_keywords', {})
    oac_config = med_config.get('oral_anticoagulants', {})
    
    anticoagulant_codes = (
        oac_config.get('generic_names', []) + 
        oac_config.get('brand_names', [])
    )
    
    for med in medications:
        med_code = med.get('medicationCodeableConcept', {})
        med_text = str(med_code).lower()
        
        for anticoag in anticoagulant_codes:
            if anticoag in med_text:
                return True
    
    return False

def check_bleeding_diathesis_updated(conditions):
    """
    使用配置中的代碼檢查慢性出血素質
    
    Args:
        conditions: 條件列表
    
    Returns:
        tuple: (是否有出血素質, 出血資訊)
    """
    # 從配置中獲取 SNOMED codes
    config = get_cdss_config()
    snomed_config = config.get('precise_hbr_snomed_codes', {})
    diathesis_config = snomed_config.get('bleeding_diathesis', {})
    bleeding_diathesis_snomed_codes = diathesis_config.get('specific_codes', ['64779008'])
    
    for condition in conditions:
        # 檢查 SNOMED codes
        for coding in condition.get('code', {}).get('coding', []):
            if (coding.get('system') == 'http://snomed.info/sct' and 
                coding.get('code') in bleeding_diathesis_snomed_codes):
                return True, coding.get('display', 'Bleeding diathesis')
        
        # 檢查文字中的出血素質術語
        condition_text = get_condition_text(condition).lower()
        bleeding_keywords = ['bleeding disorder', 'bleeding diathesis', 'hemorrhagic diathesis', 
                           'hemophilia', 'von willebrand', 'coagulation disorder']
        for keyword in bleeding_keywords:
            if keyword in condition_text:
                return True, condition_text
    
    return False, None

def check_prior_bleeding_updated(conditions):
    """
    使用配置中的代碼檢查既往出血史
    
    Args:
        conditions: 條件列表
    
    Returns:
        tuple: (是否有出血史, 出血證據列表)
    """
    # 從配置中獲取 SNOMED codes
    config = get_cdss_config()
    snomed_config = config.get('precise_hbr_snomed_codes', {})
    prior_bleeding_config = snomed_config.get('prior_bleeding', {})
    prior_bleeding_snomed_codes = prior_bleeding_config.get('specific_codes', [])
    
    found_bleeding = []
    
    for condition in conditions:
        # 檢查 SNOMED codes
        for coding in condition.get('code', {}).get('coding', []):
            if (coding.get('system') == 'http://snomed.info/sct' and 
                coding.get('code') in prior_bleeding_snomed_codes):
                found_bleeding.append(coding.get('display', 'Prior bleeding'))
        
        # 檢查文字中的出血術語
        condition_text = get_condition_text(condition).lower()
        bleeding_keywords = ['hemorrhage', 'bleeding', 'hemarthrosis', 'hematuria', 'hemothorax',
                           'hemopericardium', 'hemoperitoneum', 'retroperitoneal hematoma']
        for keyword in bleeding_keywords:
            if keyword in condition_text:
                found_bleeding.append(condition_text)
                break
    
    return len(found_bleeding) > 0, found_bleeding

def check_liver_cirrhosis_portal_hypertension_updated(conditions):
    """
    使用配置中的代碼檢查肝硬化合併門靜脈高壓
    要求同時滿足：
    1. 肝硬化的證據（SNOMED code 或文字）
    2. 門靜脈高壓的證據（腹水、靜脈曲張或腦病變）
    
    Args:
        conditions: 條件列表
    
    Returns:
        tuple: (是否有肝臟狀況, 發現的條件列表)
    """
    # 獲取配置
    config = get_cdss_config()
    snomed_config = config.get('precise_hbr_snomed_codes', {})
    liver_config = snomed_config.get('liver_cirrhosis', {})
    
    cirrhosis_snomed_code = liver_config.get('parent_code', '19943007')
    cirrhosis_keywords = liver_config.get('cirrhosis_keywords', ['cirrhosis'])
    
    pht_config = liver_config.get('portal_hypertension_criteria', {})
    additional_criteria = pht_config.get('additional_criteria', ['ascites', 'portal hypertension', 'esophageal varices', 'hepatic encephalopathy'])
    pht_snomed_codes = pht_config.get('snomed_codes', [])
    
    has_cirrhosis = False
    has_additional_criteria = False
    found_conditions = []
    
    for condition in conditions:
        condition_text = get_condition_text(condition).lower()
        
        # 檢查肝硬化 SNOMED code
        for coding in condition.get('code', {}).get('coding', []):
            code = coding.get('code', '')
            system = coding.get('system', '')
            
            # 檢查肝硬化 SNOMED code
            if system == 'http://snomed.info/sct' and code == cirrhosis_snomed_code:
                has_cirrhosis = True
                found_conditions.append(coding.get('display', 'Liver cirrhosis'))
            
            # 檢查門靜脈高壓 SNOMED codes
            if system == 'http://snomed.info/sct' and code in pht_snomed_codes:
                has_additional_criteria = True
                found_conditions.append(coding.get('display', 'Portal hypertension manifestation'))
        
        # 檢查文字中的肝硬化關鍵詞
        for keyword in cirrhosis_keywords:
            if keyword in condition_text:
                has_cirrhosis = True
                found_conditions.append(f"Found cirrhosis: {condition_text[:50]}...")
                break
        
        # 檢查文字中的門靜脈高壓標準
        for criteria in additional_criteria:
            if criteria in condition_text:
                has_additional_criteria = True
                found_conditions.append(f"Found portal hypertension sign: {criteria}")
                break
    
    # 必須同時有肝硬化和附加標準（門靜脈高壓徵象）
    return (has_cirrhosis and has_additional_criteria), found_conditions

def check_active_cancer_updated(conditions):
    """
    使用配置中的代碼檢查活動性惡性腫瘤疾病
    
    Args:
        conditions: 條件列表
    
    Returns:
        tuple: (是否有活動性癌症, 癌症資訊)
    """
    # 從配置中獲取 SNOMED codes
    config = get_cdss_config()
    snomed_config = config.get('precise_hbr_snomed_codes', {})
    cancer_config = snomed_config.get('active_cancer', {})
    malignancy_parent_code = cancer_config.get('parent_code', '363346000')
    excluded_codes = cancer_config.get('exclude_codes', ['254637007', '254632001'])
    
    for condition in conditions:
        # 首先檢查臨床狀態
        clinical_status = condition.get('clinicalStatus', {})
        if isinstance(clinical_status, dict):
            status_code = None
            for coding in clinical_status.get('coding', []):
                if coding.get('system') == 'http://terminology.hl7.org/CodeSystem/condition-clinical':
                    status_code = coding.get('code')
                    break
        else:
            status_code = str(clinical_status).lower()
        
        # 僅考慮活動狀態
        if status_code != 'active':
            continue
        
        # 檢查 SNOMED codes
        for coding in condition.get('code', {}).get('coding', []):
            if coding.get('system') == 'http://snomed.info/sct':
                code = coding.get('code')
                
                # 排除特定的皮膚癌
                if code in excluded_codes:
                    continue
                
                # 包含惡性腫瘤疾病及其後代
                if code == malignancy_parent_code:
                    return True, coding.get('display', 'Active malignant neoplastic disease')
        
        # 檢查文字中的癌症術語（但仍要求活動狀態）
        condition_text = get_condition_text(condition).lower()
        cancer_keywords = ['cancer', 'malignancy', 'neoplasm', 'carcinoma', 'sarcoma', 'lymphoma', 'leukemia']
        exclusion_keywords = ['basal cell', 'squamous cell', 'skin cancer']
        
        # 檢查是否是排除的皮膚癌
        is_excluded = any(exclusion in condition_text for exclusion in exclusion_keywords)
        if is_excluded:
            continue
        
        # 檢查癌症關鍵詞
        for keyword in cancer_keywords:
            if keyword in condition_text:
                return True, condition_text
    
    return False, None

def check_arc_hbr_factors(raw_data, medications):
    """
    使用更新的 valueset 邏輯檢查 ARC-HBR 風險因素
    
    Args:
        raw_data: 原始 FHIR 資料
        medications: 藥物列表
    
    Returns:
        dict: 包含 has_factors 和發現的因素列表
    """
    factors = []
    conditions = raw_data.get('conditions', [])
    
    # 使用配置中的閾值檢查血小板減少症
    config = get_cdss_config()
    snomed_config = config.get('precise_hbr_snomed_codes', {})
    thrombocytopenia_config = snomed_config.get('thrombocytopenia', {})
    platelet_threshold = thrombocytopenia_config.get('threshold', {}).get('value', 100)
    
    platelets = raw_data.get('PLATELETS', [])
    if platelets:
        plt_obs = platelets[0]
        plt_val = get_value_from_observation(plt_obs, TARGET_UNITS['PLATELETS'])
        if plt_val and plt_val < platelet_threshold:
            factors.append(f"Thrombocytopenia (platelets < {platelet_threshold}×10⁹/L)")
    
    # 使用更新的邏輯檢查慢性出血素質
    has_bleeding_diathesis, bleeding_info = check_bleeding_diathesis_updated(conditions)
    if has_bleeding_diathesis:
        factors.append(f"Chronic bleeding diathesis: {bleeding_info}")
    
    # 使用更新的邏輯檢查活動性惡性腫瘤
    has_active_cancer, cancer_info = check_active_cancer_updated(conditions)
    if has_active_cancer:
        factors.append(f"Active malignancy: {cancer_info}")
    
    # 使用更新的邏輯檢查肝硬化合併門靜脈高壓
    has_liver_condition, liver_info = check_liver_cirrhosis_portal_hypertension_updated(conditions)
    if has_liver_condition:
        factors.append(f"Liver cirrhosis with portal hypertension: {liver_info}")
    
    # 使用配置中的關鍵詞檢查 NSAIDs 或皮質類固醇
    med_config = config.get('medication_keywords', {})
    nsaid_config = med_config.get('nsaids_corticosteroids', {})
    drug_codes = (
        nsaid_config.get('nsaid_keywords', []) + 
        nsaid_config.get('corticosteroid_keywords', [])
    )
    
    for med in medications:
        med_text = str(med.get('medicationCodeableConcept', {})).lower()
        for code in drug_codes:
            if code in med_text:
                factors.append("Long-term NSAIDs or corticosteroids")
                break
    
    return {
        'has_factors': len(factors) > 0,
        'factors': factors
    }

def check_arc_hbr_factors_detailed(raw_data, medications):
    """
    檢查個別 ARC-HBR 風險因素並返回詳細分解
    
    Args:
        raw_data: 原始 FHIR 資料
        medications: 藥物列表
    
    Returns:
        dict: 包含個別因素標記的字典，用於 UI 顯示
    """
    conditions = raw_data.get('conditions', [])
    
    # 使用配置中的閾值檢查血小板減少症
    config = get_cdss_config()
    snomed_config = config.get('precise_hbr_snomed_codes', {})
    thrombocytopenia_config = snomed_config.get('thrombocytopenia', {})
    platelet_threshold = thrombocytopenia_config.get('threshold', {}).get('value', 100)
    
    has_thrombocytopenia = False
    platelets = raw_data.get('PLATELETS', [])
    if platelets:
        plt_obs = platelets[0]
        plt_val = get_value_from_observation(plt_obs, TARGET_UNITS['PLATELETS'])
        if plt_val and plt_val < platelet_threshold:
            has_thrombocytopenia = True
    
    # 檢查慢性出血素質
    has_bleeding_diathesis, _ = check_bleeding_diathesis_updated(conditions)
    
    # 檢查活動性惡性腫瘤
    has_active_cancer, _ = check_active_cancer_updated(conditions)
    
    # 檢查肝硬化合併門靜脈高壓
    has_liver_condition, _ = check_liver_cirrhosis_portal_hypertension_updated(conditions)
    
    # 使用配置中的關鍵詞檢查 NSAIDs 或皮質類固醇
    has_nsaids = False
    med_config = config.get('medication_keywords', {})
    nsaid_config = med_config.get('nsaids_corticosteroids', {})
    drug_codes = (
        nsaid_config.get('nsaid_keywords', []) + 
        nsaid_config.get('corticosteroid_keywords', [])
    )
    
    for med in medications:
        med_text = str(med.get('medicationCodeableConcept', {})).lower()
        for code in drug_codes:
            if code in med_text:
                has_nsaids = True
                break
        if has_nsaids:
            break
    
    # 確定是否存在任何因素
    has_any_factor = any([
        has_thrombocytopenia,
        has_bleeding_diathesis,
        has_active_cancer,
        has_liver_condition,
        has_nsaids
    ])
    
    return {
        'has_any_factor': has_any_factor,
        'thrombocytopenia': has_thrombocytopenia,
        'bleeding_diathesis': has_bleeding_diathesis,
        'active_malignancy': has_active_cancer,
        'liver_cirrhosis': has_liver_condition,
        'nsaids_corticosteroids': has_nsaids
    }

def check_bleeding_history(conditions):
    """
    檢查患者條件中的自發性出血史
    
    Args:
        conditions: 條件列表
    
    Returns:
        tuple: (是否有出血史, 出血證據列表)
    """
    config = get_cdss_config()
    if not config:
        return False, []
    
    # 從統一配置中獲取 SNOMED codes
    snomed_config = config.get('precise_hbr_snomed_codes', {})
    prior_bleeding_codes = snomed_config.get('prior_bleeding', {}).get('specific_codes', [])
    bleeding_keywords = config.get('bleeding_history_keywords', [])
    
    bleeding_evidence = []
    
    # 檢查 SNOMED codes
    for condition in conditions:
        # 檢查編碼條件
        for coding in condition.get('code', {}).get('coding', []):
            system = coding.get('system', '')
            code = coding.get('code', '')
            
            # 對照出血史 SNOMED codes
            if system == 'http://snomed.info/sct' and code in prior_bleeding_codes:
                display = coding.get('display', condition.get('code', {}).get('text', 'Bleeding history'))
                bleeding_evidence.append(display)
                break
        
        # 檢查基於文字的條件
        condition_text = ""
        if condition.get('code', {}).get('text'):
            condition_text += condition['code']['text'].lower().strip() + " "
        for coding in condition.get('code', {}).get('coding', []):
            if coding.get('display'):
                condition_text += coding['display'].lower().strip() + " "
        
        condition_text = condition_text.strip()
        if condition_text:
            for keyword in bleeding_keywords:
                if keyword.lower() in condition_text:
                    display_text = condition.get('code', {}).get('text', 
                                                condition.get('code', {}).get('coding', [{}])[0].get('display', 'Bleeding history'))
                    bleeding_evidence.append(display_text)
                    break
    
    has_bleeding_history = len(bleeding_evidence) > 0
    return has_bleeding_history, bleeding_evidence


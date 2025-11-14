"""
Tradeoff Analysis Calculator
出血-血栓風險權衡分析計算器

基於 ARC-HBR 模型計算出血和血栓風險
"""
import json
import logging
import math
import os

from fhirclient import client
from fhirclient.models import observation, condition, medicationrequest, procedure

from services.cdss_config_loader import get_cdss_config
from services.unit_conversion import TARGET_UNITS, get_value_from_observation
from services.fhir_utils import resource_has_code, calculate_egfr

def get_tradeoff_model_data(fhir_server_url, access_token, client_id, patient_id):
    """
    獲取出血-血栓權衡模型所需的額外資料
    這補充了 get_fhir_data 獲取的資料
    現在創建自己的客戶端以提高穩健性
    
    Args:
        fhir_server_url: FHIR 伺服器 URL
        access_token: 訪問令牌
        client_id: 客戶端 ID
        patient_id: 患者 ID
    
    Returns:
        dict: Tradeoff 資料
    """
    try:
        settings = {
            'app_id': client_id,
            'api_base': fhir_server_url
        }
        fhir_client = client.FHIRClient(settings=settings)
        
        # 這是為 session 設置 header 的正確方式
        import requests
        if not hasattr(fhir_client.server, 'session'):
            fhir_client.server.session = requests.Session()
        fhir_client.server.session.headers["Authorization"] = f"Bearer {access_token}"

    except Exception as e:
        logging.error(f"Failed to create FHIRClient in get_tradeoff_model_data: {e}")
        # 客戶端創建失敗時返回空資料結構
        return {
            "diabetes": False, "prior_mi": False, "smoker": False,
            "nstemi_stemi": False, "complex_pci": False, "bms_used": False,
            "copd": False, "oac_discharge": False
        }

    tradeoff_data = {
        "diabetes": False,
        "prior_mi": False,
        "smoker": False,
        "nstemi_stemi": False,
        "complex_pci": False,
        "bms_used": False,
        "copd": False,
        "oac_discharge": False
    }

    # 使用更廣泛的條件搜尋來查找相關診斷
    try:
        search_params = {'patient': patient_id, '_count': '200'}
        # 注意：fhirclient 的 perform() 不接受 timeout 參數
        # Timeout 通過 session 上的 HTTPAdapter 配置
        conditions = condition.Condition.where(search_params).perform(fhir_client.server)
        
        if conditions.entry:
            for entry in conditions.entry:
                c = entry.resource
                # 從配置中獲取 SNOMED codes
                config = get_cdss_config()
                snomed_codes = config.get('tradeoff_analysis', {}).get('snomed_codes', {})
                
                # 糖尿病
                diabetes_code = snomed_codes.get('diabetes', '73211009')
                if resource_has_code(c.as_json(), 'http://snomed.info/sct', diabetes_code):
                    tradeoff_data["diabetes"] = True
                
                # 心肌梗塞
                mi_code = snomed_codes.get('myocardial_infarction', '22298006')
                if resource_has_code(c.as_json(), 'http://snomed.info/sct', mi_code):
                    tradeoff_data["prior_mi"] = True
                
                # NSTEMI/STEMI
                nstemi_code = snomed_codes.get('nstemi', '164868009')
                stemi_code = snomed_codes.get('stemi', '164869001')
                if resource_has_code(c.as_json(), 'http://snomed.info/sct', nstemi_code) or \
                   resource_has_code(c.as_json(), 'http://snomed.info/sct', stemi_code):
                    tradeoff_data["nstemi_stemi"] = True
                
                # COPD
                copd_code = snomed_codes.get('copd', '13645005')
                if resource_has_code(c.as_json(), 'http://snomed.info/sct', copd_code):
                    tradeoff_data["copd"] = True

    except Exception as e:
        logging.warning(f"Error fetching conditions for tradeoff model: {e}")

    # 從 Observations 檢查吸菸狀態
    try:
        search_params = {'patient': patient_id, 'code': '72166-2'}  # Smoking status LOINC
        # 注意：fhirclient 的 perform() 不接受 timeout 參數
        # Timeout 通過 session 上的 HTTPAdapter 配置
        obs_search = observation.Observation.where(search_params).perform(fhir_client.server)
        if obs_search and obs_search.entry:
            # 按日期安全排序
            sorted_obs = []
            for entry in obs_search.entry:
                if entry.resource:
                    # 使用安全的方式獲取日期，帶降級
                    date_str = '1900-01-01' # 降級
                    if hasattr(entry.resource, 'effectiveDateTime') and entry.resource.effectiveDateTime:
                        date_str = entry.resource.effectiveDateTime.isostring
                    elif hasattr(entry.resource, 'effectivePeriod') and entry.resource.effectivePeriod and entry.resource.effectivePeriod.start:
                        date_str = entry.resource.effectivePeriod.start.isostring
                    sorted_obs.append((date_str, entry.resource))
            
            if sorted_obs:
                sorted_obs.sort(key=lambda x: x[0], reverse=True)
                latest_obs = sorted_obs[0][1] # 獲取資源部分
                # 檢查當前吸菸者代碼
                if latest_obs.valueCodeableConcept and latest_obs.valueCodeableConcept.coding:
                    if latest_obs.valueCodeableConcept.coding[0].code in ['449868002', 'LA18978-9']: 
                        tradeoff_data["smoker"] = True
    except Exception as e:
        logging.warning(f"Error fetching smoking status: {e}", exc_info=True)

    # 從 Procedures 檢查複雜 PCI 和 BMS
    try:
        search_params = {'patient': patient_id, '_count': '50'}
        # 注意：fhirclient 的 perform() 不接受 timeout 參數
        # Timeout 通過 session 上的 HTTPAdapter 配置
        procedures = procedure.Procedure.where(search_params).perform(fhir_client.server)
        if procedures.entry:
            # 從配置中獲取 SNOMED codes
            config = get_cdss_config()
            snomed_codes = config.get('tradeoff_analysis', {}).get('snomed_codes', {})
            complex_pci_code = snomed_codes.get('complex_pci', '397682003')
            bms_code = snomed_codes.get('bare_metal_stent', '427183000')
            
            for entry in procedures.entry:
                p = entry.resource
                # 複雜 PCI
                if resource_has_code(p.as_json(), 'http://snomed.info/sct', complex_pci_code):
                    tradeoff_data["complex_pci"] = True
                # 裸金屬支架 (BMS)
                if resource_has_code(p.as_json(), 'http://snomed.info/sct', bms_code):
                    tradeoff_data["bms_used"] = True
    except Exception as e:
        logging.warning(f"Error fetching procedures for tradeoff model: {e}")
        
    # 從 MedicationRequest 檢查出院時的 OAC
    try:
        search_params = {'patient': patient_id, 'category': 'outpatient'}
        # 注意：fhirclient 的 perform() 不接受 timeout 參數
        # Timeout 通過 session 上的 HTTPAdapter 配置
        med_requests = medicationrequest.MedicationRequest.where(search_params).perform(fhir_client.server)
        if med_requests.entry:
            # 從配置中獲取 RxNorm codes
            config = get_cdss_config()
            rxnorm_codes = config.get('tradeoff_analysis', {}).get('rxnorm_codes', {})
            oac_codes = [
                rxnorm_codes.get('warfarin', '11289'),
                rxnorm_codes.get('rivaroxaban', '21821'),
                rxnorm_codes.get('apixaban', '1364430'),
                rxnorm_codes.get('dabigatran', '1037042'),
                rxnorm_codes.get('edoxaban', '1537033')
            ]
            
            for entry in med_requests.entry:
                mr = entry.resource
                # 檢查口服抗凝劑
                if any(resource_has_code(mr.as_json(), 'http://www.nlm.nih.gov/research/umls/rxnorm', code) for code in oac_codes):
                    tradeoff_data["oac_discharge"] = True
    except Exception as e:
        logging.warning(f"Error fetching medication requests for OAC: {e}")

    return tradeoff_data

def get_tradeoff_model_predictors():
    """
    從 ARC-HBR 模型檔案載入並返回所有預測因子列表
    
    Returns:
        dict or None: 模型字典，如果載入失敗則為 None
    """
    script_dir = os.path.dirname(os.path.dirname(__file__))  # 回到主目錄
    model_path = os.path.join(script_dir, 'fhir_resources', 'valuesets', 'arc-hbr-model.json')
    
    # 添加詳細日誌以進行雲端部署調試
    logging.info(f"Attempting to load tradeoff model from: {model_path}")
    logging.info(f"Script directory: {script_dir}")
    logging.info(f"File exists: {os.path.exists(model_path)}")
    
    try:
        with open(model_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logging.info(f"JSON loaded successfully. Keys: {list(data.keys())}")
            
            if 'tradeoffModel' not in data:
                logging.error(f"'tradeoffModel' key not found in JSON. Available keys: {list(data.keys())}")
                return None
                
            model = data['tradeoffModel']
            logging.info(f"Tradeoff model loaded successfully. Bleeding predictors: {len(model.get('bleedingEvents', {}).get('predictors', []))}")
            logging.info(f"Thrombotic predictors: {len(model.get('thromboticEvents', {}).get('predictors', []))}")
            return model
            
    except FileNotFoundError as e:
        logging.error(f"File not found: {model_path}. Error: {e}")
        # 列出目錄中的檔案以進行調試
        try:
            files = os.listdir(script_dir)
            logging.error(f"Files in directory {script_dir}: {files}")
        except Exception as list_error:
            logging.error(f"Could not list directory contents: {list_error}")
        return None
    except KeyError as e:
        logging.error(f"Key error when parsing JSON: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error loading tradeoff model: {e}")
        return None

def detect_tradeoff_factors(raw_data, demographics, tradeoff_data):
    """
    根據患者資料檢測存在哪些權衡因素
    
    Args:
        raw_data: 原始 FHIR 資料
        demographics: 人口統計資料
        tradeoff_data: Tradeoff 資料
    
    Returns:
        dict: 檢測到的因素鍵的字典
    """
    detected_factors = {}
    
    # 從配置中獲取閾值
    config = get_cdss_config()
    tradeoff_config = config.get('tradeoff_analysis', {})
    thresholds = tradeoff_config.get('risk_factor_thresholds', {})
    
    # 年齡閾值
    age_threshold = thresholds.get('age_threshold', 65)
    if demographics.get('age', 0) >= age_threshold:
        detected_factors['age_ge_65'] = True

    # 血紅蛋白閾值
    hb_obs = raw_data.get('HEMOGLOBIN', [])
    if hb_obs:
        hb_val = get_value_from_observation(hb_obs[0], TARGET_UNITS['HEMOGLOBIN'])
        if hb_val:
            hb_ranges = thresholds.get('hemoglobin_ranges', {})
            moderate = hb_ranges.get('moderate', {'min': 11, 'max': 13})
            severe = hb_ranges.get('severe', {'max': 11})
            
            if moderate['min'] <= hb_val < moderate['max']:
                detected_factors['hemoglobin_11_12.9'] = True
            elif hb_val < severe['max']:
                detected_factors['hemoglobin_lt_11'] = True

    # eGFR 閾值
    egfr_obs = raw_data.get('EGFR', [])
    cr_obs = raw_data.get('CREATININE', [])
    egfr_val = None
    if egfr_obs:
        egfr_val = get_value_from_observation(egfr_obs[0], TARGET_UNITS['EGFR'])
    elif cr_obs:
        cr_val = get_value_from_observation(cr_obs[0], TARGET_UNITS['CREATININE'])
        if cr_val and demographics.get('age') and demographics.get('gender'):
            egfr_val, _ = calculate_egfr(cr_val, demographics['age'], demographics['gender'])
            
    if egfr_val:
        egfr_ranges = thresholds.get('egfr_ranges', {})
        moderate = egfr_ranges.get('moderate', {'min': 30, 'max': 60})
        severe = egfr_ranges.get('severe', {'max': 30})
        
        if moderate['min'] <= egfr_val < moderate['max']:
            detected_factors['egfr_30_59'] = True
        elif egfr_val < severe['max']:
            detected_factors['egfr_lt_30'] = True
    
    if tradeoff_data.get('diabetes'):
        detected_factors['diabetes'] = True
    if tradeoff_data.get('prior_mi'):
        detected_factors['prior_mi'] = True
    if tradeoff_data.get('smoker'):
        detected_factors['smoker'] = True
    if tradeoff_data.get('nstemi_stemi'):
        detected_factors['nstemi_stemi'] = True
    if tradeoff_data.get('complex_pci'):
        detected_factors['complex_pci'] = True
    if tradeoff_data.get('bms_used'):
        detected_factors['bms'] = True
    if tradeoff_data.get('copd'):
        detected_factors['copd'] = True
    if tradeoff_data.get('oac_discharge'):
        detected_factors['oac_discharge'] = True
        
    return detected_factors

def convert_hr_to_probability(total_hr_score, baseline_event_rate):
    """
    將總 Hazard Ratio (HR) 分數轉換為估計的 1 年事件機率
    
    使用 Cox 比例風險模型：
    P(事件) = 1 - exp(-baseline_hazard × HR)
    
    其中 baseline_hazard 從基線事件率導出：
    baseline_hazard ≈ -ln(1 - baseline_rate)
    
    這確保了：
    1. 當 HR = 1 時，P(事件) = baseline_rate
    2. 當 HR 增加時，P(事件) 非線性增加（更真實）
    3. P(事件) 永遠不會超過 100%
    
    這比簡單的線性縮放更準確，特別是當 HR > 2 時
    
    Args:
        total_hr_score: 總 HR 分數
        baseline_event_rate: 基線事件率（百分比）
    
    Returns:
        float: 事件機率（百分比）
    """
    # 將基線事件率（百分比）轉換為基線風險
    # 公式：baseline_hazard = -ln(1 - baseline_rate/100)
    baseline_rate_decimal = baseline_event_rate / 100.0  # 將 % 轉換為小數
    
    # 處理邊緣情況：如果 baseline_rate 為 100%，風險將是無限的
    if baseline_rate_decimal >= 1.0:
        return 100.0
    
    # 計算基線風險（1 年的累積風險）
    baseline_hazard = -math.log(1 - baseline_rate_decimal)
    
    # 應用 HR 獲得調整後的風險
    adjusted_hazard = baseline_hazard * total_hr_score
    
    # 使用生存函數轉換回機率
    # P(事件) = 1 - S(t) = 1 - exp(-H(t))
    # 其中 H(t) 是累積風險
    survival_probability = math.exp(-adjusted_hazard)
    event_probability = 1 - survival_probability
    
    # 轉換為百分比並四捨五入
    event_probability_percent = event_probability * 100.0
    
    return round(min(event_probability_percent, 100.0), 2)  # 上限為 100%

def calculate_tradeoff_scores_interactive(model_predictors, active_factors):
    """
    計算出血和血栓分數並將其轉換為機率
    'active_factors' 是一個字典，如 {'smoker': true, 'diabetes': false}
    
    修正：對 Hazard Ratios 使用乘法模型（Cox 比例風險模型）
    總 HR = HR₁ × HR₂ × HR₃ × ...（或對數 HR 的總和）
    
    Args:
        model_predictors: 模型預測因子
        active_factors: 活躍因素字典
    
    Returns:
        dict: 包含出血和血栓分數及因素的字典
    """
    # 從配置中獲取基線事件率
    config = get_cdss_config()
    tradeoff_config = config.get('tradeoff_analysis', {})
    baseline_rates = tradeoff_config.get('baseline_event_rates', {})
    BASELINE_BLEEDING_RATE = baseline_rates.get('bleeding_rate_percent', 2.5)
    BASELINE_THROMBOTIC_RATE = baseline_rates.get('thrombotic_rate_percent', 2.5)

    # 使用乘法模型：從 HR = 1 開始（無風險因素）
    bleeding_score_hr = 1.0
    thrombotic_score_hr = 1.0
    
    bleeding_factors_details = []
    thrombotic_factors_details = []

    # 以 HR 計算出血分數（修正：乘以 HR）
    for predictor in model_predictors['bleedingEvents']['predictors']:
        factor_key = predictor['factor']
        if active_factors.get(factor_key, False):
            bleeding_score_hr *= predictor['hazardRatio']  # ✅ 乘法，不是加法
            bleeding_factors_details.append(f"{predictor['description']} (HR: {predictor['hazardRatio']})")
    
    # 以 HR 計算血栓分數（修正：乘以 HR）
    for predictor in model_predictors['thromboticEvents']['predictors']:
        factor_key = predictor['factor']
        if active_factors.get(factor_key, False):
            thrombotic_score_hr *= predictor['hazardRatio']  # ✅ 乘法，不是加法
            thrombotic_factors_details.append(f"{predictor['description']} (HR: {predictor['hazardRatio']})")

    # 將 HR 分數轉換為機率
    # 使用更準確的公式：風險 = 1 - exp(-baseline_hazard × HR × time)
    # 為簡單起見，近似：風險 ≈ baseline_rate × HR（當風險較低時有效）
    bleeding_prob = convert_hr_to_probability(bleeding_score_hr, BASELINE_BLEEDING_RATE)
    thrombotic_prob = convert_hr_to_probability(thrombotic_score_hr, BASELINE_THROMBOTIC_RATE)

    return {
        "bleeding_score": bleeding_prob,
        "thrombotic_score": thrombotic_prob,
        "bleeding_factors": bleeding_factors_details,
        "thrombotic_factors": thrombotic_factors_details
    }

def calculate_tradeoff_scores(raw_data, demographics, tradeoff_data):
    """
    根據 ARC-HBR 權衡模型計算出血和血栓風險分數
    
    Args:
        raw_data: 原始 FHIR 資料
        demographics: 人口統計資料
        tradeoff_data: Tradeoff 資料
    
    Returns:
        dict: 包含出血和血栓分數及因素的字典
    """
    # 構建相對於此腳本的路徑以避免生產中的 FileNotFoundError
    script_dir = os.path.dirname(os.path.dirname(__file__))  # 回到主目錄
    model_path = os.path.join(script_dir, 'fhir_resources', 'valuesets', 'arc-hbr-model.json')
    
    # 添加詳細日誌以進行調試
    logging.info(f"Loading tradeoff model from: {model_path}")
    logging.info(f"File exists: {os.path.exists(model_path)}")
    
    try:
        with open(model_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'tradeoffModel' not in data:
                logging.error(f"'tradeoffModel' key not found in JSON")
                return {
                    "error": "Invalid model file structure.",
                    "bleeding_score": 0,
                    "thrombotic_score": 0,
                    "bleeding_factors": [],
                    "thrombotic_factors": []
                }
            model = data['tradeoffModel']
            logging.info(f"Tradeoff model loaded successfully in calculate_tradeoff_scores")
    except FileNotFoundError:
        logging.error(f"CRITICAL: arc-hbr-model.json not found at {model_path}. Tradeoff calculation will fail.")
        return {
            "error": "ARC-HBR model file not found on server.",
            "bleeding_score": 0,
            "thrombotic_score": 0,
            "bleeding_factors": [],
            "thrombotic_factors": []
        }
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error in calculate_tradeoff_scores: {e}")
        return {
            "error": "Invalid JSON in model file.",
            "bleeding_score": 0,
            "thrombotic_score": 0,
            "bleeding_factors": [],
            "thrombotic_factors": []
        }

    # 修正：對 Cox 比例風險使用乘法模型
    bleeding_score = 1.0  # 從 HR = 1 開始（無風險因素）
    thrombotic_score = 1.0  # 從 HR = 1 開始（無風險因素）
    
    bleeding_factors = []
    thrombotic_factors = []

    # 輔助函數以乘以分數並記錄因素（修正）
    def add_score(event_type, factor, ratio):
        nonlocal bleeding_score, thrombotic_score
        if event_type == 'bleeding':
            bleeding_score *= ratio  # ✅ 乘法，不是加法
            bleeding_factors.append(f"{factor} (HR: {ratio})")
        else:
            thrombotic_score *= ratio  # ✅ 乘法，不是加法
            thrombotic_factors.append(f"{factor} (HR: {ratio})")

    # 人口統計
    if demographics.get('age', 0) >= 65:
        add_score('bleeding', 'Age >= 65', 1.50)

    # 血紅蛋白
    hb_obs = raw_data.get('HEMOGLOBIN', [])
    if hb_obs:
        hb_val = get_value_from_observation(hb_obs[0], TARGET_UNITS['HEMOGLOBIN'])
        if hb_val and 11 <= hb_val < 13:
            add_score('bleeding', 'Hb 11-12.9', 1.69)
            add_score('thrombotic', 'Hb 11-12.9', 1.27)
        elif hb_val and hb_val < 11:
            add_score('bleeding', 'Hb < 11', 3.99)
            add_score('thrombotic', 'Hb < 11', 1.50)

    # eGFR
    egfr_obs = raw_data.get('EGFR', [])
    if egfr_obs:
        egfr_val = get_value_from_observation(egfr_obs[0], TARGET_UNITS['EGFR'])
        if egfr_val and 30 <= egfr_val < 60:
             add_score('thrombotic', 'eGFR 30-59', 1.30)
        elif egfr_val and egfr_val < 30:
            add_score('bleeding', 'eGFR < 30', 1.43)
            add_score('thrombotic', 'eGFR < 30', 1.69)
            
    # Tradeoff 資料
    if tradeoff_data.get('diabetes'):
        add_score('thrombotic', 'Diabetes', 1.56)
    if tradeoff_data.get('prior_mi'):
        add_score('thrombotic', 'Prior MI', 1.89)
    if tradeoff_data.get('smoker'):
        add_score('bleeding', 'Smoker', 1.47)
        add_score('thrombotic', 'Smoker', 1.48)
    if tradeoff_data.get('nstemi_stemi'):
        add_score('thrombotic', 'NSTEMI/STEMI', 1.82)
    if tradeoff_data.get('complex_pci'):
        add_score('bleeding', 'Complex PCI', 1.32)
        add_score('thrombotic', 'Complex PCI', 1.50)
    if tradeoff_data.get('bms_used'):
        add_score('thrombotic', 'BMS Used', 1.53)
    if tradeoff_data.get('copd'):
        add_score('bleeding', 'COPD', 1.39)
    if tradeoff_data.get('oac_discharge'):
        add_score('bleeding', 'OAC at Discharge', 2.00)

    # 使用更新的基線率將 HR 分數轉換為機率
    # 基於 Galli M, et al. JAMA Cardiology 2021
    config = get_cdss_config()
    tradeoff_config = config.get('tradeoff_analysis', {})
    baseline_rates = tradeoff_config.get('baseline_event_rates', {})
    BASELINE_BLEEDING_RATE = baseline_rates.get('bleeding_rate_percent', 2.5)  # %（BARC 3-5 出血，1 年風險，參考組）
    BASELINE_THROMBOTIC_RATE = baseline_rates.get('thrombotic_rate_percent', 2.5)  # %（MI/ST，1 年風險，參考組）
    
    bleeding_prob = convert_hr_to_probability(bleeding_score, BASELINE_BLEEDING_RATE)
    thrombotic_prob = convert_hr_to_probability(thrombotic_score, BASELINE_THROMBOTIC_RATE)

    return {
        "bleeding_score": bleeding_prob,  # 現在返回機率 (%)，不是 HR
        "thrombotic_score": thrombotic_prob,  # 現在返回機率 (%)，不是 HR
        "bleeding_factors": bleeding_factors,
        "thrombotic_factors": thrombotic_factors
    }


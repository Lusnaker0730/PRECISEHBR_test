"""
FHIR Data Service - 主入口點
重構後的模組化版本

此檔案作為統一入口點，協調所有子模組的功能
原始 1926 行代碼已拆分為 7 個專注的模組
"""
import logging

# 導入新模組
from services.cdss_config_loader import get_loinc_codes, get_text_search_terms
from services.unit_conversion import TARGET_UNITS, get_value_from_observation
from services.fhir_utils import get_patient_demographics, get_active_medications, check_medication_interactions_bleeding_risk
from services.condition_checkers import check_bleeding_history
from services.fhir_client import (
    setup_fhir_client,
    fetch_patient_resource,
    fetch_observations_by_loinc,
    fetch_observations_by_text,
    fetch_conditions
)
from services.precise_hbr_calculator import (
    calculate_precise_hbr_score,
    calculate_bleeding_risk_percentage,
    get_risk_category_info,
    get_precise_hbr_display_info,
    calculate_risk_components
)
from services.tradeoff_calculator import (
    get_tradeoff_model_data,
    get_tradeoff_model_predictors,
    detect_tradeoff_factors,
    convert_hr_to_probability,
    calculate_tradeoff_scores_interactive,
    calculate_tradeoff_scores
)

# 重新導出常用的常量和函數，保持向後兼容性
__all__ = [
    # 主要函數
    'get_fhir_data',
    'get_patient_demographics',
    'calculate_risk_components',
    'calculate_precise_hbr_score',
    'calculate_bleeding_risk_percentage',
    'get_risk_category_info',
    'get_precise_hbr_display_info',
    'calculate_tradeoff_scores',
    'get_tradeoff_model_data',
    'get_tradeoff_model_predictors',
    'detect_tradeoff_factors',
    'calculate_tradeoff_scores_interactive',
    # 輔助函數
    'get_value_from_observation',
    'check_bleeding_history',
    'get_active_medications',
    'check_medication_interactions_bleeding_risk',
    # 常量
    'TARGET_UNITS',
]

# 獲取配置的 LOINC codes 和文字搜尋詞彙
LOINC_CODES = get_loinc_codes()
TEXT_SEARCH_TERMS = get_text_search_terms()

def get_fhir_data(fhir_server_url, access_token, patient_id, client_id):
    """
    使用 fhirclient 函式庫獲取所有所需的患者資料
    這提供了與各種 FHIR 伺服器（包括 Cerner）更好的兼容性
    
    Args:
        fhir_server_url: FHIR 伺服器 URL
        access_token: 訪問令牌
        patient_id: 患者 ID
        client_id: 客戶端 ID
    
    Returns:
        tuple: (FHIR 資源字典, 錯誤訊息)
    """
    try:
        # 設置 FHIR 客戶端
        smart, is_test_mode = setup_fhir_client(
            fhir_server_url, 
            access_token, 
            patient_id, 
            client_id
        )
        
        # 首先獲取患者資源以測試連接
        try:
            patient_resource_json = fetch_patient_resource(patient_id, smart.server)
        except Exception as e:
            # fetch_patient_resource 已經提供了詳細的錯誤訊息
            return None, str(e)

        raw_data = {"patient": patient_resource_json}
        
        # 按 LOINC codes 獲取 PRECISE-HBR 參數的觀察資料
        for resource_type, codes in LOINC_CODES.items():
            obs_list = []
            
            try:
                # 首先，嘗試按 LOINC codes 搜尋
                obs_list = fetch_observations_by_loinc(
                    patient_id,
                    resource_type,
                    codes,
                    smart.server
                )
                
                # 如果 LOINC codes 沒有結果，嘗試文字搜尋作為降級
                if not obs_list and resource_type in TEXT_SEARCH_TERMS:
                    obs_list = fetch_observations_by_text(
                        patient_id,
                        resource_type,
                        TEXT_SEARCH_TERMS[resource_type],
                        smart.server
                    )
                
                raw_data[resource_type] = obs_list
                if obs_list:
                    logging.info(f"Final result: {len(obs_list)} {resource_type} observation(s)")
                else:
                    logging.warning(f"No {resource_type} observations found for patient {patient_id}")
                
            except Exception as e:
                # 淨化日誌
                logging.warning(f"Error fetching {resource_type} for patient {patient_id}. Type: {type(e).__name__}. Continuing with empty list.")
                raw_data[resource_type] = []
        
        # 獲取條件（用於出血史）
        raw_data['conditions'] = fetch_conditions(patient_id, smart.server)
        
        # 獲取最少的藥物資料以保持兼容性
        raw_data['med_requests'] = []
        raw_data['procedures'] = []

        return raw_data, None

    except Exception as e:
        # 淨化頂層異常的日誌
        logging.error(f"An unexpected error occurred in get_fhir_data. Error type: {type(e).__name__}", exc_info=False)
        return None, "An unexpected error occurred while fetching FHIR data."

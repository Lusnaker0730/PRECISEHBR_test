"""
FHIR Client Module
FHIR 資料獲取和客戶端管理
"""
import logging
from fhirclient import client
from fhirclient.models import patient, observation, condition, medicationrequest, procedure

from services.cdss_config_loader import get_loinc_codes, get_text_search_terms
from services.fhir_utils import resource_has_code

# 獲取配置的 LOINC codes 和文字搜尋詞彙
LOINC_CODES = get_loinc_codes()
TEXT_SEARCH_TERMS = get_text_search_terms()

def setup_fhir_client(fhir_server_url, access_token, patient_id, client_id):
    """
    設置並配置 FHIR 客戶端
    
    Args:
        fhir_server_url: FHIR 伺服器 URL
        access_token: 訪問令牌
        patient_id: 患者 ID
        client_id: 客戶端 ID
    
    Returns:
        tuple: (FHIR client, is_test_mode)
    """
    # 檢測測試模式（用於開發/測試，無需 OAuth）
    is_test_mode = (access_token == 'test-mode-no-auth')
    
    if is_test_mode:
        logging.info(f"TEST MODE: Fetching data without authentication from {fhir_server_url}")
    
    # 按照 smart-on-fhir/client-py 最佳實踐設置 FHIR 客戶端
    settings = {
        'app_id': client_id,
        'api_base': fhir_server_url,
        'patient_id': patient_id,
    }
    
    # 創建 FHIR 客戶端實例
    smart = client.FHIRClient(settings=settings)
    
    # 設置授權
    if access_token and not is_test_mode:
        _setup_authenticated_client(smart, access_token)
    elif is_test_mode:
        _setup_test_mode_client(smart)
    
    # 為 session 設置自定義 adapter 和 timeout（適用於兩種模式）
    _setup_timeout_adapter(smart, is_test_mode, access_token)
    
    return smart, is_test_mode

def _setup_authenticated_client(smart, access_token):
    """設置已認證的客戶端"""
    smart.prepare()
    
    if hasattr(smart.server, 'prepare'):
        smart.server.prepare()
    
    smart.server.auth = None  # 清除任何現有的認證
    
    # 為 FHIR 請求設置適當的 headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/fhir+json, application/json',
        'Content-Type': 'application/fhir+json'
    }
    
    # 使用伺服器的 session 設置 headers
    if hasattr(smart.server, 'session'):
        smart.server.session.headers.update(headers)
    else:
        import requests
        smart.server.session = requests.Session()
        smart.server.session.headers.update(headers)

def _setup_test_mode_client(smart):
    """設置測試模式客戶端（無認證）"""
    import requests
    smart.prepare()
    
    if not hasattr(smart.server, 'session'):
        smart.server.session = requests.Session()
    
    # 設置不帶 Authorization 的 headers
    headers = {
        'Accept': 'application/fhir+json, application/json',
        'Content-Type': 'application/fhir+json'
    }
    smart.server.session.headers.update(headers)
    logging.info("TEST MODE: Session configured for public FHIR access")

def _setup_timeout_adapter(smart, is_test_mode, access_token):
    """為 session 設置自定義 timeout adapter"""
    if hasattr(smart.server, 'session'):
        import requests
        from requests.adapters import HTTPAdapter
        
        # 配置帶有更長 timeout 的自定義 adapter
        class TimeoutHTTPAdapter(HTTPAdapter):
            def __init__(self, *args, **kwargs):
                self.timeout = kwargs.pop('timeout', 60)  # 60 秒默認值
                super().__init__(*args, **kwargs)
            
            def send(self, request, **kwargs):
                kwargs['timeout'] = kwargs.get('timeout', self.timeout)
                return super().send(request, **kwargs)
        
        # 將 adapter 掛載到 HTTP 和 HTTPS
        adapter = TimeoutHTTPAdapter(timeout=90)  # condition 查詢 90 秒
        smart.server.session.mount('http://', adapter)
        smart.server.session.mount('https://', adapter)
        
        if not is_test_mode:
            # 為向後兼容也設置 _auth（僅生產模式）
            smart.server._auth = None  # 清除舊的認證
            logging.info(f"Set authorization header with token length: {len(access_token)}")
        logging.info(f"FHIR Server prepared for: {smart.server.base_uri if hasattr(smart.server, 'base_uri') else 'unknown'}")

def fetch_patient_resource(patient_id, fhir_server):
    """
    獲取患者資源
    
    Args:
        patient_id: 患者 ID
        fhir_server: FHIR 伺服器實例
    
    Returns:
        dict: 患者資源的 JSON
    
    Raises:
        Exception: 如果獲取失敗
    """
    logging.info(f"Attempting to fetch patient {patient_id}")
    
    try:
        # 使用標準 fhirclient Patient.read 方法
        patient_resource = patient.Patient.read(patient_id, fhir_server)
        logging.info(f"Successfully fetched Patient resource for patient: {patient_id}")
        return patient_resource.as_json()
    except Exception as e:
        error_msg = str(e)
        # 淨化日誌以防止 ePHI 洩漏
        logging.error(f"Error fetching patient resource for patient_id: {patient_id}. Status code or error type: {type(e).__name__}")
        
        # 記錄額外的調試資訊
        if hasattr(fhir_server, 'session') and hasattr(fhir_server.session, 'headers'):
            headers_dict = dict(fhir_server.session.headers)
            # 出於安全考慮，不要記錄完整的 token
            if 'Authorization' in headers_dict:
                headers_dict['Authorization'] = 'Bearer ***REDACTED***'
            logging.info(f"Request headers: {headers_dict}")
        
        # 記錄正在調用的確切 URL
        if hasattr(fhir_server, 'base_uri'):
            logging.info(f"Base URI: {fhir_server.base_uri}")
        
        # 提供具體的錯誤訊息
        if '401' in error_msg:
            logging.error(f"Authentication failed - Access token may be expired or invalid")
            if 'expired' in error_msg.lower():
                raise Exception(f"Access token has expired. Please re-launch the application from your EHR.")
            elif 'invalid' in error_msg.lower():
                raise Exception(f"Access token is invalid. Please re-launch the application from your EHR.")
            else:
                raise Exception(f"Authentication failed. Please re-launch the application from your EHR. Details: {str(e)}")
        elif '403' in error_msg:
            logging.error(f"Permission denied - Insufficient scope or patient access")
            raise Exception(f"Access denied. The application may not have permission to access this patient's data. Please check the application's scope configuration.")
        elif '404' in error_msg:
            logging.error(f"Patient not found")
            raise Exception(f"Patient {patient_id} not found in the FHIR server.")
        else:
            logging.error(f"Failed to fetch patient resource")
            # 也淨化返回的錯誤訊息
            raise Exception(f"Failed to retrieve patient data. Error type: {type(e).__name__}")

def fetch_observations_by_loinc(patient_id, resource_type, codes, fhir_server):
    """
    透過 LOINC codes 獲取觀察資料
    
    Args:
        patient_id: 患者 ID
        resource_type: 資源類型（如 'HEMOGLOBIN'）
        codes: LOINC codes 列表
        fhir_server: FHIR 伺服器實例
    
    Returns:
        list: 觀察資料列表（最新的一筆）
    """
    obs_list = []
    
    if not codes:
        return obs_list
    
    try:
        search_params = {
            'patient': patient_id,
            'code': ','.join(codes),
            '_count': '5'  # 獲取幾筆結果以找到最新的
        }
        
        observations = observation.Observation.where(search_params).perform(fhir_server)
        
        if observations.entry:
            # 在記憶體中按有效日期排序（比 _sort 參數更兼容）
            sorted_entries = []
            for entry in observations.entry:
                if entry.resource:
                    resource_json = entry.resource.as_json()
                    # 提取日期以進行排序
                    date_str = resource_json.get('effectiveDateTime') or resource_json.get('effectivePeriod', {}).get('start') or '1900-01-01'
                    sorted_entries.append((date_str, resource_json))
            
            # 按日期排序（最近的優先）並取第一筆
            sorted_entries.sort(key=lambda x: x[0], reverse=True)
            if sorted_entries:
                obs_list.append(sorted_entries[0][1])  # 取最新的
                logging.info(f"Successfully fetched {resource_type} observation by LOINC code")
    except Exception as e:
        logging.debug(f"LOINC code search failed for {resource_type}: {type(e).__name__}")
    
    return obs_list

def fetch_observations_by_text(patient_id, resource_type, text_terms, fhir_server):
    """
    透過文字搜尋獲取觀察資料
    
    Args:
        patient_id: 患者 ID
        resource_type: 資源類型
        text_terms: 文字搜尋詞彙列表
        fhir_server: FHIR 伺服器實例
    
    Returns:
        list: 觀察資料列表（最新的一筆）
    """
    obs_list = []
    
    if not text_terms:
        return obs_list
    
    logging.info(f"No results from LOINC codes for {resource_type}, attempting text search with terms: {text_terms}")
    
    # 嘗試每個文字搜尋詞彙
    for term in text_terms:
        try:
            text_search_params = {
                'patient': patient_id,
                'code:text': term,
                '_count': '5'
            }
            
            text_observations = observation.Observation.where(text_search_params).perform(fhir_server)
            
            if text_observations.entry:
                sorted_entries = []
                for entry in text_observations.entry:
                    if entry.resource:
                        resource_json = entry.resource.as_json()
                        date_str = resource_json.get('effectiveDateTime') or resource_json.get('effectivePeriod', {}).get('start') or '1900-01-01'
                        sorted_entries.append((date_str, resource_json))
                
                sorted_entries.sort(key=lambda x: x[0], reverse=True)
                if sorted_entries:
                    obs_list.append(sorted_entries[0][1])
                    logging.info(f"Successfully fetched {resource_type} observation by text search: '{term}'")
                    break  # 找到結果，停止搜尋
        except Exception as text_error:
            logging.debug(f"Text search failed for term '{term}': {type(text_error).__name__}")
            continue
    
    return obs_list

def fetch_conditions(patient_id, fhir_server):
    """
    獲取條件資料（用於出血史）
    
    Args:
        patient_id: 患者 ID
        fhir_server: FHIR 伺服器實例
    
    Returns:
        list: 條件資料列表
    """
    conditions_list = []
    
    try:
        logging.info(f"Attempting to fetch conditions with _count=100 for patient {patient_id} (90s timeout)")
        conditions_search = condition.Condition.where({
            'patient': patient_id,
            '_count': '100'  # 以延長的 timeout 獲取 100 個條件
        }).perform(fhir_server)
        
        if conditions_search.entry:
            for entry in conditions_search.entry:  # 處理所有返回的條件
                if entry.resource:
                    conditions_list.append(entry.resource.as_json())
        
        logging.info(f"Successfully fetched {len(conditions_list)} condition(s) with _count=100")
    except Exception as e:
        error_str = str(e)
        if '504' in error_str or 'timeout' in error_str.lower() or 'gateway time-out' in error_str.lower():
            logging.error(f"Timeout error fetching conditions for patient {patient_id}. Error type: {type(e).__name__}")
            logging.info("This suggests the FHIR server is very slow or overloaded")
        elif '401' in error_str or '403' in error_str:
            logging.error(f"Permission error fetching conditions for patient {patient_id}. Error type: {type(e).__name__}")
        else:
            logging.error(f"Unexpected error fetching conditions for patient {patient_id}. Error type: {type(e).__name__}")
        
        logging.warning(f"Continuing with empty conditions list for patient {patient_id} due to a server error.")
    
    return conditions_list


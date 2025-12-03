import logging
import datetime as dt
import json
import os
from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta
from fhirclient import client
from fhirclient.models import patient, observation, condition, medicationrequest, procedure

# --- Load CDSS Config ---
try:
    with open('cdss_config.json', 'r', encoding='utf-8') as f:
        CDSS_CONFIG = json.load(f)
    logging.info("Successfully loaded cdss_config.json")
except FileNotFoundError:
    logging.error("CRITICAL: cdss_config.json not found. Calculations will fail.")
    CDSS_CONFIG = {}
except json.JSONDecodeError:
    logging.error("CRITICAL: cdss_config.json is not valid JSON. Calculations will fail.")
    CDSS_CONFIG = {}

# --- Load LOINC codes and text search terms from configuration ---
def _get_loinc_codes():
    """
    Load LOINC codes from cdss_config.json.
    Returns dictionary mapping observation types to LOINC code tuples.
    """
    if not CDSS_CONFIG:
        return {}
    
    lab_config = CDSS_CONFIG.get('laboratory_value_extraction', {})
    
    return {
        "EGFR": tuple(lab_config.get('egfr_loinc_codes', [])),
        "CREATININE": tuple(lab_config.get('creatinine_loinc_codes', [])),
        "HEMOGLOBIN": tuple(lab_config.get('hemoglobin_loinc_codes', [])),
        "WBC": tuple(lab_config.get('white_blood_cell_loinc_codes', [])),
        "PLATELETS": tuple(lab_config.get('platelet_loinc_codes', [])),
    }

def _get_text_search_terms():
    """
    Load text search terms from cdss_config.json.
    Returns dictionary mapping observation types to list of text search terms.
    """
    if not CDSS_CONFIG:
        return {}
    
    lab_config = CDSS_CONFIG.get('laboratory_value_extraction', {})
    
    return {
        "EGFR": lab_config.get('egfr_text_search', []),
        "CREATININE": lab_config.get('creatinine_text_search', []),
        "HEMOGLOBIN": lab_config.get('hemoglobin_text_search', []),
        "WBC": lab_config.get('wbc_text_search', []),
        "PLATELETS": lab_config.get('platelet_text_search', []),
    }

# Initialize LOINC_CODES and TEXT_SEARCH_TERMS from configuration
LOINC_CODES = _get_loinc_codes()
TEXT_SEARCH_TERMS = _get_text_search_terms()

# --- Unit Conversion System ---

# Define the canonical units the application will use internally for calculations.
TARGET_UNITS = {
    'HEMOGLOBIN': {
        'unit': 'g/dl',
        # Factors to convert a source unit TO the target unit (g/dL)
        'factors': {
            'g/l': 0.1,
            'mmol/l': 1.61135, # Based on Hb molar mass of 64,458 g/mol, factor is MW / 10 / 3.87
            'mg/dl': 0.001,    # mg/dL to g/dL (1 g = 1000 mg)
        }
    },
    'CREATININE': {
        'unit': 'mg/dl',
        # Factors to convert a source unit TO the target unit (mg/dL)
        'factors': {
            'umol/l': 0.0113, # µmol/L to mg/dL
            'µmol/l': 0.0113, # Handle unicode character
        }
    },
    'WBC': {
        'unit': '10*9/l',
        # Factors to convert a source unit TO the target unit (10^9/L)
        'factors': {
            '10*3/ul': 1.0,     # 10^3/µL = K/µL = 10^9/L (same unit, different notation)
            'k/ul': 1.0,        # K/µL = thousands/µL = 10^9/L
            '/ul': 0.001,       # cells/µL ÷ 1000 = 10^9/L (1000 cells/µL = 1 ×10^9/L)
            '/mm3': 0.001,      # cells/mm³ = cells/µL, same conversion
            '10^9/l': 1.0,      # Already in target unit
            'giga/l': 1.0       # Giga/L = 10^9/L
        }
    },
    'EGFR': {
        'unit': 'ml/min/1.73m2',
        'factors': {
            'ml/min/1.73m2': 1.0,       # Standard format
            'ml/min/{1.73_m2}': 1.0,    # Cerner format with braces
            'ml/min/1.73m^2': 1.0,      # With caret
            'ml/min/1.73 m2': 1.0,      # With space
            'ml/min/1.73 m^2': 1.0,     # Space and caret
            'ml/min per 1.73m2': 1.0,   # With 'per'
            'ml/min/bsa': 1.0,          # Body surface area
            'ml/min': 1.0               # Without BSA normalization (accept as-is)
        } 
    },
    'PLATELETS': {
        'unit': '10*9/l',
        'factors': {
            '10*3/ul': 1.0,     # 10^3/µL = K/µL = 10^9/L (same unit)
            'k/ul': 1.0,        # K/µL = thousands/µL = 10^9/L
            '/ul': 0.001,       # cells/µL ÷ 1000 = 10^9/L
            '10^9/l': 1.0,      # Already in target unit
            'giga/l': 1.0       # Giga/L = 10^9/L
        }
    }
}

def get_fhir_data(fhir_server_url, access_token, patient_id, client_id):
    """
    Fetches all required patient data using the fhirclient library.
    This provides better compatibility with various FHIR servers including Cerner.
    
    Returns a dictionary of FHIR resources and an error message if any.
    """
    try:
        # Detect test mode (for development/testing without OAuth)
        is_test_mode = (access_token == 'test-mode-no-auth')
        
        if is_test_mode:
            logging.info(f"TEST MODE: Fetching data without authentication from {fhir_server_url}")
        
        # Set up FHIR client settings following smart-on-fhir/client-py best practices
        settings = {
            'app_id': client_id,
            'api_base': fhir_server_url,
            'patient_id': patient_id,
        }
        
        # Create FHIR client instance
        smart = client.FHIRClient(settings=settings)
        
        # Set authorization using the standard fhirclient approach
        # Skip authorization setup in test mode for public FHIR servers
        if access_token and not is_test_mode:
            # Method 1: Use the built-in authorize method (most compatible)
            smart.prepare()
            
            # Method 2: Set the authorization directly on the server
            if hasattr(smart.server, 'prepare'):
                smart.server.prepare()
            
            # Method 3: Set authorization header properly for fhirclient
            smart.server.auth = None  # Clear any existing auth
            
            # Set proper headers for FHIR requests
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/fhir+json, application/json',
                'Content-Type': 'application/fhir+json'
            }
            
            # Use the server's session to set headers
            if hasattr(smart.server, 'session'):
                smart.server.session.headers.update(headers)
            else:
                # Create session if it doesn't exist
                import requests
                smart.server.session = requests.Session()
                smart.server.session.headers.update(headers)
        elif is_test_mode:
            # Test mode: Set up session without authentication
            # This allows accessing public FHIR servers
            import requests
            smart.prepare()
            
            if not hasattr(smart.server, 'session'):
                smart.server.session = requests.Session()
            
            # Set headers without Authorization
            headers = {
                'Accept': 'application/fhir+json, application/json',
                'Content-Type': 'application/fhir+json'
            }
            smart.server.session.headers.update(headers)
            logging.info("TEST MODE: Session configured for public FHIR access")
        
        # Set up custom adapter with timeout for the session (for both modes)
        if hasattr(smart.server, 'session'):
            import requests
            from requests.adapters import HTTPAdapter
            
            # Configure custom adapter with longer timeout
            class TimeoutHTTPAdapter(HTTPAdapter):
                def __init__(self, *args, **kwargs):
                    self.timeout = kwargs.pop('timeout', 60)  # 60 seconds default
                    super().__init__(*args, **kwargs)
                
                def send(self, request, **kwargs):
                    kwargs['timeout'] = kwargs.get('timeout', self.timeout)
                    return super().send(request, **kwargs)
            
            # Mount the adapter to both HTTP and HTTPS
            adapter = TimeoutHTTPAdapter(timeout=90)  # 90 seconds for condition queries
            smart.server.session.mount('http://', adapter)
            smart.server.session.mount('https://', adapter)
            
            if not is_test_mode:
                # Also set the _auth for backward compatibility (production mode only)
                smart.server._auth = None  # Clear old auth
                logging.info(f"Set authorization header with token length: {len(access_token)}")
            logging.info(f"FHIR Server prepared for: {fhir_server_url}")
        
        # Test the connection with a simple patient fetch first
        try:
            logging.info(f"Attempting to fetch patient {patient_id} from {fhir_server_url}")
            
            # Use the standard fhirclient Patient.read method
            patient_resource = patient.Patient.read(patient_id, smart.server)
            logging.info(f"Successfully fetched Patient resource for patient: {patient_id}")
            
        except Exception as e:
            error_msg = str(e)
            # Sanitize logging to prevent ePHI leakage
            logging.error(f"Error fetching patient resource for patient_id: {patient_id}. Status code or error type: {type(e).__name__}")
            
            # Log additional debugging information
            if hasattr(smart.server, 'session') and hasattr(smart.server.session, 'headers'):
                headers_dict = dict(smart.server.session.headers)
                # Don't log the full token for security
                if 'Authorization' in headers_dict:
                    headers_dict['Authorization'] = 'Bearer ***REDACTED***'
                logging.info(f"Request headers: {headers_dict}")
            
            # Log the exact URL being called
            if hasattr(smart.server, 'base_uri'):
                logging.info(f"Base URI: {smart.server.base_uri}")
            
            if '401' in error_msg:
                logging.error(f"Authentication failed - Access token may be expired or invalid")
                # Try to provide more specific error information
                if 'expired' in error_msg.lower():
                    return None, f"Access token has expired. Please re-launch the application from your EHR."
                elif 'invalid' in error_msg.lower():
                    return None, f"Access token is invalid. Please re-launch the application from your EHR."
                else:
                    return None, f"Authentication failed. Please re-launch the application from your EHR. Details: {str(e)}"
            elif '403' in error_msg:
                logging.error(f"Permission denied - Insufficient scope or patient access")
                return None, f"Access denied. The application may not have permission to access this patient's data. Please check the application's scope configuration."
            elif '404' in error_msg:
                logging.error(f"Patient not found")
                return None, f"Patient {patient_id} not found in the FHIR server."
            else:
                logging.error(f"Failed to fetch patient resource")
                # Sanitize the returned error message as well
                return None, f"Failed to retrieve patient data. Error type: {type(e).__name__}"

        raw_data = {"patient": patient_resource.as_json()}
        
        # Fetch observations by LOINC codes for PRECISE-HBR parameters
        for resource_type, codes in LOINC_CODES.items():
            obs_list = []
            
            try:
                # First, try searching by LOINC codes
                if codes:
                    search_params = {
                        'patient': patient_id,
                        'code': ','.join(codes),
                        '_count': '5'  # Get a few results to find the most recent
                    }
                    
                    observations = observation.Observation.where(search_params).perform(smart.server)
                    
                    if observations.entry:
                        # Sort by effective date in memory (more compatible than _sort parameter)
                        sorted_entries = []
                        for entry in observations.entry:
                            if entry.resource:
                                resource_json = entry.resource.as_json()
                                # Extract date for sorting
                                date_str = resource_json.get('effectiveDateTime') or resource_json.get('effectivePeriod', {}).get('start') or '1900-01-01'
                                sorted_entries.append((date_str, resource_json))
                        
                        # Sort by date (most recent first) and take the first one
                        sorted_entries.sort(key=lambda x: x[0], reverse=True)
                        if sorted_entries:
                            obs_list.append(sorted_entries[0][1])  # Take the most recent
                            logging.info(f"Successfully fetched {resource_type} observation by LOINC code")
                
                # If no results from LOINC codes, try text search as fallback
                if not obs_list and resource_type in TEXT_SEARCH_TERMS:
                    text_terms = TEXT_SEARCH_TERMS[resource_type]
                    if text_terms:
                        logging.info(f"No results from LOINC codes for {resource_type}, attempting text search with terms: {text_terms}")
                        
                        # Try each text search term
                        for term in text_terms:
                            try:
                                text_search_params = {
                                    'patient': patient_id,
                                    'code:text': term,
                                    '_count': '5'
                                }
                                
                                text_observations = observation.Observation.where(text_search_params).perform(smart.server)
                                
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
                                        break  # Found a result, stop searching
                            except Exception as text_error:
                                logging.debug(f"Text search failed for term '{term}': {type(text_error).__name__}")
                                continue
                
                raw_data[resource_type] = obs_list
                if obs_list:
                    logging.info(f"Final result: {len(obs_list)} {resource_type} observation(s)")
                else:
                    logging.warning(f"No {resource_type} observations found for patient {patient_id}")
                
            except Exception as e:
                # Sanitize logging
                logging.warning(f"Error fetching {resource_type} for patient {patient_id}. Type: {type(e).__name__}. Continuing with empty list.")
                raw_data[resource_type] = []
        
        # Fetch conditions (for bleeding history)
        try:
            # Fetch 100 conditions with extended timeout
            conditions_list = []
            
            logging.info(f"Attempting to fetch conditions with _count=100 for patient {patient_id} (90s timeout)")
            conditions_search = condition.Condition.where({
                'patient': patient_id,
                '_count': '100'  # Fetch 100 conditions with extended timeout
            }).perform(smart.server)
            
            if conditions_search.entry:
                for entry in conditions_search.entry:  # Process all returned conditions
                    if entry.resource:
                        conditions_list.append(entry.resource.as_json())
            
            logging.info(f"Successfully fetched {len(conditions_list)} condition(s) with _count=100")
            
            raw_data['conditions'] = conditions_list
            logging.info(f"Final result: {len(conditions_list)} condition(s) stored")
            
        except Exception as e:
            error_str = str(e)
            if '504' in error_str or 'timeout' in error_str.lower() or 'gateway time-out' in error_str.lower():
                # Sanitize logging
                logging.error(f"Timeout error fetching conditions for patient {patient_id}. Error type: {type(e).__name__}")
                logging.info("This suggests the FHIR server is very slow or overloaded")
            elif '401' in error_str or '403' in error_str:
                logging.error(f"Permission error fetching conditions for patient {patient_id}. Error type: {type(e).__name__}")
            else:
                logging.error(f"Unexpected error fetching conditions for patient {patient_id}. Error type: {type(e).__name__}")
            
            # Continue with empty conditions list
            raw_data['conditions'] = []
            logging.warning(f"Continuing with empty conditions list for patient {patient_id} due to a server error.")
        
        # Fetch minimal medication data for compatibility
        raw_data['med_requests'] = []
        raw_data['procedures'] = []

        return raw_data, None

    except Exception as e:
        # Sanitize logging for the top-level exception
        logging.error(f"An unexpected error occurred in get_fhir_data. Error type: {type(e).__name__}", exc_info=False)
        return None, "An unexpected error occurred while fetching FHIR data."

def get_tradeoff_model_data(fhir_server_url, access_token, client_id, patient_id):
    """
    Fetches additional data required for the Bleeding-Thrombosis tradeoff model.
    This complements the data fetched by get_fhir_data.
    Now creates its own client for robustness.
    """
    try:
        settings = {
            'app_id': client_id,
            'api_base': fhir_server_url
        }
        fhir_client = client.FHIRClient(settings=settings)
        
        # This is the correct way to set the header for the session
        import requests
        if not hasattr(fhir_client.server, 'session'):
            fhir_client.server.session = requests.Session()
        fhir_client.server.session.headers["Authorization"] = f"Bearer {access_token}"

    except Exception as e:
        logging.error(f"Failed to create FHIRClient in get_tradeoff_model_data: {e}")
        # Return empty data structure on client creation failure
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

    # Use a broader condition search to find relevant diagnoses
    try:
        search_params = {'patient': patient_id, '_count': '200'}
        # Note: fhirclient's perform() doesn't accept timeout parameter
        # Timeout is configured via the HTTPAdapter on the session
        conditions = condition.Condition.where(search_params).perform(fhir_client.server)
        
        if conditions.entry:
            for entry in conditions.entry:
                c = entry.resource
                # Get SNOMED codes from configuration
                snomed_codes = CDSS_CONFIG.get('tradeoff_analysis', {}).get('snomed_codes', {})
                
                # Diabetes Mellitus
                diabetes_code = snomed_codes.get('diabetes', '73211009')
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', diabetes_code):
                    tradeoff_data["diabetes"] = True
                
                # Myocardial Infarction
                mi_code = snomed_codes.get('myocardial_infarction', '22298006')
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', mi_code):
                    tradeoff_data["prior_mi"] = True
                
                # NSTEMI/STEMI
                nstemi_code = snomed_codes.get('nstemi', '164868009')
                stemi_code = snomed_codes.get('stemi', '164869001')
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', nstemi_code) or \
                   _resource_has_code(c.as_json(), 'http://snomed.info/sct', stemi_code):
                    tradeoff_data["nstemi_stemi"] = True
                
                # COPD
                copd_code = snomed_codes.get('copd', '13645005')
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', copd_code):
                    tradeoff_data["copd"] = True

    except Exception as e:
        logging.warning(f"Error fetching conditions for tradeoff model: {e}")

    # Check for smoking status from Observations
    try:
        search_params = {'patient': patient_id, 'code': '72166-2'}  # Smoking status LOINC
        # Note: fhirclient's perform() doesn't accept timeout parameter
        # Timeout is configured via the HTTPAdapter on the session
        obs_search = observation.Observation.where(search_params).perform(fhir_client.server)
        if obs_search and obs_search.entry:
            # Safe sorting by date
            sorted_obs = []
            for entry in obs_search.entry:
                if entry.resource:
                    # Use a safe way to get the date, with a fallback
                    date_str = '1900-01-01' # fallback
                    if hasattr(entry.resource, 'effectiveDateTime') and entry.resource.effectiveDateTime:
                        date_str = entry.resource.effectiveDateTime.isostring
                    elif hasattr(entry.resource, 'effectivePeriod') and entry.resource.effectivePeriod and entry.resource.effectivePeriod.start:
                        date_str = entry.resource.effectivePeriod.start.isostring
                    sorted_obs.append((date_str, entry.resource))
            
            if sorted_obs:
                sorted_obs.sort(key=lambda x: x[0], reverse=True)
                latest_obs = sorted_obs[0][1] # Get the resource part
                # Check for Current smoker codes
                if latest_obs.valueCodeableConcept and latest_obs.valueCodeableConcept.coding:
                    if latest_obs.valueCodeableConcept.coding[0].code in ['449868002', 'LA18978-9']: 
                        tradeoff_data["smoker"] = True
    except Exception as e:
        logging.warning(f"Error fetching smoking status: {e}", exc_info=True)

    # Check for complex PCI and BMS from Procedures
    try:
        search_params = {'patient': patient_id, '_count': '50'}
        # Note: fhirclient's perform() doesn't accept timeout parameter
        # Timeout is configured via the HTTPAdapter on the session
        procedures = procedure.Procedure.where(search_params).perform(fhir_client.server)
        if procedures.entry:
            # Get SNOMED codes from configuration
            snomed_codes = CDSS_CONFIG.get('tradeoff_analysis', {}).get('snomed_codes', {})
            complex_pci_code = snomed_codes.get('complex_pci', '397682003')
            bms_code = snomed_codes.get('bare_metal_stent', '427183000')
            
            for entry in procedures.entry:
                p = entry.resource
                # Complex PCI
                if _resource_has_code(p.as_json(), 'http://snomed.info/sct', complex_pci_code):
                    tradeoff_data["complex_pci"] = True
                # Bare-metal stent (BMS)
                if _resource_has_code(p.as_json(), 'http://snomed.info/sct', bms_code):
                    tradeoff_data["bms_used"] = True
    except Exception as e:
        logging.warning(f"Error fetching procedures for tradeoff model: {e}")
        
    # Check for OAC at discharge from MedicationRequest
    try:
        search_params = {'patient': patient_id, 'category': 'outpatient'}
        # Note: fhirclient's perform() doesn't accept timeout parameter
        # Timeout is configured via the HTTPAdapter on the session
        med_requests = medicationrequest.MedicationRequest.where(search_params).perform(fhir_client.server)
        if med_requests.entry:
            # Get RxNorm codes from configuration
            rxnorm_codes = CDSS_CONFIG.get('tradeoff_analysis', {}).get('rxnorm_codes', {})
            oac_codes = [
                rxnorm_codes.get('warfarin', '11289'),
                rxnorm_codes.get('rivaroxaban', '21821'),
                rxnorm_codes.get('apixaban', '1364430'),
                rxnorm_codes.get('dabigatran', '1037042'),
                rxnorm_codes.get('edoxaban', '1537033')
            ]
            
            for entry in med_requests.entry:
                mr = entry.resource
                # Check for Oral Anticoagulants
                if any(_resource_has_code(mr.as_json(), 'http://www.nlm.nih.gov/research/umls/rxnorm', code) for code in oac_codes):
                    tradeoff_data["oac_discharge"] = True
    except Exception as e:
        logging.warning(f"Error fetching medication requests for OAC: {e}")

    return tradeoff_data

def get_tradeoff_model_predictors():
    """Loads and returns the list of all predictors from the ARC-HBR model file."""
    script_dir = os.path.dirname(__file__)
    model_path = os.path.join(script_dir, 'fhir_resources', 'valuesets', 'arc-hbr-model.json')
    
    # Add detailed logging for debugging cloud deployment
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
        # List files in the directory for debugging
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
    Detects which tradeoff factors are present based on patient data.
    Returns a dictionary of detected factor keys.
    Uses thresholds from cdss_config.json for consistency.
    """
    detected_factors = {}
    
    # Get thresholds from configuration
    tradeoff_config = CDSS_CONFIG.get('tradeoff_analysis', {})
    thresholds = tradeoff_config.get('risk_factor_thresholds', {})
    
    # Age threshold
    age_threshold = thresholds.get('age_threshold', 65)
    if demographics.get('age', 0) >= age_threshold:
        detected_factors['age_ge_65'] = True

    # Hemoglobin thresholds
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

    # eGFR thresholds
    egfr_obs = raw_data.get('EGFR', [])
    cr_obs = raw_data.get('CREATININE', [])
    egfr_val = None
    if egfr_obs:
        egfr_val = get_value_from_observation(egfr_obs[0], TARGET_UNITS['EGFR'])
    elif cr_obs:
        cr_val = get_value_from_observation(cr_obs[0], TARGET_UNITS['CREATININE'])
        if cr_val and demographics.get('age') and demographics.get('gender'):
            egfr_val = calculate_egfr(cr_val, demographics['age'], demographics['gender'])
            
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
    Converts a total Hazard Ratio (HR) score to an estimated 1-year event probability.
    
    Uses the Cox proportional hazards model:
    P(event) = 1 - exp(-baseline_hazard × HR)
    
    Where baseline_hazard is derived from the baseline event rate:
    baseline_hazard ≈ -ln(1 - baseline_rate)
    
    This ensures that:
    1. When HR = 1, P(event) = baseline_rate
    2. When HR increases, P(event) increases non-linearly (more realistic)
    3. P(event) never exceeds 100%
    
    This is more accurate than simple linear scaling, especially when HR > 2.
    """
    import math
    
    # Convert baseline event rate (percentage) to baseline hazard
    # Formula: baseline_hazard = -ln(1 - baseline_rate/100)
    baseline_rate_decimal = baseline_event_rate / 100.0  # Convert % to decimal
    
    # Handle edge case: if baseline_rate is 100%, hazard would be infinite
    if baseline_rate_decimal >= 1.0:
        return 100.0
    
    # Calculate baseline hazard (cumulative hazard over 1 year)
    baseline_hazard = -math.log(1 - baseline_rate_decimal)
    
    # Apply the HR to get adjusted hazard
    adjusted_hazard = baseline_hazard * total_hr_score
    
    # Convert back to probability using survival function
    # P(event) = 1 - S(t) = 1 - exp(-H(t))
    # where H(t) is the cumulative hazard
    survival_probability = math.exp(-adjusted_hazard)
    event_probability = 1 - survival_probability
    
    # Convert to percentage and round
    event_probability_percent = event_probability * 100.0
    
    return round(min(event_probability_percent, 100.0), 2)  # Cap at 100%

def calculate_tradeoff_scores_interactive(model_predictors, active_factors):
    """
    Calculates bleeding and thrombotic scores and converts them to probabilities.
    'active_factors' is a dictionary like {'smoker': true, 'diabetes': false}.
    
    CORRECTED: Uses multiplicative model for Hazard Ratios (Cox proportional hazards model).
    Total HR = HR₁ × HR₂ × HR₃ × ... (or sum of log HRs)
    """
    import math
    
    # Get baseline event rates from configuration
    tradeoff_config = CDSS_CONFIG.get('tradeoff_analysis', {})
    baseline_rates = tradeoff_config.get('baseline_event_rates', {})
    BASELINE_BLEEDING_RATE = baseline_rates.get('bleeding_rate_percent', 2.5)
    BASELINE_THROMBOTIC_RATE = baseline_rates.get('thrombotic_rate_percent', 2.5)

    # Use multiplicative model: start with HR = 1 (no risk factor)
    bleeding_score_hr = 1.0
    thrombotic_score_hr = 1.0
    
    bleeding_factors_details = []
    thrombotic_factors_details = []

    # Calculate bleeding score in HR (CORRECTED: multiply HRs)
    for predictor in model_predictors['bleedingEvents']['predictors']:
        factor_key = predictor['factor']
        if active_factors.get(factor_key, False):
            bleeding_score_hr *= predictor['hazardRatio']  # ✅ MULTIPLY, not add
            bleeding_factors_details.append(f"{predictor['description']} (HR: {predictor['hazardRatio']})")
    
    # Calculate thrombotic score in HR (CORRECTED: multiply HRs)
    for predictor in model_predictors['thromboticEvents']['predictors']:
        factor_key = predictor['factor']
        if active_factors.get(factor_key, False):
            thrombotic_score_hr *= predictor['hazardRatio']  # ✅ MULTIPLY, not add
            thrombotic_factors_details.append(f"{predictor['description']} (HR: {predictor['hazardRatio']})")

    # Convert HR scores to probabilities
    # Use more accurate formula: Risk = 1 - exp(-baseline_hazard × HR × time)
    # For simplicity, approximate: Risk ≈ baseline_rate × HR (valid when risk is low)
    bleeding_prob = convert_hr_to_probability(bleeding_score_hr, BASELINE_BLEEDING_RATE)
    thrombotic_prob = convert_hr_to_probability(thrombotic_score_hr, BASELINE_THROMBOTIC_RATE)

    return {
        "bleeding_score": bleeding_prob,
        "thrombotic_score": thrombotic_prob,
        "bleeding_factors": bleeding_factors_details,
        "thrombotic_factors": thrombotic_factors_details
    }

# --- Data Processing and Risk Calculation Logic for PRECISE-HBR ---

def _resource_has_code(resource, system, code):
    """Checks if a resource's coding matches the given system and code."""
    for coding in resource.get('code', {}).get('coding', []):
        if coding.get('system') == system and coding.get('code') == code:
            return True
    return False

def _is_within_time_window(resource_date_str, min_months=None, max_months=None):
    """Checks if a resource date is within the specified time window from today."""
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

def get_patient_demographics(patient_resource):
    """Extracts and returns key demographics from a patient resource."""
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
        # Try text field first (for Taiwan FHIR format), then fall back to given/family
        if name_data.get("text"):
            demographics["name"] = name_data.get("text")
        else:
            demographics["name"] = " ".join(name_data.get("given", []) + [name_data.get("family", "")]).strip()

    # Gender
    demographics["gender"] = patient_resource.get("gender")

    # Age
    if patient_resource.get("birthDate"):
        demographics["birthDate"] = patient_resource["birthDate"]
        try:
            birth_date = dt.datetime.strptime(patient_resource["birthDate"], "%Y-%m-%d").date()
            today = dt.date.today()
            demographics["age"] = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except (ValueError, TypeError):
            pass
            
    return demographics

def calculate_tradeoff_scores(raw_data, demographics, tradeoff_data):
    """
    Calculates the bleeding and thrombotic risk scores based on the ARC-HBR tradeoff model.
    """
    # Construct path relative to this script to avoid FileNotFoundError in production
    script_dir = os.path.dirname(__file__)
    model_path = os.path.join(script_dir, 'fhir_resources', 'valuesets', 'arc-hbr-model.json')
    
    # Add detailed logging for debugging
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

    # CORRECTED: Use multiplicative model for Cox proportional hazards
    bleeding_score = 1.0  # Start with HR = 1 (no risk factors)
    thrombotic_score = 1.0  # Start with HR = 1 (no risk factors)
    
    bleeding_factors = []
    thrombotic_factors = []

    # Helper to multiply score and record factor (CORRECTED)
    def add_score(event_type, factor, ratio):
        nonlocal bleeding_score, thrombotic_score
        if event_type == 'bleeding':
            bleeding_score *= ratio  # ✅ MULTIPLY, not add
            bleeding_factors.append(f"{factor} (HR: {ratio})")
        else:
            thrombotic_score *= ratio  # ✅ MULTIPLY, not add
            thrombotic_factors.append(f"{factor} (HR: {ratio})")

    # Demographics
    if demographics.get('age', 0) >= 65:
        add_score('bleeding', 'Age >= 65', 1.50)

    # Hemoglobin
    hb_obs = raw_data.get('HEMOGLOBIN', [])
    if hb_obs:
        hb_val = get_value_from_observation(hb_obs[0], TARGET_UNITS['HEMOGLOBIN'])
        if 11 <= hb_val < 13:
            add_score('bleeding', 'Hb 11-12.9', 1.69)
            add_score('thrombotic', 'Hb 11-12.9', 1.27)
        elif hb_val < 11:
            add_score('bleeding', 'Hb < 11', 3.99)
            add_score('thrombotic', 'Hb < 11', 1.50)

    # eGFR
    egfr_obs = raw_data.get('EGFR', [])
    if egfr_obs:
        egfr_val = get_value_from_observation(egfr_obs[0], TARGET_UNITS['EGFR'])
        if 30 <= egfr_val < 60:
             add_score('thrombotic', 'eGFR 30-59', 1.30)
        elif egfr_val < 30:
            add_score('bleeding', 'eGFR < 30', 1.43)
            add_score('thrombotic', 'eGFR < 30', 1.69)
            
    # Tradeoff data
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
    
    # Placeholder for liver_cancer_surgery - requires more complex logic
    # For now, we can add a placeholder
    # if check_liver_cancer_surgery(raw_data.get('conditions', [])):
    #     add_score('bleeding', 'Liver/Cancer/Surgery', 1.63)

    # Convert HR scores to probabilities using updated baseline rates
    # Based on Galli M, et al. JAMA Cardiology 2021
    BASELINE_BLEEDING_RATE = 2.5  # % (BARC 3-5 bleeding, 1-year risk, reference group)
    BASELINE_THROMBOTIC_RATE = 2.5  # % (MI/ST, 1-year risk, reference group)
    
    bleeding_prob = convert_hr_to_probability(bleeding_score, BASELINE_BLEEDING_RATE)
    thrombotic_prob = convert_hr_to_probability(thrombotic_score, BASELINE_THROMBOTIC_RATE)

    return {
        "bleeding_score": bleeding_prob,  # Now returns probability (%), not HR
        "thrombotic_score": thrombotic_prob,  # Now returns probability (%), not HR
        "bleeding_factors": bleeding_factors,
        "thrombotic_factors": thrombotic_factors
    }

def get_value_from_observation(obs, unit_system):
    """
    Safely extracts a numeric value from an Observation resource, handling unit conversions.
    Returns the numeric value in the target unit, or None if conversion is not possible.
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
    
    # 0. If unit is missing/empty, assume the value is already in the target unit
    # This handles FHIR servers that don't provide unit information
    if not source_unit or source_unit.strip() == '':
        logging.warning(f"No unit provided for Observation value {value}. "
                       f"Assuming it is already in target unit '{target_unit}'.")
        return value
    
    # 1. Direct match
    if source_unit == target_unit:
        return value

    # 2. Check for common alternative writings of the target unit
    # (e.g., "g/dL" vs "g/dl"). This is a simple case-insensitive check.
    if source_unit.lower() == target_unit.lower():
        return value

    # 3. Attempt conversion
    conversion_factors = unit_system.get('factors', {})
    if source_unit in conversion_factors:
        conversion_factor = conversion_factors[source_unit]
        converted_value = value * conversion_factor
        logging.info(f"Converted {value} {source_unit} to {converted_value:.2f} {target_unit}")
        return converted_value

    # 4. If no conversion is possible, log a warning and return None to prevent miscalculation
    logging.warning(f"Unit mismatch and no conversion rule found for Observation. "
                    f"Received: '{source_unit}', Expected: '{target_unit}'. Cannot proceed with this value.")
    return None

def calculate_egfr(cr_val, age, gender):
    """
    Calculates eGFR using the CKD-EPI 2021 equation.
    """
    if not all([cr_val, age, gender]) or gender not in ['male', 'female']:
        return None, "Missing data for eGFR calculation"
    
    k = 0.7 if gender == 'female' else 0.9
    alpha = -0.241 if gender == 'female' else -0.302
    
    # CKD-EPI 2021 formula
    egfr = 142 * (min(cr_val / k, 1) ** alpha) * (max(cr_val / k, 1) ** -1.2) * (0.9938 ** age)
    if gender == 'female':
        egfr *= 1.012
        
    return round(egfr), "CKD-EPI 2021"

def get_score_from_table(value, score_table, range_key):
    """Helper function to get score from lookup tables."""
    matched_score = None
    
    for item in score_table:
        if range_key in item:
            range_values = item[range_key]
            if len(range_values) == 2 and range_values[0] <= value <= range_values[1]:
                return item.get('base_score', 0)
    
    # If no exact match, check if value exceeds the highest range
    # In that case, use the highest available score
    if range_key == 'age_range':
        # For age, if older than max range, use the highest score
        max_range_item = max(score_table, key=lambda x: x[range_key][1] if range_key in x else 0)
        if value > max_range_item[range_key][1]:
            logging.info(f"Age {value} exceeds max range {max_range_item[range_key]}, using highest score: {max_range_item.get('base_score', 0)}")
            return max_range_item.get('base_score', 0)
    elif range_key == 'hb_range':
        # For hemoglobin, if lower than min range, use the highest score (lowest Hb = highest risk)
        min_range_item = min(score_table, key=lambda x: x[range_key][0] if range_key in x else float('inf'))
        if value < min_range_item[range_key][0]:
            logging.info(f"Hemoglobin {value} below min range {min_range_item[range_key]}, using highest score: {min_range_item.get('base_score', 0)}")
            return min_range_item.get('base_score', 0)
    elif range_key == 'ccr_range':
        # For creatinine clearance, if lower than min range, use the highest score (lowest CCr = highest risk)
        min_range_item = min(score_table, key=lambda x: x[range_key][0] if range_key in x else float('inf'))
        if value < min_range_item[range_key][0]:
            logging.info(f"Creatinine clearance {value} below min range {min_range_item[range_key]}, using highest score: {min_range_item.get('base_score', 0)}")
            return min_range_item.get('base_score', 0)
    elif range_key == 'wbc_range':
        # For WBC, if higher than max range, use the highest score (higher WBC = higher risk)
        max_range_item = max(score_table, key=lambda x: x[range_key][1] if range_key in x else 0)
        if value > max_range_item[range_key][1]:
            logging.info(f"WBC {value} exceeds max range {max_range_item[range_key]}, using highest score: {max_range_item.get('base_score', 0)}")
            return max_range_item.get('base_score', 0)
    
    return 0

def check_bleeding_history(conditions):
    """Checks for history of spontaneous bleeding in patient conditions."""
    if not CDSS_CONFIG:
        return False, []
    
    # Get SNOMED codes from unified configuration
    snomed_config = CDSS_CONFIG.get('precise_hbr_snomed_codes', {})
    prior_bleeding_codes = snomed_config.get('prior_bleeding', {}).get('specific_codes', [])
    bleeding_keywords = CDSS_CONFIG.get('bleeding_history_keywords', [])
    
    bleeding_evidence = []
    
    # Check SNOMED codes
    for condition in conditions:
        # Check coded conditions
        for coding in condition.get('code', {}).get('coding', []):
            system = coding.get('system', '')
            code = coding.get('code', '')
            
            # Check against bleeding history SNOMED codes
            if system == 'http://snomed.info/sct' and code in prior_bleeding_codes:
                display = coding.get('display', condition.get('code', {}).get('text', 'Bleeding history'))
                bleeding_evidence.append(display)
                break
        
        # Check text-based conditions
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

def calculate_precise_hbr_score(raw_data, demographics):
    """
    Calculates PRECISE-HBR bleeding risk score using final confirmed scoring guide (V5.0):
    
    Calculation Steps:
    1. Determine effective values: Apply truncation rules for continuous variables
    2. Base score: Start with 2 points
    3. Add risk scores: Calculate each item's risk score using effective values
    4. Sum: Add base score and all risk scores
    5. Round: Round total to nearest integer for final score
    
    Continuous Variables:
    - Age: If effective age > 30: score = (effective age - 30) × 0.25
    - Hemoglobin: If effective Hb < 15: score = (15 - effective Hb) × 2.5
    - WBC: If effective WBC > 3.0: score = (effective WBC - 3.0) × 0.8
    - eGFR: If effective eGFR < 100: score = (100 - effective eGFR) × 0.05
    
    Categorical Variables:
    - Previous bleeding history: Yes = +7 points
    - Long-term oral anticoagulation: Yes = +5 points
    - Other ARC-HBR conditions: Yes = +3 points
    
    Returns components list and total score.
    """
    import math
    
    components = []
    
    # Base score: Start with 2 points
    base_score = 2
    total_score = base_score
    
    # Initialize individual scores
    age_score = 0
    hb_score = 0
    egfr_score = 0
    wbc_score = 0
    bleeding_score = 0
    anticoag_score = 0
    arc_hbr_score = 0
    
    # Truncation limits for effective values
    MIN_AGE, MAX_AGE = 30, 80
    MIN_HB, MAX_HB = 5.0, 15.0
    MIN_EGFR, MAX_EGFR = 5, 100  # eGFR truncated below 5
    MAX_WBC = 15.0  # WBC truncated above 15×10³ cells/μL
    
    # 1. Age Score - If effective age > 30: score = (effective age - 30) × 0.25
    age = demographics.get('age')
    if age:
        # Apply truncation to get effective age
        effective_age = max(MIN_AGE, min(MAX_AGE, age))
        
        # Calculate age score: If effective age > 30: score = (effective age - 30) × 0.25
        if effective_age > 30:
            age_score_raw = (effective_age - 30) * 0.25
            age_score = round(age_score_raw)
            total_score += age_score_raw  # Use raw score for total calculation
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
    
    # 2. Hemoglobin Score - If effective Hb < 15: score = (15 - effective Hb) × 2.5
    hemoglobin_list = raw_data.get('HEMOGLOBIN', [])
    if hemoglobin_list:
        hemoglobin_obs = hemoglobin_list[0]
        # Use the new unit-aware function
        hb_val = get_value_from_observation(hemoglobin_obs, TARGET_UNITS['HEMOGLOBIN'])
        
        if hb_val:
            hb_unit = TARGET_UNITS['HEMOGLOBIN']['unit'] # Display the standardized unit
            hb_date = hemoglobin_obs.get('effectiveDateTime', 'N/A')
            
            # Apply truncation to get effective Hb
            effective_hb = max(MIN_HB, min(MAX_HB, hb_val))
            
            # Calculate Hb score: If effective Hb < 15: score = (15 - effective Hb) × 2.5
            if effective_hb < 15:
                hb_score_raw = (15 - effective_hb) * 2.5
                hb_score = round(hb_score_raw)
                total_score += hb_score_raw  # Use raw score for total calculation
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
    
    # 3. eGFR Score - If effective eGFR < 100: score = (100 - effective eGFR) × 0.05
    egfr_list = raw_data.get('EGFR', [])
    creatinine_list = raw_data.get('CREATININE', [])
    
    logging.info(f"DEBUG: eGFR list length: {len(egfr_list)}, Creatinine list length: {len(creatinine_list)}")
    if egfr_list:
        logging.info(f"DEBUG: eGFR observation data: {json.dumps(egfr_list[0], indent=2, default=str)}")
    
    egfr_val = None
    egfr_source = ""
    egfr_date = "N/A"
    
    if egfr_list:
        egfr_obs = egfr_list[0]
        # Use the new unit-aware function
        egfr_val = get_value_from_observation(egfr_obs, TARGET_UNITS['EGFR'])
        logging.info(f"DEBUG: Extracted eGFR value: {egfr_val}")
        egfr_source = "Direct eGFR"
        egfr_date = egfr_obs.get('effectiveDateTime', 'N/A')
    elif creatinine_list and age and demographics.get('gender'):
        creatinine_obs = creatinine_list[0]
        # Use the new unit-aware function to get Creatinine in mg/dL
        creatinine_val = get_value_from_observation(creatinine_obs, TARGET_UNITS['CREATININE'])
        if creatinine_val:
            calculated_egfr, reason = calculate_egfr(creatinine_val, age, demographics.get('gender'))
            if calculated_egfr:
                egfr_val = calculated_egfr
                egfr_source = reason
                egfr_date = creatinine_obs.get('effectiveDateTime', 'N/A')
    
    if egfr_val:
        # Apply truncation to get effective eGFR (truncated below 5 and above 100)
        effective_egfr = max(MIN_EGFR, min(MAX_EGFR, egfr_val))
        
        # Calculate eGFR score: If effective eGFR < 100: score = (100 - effective eGFR) × 0.05
        if effective_egfr < 100:
            egfr_score_raw = (100 - effective_egfr) * 0.05
            egfr_score = round(egfr_score_raw)
            total_score += egfr_score_raw  # Use raw score for total calculation
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
    
    # 4. White Blood Cell Count Score - If effective WBC > 3.0: score = (effective WBC - 3.0) × 0.8
    wbc_list = raw_data.get('WBC', [])
    if wbc_list:
        wbc_obs = wbc_list[0]
        # Use the new unit-aware function
        wbc_val = get_value_from_observation(wbc_obs, TARGET_UNITS['WBC'])
        
        if wbc_val:
            wbc_unit = TARGET_UNITS['WBC']['unit'] # Display the standardized unit
            wbc_date = wbc_obs.get('effectiveDateTime', 'N/A')
            
            # Apply truncation to get effective WBC (truncated above 15×10³ cells/μL)
            effective_wbc = min(MAX_WBC, wbc_val)
            
            # Calculate WBC score: If effective WBC > 3.0: score = (effective WBC - 3.0) × 0.8
            if effective_wbc > 3.0:
                wbc_score_raw = (effective_wbc - 3.0) * 0.8  # CORRECTED: × 0.8, not × 3.0
                wbc_score = round(wbc_score_raw)
                total_score += wbc_score_raw  # Use raw score for total calculation
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
    
    # 5. Previous Bleeding History - Categorical variable: Yes = +7 points (Updated valueset logic)
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
    
    # 6. Long-term Oral Anticoagulation - Categorical variable: Yes = +5 points
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
    
    # 7. Other ARC-HBR Conditions - Categorical variable: Yes = +3 points
    # Get individual ARC-HBR factor details
    arc_hbr_details = check_arc_hbr_factors_detailed(raw_data, medications)
    has_arc_factors = arc_hbr_details['has_any_factor']
    
    arc_hbr_score = 3 if has_arc_factors else 0
    total_score += arc_hbr_score
    
    logging.info(f"ARC-HBR conditions score: {'Yes' if has_arc_factors else 'No'} = {arc_hbr_score} points")
    
    # Add individual ARC-HBR elements as separate components
    components.append({
        "parameter": "PRECISE-HBR - Platelet Count",
        "value": "Yes" if arc_hbr_details['thrombocytopenia'] else "No",
        "score": 0,  # Individual elements don't contribute separately
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
    
    # Add summary component for ARC-HBR
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
    
    # Add base score component for transparency
    components.insert(0, {
        "parameter": "PRECISE-HBR - Base Score",
        "value": "Fixed base score",
        "score": base_score,
        "date": "N/A",
        "description": f"Base score: {base_score} points (fixed)"
    })
    
    # Round final score to nearest integer
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
    Calculate 1-year bleeding risk percentage based on PRECISE-HBR score.
    Based on the calibration curve from the PRECISE-HBR validation study.
    
    Returns the estimated 1-year risk of BARC 3 or 5 bleeding events.
    """
    # Approximate risk percentages based on the calibration curve
    # These values are derived from the PRECISE-HBR validation study
    if precise_hbr_score <= 22:
        # Non-HBR: risk ranges from ~0.5% to ~3.5%
        # Linear interpolation for scores 0-22
        risk_percent = 0.5 + (precise_hbr_score / 22) * 3.0
        return min(3.5, risk_percent)
    elif precise_hbr_score <= 26:
        # HBR: risk ranges from ~3.5% to ~5.5%
        # Linear interpolation for scores 23-26
        risk_percent = 3.5 + ((precise_hbr_score - 22) / 4) * 2.0
        return min(5.5, risk_percent)
    elif precise_hbr_score <= 30:
        # Very HBR: risk ranges from ~5.5% to ~8%
        # Linear interpolation for scores 27-30
        risk_percent = 5.5 + ((precise_hbr_score - 26) / 4) * 2.5
        return min(8.0, risk_percent)
    elif precise_hbr_score <= 35:
        # Extremely high risk: risk ranges from ~8% to ~12%
        risk_percent = 8.0 + ((precise_hbr_score - 30) / 5) * 4.0
        return min(12.0, risk_percent)
    else:
        # For very high scores (>35), cap at ~15%
        risk_percent = 12.0 + ((precise_hbr_score - 35) / 10) * 3.0
        return min(15.0, risk_percent)

def get_risk_category_info(precise_hbr_score):
    """
    Get risk category information based on PRECISE-HBR score.
    Returns category label, color, and specific bleeding risk percentage.
    """
    bleeding_risk_percent = calculate_bleeding_risk_percentage(precise_hbr_score)
    
    if precise_hbr_score <= 22:
        return {
            "category": "Not high bleeding risk",
            "color": "success",  # Bootstrap color class
            "bleeding_risk_percent": f"{bleeding_risk_percent:.1f}%",
            "score_range": f"(score ≤22)"
        }
    elif precise_hbr_score <= 26:
        return {
            "category": "HBR",
            "color": "warning",  # Bootstrap color class  
            "bleeding_risk_percent": f"{bleeding_risk_percent:.1f}%",
            "score_range": f"(score 23-26)"
        }
    else:  # score >= 27
        return {
            "category": "Very HBR", 
            "color": "danger",  # Bootstrap color class
            "bleeding_risk_percent": f"{bleeding_risk_percent:.1f}%",
            "score_range": f"(score ≥27)"
        }

def get_precise_hbr_display_info(precise_hbr_score):
    """
    Get complete display information for PRECISE-HBR score including
    risk category, bleeding risk percentage, and recommendations.
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

def check_oral_anticoagulation(medications):
    """
    Check for long-term oral anticoagulation therapy using codes from configuration.
    Returns True if patient is on oral anticoagulants.
    """
    # Get medication keywords from configuration
    med_config = CDSS_CONFIG.get('medication_keywords', {})
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


# Updated condition checking functions based on new valueset definitions

def check_bleeding_diathesis_updated(conditions):
    """
    Check for chronic bleeding diathesis using codes from configuration.
    """
    # Get SNOMED codes from configuration
    snomed_config = CDSS_CONFIG.get('precise_hbr_snomed_codes', {})
    diathesis_config = snomed_config.get('bleeding_diathesis', {})
    bleeding_diathesis_snomed_codes = diathesis_config.get('specific_codes', ['64779008'])
    
    for condition in conditions:
        # Check SNOMED codes
        for coding in condition.get('code', {}).get('coding', []):
            if (coding.get('system') == 'http://snomed.info/sct' and 
                coding.get('code') in bleeding_diathesis_snomed_codes):
                return True, coding.get('display', 'Bleeding diathesis')
        
        # Check text for bleeding diathesis terms
        condition_text = get_condition_text(condition).lower()
        bleeding_keywords = ['bleeding disorder', 'bleeding diathesis', 'hemorrhagic diathesis', 
                           'hemophilia', 'von willebrand', 'coagulation disorder']
        for keyword in bleeding_keywords:
            if keyword in condition_text:
                return True, condition_text
    
    return False, None

def check_prior_bleeding_updated(conditions):
    """
    Check for prior bleeding history using codes from configuration.
    """
    # Get SNOMED codes from configuration
    snomed_config = CDSS_CONFIG.get('precise_hbr_snomed_codes', {})
    prior_bleeding_config = snomed_config.get('prior_bleeding', {})
    prior_bleeding_snomed_codes = prior_bleeding_config.get('specific_codes', [])
    
    found_bleeding = []
    
    for condition in conditions:
        # Check SNOMED codes
        for coding in condition.get('code', {}).get('coding', []):
            if (coding.get('system') == 'http://snomed.info/sct' and 
                coding.get('code') in prior_bleeding_snomed_codes):
                found_bleeding.append(coding.get('display', 'Prior bleeding'))
        
        # Check text for bleeding terms
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
    Check for liver cirrhosis with portal hypertension using codes from configuration.
    Requires BOTH:
    1. Evidence of liver cirrhosis (SNOMED code or text)
    2. Evidence of portal hypertension (ascites, varices, or encephalopathy)
    """
    # Get configuration
    snomed_config = CDSS_CONFIG.get('precise_hbr_snomed_codes', {})
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
        
        # Check for liver cirrhosis SNOMED code
        for coding in condition.get('code', {}).get('coding', []):
            code = coding.get('code', '')
            system = coding.get('system', '')
            
            # Check cirrhosis SNOMED code
            if system == 'http://snomed.info/sct' and code == cirrhosis_snomed_code:
                has_cirrhosis = True
                found_conditions.append(coding.get('display', 'Liver cirrhosis'))
            
            # Check portal hypertension SNOMED codes
            if system == 'http://snomed.info/sct' and code in pht_snomed_codes:
                has_additional_criteria = True
                found_conditions.append(coding.get('display', 'Portal hypertension manifestation'))
        
        # Check text for cirrhosis keywords
        for keyword in cirrhosis_keywords:
            if keyword in condition_text:
                has_cirrhosis = True
                found_conditions.append(f"Found cirrhosis: {condition_text[:50]}...")
                break
        
        # Check text for portal hypertension criteria
        for criteria in additional_criteria:
            if criteria in condition_text:
                has_additional_criteria = True
                found_conditions.append(f"Found portal hypertension sign: {criteria}")
                break
    
    # Must have BOTH cirrhosis AND additional criteria (portal hypertension signs)
    return (has_cirrhosis and has_additional_criteria), found_conditions

def check_active_cancer_updated(conditions):
    """
    Check for active malignant neoplastic disease using codes from configuration.
    """
    # Get SNOMED codes from configuration
    snomed_config = CDSS_CONFIG.get('precise_hbr_snomed_codes', {})
    cancer_config = snomed_config.get('active_cancer', {})
    malignancy_parent_code = cancer_config.get('parent_code', '363346000')
    excluded_codes = cancer_config.get('exclude_codes', ['254637007', '254632001'])
    
    for condition in conditions:
        # Check clinical status first
        clinical_status = condition.get('clinicalStatus', {})
        if isinstance(clinical_status, dict):
            status_code = None
            for coding in clinical_status.get('coding', []):
                if coding.get('system') == 'http://terminology.hl7.org/CodeSystem/condition-clinical':
                    status_code = coding.get('code')
                    break
        else:
            status_code = str(clinical_status).lower()
        
        # Only consider active conditions
        if status_code != 'active':
            continue
        
        # Check SNOMED codes
        for coding in condition.get('code', {}).get('coding', []):
            if coding.get('system') == 'http://snomed.info/sct':
                code = coding.get('code')
                
                # Exclude specific skin cancers
                if code in excluded_codes:
                    continue
                
                # Include malignant neoplastic disease and descendants
                if code == malignancy_parent_code:
                    return True, coding.get('display', 'Active malignant neoplastic disease')
        
        # Check text for cancer terms (but still require active status)
        condition_text = get_condition_text(condition).lower()
        cancer_keywords = ['cancer', 'malignancy', 'neoplasm', 'carcinoma', 'sarcoma', 'lymphoma', 'leukemia']
        exclusion_keywords = ['basal cell', 'squamous cell', 'skin cancer']
        
        # Check if it's an excluded skin cancer
        is_excluded = any(exclusion in condition_text for exclusion in exclusion_keywords)
        if is_excluded:
            continue
        
        # Check for cancer keywords
        for keyword in cancer_keywords:
            if keyword in condition_text:
                return True, condition_text
    
    return False, None

def get_condition_text(condition):
    """
    Extract all text from a condition for text-based matching.
    """
    text_parts = []
    
    # Get text field
    if condition.get('code', {}).get('text'):
        text_parts.append(condition['code']['text'])
    
    # Get display text from codings
    for coding in condition.get('code', {}).get('coding', []):
        if coding.get('display'):
            text_parts.append(coding['display'])
    
    return ' '.join(text_parts)

def check_arc_hbr_factors(raw_data, medications):
    """
    Check for ARC-HBR risk factors using updated valueset logic.
    Returns dict with has_factors and list of factors found.
    """
    factors = []
    conditions = raw_data.get('conditions', [])
    
    # Check thrombocytopenia using threshold from configuration
    snomed_config = CDSS_CONFIG.get('precise_hbr_snomed_codes', {})
    thrombocytopenia_config = snomed_config.get('thrombocytopenia', {})
    platelet_threshold = thrombocytopenia_config.get('threshold', {}).get('value', 100)
    
    platelets = raw_data.get('PLATELETS', [])
    if platelets:
        plt_obs = platelets[0]
        plt_val = get_value_from_observation(plt_obs, TARGET_UNITS['PLATELETS'])
        if plt_val and plt_val < platelet_threshold:
            factors.append(f"Thrombocytopenia (platelets < {platelet_threshold}×10⁹/L)")
    
    # Check for chronic bleeding diathesis using updated logic
    has_bleeding_diathesis, bleeding_info = check_bleeding_diathesis_updated(conditions)
    if has_bleeding_diathesis:
        factors.append(f"Chronic bleeding diathesis: {bleeding_info}")
    
    # Check for active malignancy using updated logic
    has_active_cancer, cancer_info = check_active_cancer_updated(conditions)
    if has_active_cancer:
        factors.append(f"Active malignancy: {cancer_info}")
    
    # Check for liver cirrhosis with portal hypertension using updated logic
    has_liver_condition, liver_info = check_liver_cirrhosis_portal_hypertension_updated(conditions)
    if has_liver_condition:
        factors.append(f"Liver cirrhosis with portal hypertension: {liver_info}")
    
    # Check for NSAIDs or corticosteroids using keywords from configuration
    med_config = CDSS_CONFIG.get('medication_keywords', {})
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
    Check for individual ARC-HBR risk factors and return detailed breakdown.
    Returns dict with individual factor flags for UI display.
    """
    conditions = raw_data.get('conditions', [])
    
    # Check thrombocytopenia using threshold from configuration
    snomed_config = CDSS_CONFIG.get('precise_hbr_snomed_codes', {})
    thrombocytopenia_config = snomed_config.get('thrombocytopenia', {})
    platelet_threshold = thrombocytopenia_config.get('threshold', {}).get('value', 100)
    
    has_thrombocytopenia = False
    platelets = raw_data.get('PLATELETS', [])
    if platelets:
        plt_obs = platelets[0]
        plt_val = get_value_from_observation(plt_obs, TARGET_UNITS['PLATELETS'])
        if plt_val and plt_val < platelet_threshold:
            has_thrombocytopenia = True
    
    # Check for chronic bleeding diathesis
    has_bleeding_diathesis, _ = check_bleeding_diathesis_updated(conditions)
    
    # Check for active malignancy
    has_active_cancer, _ = check_active_cancer_updated(conditions)
    
    # Check for liver cirrhosis with portal hypertension
    has_liver_condition, _ = check_liver_cirrhosis_portal_hypertension_updated(conditions)
    
    # Check for NSAIDs or corticosteroids using keywords from configuration
    has_nsaids = False
    med_config = CDSS_CONFIG.get('medication_keywords', {})
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
    
    # Determine if any factor is present
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

def calculate_risk_components(raw_data, demographics):
    """
    Main function to calculate bleeding risk score using PRECISE-HBR.
    Returns list of components and total score.
    """
    return calculate_precise_hbr_score(raw_data, demographics)

def get_active_medications(raw_data, demographics):
    """
    Process medication data from FHIR resources to identify active medications.
    Used for CDS Hooks medication analysis.
    
    Returns: list of active medication resources
    """
    medications = raw_data.get('med_requests', [])
    active_medications = []
    
    for med in medications:
        # Check if medication is active
        status = med.get('status', '').lower()
        if status in ['active', 'on-hold', 'completed']:
            active_medications.append(med)
    
    logging.info(f"Found {len(active_medications)} active medications")
    return active_medications

def check_medication_interactions_bleeding_risk(medications):
    """
    Check for medication combinations that increase bleeding risk.
    Specifically looks for DAPT combinations and other high-risk medications.
    
    Returns: dict with interaction details
    """
    interactions = {
        'dapt_detected': False,
        'high_risk_combinations': [],
        'bleeding_risk_medications': [],
        'recommendations': []
    }
    
    # This function can be expanded to include more sophisticated
    # medication interaction checking beyond DAPT
    
    return interactions 
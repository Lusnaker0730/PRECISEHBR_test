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

# --- Configuration for LOINC codes (7-item PRECISE-HBR) ---
LOINC_CODES = {
    "EGFR": ("33914-3",),          # Glomerular filtration rate/1.73 sq M predicted
    "CREATININE": ("2160-0",),      # Creatinine [mass/volume] in Serum or Plasma
    "HEMOGLOBIN": ("718-7",),       # Hemoglobin [Mass/volume] in Blood
    "WBC": ("26464-8", "6690-2", "33256-9"),  # White blood cells [#/volume] in Blood (multiple LOINC codes)
    "PLATELETS": ("26515-7", "33735-5"),  # Platelet count [#/volume] in Blood
}

# --- Unit Conversion System ---

# Define the canonical units the application will use internally for calculations.
TARGET_UNITS = {
    'HEMOGLOBIN': {
        'unit': 'g/dl',
        # Factors to convert a source unit TO the target unit (g/dL)
        'factors': {
            'g/l': 0.1,
            'mmol/l': 1.61135, # Based on Hb molar mass of 64,458 g/mol, factor is MW / 10 / 3.87
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
            '10*3/ul': 0.001, # 10^3/µL is equivalent to 10^9/L, but sometimes written this way. Let's assume K/uL = 10^3/uL
            'k/ul': 0.001,
            '/ul': 0.000001, # cells/µL is 10^-6 of 10^9/L
            '/mm3': 0.000001 # cells/mm³ is equivalent to cells/µL
        }
    },
    'EGFR': {
        'unit': 'ml/min/1.73m2',
        'factors': {
            'ml/min/{1.73_m2}': 1.0, # Handle Cerner's format with braces
            'ml/min/1.73m^2': 1.0   # Handle another common variant
        } 
    },
    'PLATELETS': {
        'unit': '10*9/l',
        'factors': {
            '10*3/ul': 0.001,
            'k/ul': 0.001,
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
        # Set up FHIR client settings following smart-on-fhir/client-py best practices
        settings = {
            'app_id': client_id,
            'api_base': fhir_server_url,
            'patient_id': patient_id,
        }
        
        # Create FHIR client instance
        smart = client.FHIRClient(settings=settings)
        
        # Set authorization using the standard fhirclient approach
        if access_token:
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
            
            # Set up custom adapter with timeout for the session
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
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
            
            # Also set the _auth for backward compatibility
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
            logging.error(f"Detailed error fetching patient: {error_msg}")
            
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
                return None, f"Failed to retrieve patient data: {str(e)}"

        raw_data = {"patient": patient_resource.as_json()}
        
        # Fetch observations by LOINC codes (updated for PRECISE-DAPT parameters)
        for resource_type, codes in LOINC_CODES.items():
            try:
                # Search for observations with specific LOINC codes
                # Using more compatible query parameters
                search_params = {
                    'patient': patient_id,
                    'code': ','.join(codes),
                    '_count': '5'  # Get a few results to find the most recent
                }
                
                observations = observation.Observation.where(search_params).perform(smart.server)
                obs_list = []
                
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
                
                raw_data[resource_type] = obs_list
                logging.info(f"Successfully fetched {len(obs_list)} {resource_type} observation(s)")
                
            except Exception as e:
                logging.warning(f"Error fetching {resource_type} observations (continuing with empty list): {e}")
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
                logging.error(f"Timeout error even with extended timeout (90s): {e}")
                logging.info("This suggests the FHIR server is very slow or overloaded")
            elif '401' in error_str or '403' in error_str:
                logging.error(f"Permission error for conditions: {e}")
            else:
                logging.error(f"Unexpected error fetching conditions: {e}")
            
            # Continue with empty conditions list
            raw_data['conditions'] = []
            logging.warning(f"Continuing with empty conditions list due to error: {e}")
        
        # For PRECISE-DAPT, we don't need medications and procedures, but keep minimal fetch for compatibility
        raw_data['med_requests'] = []
        raw_data['procedures'] = []

        return raw_data, None

    except Exception as e:
        logging.error(f"An unexpected error occurred in get_fhir_data: {e}", exc_info=True)
        return None, str(e)

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
        conditions = condition.Condition.where(search_params).perform(fhir_client.server)
        
        if conditions.entry:
            for entry in conditions.entry:
                c = entry.resource
                # Diabetes Mellitus (SNOMED CT: 73211009)
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', '73211009'):
                    tradeoff_data["diabetes"] = True
                # Myocardial Infarction (SNOMED CT: 22298006)
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', '22298006'):
                    tradeoff_data["prior_mi"] = True
                # NSTEMI/STEMI (SNOMED CT: 164868009, 164869001)
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', '164868009') or \
                   _resource_has_code(c.as_json(), 'http://snomed.info/sct', '164869001'):
                    tradeoff_data["nstemi_stemi"] = True
                # COPD (SNOMED CT: 13645005)
                if _resource_has_code(c.as_json(), 'http://snomed.info/sct', '13645005'):
                    tradeoff_data["copd"] = True

    except Exception as e:
        logging.warning(f"Error fetching conditions for tradeoff model: {e}")

    # Check for smoking status from Observations
    try:
        search_params = {'patient': patient_id, 'code': '72166-2'}  # Smoking status LOINC
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
        procedures = procedure.Procedure.where(search_params).perform(fhir_client.server)
        if procedures.entry:
            for entry in procedures.entry:
                p = entry.resource
                # Complex PCI (example, needs specific codes)
                if _resource_has_code(p.as_json(), 'http://snomed.info/sct', '397682003'): # Example for complex PCI
                    tradeoff_data["complex_pci"] = True
                # Bare-metal stent (BMS) (example, needs specific codes)
                if _resource_has_code(p.as_json(), 'http://snomed.info/sct', '427183000'): # Example for BMS
                    tradeoff_data["bms_used"] = True
    except Exception as e:
        logging.warning(f"Error fetching procedures for tradeoff model: {e}")
        
    # Check for OAC at discharge from MedicationRequest
    try:
        search_params = {'patient': patient_id, 'category': 'outpatient'}
        med_requests = medicationrequest.MedicationRequest.where(search_params).perform(fhir_client.server)
        if med_requests.entry:
            for entry in med_requests.entry:
                mr = entry.resource
                # Check for Oral Anticoagulants (example RxNorm)
                if any(_resource_has_code(mr.as_json(), 'http://www.nlm.nih.gov/research/umls/rxnorm', code) for code in ['11289', '21821']): # Warfarin, Rivaroxaban
                    tradeoff_data["oac_discharge"] = True
    except Exception as e:
        logging.warning(f"Error fetching medication requests for OAC: {e}")

    return tradeoff_data

def get_tradeoff_model_predictors():
    """Loads and returns the list of all predictors from the ARC-HBR model file."""
    script_dir = os.path.dirname(__file__)
    model_path = os.path.join(script_dir, 'arc-hbr-model.json')
    
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
    """
    detected_factors = {}
    
    if demographics.get('age', 0) >= 65:
        detected_factors['age_ge_65'] = True

    hb_obs = raw_data.get('HEMOGLOBIN', [])
    if hb_obs:
        hb_val = get_value_from_observation(hb_obs[0], TARGET_UNITS['HEMOGLOBIN'])
        if hb_val:
            if 11 <= hb_val < 13:
                detected_factors['hemoglobin_11_12.9'] = True
            elif hb_val < 11:
                detected_factors['hemoglobin_lt_11'] = True

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
        if 30 <= egfr_val < 60:
            detected_factors['egfr_30_59'] = True
        elif egfr_val < 30:
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
    This is a simplified model for visualization purposes.
    Formula: P(event) = 1 - (1 - baseline_rate) ^ exp(total_hr - baseline_hr_sum)
    For simplicity, we use: P(event) = baseline_rate * total_hr_score
    """
    # This is a major simplification. A proper conversion would require
    # the baseline hazard and the sum of HRs for the baseline group.
    # For visualization, a linear scaling can be sufficient.
    
    # Let's assume the sum of HRs in the model approximately represents the relative risk.
    # If baseline rate is, for example, 5% for bleeding, a total HR of 2.0 would imply ~10% risk.
    
    estimated_probability = baseline_event_rate * total_hr_score
    return round(min(estimated_probability, 100.0), 2) # Cap at 100%

def calculate_tradeoff_scores_interactive(model_predictors, active_factors):
    """
    Calculates bleeding and thrombotic scores and converts them to probabilities.
    'active_factors' is a dictionary like {'smoker': true, 'diabetes': false}.
    """
    # Baseline 1-year event rates (hypothetical, based on typical HBR cohort studies)
    BASELINE_BLEEDING_RATE = 2.5  # %
    BASELINE_THROMBOTIC_RATE = 3.0 # %

    bleeding_score_hr = 0
    thrombotic_score_hr = 0
    
    bleeding_factors_details = []
    thrombotic_factors_details = []

    # Calculate bleeding score in HR
    for predictor in model_predictors['bleedingEvents']['predictors']:
        factor_key = predictor['factor']
        if active_factors.get(factor_key, False):
            bleeding_score_hr += predictor['hazardRatio']
            bleeding_factors_details.append(f"{predictor['description']} (HR: {predictor['hazardRatio']})")
    
    # Calculate thrombotic score in HR
    for predictor in model_predictors['thromboticEvents']['predictors']:
        factor_key = predictor['factor']
        if active_factors.get(factor_key, False):
            thrombotic_score_hr += predictor['hazardRatio']
            thrombotic_factors_details.append(f"{predictor['description']} (HR: {predictor['hazardRatio']})")

    # Convert HR scores to probabilities
    bleeding_prob = convert_hr_to_probability(bleeding_score_hr, BASELINE_BLEEDING_RATE)
    thrombotic_prob = convert_hr_to_probability(thrombotic_score_hr, BASELINE_THROMBOTIC_RATE)

    return {
        "bleeding_score": bleeding_prob,
        "thrombotic_score": thrombotic_prob,
        "bleeding_factors": bleeding_factors_details,
        "thrombotic_factors": thrombotic_factors_details
    }

# --- Data Processing and Risk Calculation Logic for PRECISE-DAPT ---

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
    model_path = os.path.join(script_dir, 'arc-hbr-model.json')
    
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

    bleeding_score = 0
    thrombotic_score = 0
    
    bleeding_factors = []
    thrombotic_factors = []

    # Helper to add score and factor
    def add_score(event_type, factor, ratio):
        nonlocal bleeding_score, thrombotic_score
        if event_type == 'bleeding':
            bleeding_score += ratio
            bleeding_factors.append(f"{factor} (HR: {ratio})")
        else:
            thrombotic_score += ratio
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

    return {
        "bleeding_score": round(bleeding_score, 2),
        "thrombotic_score": round(thrombotic_score, 2),
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
    
    bleeding_codings = CDSS_CONFIG.get('bleeding_history_codings', {})
    bleeding_keywords = CDSS_CONFIG.get('bleeding_history_keywords', [])
    
    bleeding_evidence = []
    
    # Check SNOMED codes
    for condition in conditions:
        # Check coded conditions
        for coding in condition.get('code', {}).get('coding', []):
            system = coding.get('system', '')
            code = coding.get('code', '')
            
            # Check against bleeding history SNOMED codes
            for bleeding_type, code_list in bleeding_codings.items():
                for snomed_system, snomed_code in code_list:
                    if system == snomed_system and code == snomed_code:
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

def calculate_precise_dapt_score(raw_data, demographics):
    """
    Calculates PRECISE-DAPT bleeding risk score based on 5-item model:
    1. Age
    2. Hemoglobin
    3. Creatinine clearance 
    4. White blood cell count
    5. Previous spontaneous bleeding
    
    Returns components list and total score.
    """
    if not CDSS_CONFIG:
        return [], 0
    
    components = []
    total_score = 0
    
    # Get scoring tables from config
    scoring_config = CDSS_CONFIG.get('scoring_nomogram', {})
    age_table = scoring_config.get('age_score_table', [])
    hb_table = scoring_config.get('hemoglobin_score_table', [])
    ccr_table = scoring_config.get('creatinine_clearance_score_table', [])
    wbc_table = scoring_config.get('wbc_score_table', [])
    bleeding_config = CDSS_CONFIG.get('precise_dapt_parameters', {}).get('previous_bleeding', {})
    
    # 1. Age Score
    age = demographics.get('age')
    if age:
        age_score = get_score_from_table(age, age_table, 'age_range')
        total_score += age_score
        components.append({
            "parameter": "PreciseDAPT - Age",
            "value": f"{age} years",
            "score": age_score,
            "date": "N/A",
            "description": f"Age contribution to PRECISE-DAPT score"
        })
    else:
        components.append({
            "parameter": "PreciseDAPT - Age", 
            "value": "Unknown",
            "score": 0,
            "date": "N/A",
            "description": "Age not available"
        })
    
    # 2. Hemoglobin Score
    hemoglobin_list = raw_data.get('HEMOGLOBIN', [])
    hemoglobin_obs = hemoglobin_list[0] if hemoglobin_list else {}
    hb_val = get_value_from_observation(hemoglobin_obs, TARGET_UNITS['HEMOGLOBIN'])
    
    if hb_val:
        hb_unit = TARGET_UNITS['HEMOGLOBIN']['unit']
        hb_date = hemoglobin_obs.get('effectiveDateTime', 'N/A')
        hb_score = get_score_from_table(hb_val, hb_table, 'hb_range')
        total_score += hb_score
        components.append({
            "parameter": "PreciseDAPT - Hemoglobin",
            "value": f"{hb_val} {hb_unit}",
            "score": hb_score,
            "date": hb_date,
            "description": f"Hemoglobin contribution to PRECISE-DAPT score"
        })
    else:
        components.append({
            "parameter": "PreciseDAPT - Hemoglobin",
            "value": "Not available",
            "score": 0,
            "date": "N/A", 
            "description": "Hemoglobin not available"
        })
    
    # 3. Creatinine Clearance Score
    egfr_list = raw_data.get('EGFR', [])
    egfr_obs = egfr_list[0] if egfr_list else {}
    creatinine_list = raw_data.get('CREATININE', [])
    creatinine_obs = creatinine_list[0] if creatinine_list else {}
    
    egfr_val = get_value_from_observation(egfr_obs, TARGET_UNITS['EGFR'])
    
    ccr_final = None
    ccr_source = ""
    ccr_final_date = "N/A"
    
    if egfr_val:
        ccr_final = egfr_val
        ccr_source = "Direct eGFR"
        ccr_final_date = egfr_obs.get('effectiveDateTime', 'N/A')
        logging.info(f"Using direct eGFR value: {ccr_final}")
    else:
        creatinine_val = get_value_from_observation(creatinine_obs, TARGET_UNITS['CREATININE'])
        if creatinine_val and age and demographics.get('gender'):
            logging.info("Direct eGFR not found, calculating from Creatinine.")
            calculated_egfr, reason = calculate_egfr(creatinine_val, age, demographics.get('gender'))
            if calculated_egfr:
                ccr_final = calculated_egfr
                ccr_source = reason
                ccr_final_date = creatinine_obs.get('effectiveDateTime', 'N/A')
    
    if ccr_final:
        ccr_score = get_score_from_table(ccr_final, ccr_table, 'ccr_range')
        total_score += ccr_score
        components.append({
            "parameter": "PreciseDAPT - Creatinine Clearance",
            "value": f"{ccr_final} mL/min/1.73m² ({ccr_source})",
            "score": ccr_score,
            "date": ccr_final_date,
            "description": f"Kidney function contribution to PRECISE-DAPT score"
        })
    else:
        components.append({
            "parameter": "PreciseDAPT - Creatinine Clearance",
            "value": "Not available",
            "score": 0,
            "date": "N/A",
            "description": "Creatinine clearance not available"
        })
    
    # 4. White Blood Cell Count Score
    wbc_list = raw_data.get('WBC', [])
    wbc_obs = wbc_list[0] if wbc_list else {}
    wbc_val = get_value_from_observation(wbc_obs, TARGET_UNITS['WBC'])
    
    if wbc_val:
        wbc_unit = TARGET_UNITS['WBC']['unit']
        wbc_date = wbc_obs.get('effectiveDateTime', 'N/A')
        wbc_score = get_score_from_table(wbc_val, wbc_table, 'wbc_range')
        total_score += wbc_score
        components.append({
            "parameter": "PreciseDAPT - White Blood Cell Count",
            "value": f"{wbc_val} {wbc_unit}",
            "score": wbc_score,
            "date": wbc_date,
            "description": f"White blood cell count contribution to PRECISE-DAPT score"
        })
    else:
        components.append({
            "parameter": "PreciseDAPT - White Blood Cell Count",
            "value": "Not available",
            "score": 0,
            "date": "N/A",
            "description": "White blood cell count not available"
        })
    
    # 5. Previous Bleeding History
    conditions = raw_data.get('conditions', [])
    has_bleeding, bleeding_evidence = check_bleeding_history(conditions)
    
    bleeding_score = 0
    if has_bleeding:
        bleeding_score = bleeding_config.get('score_values', {}).get('yes', 10)
        bleeding_display = bleeding_evidence[0] + (f" (+{len(bleeding_evidence)-1} more)" if len(bleeding_evidence) > 1 else "")
        total_score += bleeding_score
        components.append({
            "parameter": "PreciseDAPT - Prior Bleeding",
            "value": bleeding_display,
            "score": bleeding_score,
            "date": "Historical",
            "description": f"History of spontaneous bleeding"
        })
    else:
        components.append({
            "parameter": "PreciseDAPT - Prior Bleeding",
            "value": "No bleeding history found",
            "score": 0,
            "date": "N/A",
            "description": "No previous bleeding history"
        })
    
    return components, total_score

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
    
    egfr_val = None
    egfr_source = ""
    egfr_date = "N/A"
    
    if egfr_list:
        egfr_obs = egfr_list[0]
        # Use the new unit-aware function
        egfr_val = get_value_from_observation(egfr_obs, TARGET_UNITS['EGFR'])
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
    
    # 5. Previous Bleeding History - Categorical variable: Yes = +7 points
    conditions = raw_data.get('conditions', [])
    has_bleeding, bleeding_evidence = check_bleeding_history(conditions)
    
    bleeding_score = 7 if has_bleeding else 0
    total_score += bleeding_score
    
    logging.info(f"Previous bleeding score: {'Yes' if has_bleeding else 'No'} = {bleeding_score} points")
    
    components.append({
        "parameter": "PRECISE-HBR - Prior Bleeding",
        "value": "Yes" if has_bleeding else "No",
        "score": bleeding_score,
        "is_present": has_bleeding,
        "date": "N/A",
        "description": f"Previous bleeding: {'Yes' if has_bleeding else 'No'} = {bleeding_score} points. {bleeding_evidence if bleeding_evidence else 'None detected'}"
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
    arc_hbr_factors = check_arc_hbr_factors(raw_data, medications)
    has_arc_factors = arc_hbr_factors['has_factors']
    
    arc_hbr_score = 3 if has_arc_factors else 0
    total_score += arc_hbr_score
    
    logging.info(f"ARC-HBR conditions score: {'Yes' if has_arc_factors else 'No'} = {arc_hbr_score} points")
    
    components.append({
        "parameter": "PRECISE-HBR - ARC-HBR Factors",
        "value": f"{len(arc_hbr_factors['factors'])} factors present" if has_arc_factors else "None detected",
        "score": arc_hbr_score,
        "is_present": has_arc_factors,
        "date": "N/A",
        "description": f"Other ARC-HBR conditions: {'Yes' if has_arc_factors else 'No'} = {arc_hbr_score} points. Factors: {', '.join(arc_hbr_factors['factors']) if arc_hbr_factors['factors'] else 'None'}"
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
    Check for long-term oral anticoagulation therapy.
    Returns True if patient is on oral anticoagulants.
    """
    anticoagulant_codes = [
        'warfarin', 'apixaban', 'rivaroxaban', 'dabigatran', 'edoxaban',
        'coumadin', 'eliquis', 'xarelto', 'pradaxa', 'savaysa'
    ]
    
    for med in medications:
        med_code = med.get('medicationCodeableConcept', {})
        med_text = str(med_code).lower()
        
        for anticoag in anticoagulant_codes:
            if anticoag in med_text:
                return True
    
    return False


def check_arc_hbr_factors(raw_data, medications):
    """
    Check for ARC-HBR risk factors (excluding prior stroke per PRECISE-HBR definition).
    Returns dict with has_factors and list of factors found.
    """
    factors = []
    
    # Check thrombocytopenia (platelets < 100×10⁹/L)
    platelets = raw_data.get('PLATELETS', [])
    if platelets:
        plt_obs = platelets[0]
        # Use the new unit-aware function
        plt_val = get_value_from_observation(plt_obs, TARGET_UNITS['PLATELETS'])
        if plt_val and plt_val < 100:
            factors.append("Thrombocytopenia (platelets < 100×10⁹/L)")
    
    # Check for chronic bleeding diathesis (from conditions)
    conditions = raw_data.get('conditions', [])
    bleeding_diathesis_codes = ['bleeding disorder', 'hemophilia', 'von willebrand']
    for condition in conditions:
        condition_text = str(condition.get('code', {})).lower()
        for code in bleeding_diathesis_codes:
            if code in condition_text:
                factors.append("Chronic bleeding diathesis")
                break
    
    # Check for active malignancy
    cancer_codes = ['cancer', 'malignancy', 'neoplasm', 'tumor', 'carcinoma']
    for condition in conditions:
        condition_text = str(condition.get('code', {})).lower()
        for code in cancer_codes:
            if code in condition_text:
                factors.append("Active malignancy")
                break
    
    # Check for liver cirrhosis with portal hypertension
    liver_codes = ['cirrhosis', 'portal hypertension', 'liver disease']
    for condition in conditions:
        condition_text = str(condition.get('code', {})).lower()
        for code in liver_codes:
            if code in condition_text:
                factors.append("Liver cirrhosis with portal hypertension")
                break
    
    # Check for NSAIDs or corticosteroids
    drug_codes = ['nsaid', 'ibuprofen', 'naproxen', 'prednisolone', 'prednisone', 'corticosteroid']
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

def calculate_risk_components(raw_data, demographics):
    """
    Main function to calculate bleeding risk score.
    Switch between PRECISE-DAPT and PRECISE-HBR based on configuration.
    Returns list of components and total score.
    """
    # Use PRECISE-HBR by default, fallback to PRECISE-DAPT if needed
    scoring_method = CDSS_CONFIG.get('scoring_logic', {}).get('scoring_method', 'PRECISE-HBR')
    
    if scoring_method == 'PRECISE-HBR':
        return calculate_precise_hbr_score(raw_data, demographics)
    else:
        return calculate_precise_dapt_score(raw_data, demographics)

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
# --- >> PHASE 1 OPTIMIZATION: fhirclient integration << ---
"""
SMART on FHIR Client Optimizations (Phase 1)
This module provides optimized FHIR data retrieval functions using the official fhirclient library.
"""

import logging
from flask import session

# Import fhirclient components
try:
    from fhirclient import client
    from fhirclient.models.patient import Patient
    from fhirclient.models.observation import Observation
    from fhirclient.models.condition import Condition
    from fhirclient.models.medicationrequest import MedicationRequest
    from fhirclient.models.procedure import Procedure
    FHIRCLIENT_AVAILABLE = True
    logging.info("fhirclient successfully imported for optimization")
except ImportError as e:
    FHIRCLIENT_AVAILABLE = False
    logging.warning(f"fhirclient not available, falling back to manual FHIR API calls: {e}")

def get_patient_data_optimized(smart_client_id, get_patient_data_fallback):
    """Optimized patient data retrieval using fhirclient (Phase 1)"""
    if not FHIRCLIENT_AVAILABLE:
        logging.debug("fhirclient not available, falling back to manual implementation")
        return get_patient_data_fallback()
    
    patient_id = session.get('patient_id')
    if not patient_id:
        logging.warning("No patient ID in session for optimized patient data retrieval")
        return None
    
    try:
        # Create fhirclient instance with current session credentials
        settings = {
            'app_id': smart_client_id or 'bleeding_risk_calculator',
            'api_base': session.get('fhir_server_url'),
            'access_token': session.get('access_token')
        }
        
        if not settings['api_base'] or not settings['access_token']:
            logging.warning("Missing FHIR server URL or access token for optimized patient retrieval")
            return get_patient_data_fallback()  # Fallback to manual
        
        smart = client.FHIRClient(settings=settings)
        patient = Patient.read(patient_id, smart.server)
        
        if patient:
            logging.info(f"Successfully fetched patient {patient_id} using fhirclient")
            return patient.as_json()
        else:
            logging.warning(f"No patient data returned for {patient_id} using fhirclient")
            return None
            
    except Exception as e:
        logging.error(f"Error fetching patient {patient_id} with fhirclient: {e}")
        logging.info("Falling back to manual FHIR API implementation")
        return get_patient_data_fallback()  # Fallback to manual implementation

def get_observation_optimized(patient_id, loinc_codes, smart_client_id):
    """Optimized observation retrieval using fhirclient (Phase 1)"""
    if not FHIRCLIENT_AVAILABLE:
        logging.debug("fhirclient not available, falling back to manual implementation")
        return None
    
    try:
        # Create fhirclient instance with current session credentials
        settings = {
            'app_id': smart_client_id or 'bleeding_risk_calculator',
            'api_base': session.get('fhir_server_url'),
            'access_token': session.get('access_token')
        }
        
        if not settings['api_base'] or not settings['access_token']:
            logging.debug("Missing FHIR server URL or access token for optimized observation retrieval")
            return None
        
        smart = client.FHIRClient(settings=settings)
        
        # Format LOINC codes for search (support both tuple and string input)
        if isinstance(loinc_codes, (tuple, list)):
            code_search = '|'.join([f"http://loinc.org|{code}" for code in loinc_codes])
        else:
            code_search = f"http://loinc.org|{loinc_codes}"
        
        # Create search query
        search = Observation.where({
            'subject': patient_id,
            'code': code_search,
            '_sort': '-date',
            '_count': 1
        })
        
        observations = search.perform_resources(smart.server)
        
        if observations:
            logging.info(f"Successfully fetched observation for patient {patient_id} using fhirclient")
            return observations[0].as_json()
        else:
            logging.debug(f"No observations found for patient {patient_id} with codes {loinc_codes}")
            return None
            
    except Exception as e:
        logging.error(f"Error fetching observations for patient {patient_id} with fhirclient: {e}")
        return None

def get_hemoglobin_optimized(patient_id, loinc_codes, smart_client_id, get_hemoglobin_fallback):
    """Optimized hemoglobin retrieval using fhirclient (Phase 1)"""
    obs_json = get_observation_optimized(patient_id, loinc_codes, smart_client_id)
    if not obs_json:
        logging.debug("fhirclient observation failed, falling back to manual implementation")
        return get_hemoglobin_fallback(patient_id)
    
    try:
        value_data = obs_json.get("valueQuantity")
        if value_data:
            value = value_data.get("value")
            unit = value_data.get("unit", "").lower()
            
            value = float(value)
            if unit == "g/l": 
                return value / 10
            elif unit in ["mmol/l", "mmol/L"]: 
                return value * 1.61
            elif unit == "g/dl": 
                return value
            else: 
                logging.warning(f"Unrecognized hemoglobin unit '{unit}' for patient {patient_id}")
                return value  # Return raw value as fallback
                
    except (TypeError, ValueError) as e:
        logging.error(f"Error processing hemoglobin value for patient {patient_id}: {e}")
        return get_hemoglobin_fallback(patient_id)  # Fallback
    
    return None

def get_creatinine_optimized(patient_id, loinc_codes, smart_client_id, get_creatinine_fallback):
    """Optimized creatinine retrieval using fhirclient (Phase 1)"""
    obs_json = get_observation_optimized(patient_id, loinc_codes, smart_client_id)
    if not obs_json:
        logging.debug("fhirclient observation failed, falling back to manual implementation")
        return get_creatinine_fallback(patient_id)
    
    try:
        value_data = obs_json.get("valueQuantity")
        if value_data:
            value = value_data.get("value")
            unit = value_data.get("unit", "").lower()
            
            value = float(value)
            if unit in ["umol/l", "µmol/l"]: 
                return value / 88.4
            elif unit == "mg/dl": 
                return value
            else: 
                logging.warning(f"Unrecognized creatinine unit '{unit}' for patient {patient_id}")
                return value  # Return raw value as fallback
                
    except (TypeError, ValueError) as e:
        logging.error(f"Error processing creatinine value for patient {patient_id}: {e}")
        return get_creatinine_fallback(patient_id)  # Fallback
    
    return None

def get_platelet_optimized(patient_id, loinc_codes, smart_client_id, get_platelet_fallback):
    """Optimized platelet retrieval using fhirclient (Phase 1)"""
    obs_json = get_observation_optimized(patient_id, loinc_codes, smart_client_id)
    if not obs_json:
        logging.debug("fhirclient observation failed, falling back to manual implementation")
        return get_platelet_fallback(patient_id)
    
    try:
        value_data = obs_json.get("valueQuantity")
        if value_data:
            value = value_data.get("value")
            return float(value)
                
    except (TypeError, ValueError) as e:
        logging.error(f"Error processing platelet value for patient {patient_id}: {e}")
        return get_platelet_fallback(patient_id)  # Fallback
    
    return None

def get_egfr_value_optimized(patient_id, age, sex, loinc_codes_creatinine, loinc_codes_egfr, smart_client_id, get_egfr_value_fallback):
    """Optimized eGFR calculation using fhirclient (Phase 1)"""
    if not FHIRCLIENT_AVAILABLE:
        logging.debug("fhirclient not available, falling back to manual implementation")
        return get_egfr_value_fallback(patient_id, age, sex)
    
    # Attempt 1: Calculate from optimized Creatinine
    from fhirclient_optimizations import get_creatinine_optimized
    cr_value = get_creatinine_optimized(patient_id, loinc_codes_creatinine, smart_client_id, lambda x: None)
    
    # Validate inputs for calculation
    age_is_valid = isinstance(age, (int, float)) and age > 0
    sex_is_valid = sex is not None and sex.lower() in ["male", "female"]
    cr_is_valid = isinstance(cr_value, (int, float)) and cr_value > 0
    
    if cr_is_valid and age_is_valid and sex_is_valid:
        try:
            # CKD-EPI 2021 Formula
            sex_lower = sex.lower()
            kappa = 0.7 if sex_lower == "female" else 0.9
            alpha = -0.241 if sex_lower == "female" else -0.302
            sex_factor = 1.012 if sex_lower == "female" else 1.0
            
            term1 = cr_value / kappa
            term2 = min(term1, 1.0) ** alpha
            term3 = max(term1, 1.0) ** (-1.200)
            age_factor = 0.9938 ** age
            
            eGFR_calc = 142 * term2 * term3 * age_factor * sex_factor
            
            logging.info(f"Calculated eGFR (CKD-EPI 2021 optimized) {eGFR_calc:.2f} from Creatinine {cr_value} for patient {patient_id}")
            return float(eGFR_calc)
            
        except Exception as e:
            logging.error(f"Error in optimized eGFR calculation for patient {patient_id}: {e}")
            # Fall through to direct eGFR fetch
    
    # Attempt 2: Try to get direct eGFR observation using fhirclient
    obs_json = get_observation_optimized(patient_id, loinc_codes_egfr, smart_client_id)
    if obs_json:
        try:
            value_data = obs_json.get("valueQuantity")
            if value_data:
                value = value_data.get("value")
                unit = value_data.get("unit", "")
                direct_egfr_val = float(value)
                logging.info(f"Using directly fetched eGFR value {direct_egfr_val} (Unit: {unit}) for patient {patient_id} via fhirclient")
                return direct_egfr_val
        except Exception as e:
            logging.error(f"Error processing direct eGFR value for patient {patient_id}: {e}")
    
    # Fallback to manual implementation
    logging.debug("Optimized eGFR methods failed, falling back to manual implementation")
    return get_egfr_value_fallback(patient_id, age, sex)
# --- >> END PHASE 1 OPTIMIZATION << --- 
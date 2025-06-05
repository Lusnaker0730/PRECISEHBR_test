# --- >> PHASE 1 OPTIMIZATION: fhirclient integration << ---
"""
SMART on FHIR Client Optimizations (Phase 1 & Phase 2)
This module provides optimized FHIR data retrieval functions using the official fhirclient library.

Phase 1: Basic fhirclient integration with fallback mechanisms
Phase 2: Advanced batch operations, intelligent caching, and performance optimization
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from flask import session
import urllib.parse

# Import fhirclient components
try:
    from fhirclient import client
    from fhirclient.models.patient import Patient
    from fhirclient.models.observation import Observation
    from fhirclient.models.condition import Condition
    from fhirclient.models.medicationrequest import MedicationRequest
    from fhirclient.models.procedure import Procedure
    from fhirclient.models.bundle import Bundle
    FHIRCLIENT_AVAILABLE = True
    logging.info("fhirclient successfully imported for optimization")
except ImportError as e:
    FHIRCLIENT_AVAILABLE = False
    logging.warning(f"fhirclient not available, falling back to manual FHIR API calls: {e}")

# --- >> PHASE 2: Advanced Optimization Features << ---

class PerformanceMetrics:
    """Performance monitoring for optimization operations"""
    def __init__(self):
        self.metrics = defaultdict(list)
        self.cache_stats = {'hits': 0, 'misses': 0, 'errors': 0}
        self._lock = threading.Lock()
    
    def record_operation(self, operation_type: str, duration: float, success: bool = True):
        """Record performance metrics for an operation"""
        with self._lock:
            self.metrics[operation_type].append({
                'duration': duration,
                'timestamp': datetime.now(),
                'success': success
            })
    
    def record_cache_hit(self):
        """Record cache hit"""
        with self._lock:
            self.cache_stats['hits'] += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        with self._lock:
            self.cache_stats['misses'] += 1
    
    def record_cache_error(self):
        """Record cache error"""
        with self._lock:
            self.cache_stats['errors'] += 1
    
    def get_summary(self, operation_type: str = None) -> Dict:
        """Get performance summary"""
        with self._lock:
            if operation_type:
                ops = self.metrics.get(operation_type, [])
                if not ops:
                    return {'operation': operation_type, 'count': 0}
                
                durations = [op['duration'] for op in ops if op['success']]
                return {
                    'operation': operation_type,
                    'count': len(ops),
                    'success_rate': sum(1 for op in ops if op['success']) / len(ops),
                    'avg_duration': sum(durations) / len(durations) if durations else 0,
                    'min_duration': min(durations) if durations else 0,
                    'max_duration': max(durations) if durations else 0
                }
            else:
                total_ops = sum(len(ops) for ops in self.metrics.values())
                cache_total = sum(self.cache_stats.values())
                cache_hit_rate = self.cache_stats['hits'] / cache_total if cache_total > 0 else 0
                
                return {
                    'total_operations': total_ops,
                    'cache_hit_rate': cache_hit_rate,
                    'cache_stats': self.cache_stats.copy(),
                    'operations': {op_type: self.get_summary(op_type) for op_type in self.metrics.keys()}
                }

class IntelligentCache:
    """Intelligent caching system for FHIR resources"""
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self.cache = {}
        self.access_times = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._lock = threading.Lock()
    
    def _generate_key(self, resource_type: str, patient_id: str, params: Dict = None) -> str:
        """Generate cache key"""
        key_parts = [resource_type, patient_id]
        if params:
            sorted_params = sorted(params.items())
            key_parts.extend([f"{k}:{v}" for k, v in sorted_params])
        return "|".join(key_parts)
    
    def _is_expired(self, entry: Dict) -> bool:
        """Check if cache entry is expired"""
        return datetime.now() > entry['expires_at']
    
    def _evict_if_needed(self):
        """Evict old entries if cache is full"""
        if len(self.cache) >= self.max_size:
            # Remove oldest accessed entries
            sorted_keys = sorted(self.access_times.items(), key=lambda x: x[1])
            keys_to_remove = [k for k, _ in sorted_keys[:self.max_size // 4]]  # Remove 25%
            for key in keys_to_remove:
                self.cache.pop(key, None)
                self.access_times.pop(key, None)
    
    def get(self, resource_type: str, patient_id: str, params: Dict = None) -> Optional[Any]:
        """Get cached resource"""
        key = self._generate_key(resource_type, patient_id, params)
        
        with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if not self._is_expired(entry):
                    self.access_times[key] = datetime.now()
                    return entry['data']
                else:
                    # Remove expired entry
                    self.cache.pop(key, None)
                    self.access_times.pop(key, None)
        
        return None
    
    def set(self, resource_type: str, patient_id: str, data: Any, params: Dict = None, ttl: int = None):
        """Set cached resource"""
        key = self._generate_key(resource_type, patient_id, params)
        ttl = ttl or self.default_ttl
        
        with self._lock:
            self._evict_if_needed()
            
            self.cache[key] = {
                'data': data,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(seconds=ttl)
            }
            self.access_times[key] = datetime.now()
    
    def clear_patient(self, patient_id: str):
        """Clear all cached data for a specific patient"""
        with self._lock:
            keys_to_remove = [k for k in self.cache.keys() if patient_id in k]
            for key in keys_to_remove:
                self.cache.pop(key, None)
                self.access_times.pop(key, None)

class BatchOperationManager:
    """Manager for batch FHIR operations"""
    def __init__(self, smart_client: Optional[Any] = None):
        self.smart_client = smart_client
        self.batch_requests = []
        self.max_batch_size = 50  # Typical FHIR server limit
    
    def add_request(self, resource_type: str, search_params: Dict):
        """Add a request to the batch"""
        self.batch_requests.append({
            'resource_type': resource_type,
            'params': search_params,
            'method': 'GET'
        })
    
    def execute_batch(self) -> Dict[str, Any]:
        """Execute batch requests"""
        if not self.smart_client or not self.batch_requests:
            return {}
        
        results = {}
        
        # Split into chunks if needed
        for i in range(0, len(self.batch_requests), self.max_batch_size):
            chunk = self.batch_requests[i:i + self.max_batch_size]
            
            try:
                # Create bundle for batch request
                bundle = Bundle()
                bundle.type = "batch"
                bundle.entry = []
                
                for idx, request in enumerate(chunk):
                    # Create bundle entry for each request
                    entry = Bundle.BundleEntry()
                    entry.request = Bundle.BundleEntryRequest()
                    entry.request.method = request['method']
                    
                    # Build URL with parameters
                    url = request['resource_type']
                    if request['params']:
                        params_str = '&'.join([f"{k}={v}" for k, v in request['params'].items()])
                        url += f"?{params_str}"
                    
                    entry.request.url = url
                    bundle.entry.append(entry)
                
                # Execute batch request
                response = bundle.create(self.smart_client.server)
                
                if response and hasattr(response, 'entry'):
                    for idx, entry in enumerate(response.entry):
                        request_key = f"batch_{i + idx}"
                        if entry.response and entry.response.status.startswith('2'):
                            results[request_key] = entry.resource.as_json() if entry.resource else None
                        else:
                            results[request_key] = None
                            
            except Exception as e:
                logging.error(f"Batch execution failed: {e}")
                # Return individual None results for failed batch
                for idx in range(len(chunk)):
                    results[f"batch_{i + idx}"] = None
        
        return results
    
    def clear(self):
        """Clear batch requests"""
        self.batch_requests = []

# Global instances
performance_metrics = PerformanceMetrics()
intelligent_cache = IntelligentCache()

# --- >> PHASE 2: Enhanced Functions << ---

def get_smart_client_cached(smart_client_id: str) -> Optional[Any]:
    """Get or create cached SMART client"""
    cache_key = f"smart_client_{session.get('fhir_server_url')}_{session.get('access_token', '')[:10]}"
    
    client_instance = intelligent_cache.get('smart_client', cache_key)
    if client_instance:
        performance_metrics.record_cache_hit()
        return client_instance
    
    performance_metrics.record_cache_miss()
    
    try:
        settings = {
            'app_id': smart_client_id or 'bleeding_risk_calculator',
            'api_base': session.get('fhir_server_url'),
            'access_token': session.get('access_token')
        }
        
        if not settings['api_base'] or not settings['access_token']:
            return None
        
        smart = client.FHIRClient(settings=settings)
        intelligent_cache.set('smart_client', cache_key, smart, ttl=1800)  # 30 minutes
        return smart
        
    except Exception as e:
        logging.error(f"Error creating SMART client: {e}")
        performance_metrics.record_cache_error()
        return None

def get_multiple_observations_batch(patient_id: str, observation_configs: List[Dict], smart_client_id: str) -> Dict[str, Any]:
    """Get multiple observations using batch operations (Phase 2)"""
    if not FHIRCLIENT_AVAILABLE:
        return {}
    
    start_time = time.time()
    
    try:
        smart = get_smart_client_cached(smart_client_id)
        if not smart:
            return {}
        
        batch_manager = BatchOperationManager(smart)
        results = {}
        
        # Check cache first
        cached_results = {}
        uncached_configs = []
        
        for config in observation_configs:
            cache_params = {
                'codes': config.get('loinc_codes'),
                'count': config.get('count', 1)
            }
            cached_data = intelligent_cache.get('observation', patient_id, cache_params)
            if cached_data:
                cached_results[config['name']] = cached_data
                performance_metrics.record_cache_hit()
            else:
                uncached_configs.append(config)
                performance_metrics.record_cache_miss()
        
        # Batch fetch uncached observations
        if uncached_configs:
            for config in uncached_configs:
                loinc_codes = config.get('loinc_codes', [])
                if isinstance(loinc_codes, (tuple, list)):
                    code_search = '|'.join([f"http://loinc.org|{code}" for code in loinc_codes])
                else:
                    code_search = f"http://loinc.org|{loinc_codes}"
                
                search_params = {
                    'subject': patient_id,
                    'code': code_search,
                    '_sort': '-date',
                    '_count': config.get('count', 1)
                }
                
                batch_manager.add_request('Observation', search_params)
            
            batch_results = batch_manager.execute_batch()
            
            # Process batch results and cache them
            for idx, config in enumerate(uncached_configs):
                batch_key = f"batch_{idx}"
                if batch_key in batch_results and batch_results[batch_key]:
                    obs_data = batch_results[batch_key]
                    results[config['name']] = obs_data
                    
                    # Cache the result
                    cache_params = {
                        'codes': config.get('loinc_codes'),
                        'count': config.get('count', 1)
                    }
                    intelligent_cache.set('observation', patient_id, obs_data, cache_params)
                else:
                    results[config['name']] = None
        
        # Combine cached and fresh results
        results.update(cached_results)
        
        duration = time.time() - start_time
        performance_metrics.record_operation('batch_observations', duration, True)
        
        logging.info(f"Batch observation fetch completed in {duration:.3f}s for patient {patient_id}")
        return results
        
    except Exception as e:
        duration = time.time() - start_time
        performance_metrics.record_operation('batch_observations', duration, False)
        logging.error(f"Error in batch observation fetch: {e}")
        return {}

def get_lab_values_optimized_batch(patient_id: str, age: int, sex: str, smart_client_id: str, loinc_codes_dict: Dict) -> Dict[str, Any]:
    """Get all lab values in a single optimized batch operation (Phase 2)"""
    if not FHIRCLIENT_AVAILABLE:
        return {}
    
    # Define observation configurations for batch operation
    obs_configs = [
        {
            'name': 'hemoglobin',
            'loinc_codes': loinc_codes_dict.get('HEMOGLOBIN', []),
            'count': 1
        },
        {
            'name': 'creatinine',
            'loinc_codes': loinc_codes_dict.get('CREATININE', []),
            'count': 1
        },
        {
            'name': 'platelet',
            'loinc_codes': loinc_codes_dict.get('PLATELET', []),
            'count': 1
        },
        {
            'name': 'egfr_direct',
            'loinc_codes': loinc_codes_dict.get('EGFR_DIRECT', []),
            'count': 1
        }
    ]
    
    # Get all observations in batch
    batch_results = get_multiple_observations_batch(patient_id, obs_configs, smart_client_id)
    
    # Process results
    lab_values = {}
    
    # Process Hemoglobin
    hb_obs = batch_results.get('hemoglobin')
    if hb_obs and hb_obs.get('valueQuantity'):
        lab_values['hemoglobin'] = _process_hemoglobin_value(hb_obs['valueQuantity'])
    else:
        lab_values['hemoglobin'] = None
    
    # Process Creatinine
    cr_obs = batch_results.get('creatinine')
    if cr_obs and cr_obs.get('valueQuantity'):
        lab_values['creatinine'] = _process_creatinine_value(cr_obs['valueQuantity'])
    else:
        lab_values['creatinine'] = None
    
    # Process Platelet
    plt_obs = batch_results.get('platelet')
    if plt_obs and plt_obs.get('valueQuantity'):
        lab_values['platelet'] = _process_platelet_value(plt_obs['valueQuantity'])
    else:
        lab_values['platelet'] = None
    
    # Process eGFR (direct or calculated)
    egfr_obs = batch_results.get('egfr_direct')
    if egfr_obs and egfr_obs.get('valueQuantity'):
        lab_values['egfr'] = _process_egfr_value(egfr_obs['valueQuantity'])
    else:
        # Calculate eGFR from creatinine if available
        lab_values['egfr'] = _calculate_egfr_ckd_epi(lab_values.get('creatinine'), age, sex)
    
    return lab_values

def _process_hemoglobin_value(value_quantity: Dict) -> Optional[float]:
    """Process hemoglobin observation value"""
    try:
        value = float(value_quantity.get("value"))
        unit = value_quantity.get("unit", "").lower()
        
        if unit == "g/l": 
            return value / 10
        elif unit in ["mmol/l", "mmol/L"]: 
            return value * 1.61
        elif unit == "g/dl": 
            return value
        else: 
            logging.warning(f"Unrecognized hemoglobin unit '{unit}'")
            return value  # Return raw value as fallback
    except (TypeError, ValueError) as e:
        logging.error(f"Error processing hemoglobin value: {e}")
        return None

def _process_creatinine_value(value_quantity: Dict) -> Optional[float]:
    """Process creatinine observation value"""
    try:
        value = float(value_quantity.get("value"))
        unit = value_quantity.get("unit", "").lower()
        
        if unit in ["umol/l", "µmol/l"]: 
            return value / 88.4
        elif unit == "mg/dl": 
            return value
        else: 
            logging.warning(f"Unrecognized creatinine unit '{unit}'")
            return value  # Return raw value as fallback
    except (TypeError, ValueError) as e:
        logging.error(f"Error processing creatinine value: {e}")
        return None

def _process_platelet_value(value_quantity: Dict) -> Optional[float]:
    """Process platelet observation value"""
    try:
        return float(value_quantity.get("value"))
    except (TypeError, ValueError) as e:
        logging.error(f"Error processing platelet value: {e}")
        return None

def _process_egfr_value(value_quantity: Dict) -> Optional[float]:
    """Process eGFR observation value"""
    try:
        return float(value_quantity.get("value"))
    except (TypeError, ValueError) as e:
        logging.error(f"Error processing eGFR value: {e}")
        return None

def _calculate_egfr_ckd_epi(creatinine: Optional[float], age: int, sex: str) -> Optional[float]:
    """Calculate eGFR using CKD-EPI 2021 formula"""
    if not creatinine or not age or not sex:
        return None
    
    try:
        sex_lower = sex.lower()
        if sex_lower not in ["male", "female"]:
            return None
        
        kappa = 0.7 if sex_lower == "female" else 0.9
        alpha = -0.241 if sex_lower == "female" else -0.302
        sex_factor = 1.012 if sex_lower == "female" else 1.0
        
        term1 = creatinine / kappa
        term2 = min(term1, 1.0) ** alpha
        term3 = max(term1, 1.0) ** (-1.200)
        age_factor = 0.9938 ** age
        
        return 142 * term2 * term3 * age_factor * sex_factor
        
    except Exception as e:
        logging.error(f"Error calculating eGFR: {e}")
        return None

def get_performance_summary() -> Dict:
    """Get current performance metrics summary"""
    return performance_metrics.get_summary()

def clear_patient_cache(patient_id: str):
    """Clear all cached data for a specific patient"""
    intelligent_cache.clear_patient(patient_id)

# --- >> PHASE 1 FUNCTIONS (MAINTAINED FOR BACKWARD COMPATIBILITY) << ---

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

def get_observation_optimized(patient_id, loinc_codes, smart_client_id, fallback_func):
    """
    Enhanced optimized observation fetching with better error handling
    """
    try:
        if not FHIRCLIENT_AVAILABLE:
            return fallback_func(patient_id)
        
        # Enhanced error handling for URL encoding issues
        try:
            # Ensure patient_id is properly encoded
            if isinstance(patient_id, bytes):
                patient_id = patient_id.decode('utf-8')
            
            # Ensure LOINC codes are properly formatted
            if isinstance(loinc_codes, str):
                codes_param = loinc_codes
            elif isinstance(loinc_codes, list):
                codes_param = ','.join(str(code) for code in loinc_codes)
            else:
                codes_param = str(loinc_codes)
            
            smart_client = get_smart_client_cached(smart_client_id)
            if not smart_client:
                return fallback_func(patient_id)
            
            # Use safer URL construction
            search_params = {
                'patient': patient_id,
                'code': codes_param,
                '_sort': '-date',
                '_count': '10'
            }
            
            observations = Observation.where(search_params).perform(smart_client.server)
            
            if observations and len(observations) > 0:
                performance_metrics.record_operation('observation_fetch', 0.1, True)
                return observations[0]  # Return most recent
            else:
                performance_metrics.record_operation('observation_fetch', 0.1, False)
                return fallback_func(patient_id)
                
        except (UnicodeDecodeError, UnicodeEncodeError, TypeError) as encoding_error:
            logging.warning(f"Encoding error in observation fetch for patient {patient_id}: {encoding_error}")
            return fallback_func(patient_id)
        except Exception as fhir_error:
            if "quote_from_bytes" in str(fhir_error):
                logging.warning(f"FHIR client URL encoding issue for patient {patient_id}: {fhir_error}")
            else:
                logging.error(f"FHIR client error for patient {patient_id}: {fhir_error}")
            return fallback_func(patient_id)
            
    except Exception as e:
        logging.error(f"Error in optimized observation fetch: {e}")
        return fallback_func(patient_id)

def get_hemoglobin_optimized(patient_id, loinc_codes, smart_client_id, get_hemoglobin_fallback):
    """Optimized hemoglobin retrieval using fhirclient (Phase 1)"""
    obs_json = get_observation_optimized(patient_id, loinc_codes, smart_client_id, lambda x: None)
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
    obs_json = get_observation_optimized(patient_id, loinc_codes, smart_client_id, lambda x: None)
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
    obs_json = get_observation_optimized(patient_id, loinc_codes, smart_client_id, lambda x: None)
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
    obs_json = get_observation_optimized(patient_id, loinc_codes_egfr, smart_client_id, lambda x: None)
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
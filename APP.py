import os
import json
import math
import datetime
import logging
import hashlib # For PKCE
import base64  # For PKCE
from urllib.parse import urlencode, urljoin # Added urljoin
import re # For PKCE code_verifier cleanup
import time # For ValueSet caching

from dotenv import load_dotenv
from flask import Flask, request, jsonify, url_for, redirect, session, render_template, flash
import requests
from werkzeug.security import generate_password_hash, check_password_hash # Kept if needed elsewhere

# --- Authentication Imports ---
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import jwt # For ID Token validation
from jwt import PyJWKClient # For ID Token validation
# --- End Authentication Imports ---

from flask_cors import CORS

# --- SMART on FHIR Client (Phase 1 Optimization) ---
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

# Import optimization functions
try:
    import fhirclient_optimizations
    OPTIMIZATIONS_AVAILABLE = False  # EMERGENCY DISABLE - Force manual mode only
    logging.info("fhirclient optimizations module imported but DISABLED for stability")
except ImportError as e:
    OPTIMIZATIONS_AVAILABLE = False
    logging.warning(f"fhirclient optimizations not available: {e}")
# --- End SMART on FHIR Client Imports ---

# --- Load Environment Variables ---
load_dotenv()

# --- >> PRODUCTION SECURITY: Environment Variables Validation << ---
REQUIRED_ENV_VARS = [
    'FLASK_SECRET_KEY',
    'SMART_CLIENT_ID',
    'SMART_REDIRECT_URI',
    'APP_BASE_URL'
]

def validate_environment():
    """驗證必要的環境變數"""
    missing_vars = []
    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Validate environment on startup
try:
    validate_environment()
    logging.info("Environment variables validation passed")
except ValueError as e:
    logging.error(f"Environment validation failed: {e}")
    # In production, you might want to exit here
    # raise e
# --- >> END PRODUCTION SECURITY << ---

# --- >> SMART 設定 (從環境變數讀取) << ---
SMART_CLIENT_ID = os.getenv('SMART_CLIENT_ID')
SMART_CLIENT_SECRET = os.getenv('SMART_CLIENT_SECRET') # Public client 可能不需要
SMART_SCOPES = os.getenv('SMART_SCOPES', 'launch/patient openid fhirUser profile email patient/Patient.read patient/Observation.read patient/Condition.read patient/MedicationRequest.read online_access') # 加入 online_access

# --- MODIFIED: Read SMART_REDIRECT_URI from environment and clean it ---
raw_redirect_uri = os.getenv('SMART_REDIRECT_URI')
if raw_redirect_uri:
    # Remove any comments (starting with #) and clean whitespace
    SMART_REDIRECT_URI = raw_redirect_uri.split('#')[0].strip()
    # Additional validation - ensure no spaces or comments remain
    if ' ' in SMART_REDIRECT_URI:
        SMART_REDIRECT_URI = SMART_REDIRECT_URI.split()[0]
    logging.info(f"SMART_REDIRECT_URI from os.getenv, cleaned: '{SMART_REDIRECT_URI}'")
else:
    SMART_REDIRECT_URI = "http://127.0.0.1:8080/callback"
    logging.info(f"SMART_REDIRECT_URI not in os.getenv, using default: '{SMART_REDIRECT_URI}'")
# --- END MODIFIED ---

# --- >> 結束 SMART 設定 << ---
APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://127.0.0.1:8080') # 本地開發預設值

# --- >> NEW: LOINC Code Definitions << ---
LOINC_CODES = {
    "CREATININE": ("2160-0", "38483-4", "59826-8"),
    "HEMOGLOBIN": ("718-7", "30313-1", "59260-0"),
    "PLATELET": ("777-3", "26515-7", "778-1"), # Based on user's recent change in get_platelet
    "EGFR_DIRECT": ("33914-3",) # Direct eGFR observation LOINC
}
# --- >> END NEW: LOINC Code Definitions << ---

# --- >> SMART Scope Management << ---
def validate_and_optimize_scopes(requested_scopes, context='patient'):
    """
    Validates and optimizes SMART scopes based on Oracle Health best practices.
    Returns optimized scope string.
    """
    scopes = requested_scopes.split() if isinstance(requested_scopes, str) else requested_scopes
    
    # Base required scopes
    base_scopes = ['openid', 'fhirUser']
    
    # Context-specific scopes
    if context == 'patient':
        base_scopes.append('launch/patient')
        # Ensure patient context for all clinical data scopes
        clinical_scopes = []
        for scope in scopes:
            if scope.startswith('user/') and any(resource in scope for resource in ['Patient', 'Observation', 'Condition', 'MedicationRequest', 'Procedure']):
                # Convert user scopes to patient scopes for patient context
                clinical_scopes.append(scope.replace('user/', 'patient/'))
            elif scope.startswith('patient/'):
                clinical_scopes.append(scope)
            elif scope in ['openid', 'fhirUser', 'profile', 'email', 'online_access', 'offline_access', 'launch', 'launch/patient']:
                clinical_scopes.append(scope)
        scopes = clinical_scopes
    
    # Add refresh capability for better user experience
    if 'online_access' not in scopes and 'offline_access' not in scopes:
        scopes.append('online_access')
    
    # Combine and deduplicate
    all_scopes = list(set(base_scopes + scopes))
    
    # Remove any invalid or unsupported scopes
    valid_scope_patterns = [
        r'^openid$',
        r'^fhirUser$',
        r'^profile$',
        r'^email$',
        r'^launch$',
        r'^launch/patient$',
        r'^launch/encounter$',
        r'^online_access$',
        r'^offline_access$',
        r'^(patient|user|system)/(Patient|Observation|Condition|MedicationRequest|Procedure|Encounter|AllergyIntolerance|DiagnosticReport)\.(read|write|\*)$'
    ]
    
    import re
    validated_scopes = []
    for scope in all_scopes:
        if any(re.match(pattern, scope) for pattern in valid_scope_patterns):
            validated_scopes.append(scope)
        else:
            logging.warning(f"Removing invalid scope: {scope}")
    
    return ' '.join(validated_scopes)

# --- >> 結束 SMART Scope Management << ---

# --- Load External CDSS Configuration ---
# Support custom config path for testing
CONFIG_FILE = os.getenv('CDSS_CONFIG_PATH', os.path.join(os.path.dirname(__file__), "cdss_config.json"))
try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        cdss_config = json.load(f)
    logging.basicConfig(level=logging.INFO) # Set basic logging before app logger is ready
    logging.info(f"Loaded CDSS configuration version {cdss_config.get('version', 'N/A')}")

    # --- Convert loaded code lists back to sets of tuples/sets for efficient lookup ---
    OAC_CODINGS_CONFIG = set(tuple(item) for item in cdss_config.get('medication_codings', {}).get('oac', []))
    NSAID_STEROID_CODINGS_CONFIG = set(tuple(item) for item in cdss_config.get('medication_codings', {}).get('nsaid_steroid', []))
    CONDITION_CODES_SCORE_2_CONFIG = set(
        tuple(item) for item in cdss_config.get('condition_rules', {}).get('codes_score_2', [])
        if isinstance(item, list) and len(item) == 2
    ) # Expects list of [system, code]
    CONDITION_PREFIX_RULES_CONFIG = cdss_config.get('condition_rules', {}).get('prefix_rules', [])
    CONDITION_VALUESET_RULES_CONFIG = cdss_config.get('condition_rules', {}).get('value_set_rules', []) # <-- NEW
    # --- NEW: Load Local ValueSet Rules and Definitions ---
    CONDITION_LOCAL_VALUESET_RULES_CONFIG = cdss_config.get('condition_rules', {}).get('local_valueset_rules', [])
    LOCAL_VALUESETS_CONFIG = {
        key: set(tuple(item) for item in value)
        for key, value in cdss_config.get('local_valuesets', {}).items()
    }
    # --- END NEW ---
    RISK_PARAMS_CONFIG = cdss_config.get('risk_score_parameters', {})
    FINAL_RISK_THRESHOLD_CONFIG = cdss_config.get('final_risk_threshold', {})
    BLOOD_TRANSFUSION_CODES_CONFIG = set(tuple(item) for item in cdss_config.get('procedure_codings', {}).get('blood_transfusion', []) if isinstance(item, list) and len(item) == 2) # MODIFIED

    # --- MODIFIED: Load Keywords for Condition Text Analysis (Score 2) from Config ---
    # Load the list from JSON, provide an empty list as default if keys are missing
    condition_text_keywords_list = cdss_config.get('condition_rules', {}).get('text_keywords_score_2', [])
    # Convert the list to a set for efficient lookup
    CONDITION_TEXT_KEYWORDS_SCORE_2_CONFIG = set(condition_text_keywords_list)
    logging.info(f"Loaded {len(CONDITION_TEXT_KEYWORDS_SCORE_2_CONFIG)} keywords for condition text analysis from config.")
    # --- END MODIFIED ---


except FileNotFoundError:
    logging.error(f"CRITICAL: CDSS configuration file not found at {CONFIG_FILE}")
    # Create a minimal config if not found to allow app to start for auth testing
    cdss_config = {}
    OAC_CODINGS_CONFIG, NSAID_STEROID_CODINGS_CONFIG, CONDITION_CODES_SCORE_2_CONFIG, \
    CONDITION_PREFIX_RULES_CONFIG, CONDITION_VALUESET_RULES_CONFIG, CONDITION_LOCAL_VALUESET_RULES_CONFIG, \
    LOCAL_VALUESETS_CONFIG, RISK_PARAMS_CONFIG, FINAL_RISK_THRESHOLD_CONFIG, \
    BLOOD_TRANSFUSION_CODES_CONFIG, CONDITION_TEXT_KEYWORDS_SCORE_2_CONFIG = [set() for _ in range(11)] # Adjusted count for new configs
    # Ensure CONDITION_CODES_SCORE_2_CONFIG is initialized as a set even if file not found
    CONDITION_CODES_SCORE_2_CONFIG = set() # Explicitly set for clarity if using the loop above
    CONDITION_PREFIX_RULES_CONFIG = [] # it's a list
    CONDITION_VALUESET_RULES_CONFIG = [] # <-- NEW: Initialize if config file not found
    CONDITION_LOCAL_VALUESET_RULES_CONFIG = [] # <-- NEW: Initialize if config file not found
    LOCAL_VALUESETS_CONFIG = {} # <-- NEW: Initialize if config file not found
    RISK_PARAMS_CONFIG = {}
    FINAL_RISK_THRESHOLD_CONFIG = {}
    BLOOD_TRANSFUSION_CODES_CONFIG = set() # MODIFIED: Ensure it's a set if file not found
    logging.warning(f"CDSS configuration file not found at {CONFIG_FILE}. Using empty config.")
    # raise FileNotFoundError(f"CDSS configuration file not found: {CONFIG_FILE}") # Comment out to allow startup
except json.JSONDecodeError as e:
    logging.error(f"CRITICAL: Error decoding JSON from {CONFIG_FILE}: {e}")
    raise ValueError(f"Invalid JSON in CDSS configuration file: {CONFIG_FILE}")
except Exception as e:
    logging.error(f"CRITICAL: Unexpected error loading CDSS config: {e}", exc_info=True)
    raise
# --- End Load External CDSS Configuration ---


app = Flask(__name__, template_folder='templates')

# --- >> PRODUCTION SECURITY: Enhanced Security Configuration << ---
def configure_production_security(app):
    """配置生產環境安全設定"""
    from datetime import timedelta
    
    # 基本安全配置
    app.config.update(
        SESSION_COOKIE_SECURE=True if not app.debug else False,  # Only HTTPS in production
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='None' if not app.debug else 'Lax',  # Oracle Health iframe compatibility
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max file size
    )
    
    # Oracle Health specific session configuration
    if not app.debug:
        # In production, configure for Oracle Health iframe embedding
        app.config['SESSION_COOKIE_SECURE'] = True  # Required for SameSite=None
        app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # Allow cross-site iframe embedding
    
    # HTTPS 強制執行 (僅在生產環境)
    @app.before_request
    def force_https():
        if not app.debug and not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
            return redirect(request.url.replace('http://', 'https://'), code=301)

# Apply security configuration
configure_production_security(app)
# --- >> END PRODUCTION SECURITY << ---

# --- Specific CORS configuration ---
# Allow all origins for general routes (like SMART launch, callback, UI)
CORS(app, resources={r"/*": {"origins": "*"}})

# More specific CORS for /cds-services/ to allow sandbox.cds-hooks.org
CORS(app, resources={
    r"/cds-services/*": {
        "origins": "https://sandbox.cds-hooks.org", 
        "methods": ["GET", "POST", "OPTIONS"], 
        "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With", "fhir-authorization"],
        "supports_credentials": True
    }
})
# --- End CORS configuration ---

app.static_folder = 'static'

# --- ValueSet Cache Initialization ---
app.expanded_valuesets_cache = {}
app.expanded_valuesets_cache_expiry_seconds = 3600 # Cache for 1 hour, adjust as needed
# --- End ValueSet Cache Initialization ---

# --- Flask App Configuration ---
app.logger.setLevel(logging.INFO) # Set level for app logger
app.secret_key = os.getenv('FLASK_SECRET_KEY')
if not app.secret_key:
    # For development, generate one if not set, but log a warning
    app.secret_key = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
    app.logger.warning("FLASK_SECRET_KEY not set in environment. Generated a temporary one. SET THIS IN PRODUCTION!")
    # raise ValueError("No FLASK_SECRET_KEY set.")

# --- >> PRODUCTION SECURITY: Enhanced Security Headers << ---
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # 安全標頭
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'  # Allow embedding in same origin
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # CSP 設定 - 允許必要的外部資源
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://code.jquery.com https://cdn.jsdelivr.net https://stackpath.bootstrapcdn.com "
        "https://cdnjs.cloudflare.com https://sandbox.cds-hooks.org; "
        "style-src 'self' 'unsafe-inline' "
        "https://stackpath.bootstrapcdn.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self' https: wss:; "
        "frame-ancestors 'self' https://*.cerner.com https://*.oracle.com; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "manifest-src 'self';"
    )
    response.headers['Content-Security-Policy'] = csp_policy
    
    # Oracle Health/Cerner iframe compatibility
    # P3P header for IE cookie compatibility in iframes
    response.headers['P3P'] = 'CP="NOI ADM DEV PSAi COM NAV OUR OTRo STP IND DEM"'
    
    # For Edge: Set SameSite=None; Secure for cookies in iframe context
    # This is handled in session cookie configuration
    
    return response
# --- >> END PRODUCTION SECURITY: Enhanced Security Headers << ---

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index' # Redirect to landing page if login required
login_manager.login_message = "Please log in to access this page. If this is a SMART on FHIR application, please launch through your EHR system."
login_manager.login_message_category = "warning"

# --- Authlib Configuration ---
# The oauth object is initialized, but specific clients might be configured dynamically or not used directly
# if we are manually handling SMART OAuth flow due to dynamic 'iss'.
oauth = OAuth(app)

# --- Simple User Model for Flask-Login ---
# Represents a user authenticated via SMART/EHR
class User(UserMixin):
    def __init__(self, user_id, name=None, email=None, fhir_user_url=None): # Added fhir_user_url
        self.id = user_id # Typically the EHR user ID (e.g., from 'sub' or 'profile' claim)
        self.name = name
        self.email = email
        self.fhir_user_url = fhir_user_url # Store the FHIR profile URL if available

# user_loader still needed by Flask-Login
@login_manager.user_loader
def load_user(user_id):
    # Retrieve user info stored in session during callback
    user_info = session.get('user_info')
    if user_info and user_info.get('id') == user_id:
        return User(user_id=user_info['id'],
                    name=user_info.get('name'),
                    email=user_info.get('email'),
                    fhir_user_url=user_info.get('fhir_user_url')) # <-- Load fhir_user_url
    return None # User not found in session
# --- End User Model ---

# --- >> PRODUCTION SECURITY: Health Check and Monitoring << ---
@app.route('/health')
def health_check():
    """健康檢查端點"""
    try:
        import time
        health_data = {
            'status': 'healthy',
            'timestamp': time.time(),
            'version': os.environ.get('APP_VERSION', 'unknown'),
            'environment': 'production' if not app.debug else 'development'
        }
        
        # 檢查關鍵配置
        config_checks = {
            'flask_secret_key': bool(app.secret_key),
            'smart_client_id': bool(SMART_CLIENT_ID),
            'smart_redirect_uri': bool(SMART_REDIRECT_URI),
            'cdss_config_loaded': bool(cdss_config)
        }
        
        health_data['config_checks'] = config_checks
        
        # 如果關鍵配置缺失，返回 degraded 狀態
        if not all(config_checks.values()):
            health_data['status'] = 'degraded'
            return jsonify(health_data), 503
        
        return jsonify(health_data), 200
        
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }), 503
# --- >> END PRODUCTION SECURITY << ---

# --- >> NEW: ValueSet Helper Functions << ---
def _fetch_and_expand_valueset(valueset_url_or_id, fhir_server_url, headers):
    """
    Fetches and expands a ValueSet from the FHIR server.
    Returns a set of (system, code) tuples from the expansion, or None on failure.
    `valueset_url_or_id` can be a canonical URL or a relative ID like 'ValueSet/my-vs-id'.
    """
    if not fhir_server_url or not headers:
        app.logger.error(f"Cannot expand ValueSet '{valueset_url_or_id}': Missing FHIR server URL or auth headers.")
        return None

    # Construct the full $expand URL
    # If valueset_url_or_id is already a full URL, requests will handle it.
    # If it's a relative path like "ValueSet/id" or just "id", urljoin with fhir_server_url.
    if valueset_url_or_id.startswith("http://") or valueset_url_or_id.startswith("https://"):
        # Assumes it's a canonical URL that might be resolvable directly,
        # or it's a full URL to a ValueSet resource on a potentially different server.
        # For simplicity here, we assume ValueSets are on the *same* fhir_server_url.
        # A more robust resolver might be needed for true canonical URL resolution.
        # If it's a canonical URL but not the server's base, this might need adjustment.
        # Let's assume for now it's either a relative ID or a full URL to THIS server.
        if fhir_server_url not in valueset_url_or_id:
             # If it's like "ValueSet/id", make it absolute.
            if not valueset_url_or_id.startswith("ValueSet/"): # if just "id"
                 vs_path = f"ValueSet/{valueset_url_or_id}"
            else: # "ValueSet/id"
                 vs_path = valueset_url_or_id
            expand_target_url = f"{fhir_server_url}/{vs_path}"
        else: # It's already a full URL containing the fhir_server_url base
            expand_target_url = valueset_url_or_id

    else: # It's a relative ID like "my-vs-id" or "ValueSet/my-vs-id"
        if not valueset_url_or_id.startswith("ValueSet/"):
            vs_path = f"ValueSet/{valueset_url_or_id}"
        else:
            vs_path = valueset_url_or_id
        expand_target_url = f"{fhir_server_url}/{vs_path}"


    expand_url = f"{expand_target_url}/$expand"
    # Add a count parameter to potentially limit results if expansions are huge,
    # though typically we want all codes. Some servers might page $expand.
    # params = {"_count": "500"} # Optional: if server supports and it's needed

    app.logger.info(f"Expanding ValueSet: GET {expand_url}")
    try:
        response = requests.get(expand_url, headers=headers, timeout=20) # Increased timeout for $expand
        response.raise_for_status()
        expanded_vs = response.json()

        codes = set()
        if expanded_vs.get("resourceType") == "ValueSet" and "expansion" in expanded_vs:
            expansion = expanded_vs["expansion"]
            total_codes = expansion.get("total", len(expansion.get("contains", [])))
            app.logger.info(f"ValueSet '{valueset_url_or_id}' expanded. Total codes (reported by server): {total_codes}. Processing up to {len(expansion.get('contains', []))} contained codes.")
            
            for item in expansion.get("contains", []):
                system = item.get("system")
                code = item.get("code")
                # version = item.get("version") # Could also store version if important
                if system and code:
                    codes.add((system, code))
            
            # Note: Servers might page $expand results using offset and count in `expansion`.
            # A full implementation might need to handle fetching all pages.
            # For now, we process what's in the first response's "contains".
            if len(codes) == 0 and total_codes > 0:
                 app.logger.warning(f"ValueSet '{valueset_url_or_id}' expansion reported {total_codes} codes, but no codes were extracted from 'contains' array. Check ValueSet content and server $expand behavior.")
            elif len(codes) < total_codes:
                 app.logger.warning(f"ValueSet '{valueset_url_or_id}' expansion reported {total_codes} codes, but only {len(codes)} were extracted. Server might be paging $expand results, which is not fully handled here.")


            return codes
        else:
            app.logger.error(f"Failed to expand ValueSet '{valueset_url_or_id}': Response is not a ValueSet or missing 'expansion'. Response: {str(expanded_vs)[:500]}")
            return None
    except requests.exceptions.Timeout:
        app.logger.error(f"Timeout expanding ValueSet '{valueset_url_or_id}' from {expand_url}.")
        return None
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error expanding ValueSet '{valueset_url_or_id}' from {expand_url}: {e}")
        if e.response is not None:
            app.logger.error(f"Response content: {e.response.text[:500]}")
        return None
    except ValueError as e: # JSONDecodeError
        app.logger.error(f"Error decoding JSON response for ValueSet '{valueset_url_or_id}' expansion: {e}")
        return None


def _expand_valueset_cached(valueset_url_or_id):
    """
    Retrieves expanded codes for a ValueSet, using an in-memory cache.
    Returns a set of (system, code) tuples or None.
    Relies on _get_fhir_server_url() and _get_fhir_request_headers() from session/context.
    """
    cache = app.expanded_valuesets_cache
    expiry_seconds = app.expanded_valuesets_cache_expiry_seconds
    now = time.time()

    if valueset_url_or_id in cache:
        cached_item = cache[valueset_url_or_id]
        if now < cached_item["timestamp"] + expiry_seconds:
            app.logger.info(f"Using cached expansion for ValueSet '{valueset_url_or_id}'.")
            return cached_item["codes"]
        else:
            app.logger.info(f"Cached expansion for ValueSet '{valueset_url_or_id}' expired.")
            # Fall through to fetch again

    # Attempt to get FHIR server URL and headers from the current context (e.g., session)
    # This is a simplification. In a robust CDS service, token/server URL management
    # for background tasks or service-to-service calls would be more complex.
    fhir_server = _get_fhir_server_url()
    headers = _get_fhir_request_headers()

    if not fhir_server or not headers:
        # This will often be the case in a pure prefetch scenario without fhirAuthorization
        app.logger.warning(f"Cannot expand ValueSet '{valueset_url_or_id}': FHIR server URL or auth headers not available in current context. ValueSet rule may not apply if not already cached.")
        return None # Cannot fetch without server/auth info

    expanded_codes = _fetch_and_expand_valueset(valueset_url_or_id, fhir_server, headers)

    if expanded_codes is not None: # Cache even if it's an empty set (successful expansion of an empty VS)
        app.logger.info(f"Successfully expanded and cached ValueSet '{valueset_url_or_id}' with {len(expanded_codes)} codes.")
        cache[valueset_url_or_id] = {"timestamp": now, "codes": expanded_codes}
        return expanded_codes
    else:
        # If expansion failed, don't cache a failure indefinitely as None.
        # Let it try again next time. Or, could cache "None" for a shorter period.
        app.logger.warning(f"Failed to expand ValueSet '{valueset_url_or_id}'. Not caching failure.")
        # To prevent hammering a failing ValueSet, one might implement a shorter error cache duration.
        # For now, if it fails, it will try to fetch next time it's requested.
        return None
# --- >> END NEW: ValueSet Helper Functions << ---


# --- SMART on FHIR Launch and Callback Routes ---
@app.route('/')
def index():
    """Serves the index page.
    This page might explain how to launch the app from an EHR,
    or provide a test launch button for development.
    """
    return render_template('index.html', title="Smart Medical Risk Calculator")

@app.route('/launch')
def launch():
    app.logger.info(f"Using configured SMART_REDIRECT_URI: '{SMART_REDIRECT_URI}'") # MODIFIED LOGGING
    """
    Initiates the SMART on FHIR launch sequence.
    1. Receives 'iss' (FHIR server URL) and 'launch' (opaque token) from EHR.
    2. Fetches FHIR server's metadata (SMART configuration or /metadata).
    3. Generates PKCE code_challenge and state.
    4. Redirects user to the EHR's authorization endpoint.
    """
    iss = request.args.get('iss')
    launch_token = request.args.get('launch')

    app.logger.info(f"Launch initiated. ISS: {iss}, Launch Token: {launch_token}")

    # Validate and normalize ISS URL
    if not iss:
        flash("啟動參數錯誤：缺少 ISS 參數。", "danger")
        return redirect(url_for('index'))
    
    # Add scheme if missing
    if not iss.startswith(('http://', 'https://')):
        iss = 'https://' + iss
        app.logger.info(f"Added https:// scheme to ISS: {iss}")

    if not SMART_CLIENT_ID:
        flash("應用程式設定錯誤：SMART_CLIENT_ID 未設定。", "danger")
        return redirect(url_for('index'))
    if not SMART_REDIRECT_URI:
        flash("應用程式設定錯誤：SMART_REDIRECT_URI 未設定。", "danger")
        return redirect(url_for('index'))


    session['fhir_server_url'] = iss
    session['launch_token'] = launch_token # Store if needed, though often not directly used by client

    # Fetch server metadata (SMART configuration preferred, then /metadata)
    try:
        authorize_url = None
        token_url = None
        jwks_uri = None

        # Try .well-known/smart-configuration first
        smart_config_url = urljoin(iss.rstrip('/') + '/', '.well-known/smart-configuration')
        app.logger.info(f"Attempting to fetch SMART configuration from: {smart_config_url}")
        try:
            metadata_resp = requests.get(smart_config_url, headers={'Accept': 'application/json'}, timeout=10)
            metadata_resp.raise_for_status()
            metadata = metadata_resp.json()
            app.logger.info(f"SMART configuration fetched successfully: {metadata}")
            authorize_url = metadata.get('authorization_endpoint')
            token_url = metadata.get('token_endpoint')
            jwks_uri = metadata.get('jwks_uri')
        except requests.exceptions.RequestException as e_smart:
            app.logger.warning(f"Failed to fetch SMART config ({smart_config_url}): {e_smart}. Falling back to /metadata.")
            # Fallback to /metadata
            fhir_metadata_url = urljoin(iss.rstrip('/') + '/', 'metadata')
            app.logger.info(f"Attempting to fetch /metadata from: {fhir_metadata_url}")
            metadata_resp = requests.get(fhir_metadata_url, headers={'Accept': 'application/fhir+json'}, timeout=10)
            metadata_resp.raise_for_status()
            metadata = metadata_resp.json()
            app.logger.info(f"/metadata fetched successfully (partially shown): {str(metadata)[:500]}")

            # Extract OAuth URIs from FHIR /metadata (SMART-specific extension)
            security_extensions = None
            for rest_resource in metadata.get('rest', []):
                security_info = rest_resource.get('security')
                if security_info:
                    security_extensions = security_info.get('extension')
                    if security_extensions:
                        break
            
            if security_extensions:
                oauth_uris_extension = next((ext for ext in security_extensions if ext.get('url') == 'http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris'), None)
                if oauth_uris_extension:
                    for ext_uri in oauth_uris_extension.get('extension', []):
                        if ext_uri.get('url') == 'authorize':
                            authorize_url = ext_uri.get('valueUri')
                        elif ext_uri.get('url') == 'token':
                            token_url = ext_uri.get('valueUri')
            # JWKS URI is typically not in /metadata in a standard way for SMART.
            # It's usually part of .well-known/openid-configuration or .well-known/smart-configuration

        if not authorize_url or not token_url:
            app.logger.error(f"Could not find authorize or token URI in metadata from {iss}.")
            flash("FHIR 伺服器元數據缺少必要的 OAuth URI。", "danger")
            return redirect(url_for('index'))

        session['authorize_url'] = authorize_url
        session['token_url'] = token_url
        if jwks_uri:
            session['jwks_uri'] = jwks_uri
        app.logger.info(f"OAuth Endpoints: Authorize='{authorize_url}', Token='{token_url}', JWKS_URI='{jwks_uri}'")

    except requests.exceptions.Timeout:
        app.logger.error(f"Timeout fetching metadata from {iss}.")
        flash(f"連接 FHIR 伺服器 ({iss}) 超時，無法獲取元數據。", "danger")
        return redirect(url_for('index'))
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to retrieve FHIR server metadata from {iss}: {e}")
        flash(f"無法連接 FHIR 伺服器 ({iss}) 或獲取元數據。", "danger")
        return redirect(url_for('index'))
    except (ValueError, KeyError) as e: # Handles JSONDecodeError or missing keys
        app.logger.error(f"Error parsing metadata from {iss}: {e}")
        flash("解析 FHIR 伺服器元數據時發生錯誤。", "danger")
        return redirect(url_for('index'))

    # PKCE Code Verifier and Challenge - Enhanced per RFC 7636
    # Generate a cryptographically random 32-byte code verifier
    code_verifier_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(code_verifier_bytes).decode('utf-8').rstrip('=')
    
    # Ensure code verifier meets RFC 7636 requirements (43-128 characters, unreserved characters)
    if len(code_verifier) < 43:
        # Pad with additional random bytes if needed
        additional_bytes = os.urandom(8)
        code_verifier += base64.urlsafe_b64encode(additional_bytes).decode('utf-8').rstrip('=')
    
    # Clean any potentially problematic characters (though base64url should be safe)
    code_verifier = re.sub('[^a-zA-Z0-9_.-~]+', '', code_verifier) # Per RFC 7636
    session['pkce_code_verifier'] = code_verifier

    # Generate SHA256 challenge
    code_challenge_sha256 = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_sha256).decode('utf-8').rstrip('=')

    # Enhanced state parameter generation - use 256 bits of entropy
    state_bytes = os.urandom(32)
    state = base64.urlsafe_b64encode(state_bytes).decode('utf-8').rstrip('=')
    session['oauth_state'] = state

    # Clean up the scopes (from environment variable)
    scopes = SMART_SCOPES
    
    # Apply Oracle Health best practices for scope optimization
    optimized_scopes = validate_and_optimize_scopes(scopes, context='patient')
    app.logger.info(f"Optimized scopes: {optimized_scopes}")
    
    # Build the authorization URL
    auth_params = {
        'response_type': 'code',
        'client_id': SMART_CLIENT_ID,
        'redirect_uri': SMART_REDIRECT_URI,
        'scope': optimized_scopes,
        'state': state,
        'aud': iss, # Audience is the FHIR server (resource server)
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    # --- MODIFIED: Add launch token to auth_params if it exists ---
    if launch_token: # launch_token was retrieved from request.args at the start of /launch
        auth_params['launch'] = launch_token
        app.logger.info(f"Including launch token in authorization redirect parameters: {launch_token}")
    # --- END MODIFIED ---

    full_auth_url = f"{session['authorize_url']}?{urlencode(auth_params)}"
    app.logger.info(f"Redirecting user to authorization server: {session['authorize_url']}")
    return redirect(full_auth_url)

@app.route('/callback')
def callback():
    """
    Handles the OAuth2 callback from the authorization server.
    1. Validates the 'state' parameter.
    2. Exchanges the authorization 'code' for an access token (and ID token).
    3. Validates the ID token (signature, claims).
    4. Stores token and user information in session.
    5. Logs in the user via Flask-Login.
    6. Redirects to the main application page.
    """
    auth_code = request.args.get('code')
    returned_state = request.args.get('state')
    error = request.args.get('error')
    error_description = request.args.get('error_description')

    app.logger.info(f"Callback received. Code: {'Present' if auth_code else 'Missing'}, State: {returned_state}, Error: {error}")

    expected_state = session.pop('oauth_state', None)
    if not expected_state or returned_state != expected_state:
        app.logger.warning(f"OAuth state mismatch. Expected: '{expected_state}', Got: '{returned_state}'") # MODIFIED LOGGING
        flash("登入失敗：安全性檢查未通過 (state mismatch)。請重試。", "danger")
        return redirect(url_for('index'))

    if error:
        app.logger.error(f"OAuth authorization error from server. Error: {error}, Description: {error_description}")
        flash(f"授權失敗：{error_description or error}", "danger")
        return redirect(url_for('index'))

    if not auth_code:
        app.logger.error("Authorization code missing in callback and no error reported.")
        flash("登入失敗：授權碼遺失。請重試。", "danger")
        return redirect(url_for('index'))

    token_url = session.get('token_url')
    code_verifier = session.pop('pkce_code_verifier', None)
    fhir_server_url = session.get('fhir_server_url') # This is the 'iss'
    launch_token = session.get('launch_token') # Retrieve the launch token

    if not token_url or not code_verifier or not fhir_server_url:
        app.logger.error("Session data missing for token exchange (token_url, code_verifier, or fhir_server_url).")
        flash("登入時發生錯誤 (session 資料遺失)。請重新從 EHR 啟動應用程式。", "danger")
        return redirect(url_for('index'))

    token_payload = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': SMART_REDIRECT_URI,
        'client_id': SMART_CLIENT_ID,
        'code_verifier': code_verifier
    }
    # --- MODIFIED: Include launch token if present ---
    if launch_token:
        token_payload['launch'] = launch_token
        app.logger.info("Including launch token in token exchange payload.")
    # --- END MODIFIED ---

    # For public clients, client_secret is NOT sent in the payload.
    # If this were a confidential client using client_secret_post:
    # token_payload['client_secret'] = SMART_CLIENT_SECRET
    # If using client_secret_basic, it would be in an Authorization header.

    try:
        # Redact sensitive info from log, show structure
        log_payload = {k: (v if k not in ['code', 'code_verifier', 'client_id'] else '***') for k,v in token_payload.items()}
        app.logger.info(f"Exchanging code for token at {token_url} with payload: {log_payload}")
        
        # Standard headers for token request
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        token_response = requests.post(token_url, data=token_payload, headers=headers, timeout=15)
        token_response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        token_data = token_response.json()

        log_token_data = {k: (v if k not in ['access_token', 'id_token', 'refresh_token'] else '***') for k,v in token_data.items()}
        app.logger.info(f"Token response received: {log_token_data}")

    except requests.exceptions.Timeout:
        app.logger.error(f"Token exchange request to {token_url} timed out.")
        flash("獲取 Access Token 時請求超時。", "danger")
        return redirect(url_for('index'))
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"Token exchange HTTPError: {e}. Response: {e.response.text if e.response else 'N/A'}")
        error_detail = e.response.json().get('error_description', e.response.text) if e.response and e.response.content else str(e)
        flash(f"無法獲取 Access Token。伺服器回應：{error_detail}", "danger")
        return redirect(url_for('index'))
    except requests.exceptions.RequestException as e: # Catch other network/request errors
        app.logger.error(f"Token exchange failed due to RequestException: {e}")
        flash("無法獲取 Access Token，發生網路或伺服器錯誤。", "danger")
        return redirect(url_for('index'))
    except ValueError: # JSONDecodeError
        app.logger.error(f"Error decoding token response from {token_url}. Response: {token_response.text if 'token_response' in locals() else 'N/A'}")
        flash("從伺服器收到的 Token 回應格式無效。", "danger")
        return redirect(url_for('index'))

    session['access_token'] = token_data.get('access_token')
    session['patient_id'] = token_data.get('patient') # Critical for launch/patient scope
    session['scopes_granted'] = token_data.get('scope')
    session['id_token_jwt'] = token_data.get('id_token') # Store raw ID token string
    session['refresh_token'] = token_data.get('refresh_token') # Store refresh token for session renewal
    session['token_expires_at'] = time.time() + token_data.get('expires_in', 600) # Store expiration time
    # fhir_server_url is already in session from launch

    if not session.get('access_token'):
        app.logger.error("Access token not found in token response.")
        flash("登入失敗：未從伺服器收到 Access Token。", "danger")
        return redirect(url_for('index'))

    if 'launch/patient' in SMART_SCOPES.split(' ') and not session.get('patient_id'):
         app.logger.warning("Patient ID not received in token response, but 'launch/patient' scope was requested.")
         # Depending on app logic, this might be an error or just a warning.
         # flash("警告：EHR 未提供病患情境。某些功能可能受限。", "warning")

    # ID Token Validation
    id_token_jwt_str = token_data.get('id_token')
    user_info_claims = {'id': None, 'name': 'SMART User', 'email': None, 'fhir_user_url': None}

    if id_token_jwt_str:
        try:
            jwks_uri = session.get('jwks_uri')
            # If JWKS URI was not found via smart-configuration, try .well-known/openid-configuration
            if not jwks_uri:
                oidc_config_url = urljoin(fhir_server_url.rstrip('/') + '/', '.well-known/openid-configuration')
                app.logger.info(f"JWKS URI not in session from SMART config. Attempting OIDC config: {oidc_config_url}")
                try:
                    oidc_resp = requests.get(oidc_config_url, headers={'Accept': 'application/json'}, timeout=5)
                    oidc_resp.raise_for_status()
                    oidc_metadata = oidc_resp.json()
                    jwks_uri = oidc_metadata.get('jwks_uri')
                    if jwks_uri:
                        session['jwks_uri'] = jwks_uri # Store for this session
                        app.logger.info(f"Found JWKS URI via OIDC config: {jwks_uri}")
                    else:
                        app.logger.warning(f"OIDC config at {oidc_config_url} did not contain jwks_uri.")
                except requests.exceptions.RequestException as e_oidc:
                    app.logger.warning(f"Failed to fetch or parse OIDC config from {oidc_config_url}: {e_oidc}")
            
            if not jwks_uri:
                app.logger.error("JWKS URI is not available. Cannot validate ID Token signature.")
                # This is a security risk. Depending on policy, might deny login or proceed with warning.
                flash("安全性警告：無法驗證使用者身份 (缺少 JWKS URI)。", "warning")
            else:
                # MODIFIED: Remove cache_jwk_set and lifespan for compatibility
                jwk_client = PyJWKClient(jwks_uri) # Cache keys (using default caching)
                
                # --- >> NEW: Log ID Token header and JWKS URI for debugging << ---
                try:
                    unverified_header = jwt.get_unverified_header(id_token_jwt_str)
                    app.logger.info(f"ID Token unverified header: {unverified_header}")
                except Exception as e_header:
                    app.logger.error(f"Could not get unverified header from ID Token: {e_header}")
                app.logger.info(f"Using JWKS URI for ID Token validation: {jwks_uri}")
                # --- >> END NEW LOGGING << ---

                signing_key_obj = None
                kid_lookup_failed = False
                try:
                    # Try to get key normally using kid from token (if present)
                    signing_key_obj = jwk_client.get_signing_key_from_jwt(id_token_jwt_str)
                except jwt.PyJWKClientError as e_jwk_client: # Catch if kid is missing/None and not found in JWKS
                    app.logger.warning(f"jwk_client.get_signing_key_from_jwt failed (PyJWKClientError: {e_jwk_client}). This can happen if KID is missing or not in JWKS. Will attempt fallback.")
                    kid_lookup_failed = True
                except jwt.exceptions.DecodeError as e_decode: # Catch if token header itself is malformed (e.g., can't get kid)
                    app.logger.warning(f"Could not decode token to get KID (DecodeError: {e_decode}). Will attempt fallback.")
                    kid_lookup_failed = True
                # Add a check in case get_signing_key_from_jwt returns None without raising an error (though unlikely for this case)
                if not signing_key_obj and not kid_lookup_failed:
                    app.logger.warning("get_signing_key_from_jwt returned None without error. Attempting fallback.")
                    kid_lookup_failed = True
                
                if kid_lookup_failed: # If initial attempt failed, try fallback by algorithm
                    unverified_header = jwt.get_unverified_header(id_token_jwt_str)
                    token_alg = unverified_header.get('alg')
                    if token_alg:
                        app.logger.info(f"Token algorithm for fallback: {token_alg}. Attempting to find a matching key in JWKS.")
                        try:
                            jwks = jwk_client.get_jwk_set()
                            for key_in_set in jwks.keys: # key_in_set is a PyJWK object
                                # MODIFIED: Access algorithm from the key's internal _jwk_data dictionary
                                key_specific_alg = key_in_set._jwk_data.get('alg')
                                if key_specific_alg == token_alg:
                                    signing_key_obj = key_in_set
                                    # key_in_set.key_id is the correct property for the kid
                                    app.logger.info(f"Fallback: Found a key in JWKS matching algorithm {token_alg}. KID from JWKS: {key_in_set.key_id}")
                                    break 
                            if not signing_key_obj:
                                app.logger.error(f"Fallback: No key found in JWKS matching algorithm {token_alg}.")
                        except Exception as e_jwks_fetch:
                            app.logger.error(f"Fallback: Error fetching or processing JWKS to find key by alg: {e_jwks_fetch}")
                    else:
                        app.logger.error("Fallback: Cannot attempt key selection by alg because algorithm is missing in token header.")
                
                if not signing_key_obj:
                    app.logger.error("Failed to obtain any signing key for ID token validation after all attempts.")
                    flash("登入失敗：無法獲取驗證使用者身份所需的金鑰。", "danger")
                    return redirect(url_for('index'))

                # Algorithms supported by many EHRs.
                algorithms = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]

                decoded_id_token = jwt.decode(
                    id_token_jwt_str,
                    signing_key_obj.key, # Use the .key attribute of the selected PyJWK object
                    algorithms=algorithms, # PyJWT will filter by the alg from token header if only one is provided, or check against this list
                    audience=SMART_CLIENT_ID,
                    issuer=fhir_server_url # Must match the 'iss' received at launch
                )
                session['id_token_claims'] = decoded_id_token # Store decoded claims
                app.logger.info(f"ID Token validated and decoded: {decoded_id_token}")

                user_info_claims['id'] = decoded_id_token.get('sub')
                user_info_claims['name'] = decoded_id_token.get('name', decoded_id_token.get('profile_name')) # Some use 'profile_name'
                if not user_info_claims['name'] and isinstance(decoded_id_token.get('profile'), str) and '/' not in decoded_id_token.get('profile'):
                     user_info_claims['name'] = decoded_id_token.get('profile') # if profile is just a name string
                user_info_claims['email'] = decoded_id_token.get('email')
                user_info_claims['fhir_user_url'] = decoded_id_token.get('fhirUser', decoded_id_token.get('profile')) # 'profile' can be FHIR Practitioner/Patient URL

        except jwt.ExpiredSignatureError:
            app.logger.error("ID token has expired.")
            flash("登入失敗：您的身份驗證已過期。請重試。", "danger")
            return redirect(url_for('index'))
        except jwt.InvalidAudienceError:
            app.logger.error(f"Invalid audience in ID token. Expected {SMART_CLIENT_ID}, Got {jwt.InvalidAudienceError.args[0] if jwt.InvalidAudienceError.args else 'Unknown'}")
            flash("登入失敗：使用者身份驗證失敗 (audience 不符)。", "danger")
            return redirect(url_for('index'))
        except jwt.InvalidIssuerError:
            app.logger.error(f"Invalid issuer in ID token. Expected {fhir_server_url}, Got {jwt.InvalidIssuerError.args[0] if jwt.InvalidIssuerError.args else 'Unknown'}")
            flash("登入失敗：使用者身份驗證失敗 (issuer 不符)。", "danger")
            return redirect(url_for('index'))
        except jwt.exceptions.DecodeError as e: # Covers various decoding issues e.g. wrong key, bad format
            app.logger.error(f"ID token decode error: {e}")
            flash("登入失敗：無法解碼使用者身份資訊。", "danger")
            return redirect(url_for('index'))
        except jwt.PyJWKClientError as e: # Errors from PyJWKClient (e.g. fetching keys)
            app.logger.error(f"Error obtaining signing keys for ID token: {e}")
            flash("登入失敗：無法獲取驗證使用者身份所需的金鑰。", "danger")
            return redirect(url_for('index'))
        except jwt.PyJWTError as e: # Catch-all for other JWT errors
            app.logger.error(f"General ID token validation error: {e}")
            flash(f"登入失敗：使用者身份驗證時發生錯誤 ({type(e).__name__})。", "danger")
            return redirect(url_for('index'))
        except Exception as e: # Catch other potential errors
            app.logger.error(f"Unexpected error during ID token validation: {e}", exc_info=True)
            flash("驗證使用者身份時發生未預期錯誤。", "danger")
            return redirect(url_for('index'))
    else:
        app.logger.warning("ID Token not present in token response. User identity not fully verified via OIDC.")
        # Decide if this is acceptable. For many SMART apps, ID token is crucial.
        # user_info_claims['id'] will remain None or be based on a placeholder.

    # Create user session using Flask-Login
    effective_user_id = user_info_claims['id'] if user_info_claims['id'] else "smart_fhir_user" # Fallback user ID
    session['user_info'] = { # This is used by load_user
        'id': effective_user_id,
        'name': user_info_claims.get('name', 'SMART User'),
        'email': user_info_claims.get('email'),
        'fhir_user_url': user_info_claims.get('fhir_user_url')
    }
    
    current_user_obj = User(user_id=effective_user_id,
                            name=session['user_info']['name'],
                            email=session['user_info']['email'],
                            fhir_user_url=session['user_info']['fhir_user_url'])
    login_user(current_user_obj) # Flask-Login's login_user
    app.logger.info(f"User '{effective_user_id}' logged in. Patient context: {session.get('patient_id')}")

    # Redirect to the main application page
    return redirect(url_for('main_app_page'))


@app.route('/main_app')
@login_required
def main_app_page():
    """Main application page, accessible after successful login."""
    patient_id = session.get('patient_id')
    patient_resource = None
    patient_name = "N/A"

    if patient_id:
        app.logger.info(f"Main app page: Attempting to fetch patient data for patient ID: {patient_id}")
        
        # Phase 1 Optimization: Try optimized approach first, fall back to manual
        if OPTIMIZATIONS_AVAILABLE:
            try:
                patient_resource = fhirclient_optimizations.get_patient_data_optimized(
                    SMART_CLIENT_ID, get_patient_data
                )
                if patient_resource:
                    app.logger.info(f"Patient resource fetched using optimization: {patient_resource.get('id')}")
                else:
                    app.logger.info("Optimization returned None, using fallback")
                    patient_resource = get_patient_data()
            except Exception as e:
                app.logger.error(f"Error in optimized patient data retrieval: {e}")
                patient_resource = get_patient_data()
        else:
            patient_resource = get_patient_data() # Original manual approach
        
        if patient_resource:
            app.logger.info(f"Patient resource fetched: {patient_resource.get('id')}")
            # Extract patient name using the helper function
            patient_name = get_human_name_text(patient_resource.get("name"))
            app.logger.info(f"Extracted patient name: {patient_name}")
        else:
            app.logger.warning(f"Could not fetch patient resource for ID: {patient_id}")
    else:
        app.logger.info("Main app page: No patient_id in session.")

    # For the <pre> block display, we can pass the whole patient_resource if available,
    # or a simplified dict if not.
    # The patient_data for the template will now primarily be the patient_resource itself.
    display_patient_data = patient_resource if patient_resource else {"id": patient_id, "name": patient_name}

    return render_template('main_app.html', 
                           title="FHIR ARC-HBR Bleeding Risk Calculator", 
                           current_user=current_user, 
                           patient_data=display_patient_data, # Pass the full resource or simplified dict
                           patient_name_display=patient_name) # Pass the extracted patient name separately for easy use


@app.route('/logout')
@login_required
def logout():
    """
    Logs out the user and clears session data.
    """
    user_name = session.get('user_info', {}).get('name', 'Unknown')
    app.logger.info(f"User '{user_name}' logging out")
    
    logout_user() # Flask-Login logout
    
    # Clear SMART/OAuth session data
    session.pop('access_token', None)
    session.pop('refresh_token', None)
    session.pop('patient_id', None)
    session.pop('scopes_granted', None)
    session.pop('id_token_jwt', None)
    session.pop('id_token_claims', None)
    session.pop('fhir_server_url', None)
    session.pop('user_info', None)
    session.pop('token_expires_at', None)
    
    flash("已成功登出。", "success")
    return redirect(url_for('index'))


@app.route('/auth-error')
def auth_error():
    """
    Handles authentication and authorization errors with user-friendly guidance.
    """
    error_code = request.args.get('error', 'unknown_error')
    error_description = request.args.get('error_description', '')
    error_uri = request.args.get('error_uri', '')
    
    app.logger.warning(f"Authentication error: {error_code} - {error_description}")
    
    # Provide user-friendly error messages and guidance
    error_messages = {
        'access_denied': {
            'title': '授權被拒絕',
            'message': '您已拒絕授權或管理員已限制存取權限。',
            'guidance': [
                '確認您有適當的權限存取此應用程式',
                '聯繫您的系統管理員以獲得協助',
                '檢查是否需要重新登入 EHR 系統'
            ]
        },
        'invalid_request': {
            'title': '無效的請求',
            'message': '授權請求包含無效的參數。',
            'guidance': [
                '請重新啟動應用程式',
                '確保從 EHR 系統正確啟動',
                '聯繫技術支援如果問題持續發生'
            ]
        },
        'unauthorized_client': {
            'title': '未授權的客戶端',
            'message': '此應用程式尚未註冊或已被暫停。',
            'guidance': [
                '聯繫您的系統管理員',
                '確認應用程式已正確註冊',
                '檢查應用程式是否已被暫停'
            ]
        },
        'server_error': {
            'title': '伺服器錯誤',
            'message': '授權伺服器發生內部錯誤。',
            'guidance': [
                '請稍後再試',
                '檢查 EHR 系統狀態',
                '聯繫技術支援如果問題持續發生'
            ]
        }
    }
    
    error_info = error_messages.get(error_code, {
        'title': '未知錯誤',
        'message': error_description or '發生未預期的錯誤。',
        'guidance': [
            '請重新嘗試授權流程',
            '確保網路連接正常',
            '聯繫技術支援以獲得協助'
        ]
    })
    
    return render_template('error.html', 
                         error_code=error_code,
                         error_info=error_info,
                         error_uri=error_uri,
                         error_description=error_description)


# --- End SMART on FHIR Routes ---


# --- FHIR Helper Functions (Using Session for Token/Server) ---

def refresh_access_token():
    """
    Refreshes the access token using the refresh token.
    Returns True if successful, False otherwise.
    """
    refresh_token = session.get('refresh_token')
    token_url = session.get('token_url')
    fhir_server_url = session.get('fhir_server_url')
    
    if not refresh_token or not token_url:
        app.logger.warning("Cannot refresh token: missing refresh_token or token_url")
        return False
    
    refresh_payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': SMART_CLIENT_ID
    }
    
    # For confidential clients, include client_secret
    if SMART_CLIENT_SECRET:
        refresh_payload['client_secret'] = SMART_CLIENT_SECRET
    
    try:
        app.logger.info("Attempting to refresh access token")
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        token_response = requests.post(token_url, data=refresh_payload, headers=headers, timeout=15)
        token_response.raise_for_status()
        token_data = token_response.json()
        
        # Update session with new token data
        session['access_token'] = token_data.get('access_token')
        session['token_expires_at'] = time.time() + token_data.get('expires_in', 600)
        session['scopes_granted'] = token_data.get('scope', session.get('scopes_granted'))
        
        # Update refresh token if provided (some servers issue new refresh tokens)
        new_refresh_token = token_data.get('refresh_token')
        if new_refresh_token:
            session['refresh_token'] = new_refresh_token
        
        app.logger.info("Access token refreshed successfully")
        return True
        
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"Token refresh failed with HTTP error: {e}")
        if e.response and e.response.status_code == 401:
            app.logger.warning("Refresh token may be expired or revoked")
            # Clear session data to force re-authentication
            session.pop('access_token', None)
            session.pop('refresh_token', None)
            session.pop('token_expires_at', None)
        return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Token refresh failed due to RequestException: {e}")
        return False
    except ValueError as e:
        app.logger.error(f"Error decoding refresh token response: {e}")
        return False


def is_token_expired():
    """
    Check if the current access token is expired or will expire soon.
    Returns True if token is expired or will expire within 60 seconds.
    """
    expires_at = session.get('token_expires_at')
    if not expires_at:
        return True
    
    # Consider token expired if it expires within 60 seconds
    return time.time() >= (expires_at - 60)


# ... (Helper functions _get_fhir_request_headers, _get_fhir_server_url remain the same) ...
def _get_fhir_request_headers():
    """Gets Authorization header from session with automatic token refresh."""
    access_token = session.get('access_token')
    
    # Check if token is expired and try to refresh
    if access_token and is_token_expired():
        app.logger.info("Access token is expired or expiring soon, attempting refresh")
        if refresh_access_token():
            access_token = session.get('access_token')
        else:
            app.logger.warning("Token refresh failed, current token may be invalid")
    
    if not access_token:
        app.logger.error("Access token not found in session for FHIR request.")
        return None
    
    return {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/fhir+json'
    }

def _get_fhir_server_url():
    """Gets FHIR server URL from session."""
    url = session.get('fhir_server_url')
    if not url:
        app.logger.error("FHIR server URL (iss) not found in session.")
        return None
    return url.rstrip('/')

# ... (calculate_age, get_human_name_text remain the same) ...
def calculate_age(birth_date_str):
    try:
        birth_date = datetime.datetime.strptime(birth_date_str, "%Y-%m-%d").date() # Use .date()
        today = datetime.date.today() # Use date objects for comparison
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except (ValueError, TypeError):
        return None

def get_human_name_text(name_list):
    if not name_list: return "N/A"
    preferred_name = first_name = None
    for name in name_list:
        if not first_name: first_name = name
        if name.get("use") in ["official", "usual"]: preferred_name = name; break
    target_name = preferred_name or first_name
    if not target_name: return "N/A"
    if target_name.get("text"): return target_name["text"]
    family = target_name.get("family", ""); given = " ".join(target_name.get("given", []))
    full_name = f"{family}{''.join(given)}"; return full_name.strip() or "N/A"

# ... (get_patient_data, get_observation, get_creatinine, get_hemoglobin, get_platelet remain the same) ...
def get_patient_data(): # Renamed from get_patient_by_id
    """Gets the current patient's resource from session context."""
    fhir_server = _get_fhir_server_url()
    patient_id = session.get('patient_id')
    headers = _get_fhir_request_headers()
    if not fhir_server or not patient_id or not headers: return None

    url = f"{fhir_server}/Patient/{patient_id}"
    app.logger.info(f"Fetching Patient: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    # ... (Add specific logging for errors as before) ...
    except requests.exceptions.Timeout: app.logger.error(f"Timeout fetching patient {patient_id}")
    except requests.exceptions.RequestException as e: app.logger.error(f"Error fetching patient {patient_id}: {e}")
    except ValueError as e: app.logger.error(f"Error parsing patient response for {patient_id}: {e}")
    except Exception as e: app.logger.error(f"Unexpected error getting patient {patient_id}: {e}", exc_info=True)
    return None

def get_observation(patient_id, loinc_code):
    """Gets latest Observation for a patient and LOINC code."""
    fhir_server = _get_fhir_server_url(); headers = _get_fhir_request_headers()
    if not fhir_server or not headers: return None
    url = f"{fhir_server}/Observation"; params = {"patient": patient_id, "code": loinc_code, "_sort": "-date", "_count": 1}
    app.logger.info(f"Fetching Observation: {loinc_code} for patient {patient_id}")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status(); data = response.json()
        if "entry" in data and data["entry"]: return data["entry"][0]["resource"]
    # ... (Add specific logging for errors) ...
    except requests.exceptions.Timeout: app.logger.error(f"Timeout fetching Observation {loinc_code} for patient {patient_id}")
    except requests.exceptions.RequestException as e: app.logger.error(f"Error fetching Observation {loinc_code} for patient {patient_id}: {e}")
    except ValueError as e: app.logger.error(f"Error parsing Observation response for {loinc_code}, patient {patient_id}: {e}")
    except Exception as e: app.logger.error(f"Unexpected error getting observation {loinc_code} for {patient_id}: {e}", exc_info=True)
    return None

def get_creatinine(patient_id):
    """Gets latest Creatinine observation and converts to mg/dL."""
    # MODIFIED: Use centralized LOINC codes
    creatinine_loinc_tuple = LOINC_CODES["CREATININE"]
    codes = ",".join(creatinine_loinc_tuple)
    obs = get_observation(patient_id, codes)
    if obs:
        value_data = obs.get("valueQuantity")
        if value_data:
            value = value_data.get("value"); unit = value_data.get("unit", "").lower()
            try:
                value = float(value)
                if unit in ["umol/l", "µmol/l"]: return value / 88.4
                elif unit == "mg/dl": return value
                else: app.logger.warning(f"Unrecognized creatinine unit '{unit}' for patient {patient_id}")
            except (TypeError, ValueError):
                app.logger.error(f"Could not convert creatinine value '{value}' to float for patient {patient_id}")
                pass # Logged in get_observation if parsing failed there
    return None

def get_hemoglobin(patient_id):
    """Gets latest Hemoglobin observation and converts to g/dL."""
    # MODIFIED: Use centralized LOINC codes
    hemoglobin_loinc_tuple = LOINC_CODES["HEMOGLOBIN"]
    codes = ",".join(hemoglobin_loinc_tuple)
    obs = get_observation(patient_id, codes)
    if obs:
        value_data = obs.get("valueQuantity")
        if value_data:
            value = value_data.get("value"); unit = value_data.get("unit", "").lower()
            try:
                value = float(value)
                if unit == "g/l": return value / 10
                elif unit in ["mmol/l", "mmol/L"]: return value * 1.61 # Check conversion factor
                elif unit == "g/dl": return value
                else: app.logger.warning(f"Unrecognized hemoglobin unit '{unit}' for patient {patient_id}")
            except (TypeError, ValueError):
                app.logger.error(f"Could not convert hemoglobin value '{value}' to float for patient {patient_id}")
                pass
    return None

def get_platelet(patient_id):
    """Gets latest Platelet observation value."""
    # MODIFIED: Use centralized LOINC codes
    platelet_loinc_tuple = LOINC_CODES["PLATELET"]
    codes = ",".join(platelet_loinc_tuple)
    obs = get_observation(patient_id, codes)
    if obs:
        value_data = obs.get("valueQuantity")
        if value_data:
            value = value_data.get("value")
            try: return float(value)
            except (TypeError, ValueError):
                app.logger.error(f"Could not convert platelet value '{value}' to float for patient {patient_id}")
                pass
    return None

# --- get_egfr_value remains the same (already implements fallback) ---
def get_egfr_value(patient_id, age, sex):
    """
    Calculates or fetches eGFR using CKD-EPI 2021 formula.
    Tries to calculate from Creatinine first. If unavailable,
    falls back to fetching direct eGFR observation (LOINC 33914-3).
    Returns eGFR value (float) or None.
    """
    # Attempt 1: Calculate from Creatinine using CKD-EPI 2021
    cr_value = get_creatinine(patient_id) # Assumes get_creatinine returns in mg/dL

    # Validate inputs needed for calculation
    age_is_valid = isinstance(age, (int, float)) and age > 0
    sex_is_valid = sex is not None and sex.lower() in ["male", "female"]
    cr_is_valid = isinstance(cr_value, (int, float)) and cr_value > 0

    if cr_is_valid and age_is_valid and sex_is_valid:
        try:
            # --- CKD-EPI 2021 Formula Implementation ---
            sex_lower = sex.lower()
            kappa = 0.7 if sex_lower == "female" else 0.9
            alpha = -0.241 if sex_lower == "female" else -0.302
            sex_factor = 1.012 if sex_lower == "female" else 1.0

            term1 = cr_value / kappa
            # Use Python's min() and max() which work directly
            term2 = min(term1, 1.0) ** alpha
            term3 = max(term1, 1.0) ** (-1.200)
            age_factor = 0.9938 ** age

            eGFR_calc = 142 * term2 * term3 * age_factor * sex_factor
            # --- End CKD-EPI 2021 Formula ---

            app.logger.info(f"Calculated eGFR (CKD-EPI 2021) {eGFR_calc:.2f} from Creatinine {cr_value} for patient {patient_id}")
            return float(eGFR_calc)

        except OverflowError:
            app.logger.error(f"Math OverflowError calculating eGFR (CKD-EPI 2021) for patient {patient_id}. Inputs: cr={cr_value}, age={age}, sex={sex}")
        except Exception as e:
            app.logger.error(f"Error calculating eGFR (CKD-EPI 2021) from Creatinine for patient {patient_id}: {e}")
            # Fall through to attempt fetching direct eGFR

    # Attempt 2: Fetch direct eGFR observation if Creatinine was invalid or calculation failed
    if not cr_is_valid:
        app.logger.warning(f"Creatinine value '{cr_value}' is invalid for patient {patient_id}. Attempting to fetch direct eGFR (LOINC: {','.join(LOINC_CODES['EGFR_DIRECT'])}).")
    elif not age_is_valid or not sex_is_valid:
        app.logger.warning(f"Age '{age}' or Sex '{sex}' is invalid for eGFR calculation for patient {patient_id}. Attempting to fetch direct eGFR (LOINC: {','.join(LOINC_CODES['EGFR_DIRECT'])}).")
    else: # Log if calculation failed despite valid inputs
        app.logger.warning(f"Calculation failed for patient {patient_id} despite valid inputs (Cr: {cr_value}, Age: {age}, Sex: {sex}). Attempting to fetch direct eGFR (LOINC: {','.join(LOINC_CODES['EGFR_DIRECT'])}).")

    # MODIFIED: Use centralized LOINC code for direct eGFR
    direct_egfr_loinc_str = ",".join(LOINC_CODES["EGFR_DIRECT"])
    direct_egfr_obs = get_observation(patient_id, direct_egfr_loinc_str)

    if direct_egfr_obs:
        value_data = direct_egfr_obs.get("valueQuantity")
        if value_data:
            value = value_data.get("value")
            unit = value_data.get("unit", "") # Check unit if needed, e.g., mL/min/{1.73_m2}
            try:
                direct_egfr_val = float(value)
                app.logger.info(f"Using directly fetched eGFR value {direct_egfr_val} (Unit: {unit}) for patient {patient_id}")
                # Consider adding unit check/conversion if necessary for consistency
                # For example: if '1.73' in unit: # adjust if needed?
                return direct_egfr_val
            except (TypeError, ValueError):
                app.logger.error(f"Could not convert fetched direct eGFR value '{value}' to float for patient {patient_id}")
        else:
            app.logger.warning(f"Fetched direct eGFR observation for patient {patient_id} is missing valueQuantity.")
    else:
        app.logger.warning(f"Could not find direct eGFR Observation (LOINC: {','.join(LOINC_CODES['EGFR_DIRECT'])}) for patient {patient_id}.")

    return None # Return None if both attempts fail

# --- MODIFIED: get_condition_points signature unchanged, but usage inside is affected by where keywords come from ---
def get_condition_points(patient_id, codes_score_2, prefix_rules, text_keywords_score_2, value_set_rules, local_valueset_rules, local_valuesets_definitions): # ADDED local_valueset_rules and definitions
    """Fetches conditions and calculates points based on codes, prefixes, text keywords, ValueSets (URL-based), and Local ValueSets.
       MODIFIED: No longer filters by date globally, but prefix rules can have own date conditions.
       NOW RETURNS: (score, matched_details_list)
    """
    fhir_server = _get_fhir_server_url(); headers = _get_fhir_request_headers()
    if not fhir_server or not headers: return 0, []
    max_score = 0
    matched_conditions_details = []
    today = datetime.date.today()

    url = f"{fhir_server}/Condition"
    params = {"patient": patient_id, "_count": 200}
    processed_conditions = set()
    pages_fetched = 0 
    MAX_PAGES = 10

    try:
        while url and pages_fetched < MAX_PAGES:
            if max_score == 2 and any(d['score_contribution'] == 2 for d in matched_conditions_details): # Optimization: if max score is 2 from a single condition type
                 break
            pages_fetched += 1
            app.logger.debug(f"Fetching conditions page {pages_fetched} from: {url} with params: {params}")
            response = requests.get(url, headers=headers, params=params, timeout=20)
            params = None 
            response.raise_for_status(); data = response.json()

            if "entry" in data:
                for entry in data["entry"]:
                    if "resource" in entry and entry["resource"]["resourceType"] == "Condition":
                        cond = entry["resource"]; cond_id = cond.get("id")
                        if cond_id and cond_id in processed_conditions: continue

                        code_data = cond.get("code");
                        # MODIFIED: Improved logic for condition_display_text
                        condition_display_text = "N/A" # Default
                        if code_data:
                            text_from_code = code_data.get("text")
                            if text_from_code: # Prioritize code.text if it's non-empty
                                condition_display_text = text_from_code
                            else: # code.text is missing or empty, try coding.display
                                codings = code_data.get("coding")
                                if codings and len(codings) > 0:
                                    display_from_coding = codings[0].get("display")
                                    if display_from_coding: # Use coding.display if it's non-empty
                                        condition_display_text = display_from_coding
                        # END MODIFIED condition_display_text logic

                        status_coding = cond.get("clinicalStatus", {}).get("coding", [{}])[0]
                        status = status_coding.get("code", "").lower()

                        recorded_date_str = cond.get("recordedDate"); parsed_date = None
                        if recorded_date_str:
                            try: 
                                date_str_part = recorded_date_str.split('T')[0]
                                if len(date_str_part) >= 10: parsed_date = datetime.datetime.strptime(date_str_part[:10], "%Y-%m-%d").date()
                            except ValueError: pass

                        initial_max_score_for_condition = 0 # To track if this specific condition contributes anything new

                        # --- 1. Check Codes and Prefixes ---
                        if code_data and "coding" in code_data:
                            for coding in code_data.get("coding", []):
                                code = coding.get("code")
                                system = coding.get("system")
                                if code:
                                    code_upper = code.upper()
                                    # Check direct code match for score 2
                                    if (system, code) in codes_score_2:
                                        if initial_max_score_for_condition < 2: # Only add if it increases score
                                            matched_conditions_details.append({
                                                "text": condition_display_text,
                                                "detail": f"Direct code match: ({system}, {code})",
                                                "score_contribution": 2,
                                                "date": parsed_date.strftime("%Y-%m-%d") if parsed_date else "N/A"
                                            })
                                            initial_max_score_for_condition = 2
                                        max_score = max(max_score, 2)
                                        app.logger.debug(f"Condition ID {cond_id}: Code ({system}, {code}) matched direct rule for score 2.")
                                        break 

                                    # Check prefix rules
                                    for rule in prefix_rules:
                                        prefix_definition = rule.get("prefix")
                                        if not isinstance(prefix_definition, list) or len(prefix_definition) != 2:
                                            continue
                                        rule_system, rule_prefix_str = prefix_definition[0], prefix_definition[1].upper()
                                        score_value = rule.get("score", 0)
                                        rule_conditions = rule.get("conditions")

                                        if system == rule_system and code_upper.startswith(rule_prefix_str):
                                            rule_match = False
                                            if rule_conditions:
                                                req_status = rule_conditions.get("status"); date_condition_met = True
                                                if req_status and status != req_status: continue 
                                                max_m = rule_conditions.get("max_months_ago"); min_m = rule_conditions.get("min_months_ago")
                                                if parsed_date:
                                                    if max_m is not None and parsed_date < (today - datetime.timedelta(days=max_m * 30 + 15)): date_condition_met = False
                                                    if min_m is not None and parsed_date >= (today - datetime.timedelta(days=min_m * 30 + 15)): date_condition_met = False
                                                elif max_m is not None or min_m is not None: date_condition_met = False 

                                                if date_condition_met: rule_match = True
                                            else: 
                                                rule_match = True

                                            if rule_match and score_value > 0:
                                                if initial_max_score_for_condition < score_value:
                                                    matched_conditions_details.append({
                                                        "text": condition_display_text,
                                                        "detail": f"Prefix rule match: {rule_prefix_str} (System: {rule_system}) on code ({system}, {code})",
                                                        "score_contribution": score_value,
                                                        "date": parsed_date.strftime("%Y-%m-%d") if parsed_date else "N/A"
                                                    })
                                                    initial_max_score_for_condition = max(initial_max_score_for_condition, score_value)
                                                max_score = max(max_score, score_value)
                                                app.logger.debug(f"Condition ID {cond_id}: Code {code} (System: {system}) matched prefix rule '{rule_prefix_str}' for score {score_value}.")
                                                if initial_max_score_for_condition == 2: break 
                                    if initial_max_score_for_condition == 2: break 
                        # --- End Code/Prefix Check ---

                        # --- 2. Check Text if overall max_score < 2 (or current condition's score < 2) ---
                        if max_score < 2 and initial_max_score_for_condition < 2 and code_data:
                            texts_to_join = []
                            current_code_text = code_data.get("text")
                            if current_code_text: texts_to_join.append(current_code_text.lower())
                            for coding_entry in code_data.get("coding", []): # Corrected variable name
                                display_text = coding_entry.get("display")
                                if display_text: texts_to_join.append(display_text.lower())
                            condition_text_content = " ".join(texts_to_join).strip()

                            if condition_text_content:
                                for keyword in text_keywords_score_2:
                                    if keyword.lower() in condition_text_content:
                                        app.logger.info(f"Condition ID {cond_id}: Text '{condition_text_content[:100]}' matched keyword '{keyword}'. Assigning score 2.")
                                        if initial_max_score_for_condition < 2:
                                            matched_conditions_details.append({
                                                "text": condition_display_text,
                                                "detail": f"Keyword match: '{keyword}' in text '{condition_text_content[:50]}...'",
                                                "score_contribution": 2,
                                                "date": parsed_date.strftime("%Y-%m-%d") if parsed_date else "N/A"
                                            })
                                            initial_max_score_for_condition = 2
                                        max_score = 2
                                        break 
                        # --- End Text Check ---

                        # --- 3. Check ValueSet Rules if overall max_score < 2 (or current condition's score < 2) ---
                        if max_score < 2 and initial_max_score_for_condition < 2:
                            for vs_rule in value_set_rules:
                                vs_url = vs_rule.get("url"); vs_score = vs_rule.get("score", 0); vs_system_filter = vs_rule.get("system_filter")
                                if not vs_url or vs_score == 0: continue

                                expanded_codes = _expand_valueset_cached(vs_url)
                                if expanded_codes:
                                    if code_data and "coding" in code_data:
                                        for cond_coding_entry in code_data.get("coding", []):
                                            cond_system = cond_coding_entry.get("system"); cond_code_val = cond_coding_entry.get("code")
                                            if cond_system and cond_code_val:
                                                if vs_system_filter and cond_system != vs_system_filter: continue 
                                                if (cond_system, cond_code_val) in expanded_codes:
                                                    if initial_max_score_for_condition < vs_score:
                                                        matched_conditions_details.append({
                                                            "text": condition_display_text,
                                                            "detail": f"ValueSet match: ({cond_system}, {cond_code_val}) in {vs_url}",
                                                            "score_contribution": vs_score,
                                                            "date": parsed_date.strftime("%Y-%m-%d") if parsed_date else "N/A"
                                                        })
                                                        initial_max_score_for_condition = max(initial_max_score_for_condition, vs_score)
                                                    max_score = max(max_score, vs_score)
                                                    if initial_max_score_for_condition == 2: break 
                                        if initial_max_score_for_condition == 2: break 
                        # --- End ValueSet Check ---

                        # --- 4. Check Local ValueSet Rules if overall max_score < 2 (or current condition's score < 2) ---
                        if max_score < 2 and initial_max_score_for_condition < 2:
                            for local_vs_rule in local_valueset_rules:
                                local_vs_key = local_vs_rule.get("valueset_key"); local_vs_score = local_vs_rule.get("score", 0)
                                rule_conditions = local_vs_rule.get("conditions")
                                if not local_vs_key or local_vs_score == 0: continue
                                local_codes_set = local_valuesets_definitions.get(local_vs_key)

                                if local_codes_set:
                                    rule_match_for_local_vs = False
                                    if rule_conditions:
                                        req_status = rule_conditions.get("status"); date_condition_met = True
                                        if req_status and status != req_status: continue
                                        max_m = rule_conditions.get("max_months_ago"); min_m = rule_conditions.get("min_months_ago")
                                        if parsed_date:
                                            if max_m is not None and parsed_date < (today - datetime.timedelta(days=max_m * 30 + 15)): date_condition_met = False
                                            if min_m is not None and parsed_date >= (today - datetime.timedelta(days=min_m * 30 + 15)): date_condition_met = False
                                        elif max_m is not None or min_m is not None: date_condition_met = False
                                        if date_condition_met: rule_match_for_local_vs = True
                                    else: rule_match_for_local_vs = True
                                    
                                    if rule_match_for_local_vs:
                                        if code_data and "coding" in code_data:
                                            for cond_coding_entry in code_data.get("coding", []):
                                                cond_system = cond_coding_entry.get("system"); cond_code_val = cond_coding_entry.get("code")
                                                if cond_system and cond_code_val:
                                                    if (cond_system, cond_code_val) in local_codes_set:
                                                        if initial_max_score_for_condition < local_vs_score:
                                                            matched_conditions_details.append({
                                                                "text": condition_display_text,
                                                                "detail": f"Local ValueSet '{local_vs_key}' match: ({cond_system}, {cond_code_val})",
                                                                "score_contribution": local_vs_score,
                                                                "date": parsed_date.strftime("%Y-%m-%d") if parsed_date else "N/A"
                                                            })
                                                            initial_max_score_for_condition = max(initial_max_score_for_condition, local_vs_score)
                                                        max_score = max(max_score, local_vs_score)
                                                        if initial_max_score_for_condition == 2: break 
                                        if initial_max_score_for_condition == 2: break 
                        # --- End Local ValueSet Check ---
                        
                        if cond_id: processed_conditions.add(cond_id)
                        # Optimization: if max score is 2 from any single condition's evaluation, and we have details for it.
                        if max_score == 2 and any(d['score_contribution'] == 2 for d in matched_conditions_details): break 
            # --- End entry loop ---

            next_link = None
            if not (max_score == 2 and any(d['score_contribution'] == 2 for d in matched_conditions_details)):
                next_link = next((link['url'] for link in data.get('link', []) if link.get('relation') == 'next'), None)
            url = next_link

            if not url: app.logger.debug("No more condition pages or max score reached with details.")

        if pages_fetched >= MAX_PAGES: app.logger.warning(f"Stopped fetching conditions after {MAX_PAGES} pages for patient {patient_id}.")

    except requests.exceptions.RequestException as e: app.logger.error(f"Error fetching conditions for {patient_id}: {e}")
    except Exception as e: app.logger.error(f"Error processing conditions for {patient_id}: {e}", exc_info=True)

    # MODIFIED: More inclusive filtering for final_matched_details (reverted from temporary debug)
    final_matched_details = []
    if max_score > 0:
        # Include all details that had a positive score contribution
        final_matched_details = [d for d in matched_conditions_details if d.get('score_contribution', 0) > 0]
    # END MODIFIED filtering

    app.logger.info(f"Final condition score for patient {patient_id}: {max_score}. Matched conditions reported: {len(final_matched_details)}")
    return max_score, final_matched_details
# --- End MODIFIED get_condition_points ---

def get_medication_points(patient_id, oac_codings, nsaid_steroid_codings):
    """Fetches active medications and calculates points based on OAC (2 points) or NSAID/Steroid (1 point).
       NOW RETURNS: (score, matched_medication_details_list)
    """
    fhir_server = _get_fhir_server_url(); headers = _get_fhir_request_headers()
    if not fhir_server or not headers: return 0, [] # MODIFIED: Return empty list for details
    max_score = 0
    matched_medications_details = [] # NEW: List to store details
    url = f"{fhir_server}/MedicationRequest"
    params = {"patient": patient_id, "status": "active", "_count": 200}
    pages_fetched = 0
    MAX_PAGES = 10

    try:
        while url and pages_fetched < MAX_PAGES:
            if max_score == 2 and any(d['type'] == 'OAC' for d in matched_medications_details): # Optimization
                break
            pages_fetched += 1
            app.logger.debug(f"Fetching medications page {pages_fetched} from: {url} with params: {params}")
            response = requests.get(url, headers=headers, params=params, timeout=15)
            params = None; response.raise_for_status(); data = response.json()

            if "entry" in data:
                for entry in data["entry"]:
                    if "resource" in entry and entry["resource"]["resourceType"] == "MedicationRequest":
                        med_req = entry["resource"]; status = med_req.get("status", "").lower()
                        if status != 'active': continue

                        med_concept = med_req.get("medicationCodeableConcept")
                        med_display_text = med_concept.get("text", "N/A") if med_concept else "N/A"
                        if med_concept and not med_display_text and med_concept.get("coding"):
                            med_display_text = med_concept.get("coding")[0].get("display", "N/A")
                        
                        found_oac_in_current_med = False
                        current_med_score_contribution = 0
                        med_type_for_detail = "Unknown"

                        if med_concept and "coding" in med_concept:
                            for coding_entry in med_concept.get("coding", []):
                                system = coding_entry.get("system"); code = coding_entry.get("code")
                                if system and code:
                                    current_tuple = (system, code)
                                    if current_tuple in oac_codings:
                                        app.logger.info(f"OAC found: {current_tuple} ({med_display_text}) for patient {patient_id}")
                                        if max_score < 2: # Add detail only if it increases score or is new OAC
                                            matched_medications_details.append({
                                                "text": med_display_text,
                                                "detail": f"OAC: ({system}, {code})",
                                                "score_contribution": 2,
                                                "type": "OAC"
                                            })
                                        max_score = 2
                                        found_oac_in_current_med = True
                                        current_med_score_contribution = 2
                                        med_type_for_detail = "OAC"
                                        break # Found OAC, highest score for this med

                        # Only check NSAID/Steroid if OAC not found in *this current med* and overall max_score is still < 2
                        if not found_oac_in_current_med and max_score < 2:
                            if med_concept and "coding" in med_concept:
                                for coding_entry in med_concept.get("coding", []):
                                    system = coding_entry.get("system"); code = coding_entry.get("code")
                                    if system and code:
                                        current_tuple = (system, code)
                                        if current_tuple in nsaid_steroid_codings:
                                            app.logger.info(f"NSAID/Steroid found: {current_tuple} ({med_display_text}) for patient {patient_id}")
                                            if max_score < 1: # Add detail only if it increases overall score
                                                matched_medications_details.append({
                                                    "text": med_display_text,
                                                    "detail": f"NSAID/Steroid: ({system}, {code})",
                                                    "score_contribution": 1,
                                                    "type": "NSAID/Steroid"
                                                })
                                            max_score = max(max_score, 1)
                                            current_med_score_contribution = 1 # This med contributed 1
                                            med_type_for_detail = "NSAID/Steroid"
                                            break # Found NSAID/Steroid for this med
                        
                        # Optimization: if overall max_score is 2 (from any med) and we have an OAC detail, stop.
                        if max_score == 2 and any(d['type'] == 'OAC' for d in matched_medications_details):
                             break # Break entry loop
            # --- End entry loop ---

            next_link = None
            if not (max_score == 2 and any(d['type'] == 'OAC' for d in matched_medications_details)):
                next_link = next((link['url'] for link in data.get('link', []) if link.get('relation') == 'next'), None)
            url = next_link

            if not url: app.logger.debug("No more medication pages or max score reached with OAC details.")

        if pages_fetched >= MAX_PAGES: app.logger.warning(f"Stopped fetching medications after {MAX_PAGES} pages for patient {patient_id}.")

    except requests.exceptions.RequestException as e: app.logger.error(f"Error fetching MedicationRequest for {patient_id}: {e}")
    except Exception as e: app.logger.error(f"Error processing MedicationRequest for {patient_id}: {e}", exc_info=True)

    # MODIFIED: More inclusive filtering for final_matched_med_details
    final_matched_med_details = []
    if max_score > 0:
        # Include all details that had a positive score contribution
        final_matched_med_details = [d for d in matched_medications_details if d.get('score_contribution', 0) > 0]
    # END MODIFIED filtering

    app.logger.info(f"Final medication score for patient {patient_id}: {max_score}. Matched medications reported: {len(final_matched_med_details)}")
    return max_score, final_matched_med_details

# ... (calculate_bleeding_risk remains the same) ...
def calculate_bleeding_risk(age, egfr_value, hemoglobin, sex, platelet, condition_points, medication_points, blood_transfusion_points, risk_params, final_threshold):
    """Calculates bleeding risk score based on provided parameters."""
    try:
        app.logger.info("--- Bleeding Risk Calculation Start ---")
        app.logger.info(f"Input Parameters: Age={age}, eGFR={egfr_value}, Hb={hemoglobin}, Sex={sex}, Platelet={platelet}, CondPoints={condition_points}, MedPoints={medication_points}, TransfusionPoints={blood_transfusion_points}")
        app.logger.info(f"Risk Params Config (risk_score_parameters from cdss_config.json): {risk_params}")
        app.logger.info(f"Final Threshold Config (final_risk_threshold from cdss_config.json): {final_threshold}")

        base_score = 0
        age_score_component = 0
        if age is not None:
            # Assumes risk_params contains keys like 'age_gte_75_params' and 'age_gte_65_params'
            # Each of these is an object: { "score": X, "threshold": Y }
            params_age_gte_75 = risk_params.get('age_gte_75_params', {})
            params_age_gte_65 = risk_params.get('age_gte_65_params', {})

            threshold_75 = params_age_gte_75.get('threshold', 75) # Default if not in config
            score_75 = params_age_gte_75.get('score', 0)
            threshold_65 = params_age_gte_65.get('threshold', 65)
            score_65 = params_age_gte_65.get('score', 0)

            if age >= threshold_75:
                age_score_component = score_75
            elif age >= threshold_65:
                age_score_component = score_65
        base_score += age_score_component
        app.logger.info(f"Age component score: {age_score_component} (Age: {age})")

        egfr_score_component = 0
        if egfr_value is not None:
            # Example keys: 'egfr_lt_15_params', 'egfr_lt_30_params', 'egfr_lt_45_params'
            params_egfr_lt_15 = risk_params.get('egfr_lt_15_params', {})
            params_egfr_lt_30 = risk_params.get('egfr_lt_30_params', {})
            params_egfr_lt_45 = risk_params.get('egfr_lt_45_params', {})

            if egfr_value < params_egfr_lt_15.get('threshold', 15):
                egfr_score_component = params_egfr_lt_15.get('score', 0)
            elif egfr_value < params_egfr_lt_30.get('threshold', 30):
                egfr_score_component = params_egfr_lt_30.get('score', 0)
            elif egfr_value < params_egfr_lt_45.get('threshold', 45):
                egfr_score_component = params_egfr_lt_45.get('score', 0)
        base_score += egfr_score_component
        app.logger.info(f"eGFR component score: {egfr_score_component} (eGFR: {egfr_value})")

        hemoglobin_score_component = 0
        if hemoglobin is not None and sex is not None:
            sex_lower = sex.lower()
            # Example keys: 'hgb_male_lt_13_params', 'hgb_female_lt_12_params'
            params_hgb_male = risk_params.get('hgb_male_lt_13_params', {})
            params_hgb_female = risk_params.get('hgb_female_lt_12_params', {})

            if sex_lower == 'male' and hemoglobin < params_hgb_male.get('threshold', 13):
                hemoglobin_score_component = params_hgb_male.get('score', 0)
            elif sex_lower == 'female' and hemoglobin < params_hgb_female.get('threshold', 12):
                hemoglobin_score_component = params_hgb_female.get('score', 0)
        base_score += hemoglobin_score_component
        app.logger.info(f"Hemoglobin component score: {hemoglobin_score_component} (Hb: {hemoglobin}, Sex: {sex})")

        platelet_score_component = 0
        if platelet is not None:
            # Example key: 'plt_lt_100_params'
            params_plt = risk_params.get('plt_lt_100_params', {})
            if platelet < params_plt.get('threshold', 100):
                platelet_score_component = params_plt.get('score', 0)
        base_score += platelet_score_component
        app.logger.info(f"Platelet component score: {platelet_score_component} (Platelet: {platelet})")
        
        app.logger.info(f"Calculated base_score (sum of age, eGFR, Hb, plt components): {base_score}")
        app.logger.info(f"Points from Conditions: {condition_points}")
        app.logger.info(f"Points from Medications: {medication_points}")
        app.logger.info(f"Points from Blood Transfusions: {blood_transfusion_points}")

        total_score = base_score + condition_points + medication_points + blood_transfusion_points
        app.logger.info(f"Calculated total_score: {total_score}")

        risk_category = 'low' # Default to low
        # Read the high risk threshold from the specific key in config
        # Default to a very high number if key is missing or not an int/float, to prevent accidental 'high' risk
        threshold_high = final_threshold.get('high_risk_min_score') 

        app.logger.info(f"Attempting to use High risk threshold from key 'high_risk_min_score': {threshold_high}")

        # Validate threshold_high before using it
        if not isinstance(threshold_high, (int, float)):
            app.logger.warning(f"High risk threshold ('high_risk_min_score') is missing or not a number: {threshold_high}. Defaulting to effectively no high risk category for safety (scores will be low/medium).")
            # Set to infinity or a very large number if you want to ensure nothing becomes 'high' by default error
            # For now, if it's not a valid number, risk will remain 'low' or 'medium' if a medium threshold existed.
            # Given current logic, without a valid threshold_high, risk will remain 'low'.
            pass # Risk category will remain 'low' if threshold_high is not valid
        elif total_score >= threshold_high:
            risk_category = 'high'
        
        # If you want to introduce a medium category, you would add a similar check here:
        # threshold_medium = final_threshold.get('medium_risk_min_score')
        # if isinstance(threshold_medium, (int, float)) and total_score >= threshold_medium and risk_category != 'high':
        #     risk_category = 'medium'

        app.logger.info(f"Final risk_category: {risk_category} for total_score: {total_score}")
        app.logger.info("--- Bleeding Risk Calculation End ---")

        return {
            'score': total_score,
            'category': risk_category,
            'details': {
                'base_score': base_score,
                'age_score_component': age_score_component,
                'egfr_score_component': egfr_score_component,
                'hemoglobin_score_component': hemoglobin_score_component,
                'platelet_score_component': platelet_score_component,
                'condition_points': condition_points,
                'medication_points': medication_points,
                'blood_transfusion_points': blood_transfusion_points,
                'risk_params': risk_params,
                # 新增原始數值
                'age': age,
                'egfr_value': egfr_value,
                'hemoglobin': hemoglobin,
                'sex': sex,
                'platelet': platelet
            }
        }

    except Exception as e:
        app.logger.error(f"Error calculating bleeding risk: {e}", exc_info=True)
        return None

def get_blood_transfusion_points(patient_id):
    """Fetches blood transfusion procedures and calculates points based on timing."""
    try:
        fhir_server = _get_fhir_server_url()
        headers = _get_fhir_request_headers()
        if not fhir_server or not headers:
            return 0, []

        url = f"{fhir_server}/Procedure"
        params = {"patient": patient_id, "_count": 100}  # Increased count for more procedures
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "entry" not in data:
            return 0, []

        points = 0
        matched_procedures = []

        for entry in data["entry"]:
            procedure = entry["resource"]
            coded = procedure.get("code", {}).get("coding", [])
            performed_date = procedure.get("performedDateTime")
            if not performed_date:
                continue

            try:
                procedure_date = datetime.datetime.strptime(performed_date[:10], "%Y-%m-%d")
                months_diff = (datetime.datetime.now() - procedure_date).days / 30.44
                if months_diff > 12:
                    continue

                if any(tuple(c.get("system", ""), c.get("code", "")) in BLOOD_TRANSFUSION_CODES_CONFIG for c in coded):
                    if months_diff <= 6:
                        points += 2
                        matched_procedures.append({
                            "text": procedure.get("code", {}).get("text", "N/A"),
                            "reason": "Blood transfusion within 6 months",
                            "date": performed_date
                        })
                    elif months_diff <= 12:
                        points += 1
                        matched_procedures.append({
                            "text": procedure.get("code", {}).get("text", "N/A"),
                            "reason": "Blood transfusion between 6-12 months",
                            "date": performed_date
                        })

            except (ValueError, TypeError):
                continue

        return points, matched_procedures

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching procedures for patient {patient_id}: {e}")
        return 0, []
    except Exception as e:
        app.logger.error(f"Unexpected error processing procedures for patient {patient_id}: {e}", exc_info=True)
        return 0, []

# --- >> NEW HELPER: Extract Hemoglobin from prefetch bundle << ---
def get_hemoglobin_from_prefetch(obs_bundle):
    """Extracts Hemoglobin value (g/dL) from a prefetched Observation bundle.
    
    Searches for observations, optionally by LOINC codes common for Hemoglobin,
    extracts the value, and converts it to g/dL if necessary.
    """
    # MODIFIED: Use centralized LOINC codes for filtering
    HEMOGLOBIN_LOINCS_SET = set(LOINC_CODES["HEMOGLOBIN"])

    if obs_bundle and "entry" in obs_bundle:
        for entry in obs_bundle["entry"]:
            if "resource" in entry and entry["resource"]["resourceType"] == "Observation":
                obs = entry["resource"]
                obs_id_for_log = obs.get("id", "unknown_id")
                
                # Optional: Add LOINC code check here if prefetch includes many other types of observations
                found_hgb_code = False
                for coding in obs.get("code", {}).get("coding", []):
                    if coding.get("system") == "http://loinc.org" and coding.get("code") in HEMOGLOBIN_LOINCS_SET:
                        found_hgb_code = True
                        break
                if not found_hgb_code:
                    app.logger.debug(f"Prefetch Obs {obs_id_for_log} is not a target Hemoglobin code based on centralized LOINC list. Skipping.")
                    continue

                value_data = obs.get("valueQuantity")
                if value_data:
                    value_str = value_data.get("value")
                    unit = value_data.get("unit", "").lower()
                    try:
                        value = float(value_str)
                        if unit == "g/l":
                            app.logger.info(f"Found prefetch Hemoglobin: {value} {unit} (Obs ID: {obs_id_for_log}). Converting to g/dL.")
                            return value / 10.0
                        elif unit in ["mmol/l", "mmol/L"]:
                            # Conversion factor from get_hemoglobin: value * 1.61
                            app.logger.info(f"Found prefetch Hemoglobin: {value} {unit} (Obs ID: {obs_id_for_log}). Converting to g/dL.")
                            return value * 1.61
                        elif unit == "g/dl":
                            app.logger.info(f"Found prefetch Hemoglobin: {value} {unit} (Obs ID: {obs_id_for_log}).")
                            return value
                        else:
                            # Log if unit is present but unrecognized for a potential Hgb observation
                            if unit: # Only log if unit is not empty
                                app.logger.warning(f"Unrecognized hemoglobin unit '{unit}' in prefetch for Obs ID {obs_id_for_log}. Value '{value_str}' not used.")
                            # Continue to the next entry, as this one might not be Hgb or has an unusable unit
                            continue
                    except (TypeError, ValueError):
                        app.logger.warning(f"Could not convert hemoglobin value '{value_str}' to float in prefetch for Obs ID {obs_id_for_log}.")
                        continue # Try next entry
                # else:
                #     app.logger.debug(f"Prefetch Obs {obs_id_for_log} missing valueQuantity. Skipping.")
            # else:
            #     app.logger.debug(f"Prefetch entry is not an Observation or missing resource. Skipping.")

    app.logger.info("No suitable hemoglobin observation with recognized unit and value found in prefetch bundle.")
    return None
# --- >> END NEW HELPER << ---

def get_creatinine_from_prefetch(obs_bundle):
    """Extract creatinine (mg/dL) from CDS Hooks prefetch Observation bundle"""
    # MODIFIED: Use centralized LOINC codes for filtering
    CREATININE_LOINCS_SET = set(LOINC_CODES["CREATININE"])
    # Note: This simplified version takes the *first* valid entry found.
    if obs_bundle and "entry" in obs_bundle:
        for entry in obs_bundle["entry"]: # Iterate to find one with value
            if "resource" in entry and entry["resource"]["resourceType"] == "Observation":
                obs = entry["resource"]
                obs_id_for_log = obs.get("id", "unknown_id")
                # Optional: Add LOINC code check here if prefetch includes other observations
                found_creatinine_code = False
                for coding in obs.get("code",{}).get("coding",[]):
                    if coding.get("system") == "http://loinc.org" and coding.get("code") in CREATININE_LOINCS_SET:
                        found_creatinine_code = True
                        break
                if not found_creatinine_code:
                    app.logger.debug(f"Prefetch Obs {obs_id_for_log} is not a target Creatinine code based on centralized LOINC list. Skipping.")
                    continue

                value_data = obs.get("valueQuantity")
                if value_data:
                    value = value_data.get("value")
                    unit = value_data.get("unit", "").lower()
                    try:
                        value = float(value)
                        if unit in ["umol/l", "µmol/l"]:
                            app.logger.info(f"Found prefetch Creatinine: {value} {unit} (Obs ID: {obs.get('id')}). Converting to mg/dL.")
                            return value / 88.4
                        elif unit == "mg/dl":
                            app.logger.info(f"Found prefetch Creatinine: {value} {unit} (Obs ID: {obs.get('id')}).")
                            return value
                        else:
                            app.logger.warning(f"Unrecognized creatinine unit '{unit}' in prefetch for Obs ID {obs.get('id')}.")
                            continue # Try next entry if unit is wrong
                    except (TypeError, ValueError):
                        app.logger.warning(f"Could not convert creatinine value '{value}' to float in prefetch for Obs ID {obs.get('id')}.")
                        continue # Try next entry
    app.logger.info("No suitable creatinine observation found in prefetch bundle.")
    return None # No usable value found


def get_platelet_from_prefetch(obs_bundle):
    """Extract platelet count from CDS Hooks prefetch Observation bundle"""
    # MODIFIED: Use centralized LOINC codes for filtering
    PLATELET_LOINCS_SET = set(LOINC_CODES["PLATELET"])
    # Note: This simplified version takes the *first* valid numeric entry found.
    if obs_bundle and "entry" in obs_bundle:
        for entry in obs_bundle["entry"]:
            if "resource" in entry and entry["resource"]["resourceType"] == "Observation":
                obs = entry["resource"]
                obs_id_for_log = obs.get("id", "unknown_id")
                # Optional: Add LOINC code check here
                found_platelet_code = False
                for coding in obs.get("code",{}).get("coding",[]):
                    if coding.get("system") == "http://loinc.org" and coding.get("code") in PLATELET_LOINCS_SET:
                        found_platelet_code = True
                        break
                if not found_platelet_code:
                    app.logger.debug(f"Prefetch Obs {obs_id_for_log} is not a target Platelet code based on centralized LOINC list. Skipping.")
                    continue

                value_data = obs.get("valueQuantity")
                if value_data:
                    value = value_data.get("value")
                    try:
                        platelet_value = float(value)
                        app.logger.info(f"Found prefetch Platelet: {platelet_value} (Obs ID: {obs.get('id')}).")
                        return platelet_value # Return first valid float
                    except (TypeError, ValueError):
                        app.logger.warning(f"Could not convert platelet value '{value}' to float in prefetch for Obs ID {obs.get('id')}.")
                        continue # Try next entry
    app.logger.info("No suitable platelet observation found in prefetch bundle.")
    return None # No value found

# --- >> NEW HELPER: Extract direct eGFR from prefetch bundle << ---
def get_direct_egfr_from_prefetch(egfr_obs_bundle):
    """Extract value from prefetched direct eGFR Observation bundle (LOINC 33914-3)"""
    # MODIFIED: Use centralized LOINC codes for filtering (optional, as prefetch should be specific)
    EGFR_DIRECT_LOINCS_SET = set(LOINC_CODES["EGFR_DIRECT"])

    if not egfr_obs_bundle or "entry" not in egfr_obs_bundle or not egfr_obs_bundle["entry"]:
        app.logger.debug("No direct eGFR observation bundle provided or bundle is empty.")
        return None

    # Usually prefetch for _count=1 returns only one if found
    obs = egfr_obs_bundle["entry"][0].get("resource")
    if not obs or obs.get("resourceType") != "Observation":
        app.logger.warning("Prefetched direct eGFR resource not found or not an Observation.")
        return None

    # Optional: Validate that the observation is indeed the one we expect, even if prefetch was specific
    obs_id_for_log = obs.get("id", "unknown_id")
    found_egfr_code = False
    for coding in obs.get("code", {}).get("coding", []):
        if coding.get("system") == "http://loinc.org" and coding.get("code") in EGFR_DIRECT_LOINCS_SET:
            found_egfr_code = True
            break
    if not found_egfr_code:
        app.logger.warning(f"Prefetched Obs {obs_id_for_log} (expected eGFR) does not match target eGFR LOINC codes from centralized list. Value not used.")
        return None

    value_data = obs.get("valueQuantity")
    if value_data:
        value = value_data.get("value")
        unit = value_data.get("unit", "") # Check unit if needed
        try:
            direct_egfr_val = float(value)
            app.logger.info(f"Found directly prefetched eGFR value {direct_egfr_val} (Unit: {unit}, Obs ID: {obs.get('id')})")
            # Add unit check/conversion if necessary
            return direct_egfr_val
        except (TypeError, ValueError):
            app.logger.error(f"Could not convert prefetched direct eGFR value '{value}' to float (Obs ID: {obs.get('id')})")
    else:
         app.logger.warning(f"Prefetched direct eGFR observation {obs.get('id')} is missing valueQuantity.")

    return None
# --- >> END NEW HELPER << ---

# --- >> NEW HELPER: Calculate/Fetch eGFR from Prefetch Data << ---
def get_egfr_value_from_prefetch(prefetch_data, age, sex):
    """
    Calculates or fetches eGFR from prefetch data using CKD-EPI 2021.
    Tries calculation from prefetched Creatinine first. If unavailable/fails,
    falls back to extracting value from prefetched direct eGFR observation.
    Returns eGFR value (float) or None.
    """
    # Attempt 1: Calculate from prefetched Creatinine using CKD-EPI 2021
    cr_bundle = prefetch_data.get("creatinine")
    cr_value = get_creatinine_from_prefetch(cr_bundle) # Assumes returns in mg/dL or None

    age_is_valid = isinstance(age, (int, float)) and age > 0
    sex_is_valid = sex is not None and sex.lower() in ["male", "female"]
    cr_is_valid = isinstance(cr_value, (int, float)) and cr_value > 0

    if cr_is_valid and age_is_valid and sex_is_valid:
        try:
            # --- CKD-EPI 2021 Formula ---
            sex_lower = sex.lower()
            kappa = 0.7 if sex_lower == "female" else 0.9
            alpha = -0.241 if sex_lower == "female" else -0.302
            sex_factor = 1.012 if sex_lower == "female" else 1.0
            term1 = cr_value / kappa
            term2 = min(term1, 1.0) ** alpha
            term3 = max(term1, 1.0) ** (-1.200)
            age_factor = 0.9938 ** age
            eGFR_calc = 142 * term2 * term3 * age_factor * sex_factor
            # --- End CKD-EPI 2021 Formula ---
            app.logger.info(f"Calculated eGFR (CKD-EPI 2021) {eGFR_calc:.2f} from prefetched Creatinine {cr_value}")
            return float(eGFR_calc)
        except OverflowError:
            app.logger.error(f"Math OverflowError calculating eGFR from prefetched Cr. Inputs: cr={cr_value}, age={age}, sex={sex}")
        except Exception as e:
            app.logger.error(f"Error calculating eGFR (CKD-EPI 2021) from prefetched Creatinine: {e}")
            # Fall through to attempt fetching direct eGFR

    # Attempt 2: Extract from direct eGFR prefetch bundle
    if not cr_is_valid:
        app.logger.warning(f"Prefetched Creatinine value '{cr_value}' is invalid. Attempting to use direct eGFR prefetch.")
    elif not age_is_valid or not sex_is_valid:
        app.logger.warning(f"Age '{age}' or Sex '{sex}' is invalid for eGFR calculation. Attempting to use direct eGFR prefetch.")
    else: # Log if calculation failed despite valid inputs
        app.logger.warning(f"eGFR calculation failed from prefetch (Cr: {cr_value}, Age: {age}, Sex: {sex}). Attempting direct eGFR prefetch.")

    egfr_bundle = prefetch_data.get("egfr") # Get the bundle using the key 'egfr'
    direct_egfr_value = get_direct_egfr_from_prefetch(egfr_bundle)

    if direct_egfr_value is not None:
        app.logger.info(f"Using value from directly prefetched eGFR observation: {direct_egfr_value}")
        return direct_egfr_value
    else:
         app.logger.warning("Could not obtain eGFR from direct prefetch bundle.")

    return None # Return None if both attempts fail
# --- >> END NEW HELPER << ---

# --- MODIFIED: get_condition_points_from_prefetch signature unchanged, but usage inside is affected ---
def get_condition_points_from_prefetch(conditions_bundle, codes_score_2, prefix_rules, text_keywords_score_2, value_set_rules, local_valueset_rules, local_valuesets_definitions): # ADDED local_valueset_rules and definitions
    """Process prefetched Condition bundle using passed code sets, prefix rules, text keywords and ValueSet (URL and Local).
       MODIFIED: No longer performs 12-month date filtering on backend.
       NOW RETURNS: (score, matched_details_list)
    """
    max_score = 0
    matched_conditions_details = []
    # REMOVED: Date threshold calculation for 12-month filtering
    # try: 
    #     today = datetime.date.today()
    #     twelve_months_ago = today - datetime.timedelta(days=365) 
    #     perform_date_check = True
    #     app.logger.info(f"Backend date filter: Conditions must be on or after {twelve_months_ago}")
    # except Exception as e:
    #     perform_date_check = False
    #     app.logger.error(f"Error calculating date threshold for condition prefetch filter: {e}")
    today = datetime.date.today() # Still needed for prefix rule date conditions

    processed_conditions = set() # Avoid duplicate processing of same resources in bundle
    if conditions_bundle and "entry" in conditions_bundle:
        app.logger.info(f"Processing {len(conditions_bundle['entry'])} conditions from prefetch bundle.")
        for entry in conditions_bundle["entry"]:
            if max_score == 2: break # Optimization: if already reached max score, stop processing

            if "resource" in entry and entry["resource"]["resourceType"] == "Condition":
                cond = entry["resource"]
                cond_id = cond.get("id", f"nobundleid_{len(processed_conditions)}") # Generate a temporary ID if no ID exists
                if cond_id in processed_conditions: continue # Skip if already processed

                # --- Existing scoring logic --- (Now applies to all conditions from prefetch)
                # Still need to parse date for prefix rules that might have their own date conditions
                recorded_date_str = cond.get("recordedDate")
                parsed_date = None
                if recorded_date_str:
                    try:
                        date_str_part = recorded_date_str.split('T')[0]
                        if len(date_str_part) >= 10:
                            parsed_date = datetime.datetime.strptime(date_str_part[:10], "%Y-%m-%d").date()
                    except ValueError:
                        app.logger.warning(f"Could not parse recordedDate '{recorded_date_str}' for Condition ID {cond_id} for prefix rule date checks.")
                        # parsed_date remains None

                code_data = cond.get("code")
                status_coding = cond.get("clinicalStatus", {}).get("coding", [{}])[0]
                status = status_coding.get("code", "").lower()
                current_condition_max_score = 0

                # --- 1. Check Codes and Prefixes ---
                if code_data and "coding" in code_data:
                    for coding in code_data.get("coding", []):
                        code = coding.get("code")
                        system = coding.get("system") # Get system from coding
                        if code:
                            code_upper = code.upper()
                            # Check direct code match for score 2
                            if (system, code) in codes_score_2: # Check (system, code) tuple
                                if current_condition_max_score < 2:
                                    # Get condition display text
                                    condition_display_text = "N/A"
                                    if code_data:
                                        text_from_code = code_data.get("text")
                                        if text_from_code:
                                            condition_display_text = text_from_code
                                        else:
                                            codings = code_data.get("coding")
                                            if codings and len(codings) > 0:
                                                display_from_coding = codings[0].get("display")
                                                if display_from_coding:
                                                    condition_display_text = display_from_coding
                                    
                                    matched_conditions_details.append({
                                        "text": condition_display_text,
                                        "detail": f"Direct code match: ({system}, {code})",
                                        "score_contribution": 2,
                                        "date": parsed_date.strftime("%Y-%m-%d") if parsed_date else "N/A"
                                    })
                                current_condition_max_score = max(current_condition_max_score, 2); 
                                app.logger.debug(f"Condition ID {cond_id}: Code ({system}, {code}) matched direct rule for score 2.")
                                break # Max score found for this condition from direct codes

                            # Check prefix rules (possible with their own date conditions)
                            for rule in prefix_rules:
                                prefix_definition = rule.get("prefix")
                                if not isinstance(prefix_definition, list) or len(prefix_definition) != 2:
                                    app.logger.warning(f"Skipping malformed prefix rule in get_condition_points (expected [system, prefix_str]): {rule}")
                                    continue
                                rule_system, rule_prefix_str = prefix_definition[0], prefix_definition[1].upper()

                                score_value = rule.get("score", 0); rule_conditions = rule.get("conditions")
                                
                                # Check if the current coding's system matches the rule's system
                                # and if the code starts with the rule's prefix string.
                                if system == rule_system and code_upper.startswith(rule_prefix_str):
                                    rule_match = False
                                    if rule_conditions:
                                        req_status = rule_conditions.get("status"); date_condition_met = True
                                        if req_status and status != req_status: continue # Status does not match rule

                                        # Check rule-specific date conditions (using parsed_date)
                                        max_m = rule_conditions.get("max_months_ago"); min_m = rule_conditions.get("min_months_ago")
                                        if parsed_date: # Only applicable if Condition has a date
                                            if max_m is not None and parsed_date < (today - datetime.timedelta(days=max_m * 30 + 15)): date_condition_met = False
                                            if min_m is not None and parsed_date >= (today - datetime.timedelta(days=min_m * 30 + 15)): date_condition_met = False
                                        elif max_m is not None or min_m is not None: date_condition_met = False # If rule requires date but Condition does not have one, it does not match

                                        if date_condition_met: rule_match = True
                                    else: # No specific conditions in this rule, prefix match is enough
                                        rule_match = True

                                    if rule_match:
                                        current_condition_max_score = max(current_condition_max_score, score_value)
                                        app.logger.debug(f"Condition ID {cond_id}: Code {code} (System: {system}) matched prefix rule '{rule_prefix_str}' (System: {rule_system}) for score {score_value}.")
                                        if current_condition_max_score == 2: break # Exit prefix rule loop if max score reached
                            if current_condition_max_score == 2: break # Exit coding loop if max score reached
                # --- End Code/Prefix Check ---

                # --- 2. NEW: Check Text if score < 2 ---
                if current_condition_max_score < 2 and code_data:
                    texts_to_join = []
                    # Get text from code.text
                    current_code_text = code_data.get("text")
                    if current_code_text: # Check if text is not None and not empty
                        texts_to_join.append(current_code_text.lower())
                    # Get text from coding.display
                    for coding in code_data.get("coding", []):
                        display_text = coding.get("display")
                        if display_text: # Check if display is not None and not empty
                            texts_to_join.append(display_text.lower())

                    condition_text = " ".join(texts_to_join).strip()

                    if condition_text: # Only check if we have some text
                        # *** Uses the text_keywords_score_2 parameter passed to the function ***
                        for keyword in text_keywords_score_2: # text_keywords_score_2 is a SET
                            if keyword.lower() in condition_text:
                                if current_condition_max_score < 2:
                                    # Get condition display text
                                    condition_display_text = "N/A"
                                    if code_data:
                                        text_from_code = code_data.get("text")
                                        if text_from_code:
                                            condition_display_text = text_from_code
                                        else:
                                            codings = code_data.get("coding")
                                            if codings and len(codings) > 0:
                                                display_from_coding = codings[0].get("display")
                                                if display_from_coding:
                                                    condition_display_text = display_from_coding
                                    
                                    matched_conditions_details.append({
                                        "text": condition_display_text,
                                        "detail": f"Keyword match: '{keyword}' in text '{condition_text[:50]}...'",
                                        "score_contribution": 2,
                                        "date": parsed_date.strftime("%Y-%m-%d") if parsed_date else "N/A"
                                    })
                                app.logger.info(f"Prefetch Condition ID {cond_id}: Text '{condition_text[:100]}...' matched keyword '{keyword}'. Assigning score 2.")
                                current_condition_max_score = 2
                                break # Found a keyword, max score reached
                # --- End Text Check ---

                # --- 3. NEW: Check ValueSet Rules if score < 2 ---
                if current_condition_max_score < 2:
                    for vs_rule in value_set_rules:
                        vs_url = vs_rule.get("url")
                        vs_score = vs_rule.get("score", 0)
                        vs_system_filter = vs_rule.get("system_filter")

                        if not vs_url or vs_score == 0:
                            continue
                        
                        # _expand_valueset_cached might return None if not cached and no auth for live expansion
                        expanded_codes = _expand_valueset_cached(vs_url)
                        if expanded_codes:
                            app.logger.debug(f"Prefetch Condition ID {cond_id} (within 12m): Checking against ValueSet {vs_url} ({len(expanded_codes)} codes) for score {vs_score}.")
                            if code_data and "coding" in code_data:
                                for cond_coding_entry in code_data.get("coding", []):
                                    cond_system = cond_coding_entry.get("system")
                                    cond_code_val = cond_coding_entry.get("code")
                                    if cond_system and cond_code_val:
                                        if vs_system_filter and cond_system != vs_system_filter:
                                            continue
                                        if (cond_system, cond_code_val) in expanded_codes:
                                            app.logger.info(f"Prefetch Condition ID {cond_id} (within 12m): Code ({cond_system}, {cond_code_val}) matched ValueSet {vs_url}. Assigning score {vs_score}.")
                                            current_condition_max_score = max(current_condition_max_score, vs_score)
                                            if current_condition_max_score == 2: break 
                            if current_condition_max_score == 2: break 
                        else:
                            app.logger.warning(f"Prefetch Condition ID {cond_id} (within 12m): Could not expand or get cached codes for ValueSet {vs_url}. Rule will not be applied in this prefetch context if expansion requires live call without auth.")
                # --- End ValueSet Check ---

                # --- 4. NEW: Check Local ValueSet Rules if score < 2 (for prefetch) ---
                if current_condition_max_score < 2:
                    for local_vs_rule in local_valueset_rules:
                        local_vs_key = local_vs_rule.get("valueset_key")
                        local_vs_score = local_vs_rule.get("score", 0)
                        rule_conditions = local_vs_rule.get("conditions") # Get optional conditions

                        if not local_vs_key or local_vs_score == 0:
                            continue
                        
                        local_codes_set = local_valuesets_definitions.get(local_vs_key)

                        if local_codes_set:
                            rule_match_for_local_vs_prefetch = False
                            # Check rule-specific conditions (status, date) if they exist for prefetch
                            if rule_conditions:
                                req_status = rule_conditions.get("status")
                                date_condition_met_prefetch = True
                                if req_status and status != req_status: # status from the current prefetched condition
                                    continue 

                                max_m = rule_conditions.get("max_months_ago")
                                min_m = rule_conditions.get("min_months_ago")
                                # parsed_date is from the current prefetched condition
                                if parsed_date: 
                                    if max_m is not None and parsed_date < (today - datetime.timedelta(days=max_m * 30 + 15)):
                                        date_condition_met_prefetch = False
                                    if min_m is not None and parsed_date >= (today - datetime.timedelta(days=min_m * 30 + 15)):
                                        date_condition_met_prefetch = False
                                elif max_m is not None or min_m is not None: 
                                    date_condition_met_prefetch = False
                                
                                if date_condition_met_prefetch:
                                    rule_match_for_local_vs_prefetch = True
                            else: # No specific conditions in this local_vs_rule, direct match is enough
                                rule_match_for_local_vs_prefetch = True

                            if rule_match_for_local_vs_prefetch: # If rule conditions are met
                                app.logger.debug(f"Prefetch Condition ID {cond_id}: Checking Local VS '{local_vs_key}' ({len(local_codes_set)} codes) for score {local_vs_score}.")
                                if code_data and "coding" in code_data:
                                    for cond_coding_entry in code_data.get("coding", []):
                                        cond_system = cond_coding_entry.get("system")
                                        cond_code_val = cond_coding_entry.get("code")
                                        if cond_system and cond_code_val:
                                            if (cond_system, cond_code_val) in local_codes_set:
                                                app.logger.info(f"Prefetch Condition ID {cond_id}: Code ({cond_system}, {cond_code_val}) matched Local VS '{local_vs_key}' (and rule conditions). Score {local_vs_score}.")
                                                current_condition_max_score = max(current_condition_max_score, local_vs_score)
                                                if current_condition_max_score == 2: break
                                        if current_condition_max_score == 2: break 
                                if current_condition_max_score == 2: break 
                        else:
                            app.logger.warning(f"Prefetch Condition ID {cond_id}: Local ValueSet key '{local_vs_key}' not found or empty. Rule skipped.")
                # --- End Local ValueSet Check (for prefetch) ---

                max_score = max(max_score, current_condition_max_score) # Update global max score
                processed_conditions.add(cond_id) # Mark as processed

    # Filter final matched details
    final_matched_details = []
    if max_score > 0:
        final_matched_details = [d for d in matched_conditions_details if d.get('score_contribution', 0) > 0]

    app.logger.info(f"Final prefetch condition score after backend filtering and text analysis: {max_score}. Matched conditions: {len(final_matched_details)}")
    return max_score, final_matched_details
# --- End MODIFIED get_condition_points_from_prefetch ---


def get_medication_points_from_prefetch(medications_bundle, oac_codings, nsaid_steroid_codings):
    """處理預先取得的 MedicationRequest bundle，使用傳入的代碼集。
       NOW RETURNS: (score, matched_medication_details_list)
    """
    max_score = 0
    matched_medications_details = []
    if medications_bundle and "entry" in medications_bundle:
        for entry in medications_bundle["entry"]:
            if "resource" in entry and entry["resource"]["resourceType"] == "MedicationRequest":
                med_req = entry["resource"]
                status = med_req.get("status", "").lower()
                # Consider only active status from prefetch
                if status != 'active': 
                    continue

                med_concept = med_req.get("medicationCodeableConcept")
                med_display_text = med_concept.get("text", "N/A") if med_concept else "N/A"
                if med_concept and not med_display_text and med_concept.get("coding"):
                    med_display_text = med_concept.get("coding")[0].get("display", "N/A")
                
                found_oac_in_med = False
                
                if med_concept and "coding" in med_concept:
                    for coding_entry in med_concept.get("coding", []):
                        system = coding_entry.get("system")
                        code = coding_entry.get("code")
                        if system and code: # Check both exist
                            current_tuple = (system, code)
                            if current_tuple in oac_codings: 
                                if max_score < 2:
                                    matched_medications_details.append({
                                        "text": med_display_text,
                                        "detail": f"OAC: ({system}, {code})",
                                        "score_contribution": 2,
                                        "type": "OAC"
                                    })
                                max_score = 2
                                found_oac_in_med = True
                                break
                    
                    if found_oac_in_med: 
                        break # Exit outer loop if OAC found

                    # Check NSAID only if OAC not found and score < 2
                    if not found_oac_in_med and max_score < 2:
                        for coding_entry in med_concept.get("coding", []):
                            system = coding_entry.get("system")
                            code = coding_entry.get("code")
                            if system and code:
                                current_tuple = (system, code)
                                if current_tuple in nsaid_steroid_codings: 
                                    if max_score < 1:
                                        matched_medications_details.append({
                                            "text": med_display_text,
                                            "detail": f"NSAID/Steroid: ({system}, {code})",
                                            "score_contribution": 1,
                                            "type": "NSAID/Steroid"
                                        })
                                    max_score = max(max_score, 1)

            if max_score == 2: 
                break # Exit loop once max score reached
    
    # Filter final matched details
    final_matched_med_details = []
    if max_score > 0:
        final_matched_med_details = [d for d in matched_medications_details if d.get('score_contribution', 0) > 0]
    
    app.logger.info(f"Final prefetch medication score: {max_score}. Matched medications: {len(final_matched_med_details)}")
    return max_score, final_matched_med_details


@app.route("/cds-services", methods=["GET"])
def cds_services():
     # ... (CDS Discovery endpoint remains the same) ...
    try:
        json_path = os.path.join(os.path.dirname(__file__), "cds-services.json")
        with open(json_path, "r", encoding="utf-8") as f: services_def = json.load(f)

        # Dynamically generate the service URL
        base_url = APP_BASE_URL.rstrip('/') # Use configured base URL
        for service in services_def.get("services", []):
            service_id = service.get('id')
            if service_id:
                service['url'] = f"{base_url}/cds-services/{service_id}"

        return jsonify(services_def)
    except FileNotFoundError:
        app.logger.error("cds-services.json not found")
        return jsonify({"error": "CDS Hooks service definition file not found"}), 404
    except Exception as e:
        app.logger.error(f"Error reading or processing cds-services.json: {e}", exc_info=True)
        return jsonify({"error": "Internal server error processing service definition"}), 500

# --- CDS Hooks Service Endpoint ---
# --- >> MODIFIED: Pass the text keywords config variable << ---
@app.route("/cds-services/bleeding_risk_calculator", methods=["POST"])
def bleeding_risk_calculator():
    """Handles the bleeding risk calculation CDS Hook request."""
    data = request.get_json();
    if not data: return jsonify({"error": "Request body must be JSON"}), 400
    app.logger.info("Received CDS Hooks request for bleeding_risk_calculator")

    prefetch_data = data.get("prefetch", {}); patient = prefetch_data.get("patient")
    if not patient or not isinstance(patient, dict):
        app.logger.warning("Patient data missing or invalid in prefetch.")
        return jsonify({"cards": []}) # Cannot calculate without patient

    patient_id = patient.get("id"); birth_date = patient.get("birthDate")
    if not patient_id:
        app.logger.warning("Patient ID missing in prefetch.")
        return jsonify({"cards": []})

    age = calculate_age(birth_date) if birth_date else None
    sex = patient.get("gender", "unknown")

    app.logger.info(f"Processing CDS Hook for patient {patient_id}, age={age}, sex={sex}")
    
    # Log prefetch data availability for debugging
    app.logger.info(f"Prefetch data keys: {list(prefetch_data.keys())}")
    app.logger.info(f"Conditions bundle entries: {len(prefetch_data.get('conditions', {}).get('entry', []))}")
    app.logger.info(f"Medications bundle entries: {len(prefetch_data.get('medications', {}).get('entry', []))}")

    # --- Get values using prefetch helpers ---
    hb_value = get_hemoglobin_from_prefetch(prefetch_data.get("hemoglobin"))
    platelet = get_platelet_from_prefetch(prefetch_data.get("platelet"))

    # --- MODIFIED: Use the new eGFR function with fallback logic ---
    egfr_value_prefetch = get_egfr_value_from_prefetch(prefetch_data, age, sex)
    # Log the final eGFR value used
    app.logger.info(f"Using eGFR value from prefetch: {egfr_value_prefetch}")
    # --- END MODIFIED ---

    # --- MODIFIED: Get condition points and details from prefetch ---
    condition_points, matched_conditions_details = get_condition_points_from_prefetch(
        prefetch_data.get("conditions"),
        CONDITION_CODES_SCORE_2_CONFIG,
        CONDITION_PREFIX_RULES_CONFIG,
        CONDITION_TEXT_KEYWORDS_SCORE_2_CONFIG, # Pass the new config variable
        CONDITION_VALUESET_RULES_CONFIG, # Pass the ValueSet rules config
        CONDITION_LOCAL_VALUESET_RULES_CONFIG, # Pass Local VS rules
        LOCAL_VALUESETS_CONFIG # Pass Local VS definitions
    )
    # --- END MODIFIED ---
    medication_points, matched_medications_details = get_medication_points_from_prefetch(
        prefetch_data.get("medications"),
        OAC_CODINGS_CONFIG,
        NSAID_STEROID_CODINGS_CONFIG
    )
    
    # Log the collected details for debugging
    app.logger.info(f"Condition points: {condition_points}, matched conditions: {len(matched_conditions_details)}")
    app.logger.info(f"Medication points: {medication_points}, matched medications: {len(matched_medications_details)}")
    if matched_conditions_details:
        app.logger.info(f"Matched conditions details: {[c.get('text', 'N/A') for c in matched_conditions_details]}")
    if matched_medications_details:
        app.logger.info(f"Matched medications details: {[m.get('text', 'N/A') for m in matched_medications_details]}")

    # --- Call calculate_bleeding_risk with the determined eGFR value ---
    # score, risk = calculate_bleeding_risk(
    #     age, egfr_value_prefetch, hb_value, sex, platelet, # Pass the final eGFR value
    #     condition_points, medication_points,
    #     RISK_PARAMS_CONFIG,
    #     FINAL_RISK_THRESHOLD_CONFIG
    # )

    # >>> MODIFIED: Integrate blood_transfusion_points from prefetch (or fallback to live query) <<<
    blood_transfusion_points_prefetch = 0 # Default if not prefetched or prefetch fails
    # Note: The original code didn't have a specific prefetch key for blood transfusions.
    # If you add one in cds-services.json like "bloodTransfusions": "Procedure?patient={{Patient.id}}&...",
    # you would use that key here: e.g., prefetch_data.get("bloodTransfusions")
    # For now, assuming it might not be prefetched or we need a similar structure to other labs.
    # If Procedure prefetch IS available, you'd need a get_blood_transfusion_points_from_prefetch function.
    # Lacking that, we might fall back or assume it's not available via simple prefetch for this example.

    # For this example, let's assume calculate_bleeding_risk expects it, and it might be 0 if not available from prefetch
    # OR if you implement a get_blood_transfusion_points_from_prefetch later.
    # As a placeholder, if we want to use the existing live query function if not in prefetch (though CDS Hooks aims to avoid this):
    # blood_transfusion_points, _ = get_blood_transfusion_points(patient_id) # This would be a live query
    # For a pure prefetch approach, this value should come from a prefetch helper or be 0.
    # We will assume it is 0 from prefetch for now or that calculate_bleeding_risk handles None if no points found.
    # Revisit this if you have a specific prefetch query for blood transfusions.

    bleeding_risk_result = calculate_bleeding_risk(
        age=age,
        egfr_value=egfr_value_prefetch,
        hemoglobin=hb_value,
        sex=sex,
        platelet=platelet,
        condition_points=condition_points,
        medication_points=medication_points,
        blood_transfusion_points=0,  # Placeholder: Assume 0 if not from prefetch or implement prefetch logic
        risk_params=RISK_PARAMS_CONFIG,
        final_threshold=FINAL_RISK_THRESHOLD_CONFIG
    )

    if not bleeding_risk_result:
        app.logger.error(f"Failed to calculate bleeding risk for patient {patient_id}.")
        return jsonify({"cards": []}) # Or a card with an error message

    score = bleeding_risk_result['score']
    risk = bleeding_risk_result['category']
    details = bleeding_risk_result['details']
    # --- End Calculation ---

    # --- Build CDS Card response ---
    cards = []
    card_summary = f"Bleeding Risk Assessment: {risk} (Score {score})"

    # Build detailed breakdown string using details dict for consistency
    card_detail = (
        f"Patient's bleeding risk assessment is **{risk}** (based on ARC-HBR standard factors scoring).\n\n"
        f"**Score Components:**\n"
        f"- Age: {details.get('age', 'Unknown')} years ({details.get('age_score_component', 0)} points)\n"
        f"- eGFR: {format(details.get('egfr_value'), '.1f') if details.get('egfr_value') is not None else 'Unknown'} mL/min ({details.get('egfr_score_component', 0)} points)\n"
        f"- Hb: {format(details.get('hemoglobin'), '.1f') if details.get('hemoglobin') is not None else 'Unknown'} g/dL (Gender: {details.get('sex', 'Unknown')}) ({details.get('hemoglobin_score_component', 0)} points)\n"
        f"- Platelet: {format(details.get('platelet'), '.1f') if details.get('platelet') is not None else 'Unknown'} k/uL ({details.get('platelet_score_component', 0)} points)\n"
        f"- Specific Diagnoses/Text (Condition): {details.get('condition_points', 0)} points\n"
        f"- Specific Medications (Medication): {details.get('medication_points', 0)} points\n"
        f"- Blood Transfusion (Procedure): {details.get('blood_transfusion_points', 0)} points\n\n"
    )

    # Add matched conditions details if any
    if matched_conditions_details:
        card_detail += "**High-Risk Diagnoses Found:**\n"
        for cond in matched_conditions_details:
            card_detail += f"- {cond.get('text', 'N/A')} ({cond.get('score_contribution', 0)} points) - {cond.get('detail', '')}\n"
        card_detail += "\n"

    # Add matched medications details if any
    if matched_medications_details:
        card_detail += "**High-Risk Medications Found:**\n"
        for med in matched_medications_details:
            card_detail += f"- {med.get('text', 'N/A')} ({med.get('score_contribution', 0)} points) - {med.get('detail', '')}\n"
        card_detail += "\n"

    card_detail += f"**Total Score: {score}**"

    indicator_type = "info" # Default
    if risk == FINAL_RISK_THRESHOLD_CONFIG.get('high_risk_label', 'high'):
        indicator_type = "critical"
    elif risk == FINAL_RISK_THRESHOLD_CONFIG.get('medium_risk_label', 'medium'):
        indicator_type = "warning"
    # Low risk remains info

    card = {
        "summary": card_summary,
        "indicator": indicator_type,
        "detail": card_detail,
        "source": { "label": "Bleeding Risk Calculator (FHIR0730 CDS Service)" }
    }

    # Add suggestions/links only if high risk
    high_risk_label_actual = FINAL_RISK_THRESHOLD_CONFIG.get('high_risk_label', 'high')
    if risk == high_risk_label_actual:
        card["suggestions"] = [
            { "label": "Review High Bleeding Risk (HBR) Management Guidelines",
              "actions": [ {
                  "type": "open-url",
                  "description": "Open ESC 2020 HBR Guidelines Reference (Eur Heart J)",
                  "url": "https://academic.oup.com/eurheartj/article/42/13/1289/5901694"
              } ]
            }
        ]

    cards.append(card)
    app.logger.info(f"Returning {len(cards)} CDS card(s) for patient {patient_id}.")
    # --- End Card Building ---
    return jsonify({"cards": cards})
# --- End CDS Hooks Endpoints ---


# --- NEW: Bleeding Risk Calculation UI Route ---
@app.route('/calculate_risk_ui')
@login_required
def calculate_risk_ui_page():
    patient_id = session.get('patient_id')
    if not patient_id:
        flash("No patient selected, unable to perform calculation.", "warning")
        return redirect(url_for('main_app_page'))

    app.logger.info(f"Initiating bleeding risk calculation for UI display for patient: {patient_id}")

    # 1. Fetch Patient Demographics (EMERGENCY MODE: Manual Only)
    app.logger.info("🚨 EMERGENCY MODE: Using manual patient data retrieval only")
    
    patient_resource = None
    age = None
    sex = "unknown"
    
    # Simple manual patient data retrieval
    try:
        patient_resource = get_patient_data()
        if patient_resource:
            app.logger.info(f"Patient resource fetched manually: {patient_resource.get('id')}")
        else:
            app.logger.warning("No patient resource returned from manual fetch")
    except Exception as e:
        app.logger.error(f"Error in manual patient data retrieval: {e}")
        patient_resource = None
    
    if patient_resource:
        birth_date = patient_resource.get("birthDate")
        age = calculate_age(birth_date) if birth_date else None
        sex = patient_resource.get("gender", "unknown")
        app.logger.info(f"Patient {patient_id}: Age={age}, Sex={sex}")
    else:
        flash(f"Unable to retrieve basic information for patient {patient_id}. Calculation may be incomplete.", "danger")

    # 2. Fetch Lab Values (EMERGENCY MODE: Manual Only)
    app.logger.info("🚨 EMERGENCY MODE: Using manual lab value retrieval only")
    
    # Simple manual lab value retrieval - no optimizations
    try:
        app.logger.info("Fetching hemoglobin...")
        hb_value = get_hemoglobin(patient_id)
    except Exception as e:
        app.logger.error(f"Error getting hemoglobin: {e}")
        hb_value = None
    
    try:
        app.logger.info("Fetching platelet...")
        platelet_value = get_platelet(patient_id)
    except Exception as e:
        app.logger.error(f"Error getting platelet: {e}")
        platelet_value = None
    
    try:
        app.logger.info("Fetching eGFR...")
        egfr_value = get_egfr_value(patient_id, age, sex)
    except Exception as e:
        app.logger.error(f"Error getting eGFR: {e}")
        egfr_value = None

    app.logger.info(f"Patient {patient_id} Labs: Hb={hb_value}, Platelet={platelet_value}, eGFR={egfr_value}")

    # 3. Get Condition, Medication, and Blood Transfusion Points AND DETAILS
    condition_points, matched_conditions_details = get_condition_points( # MODIFIED to get details
        patient_id,
        CONDITION_CODES_SCORE_2_CONFIG,
        CONDITION_PREFIX_RULES_CONFIG,
        CONDITION_TEXT_KEYWORDS_SCORE_2_CONFIG,
        CONDITION_VALUESET_RULES_CONFIG,
        CONDITION_LOCAL_VALUESET_RULES_CONFIG, 
        LOCAL_VALUESETS_CONFIG
    )
    medication_points, matched_medications_details = get_medication_points( # MODIFIED to get details
        patient_id,
        OAC_CODINGS_CONFIG,
        NSAID_STEROID_CODINGS_CONFIG
    )
    blood_transfusion_points, matched_transfusions = get_blood_transfusion_points(patient_id)

    app.logger.info(f"Patient {patient_id} Points: Conditions={condition_points} (Details: {len(matched_conditions_details)}), Meds={medication_points} (Details: {len(matched_medications_details)}), Transfusions={blood_transfusion_points}")

    # 4. Calculate Bleeding Risk
    bleeding_risk_result = calculate_bleeding_risk(
        age=age,
        egfr_value=egfr_value,
        hemoglobin=hb_value,
        sex=sex,
        platelet=platelet_value,
        condition_points=condition_points, # Pass the score
        medication_points=medication_points, # Pass the score
        blood_transfusion_points=blood_transfusion_points,
        risk_params=RISK_PARAMS_CONFIG,
        final_threshold=FINAL_RISK_THRESHOLD_CONFIG
    )

    if not bleeding_risk_result:
        app.logger.error(f"Failed to calculate bleeding risk for patient {patient_id} for UI.")
        flash("Error occurred while calculating bleeding risk.", "danger")
        bleeding_risk_result = {}

    # Log performance metrics if available (Phase 2)
    if OPTIMIZATIONS_AVAILABLE and hasattr(fhirclient_optimizations, 'get_performance_summary'):
        try:
            perf_summary = fhirclient_optimizations.get_performance_summary()
            app.logger.info(f"Performance metrics: {perf_summary}")
        except Exception as e:
            app.logger.warning(f"Could not retrieve performance metrics: {e}")

    # Prepare data for template
    calculation_details = {
        'age': age,
        'sex': sex,
        'hb_value': hb_value,
        'platelet_value': platelet_value,
        'egfr_value': egfr_value,
        'condition_points': condition_points, # Score
        'medication_points': medication_points, # Score
        'blood_transfusion_points': blood_transfusion_points,
        'matched_transfusions': matched_transfusions,
        'matched_conditions': matched_conditions_details, # ADDED THIS LINE
        'matched_medications': matched_medications_details, # ADDED THIS LINE
        'risk_params': RISK_PARAMS_CONFIG, 
        'score': bleeding_risk_result.get('score'),
        'category': bleeding_risk_result.get('category'),
        'score_details': bleeding_risk_result.get('details', {}),
        'optimization_used': 'Manual (Emergency Mode)'  # Fixed optimization info
    }

    # Get the actual label used for high risk from config to pass to template
    # Default to 'high' if not specified, though your config has '高出血風險'
    actual_high_risk_label = FINAL_RISK_THRESHOLD_CONFIG.get('high_risk_label', 'high')
    app.logger.info(f"Passing high_risk_label_for_template: {actual_high_risk_label} to calculate_risk_ui.html")

    return render_template('calculate_risk_ui.html', 
                           title="Bleeding Risk Calculation Results", 
                           patient_id=patient_id,
                           calculation_details=calculation_details,
                           high_risk_label_for_template=actual_high_risk_label) # Pass the label
# --- END UI Route ---

# --- Import Performance Optimizer ---
try:
    from fhir_performance_optimizer import (
        global_optimizer, track_performance, get_performance_stats, cleanup_cache,
        FHIRPerformanceOptimizer
    )
    PERFORMANCE_OPTIMIZER_AVAILABLE = True
    app.logger.info("FHIR Performance Optimizer successfully imported")
except ImportError as e:
    PERFORMANCE_OPTIMIZER_AVAILABLE = False
    app.logger.warning(f"FHIR Performance Optimizer not available: {e}")
# --- End Performance Optimizer Import ---

# --- >> NEW: Performance monitoring routes << ---
@app.route('/performance')
@login_required
def performance_dashboard():
    """性能監控儀表板"""
    if not PERFORMANCE_OPTIMIZER_AVAILABLE:
        flash("性能監控模塊未啟用", "warning")
        return redirect(url_for('main_app_page'))
    
    stats = get_performance_stats()
    return render_template('performance_dashboard.html', 
                           title="性能監控儀表板", 
                           stats=stats)

@app.route('/api/performance-stats')
@login_required
def api_performance_stats():
    """API: 獲取性能統計數據"""
    if not PERFORMANCE_OPTIMIZER_AVAILABLE:
        return jsonify({"error": "Performance optimizer not available"}), 503
    
    stats = get_performance_stats()
    return jsonify(stats)

@app.route('/api/clear-cache', methods=['POST'])
@login_required
def api_clear_cache():
    """API: 清理緩存"""
    if not PERFORMANCE_OPTIMIZER_AVAILABLE:
        return jsonify({"error": "Performance optimizer not available"}), 503
    
    try:
        cleared_count = cleanup_cache()
        app.logger.info(f"Cache cleared by user {current_user.id}, {cleared_count} entries removed")
        return jsonify({
            "success": True,
            "cleared_count": cleared_count,
            "message": f"Successfully cleared {cleared_count} cache entries"
        })
    except Exception as e:
        app.logger.error(f"Error clearing cache: {e}")
        return jsonify({"error": str(e)}), 500

# --- NEW: Optimized FHIR helper functions ---
if PERFORMANCE_OPTIMIZER_AVAILABLE:
    
    @track_performance("get_patient_data_optimized", "Patient")
    def get_patient_data_optimized():
        """優化的病患數據獲取函數"""
        return get_patient_data()
    
    @track_performance("get_observation_optimized", "Observation")
    def get_observation_optimized(patient_id, loinc_code):
        """優化的觀察值獲取函數"""
        return get_observation(patient_id, loinc_code)
    
    @track_performance("get_comprehensive_patient_data", "Patient")
    def get_comprehensive_patient_data_optimized(patient_id):
        """使用批量處理獲取完整病患數據"""
        fhir_server = _get_fhir_server_url()
        headers = _get_fhir_request_headers()
        
        if not fhir_server or not headers:
            app.logger.error("Cannot get comprehensive patient data: missing FHIR server or headers")
            return None
        
        return global_optimizer.get_comprehensive_patient_data(fhir_server, headers, patient_id)
    
    @track_performance("calculate_bleeding_risk_optimized", "Risk")
    def calculate_bleeding_risk_optimized(**kwargs):
        """優化的出血風險計算"""
        return calculate_bleeding_risk(**kwargs)

# --- Modified: Enhanced calculate_risk_ui_page with performance optimization ---

# --- Main Execution ---
if __name__ == "__main__":
    app.logger.info("Starting application setup in __main__...") # NEW LOG
    # Ensure templates directory exists
    if not os.path.exists("templates"):
        os.makedirs("templates")
        app.logger.info("Created 'templates' directory.") # NEW LOG
    else:
        app.logger.info("'templates' directory already exists.") # NEW LOG
    
    # Create dummy HTML files if they don't exist for basic functionality
    # layout.html
    if not os.path.exists("templates/layout.html"):
        with open("templates/layout.html", "w", encoding="utf-8") as f:
            f.write("""<!DOCTYPE html>
<html lang=\"zh-TW\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>{{ title }} - SMART FHIR App</title>
    <link rel=\"stylesheet\" href=\"https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css\">
    <style>
        body { padding-top: 5rem; }
        .flash-messages .alert { margin-bottom: 1rem; }
    </style>
</head>
<body>
    <nav class=\"navbar navbar-expand-md navbar-dark bg-dark fixed-top\">
        <a class=\"navbar-brand\" href=\"{{ url_for('index') }}\">FHIR App</a>
        <button class=\"navbar-toggler\" type=\"button\" data-toggle=\"collapse\" data-target=\"#navbarsExampleDefault\" aria-controls=\"navbarsExampleDefault\" aria-expanded=\"false\" aria-label=\"Toggle navigation\">
            <span class=\"navbar-toggler-icon\"></span>
        </button>
        <div class=\"collapse navbar-collapse\" id=\"navbarsExampleDefault\">
            <ul class=\"navbar-nav mr-auto\">
                <li class=\"nav-item\"><a class=\"nav-link\" href=\"{{ url_for('index') }}\">首頁</a></li>
                {% if current_user.is_authenticated %}
                <li class=\"nav-item\"><a class=\"nav-link\" href=\"{{ url_for('main_app_page') }}\">主應用</a></li>
                {% endif %}
            </ul>
            <ul class=\"navbar-nav ml-auto\">
                {% if current_user.is_authenticated %}
                    <li class=\"nav-item\"><span class=\"navbar-text\">已登入：{{ current_user.name }} | </span></li>
                    <li class=\"nav-item\"><a class=\"nav-link\" href=\"{{ url_for('logout') }}\">登出</a></li>
                {% else %}
                    <!-- <li class=\"nav-item\"><a class=\"nav-link\" href=\"#\">登入 (EHR Launch)</a></li> -->
                {% endif %}
            </ul>
        </div>
    </nav>

    <main role=\"main\" class=\"container\">
        <div class=\"flash-messages\">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class=\"alert alert-{{ category }} alert-dismissible fade show\" role=\"alert\">
                            {{ message }}
                            <button type=\"button\" class=\"close\" data-dismiss=\"alert\" aria-label=\"Close\">
                                <span aria-hidden=\"true\">&times;</span>
                            </button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        {% block content %}{% endblock %}
    </main>

    <script src=\"https://code.jquery.com/jquery-3.5.1.slim.min.js\"></script>
    <script src=\"https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.3/dist/umd/popper.min.js\"></script>
    <script src=\"https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js\"></script>
</body>
</html>""")
        app.logger.info("Created 'templates/layout.html'.") # NEW LOG

    # index.html
    if not os.path.exists("templates/index.html"):
        with open("templates/index.html", "w", encoding="utf-8") as f:
            f.write("""{% extends "layout.html" %}
{% block content %}
    <div class=\"starter-template\">
        <h1>{{ title }}</h1>
        <p class=\"lead\">歡迎使用此 SMART on FHIR 應用程式。<br>
            請透過您的電子病歷 (EHR) 系統啟動此應用程式以進行病患相關操作。
        </p>
        {% if not current_user.is_authenticated %}
        <p>如果您正在進行開發且想要測試，您可以使用 SMART Health IT Sandbox 進行測試：</p>
        <div class=\"row\">
            <div class=\"col-md-6\">
                <div class=\"card mb-4\">
                    <div class=\"card-header\">
                        <h5 class=\"mb-0\">SMART Health IT R4 Sandbox</h5>
                    </div>
                    <div class=\"card-body\">
                        <p>使用 SMART Health IT R4 Sandbox 進行測試：</p>
                        <a href=\"https://launch.smarthealthit.org/launcher?iss=https://launch.smarthealthit.org/v/r4/fhir&launch=eyJhIjoiMSJ9\" 
                           class=\"btn btn-primary\">
                            從 SMART R4 Sandbox 啟動
                        </a>
                        <p class=\"mt-2 small text-muted\">這會帶您到 SMART Health IT 的啟動器頁面，您可以在那裡選擇病患和其他啟動選項。</p>
                    </div>
                </div>
            </div>
        </div>
        {% else %}
        <p>您已登入。 <a href=\"{{ url_for('main_app_page') }}\">前往主應用程式頁面</a></p>
        {% endif %}
    </div>
{% endblock %}""")
        app.logger.info("Created 'templates/index.html'.") # NEW LOG

    # main_app.html
    if not os.path.exists("templates/main_app.html"):
        with open("templates/main_app.html", "w", encoding="utf-8") as f:
            f.write("""{% extends "layout.html" %}
{% block content %}
    <h2>{{ title }}</h2>
    {% if current_user.is_authenticated %}
        <p>歡迎, <strong>{{ current_user.name or '使用者' }}</strong>!</p> {# Default to '使用者' if name is None #}
        <p>Email: {{ current_user.email or '未提供' }}</p>
        <p>FHIR User URL: {{ current_user.fhir_user_url or '未提供' }}</p>
        
        {% if session.patient_id %}
            <p>目前病患 ID: <strong>{{ session.patient_id }}</strong></p>
            <p>病患姓名: <strong>{{ patient_name_display or '未提供' }}</strong></p> {# Use the new patient_name_display variable #}
            
            {% if patient_data and patient_data.id %}
                <h4>病患資訊 (範例 FHIR Resource):</h4>
                <pre>{{ patient_data | tojson(indent=2) }}</pre>
            {% elif patient_data %}
                 <h4>病患資訊 (範例):</h4>
                 <pre>{{ patient_data | tojson(indent=2) }}</pre>
            {% endif %}
            <a href="{{ url_for('calculate_risk_ui_page') }}" class="btn btn-info mt-2">計算此病患的出血風險</a>
            {% if session.get('fhir_server_url') %}
                <a href="https://launch.smarthealthit.org/launcher?iss={{ session.get('fhir_server_url') }}" class="btn btn-secondary mt-2 ml-2">返回EHR選擇其他病患</a>
            {% endif %}
        {% else %}
            <div class="alert alert-info">目前沒有選定的病患情境。</div>
        {% endif %}
        
        <p class="mt-3">Access Token: <small>{{ session.access_token[:30] }}...</small> (僅顯示前30字元)</p>
        <p>FHIR Server URL: {{ session.fhir_server_url }}</p>
        <p>Granted Scopes: {{ session.scopes_granted }}</p>

        <h4>ID Token Claims (部分):</h4>
        <pre style="max-height: 200px; overflow-y: auto; background-color: #f8f9fa; padding: 10px; border-radius: 5px;">
        ID: {{ session.get('id_token_claims', {}).get('sub') }}
        Name: {{ session.get('id_token_claims', {}).get('name', session.get('id_token_claims', {}).get('profile_name'))}}
        Email: {{ session.get('id_token_claims', {}).get('email') }}
        fhirUser: {{ session.get('id_token_claims', {}).get('fhirUser', session.get('id_token_claims', {}).get('profile')) }}
        Exp: {{ human_readable_time(session.get('id_token_claims', {}).get('exp')) }}
        </pre>
        
    {% else %}
        <p>請登入以查看此頁面。</p>
    {% endif %}

    <!-- 您的應用程式主要內容將會放在這裡 -->
    <!-- 例如，如果這是一個UI應用程式，可以在這裡呼叫計算邏輯 -->

{% endblock %}

{% macro human_readable_time(timestamp) -%}
    {{ datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'N/A' }}
{%- endmacro %}
""")
        app.logger.info("Created 'templates/main_app.html'.") # NEW LOG

    # calculate_risk_ui.html (NEW)
    if not os.path.exists("templates/calculate_risk_ui.html"):
        with open("templates/calculate_risk_ui.html", "w", encoding="utf-8") as f:
            f.write("""{% extends "layout.html" %}
{% block content %}
    <h2>{{ title }} - 病患 ID: {{ patient_id }}</h2>

    {% if calculation_details and calculation_details.category %}
        <div class="alert alert-{% if calculation_details.category == high_risk_label_for_template %}danger{% elif calculation_details.category == 'medium' %}warning{% else %}info{% endif %}" role="alert">
            <h4>出血風險等級: <span style="text-transform: capitalize;">{{ calculation_details.category }}</span> (總分: {{ calculation_details.score }})</h4>
        </div>

        <h3>計算細節:</h3>
        <table class="table table-bordered table-sm">
            <tbody>
                <tr><th>年齡:</th><td>{{ calculation_details.age if calculation_details.age is not none else '未知' }}</td></tr>
                <tr><th>性別:</th><td>{{ calculation_details.sex if calculation_details.sex else '未知' }}</td></tr>
                <tr><th>Hb (g/dL):</th><td>{{ "%.1f" | format(calculation_details.hb_value) if calculation_details.hb_value is not none else '未測量或未知' }}</td></tr>
                <tr><th>血小板 (k/uL):</th><td>{{ "%.0f" | format(calculation_details.platelet_value) if calculation_details.platelet_value is not none else '未測量或未知' }}</td></tr>
                <tr><th>eGFR (mL/min):</th><td>{{ "%.0f" | format(calculation_details.egfr_value) if calculation_details.egfr_value is not none else '未測量或未知' }}</td></tr>
                <tr><th>特定診斷/文字點數:</th><td>{{ calculation_details.condition_points }}</td></tr>
                <tr><th>特定用藥點數:</th><td>{{ calculation_details.medication_points }}</td></tr>
                <tr><th>輸血點數:</th><td>{{ calculation_details.blood_transfusion_points }}</td></tr>
            </tbody>
        </table>

        {% if calculation_details.matched_transfusions %}
            <h5>符合條件的輸血記錄 (過去12個月內):</h5>
            <ul>
            {% for trans in calculation_details.matched_transfusions %}
                <li>{{ trans.text }} ({{ trans.date[:10] }}) - 原因: {{ trans.reason }}</li>
            {% endfor %}
            </ul>
        {% endif %}

        <h4>原始評分項目 (來自設定檔):</h4>
        <pre style="max-height: 200px; overflow-y: auto; background-color: #f8f9fa; padding: 10px; border-radius: 5px;">{{ calculation_details.score_details | tojson(indent=2) }}</pre>

        {# NEW: Conditional link for high risk guideline image #}
        {% if calculation_details.category == high_risk_label_for_template %}
            <div class="mt-3">
                <a href="{{ url_for('static', filename='images/HBR_guideline.jpg') }}" target="_blank" class="btn btn-danger">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-exclamation-triangle-fill" viewBox="0 0 16 16" style="margin-right: 5px;">
                        <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                    </svg>
                    查閱高出血風險(HBR)處置建議指引圖示
                </a>
            </div>
        {% endif %}

    {% else %}
        <div class="alert alert-warning" role="alert">
            無法計算或顯示出血風險。請檢查資料是否完整或稍後再試。
        </div>
    {% endif %}

    <a href="{{ url_for('main_app_page') }}" class="btn btn-secondary mt-3">返回主應用頁面</a>
    {% if session.get('fhir_server_url') %}
        <a href="https://launch.smarthealthit.org/launcher?iss={{ session.get('fhir_server_url') }}" class="btn btn-outline-secondary mt-3 ml-2">返回EHR選擇其他病患</a>
    {% endif %}
{% endblock %}
""")
        app.logger.info("Created 'templates/calculate_risk_ui.html'.") # NEW LOG

    app.jinja_env.globals['datetime'] = datetime # Make datetime available in templates
    app.jinja_env.globals['isinstance'] = isinstance
    app.jinja_env.globals['get_human_name_text'] = get_human_name_text


    # Remember to install PyJWT: pip install "PyJWT[crypto]"
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
# --- End Main Execution ---
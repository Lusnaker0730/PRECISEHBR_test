import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
from fhirclient import client
import fhir_data_service
from dotenv import load_dotenv
import base64
import hashlib
import re
from functools import wraps
import requests
from urllib.parse import urlparse
from flask_wtf.csrf import CSRFProtect

# --- Google Secret Manager Helper ---
# Import the Secret Manager client library.
try:
    from google.cloud import secretmanager
    HAS_SECRET_MANAGER = True
except ImportError:
    HAS_SECRET_MANAGER = False

def get_secret(env_var, default=None):
    """
    Retrieves a secret from environment variables or Google Secret Manager.
    If the value of the env_var looks like a GCP secret path, it fetches it.
    Otherwise, it returns the environment variable's value directly.
    """
    value = os.environ.get(env_var)
    if not value:
        return default

    # Check if the value is a GCP secret resource name
    if HAS_SECRET_MANAGER and value.startswith('projects/'):
        resolved_value = value
        try:
            # Handle placeholder for project ID in GAE environment
            if '${PROJECT_ID}' in resolved_value:
                gcp_project = os.environ.get('GOOGLE_CLOUD_PROJECT')
                if not gcp_project:
                    app.logger.error("GOOGLE_CLOUD_PROJECT env var not set, cannot resolve secret path.")
                    return default
                resolved_value = resolved_value.replace('${PROJECT_ID}', gcp_project)

            client = secretmanager.SecretManagerServiceClient()
            response = client.access_secret_version(name=resolved_value)
            return response.payload.data.decode('UTF-8')
        except Exception as e:
            app.logger.error(f"Failed to access secret for {env_var} at path '{resolved_value}'. Error: {e}")
            return default
    
    return value

# Import the blueprint
from tradeoff_analysis_routes import tradeoff_bp
from flask_talisman import Talisman

# --- Constants for Cerner ---
# This is now a more generic check for any Cerner domain.
CERNER_DOMAIN = 'cerner.com'

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.DEBUG)

# Environment variables are now fetched using our helper function
CLIENT_ID = get_secret('SMART_CLIENT_ID')
REDIRECT_URI = get_secret('SMART_REDIRECT_URI')
CLIENT_SECRET = get_secret('SMART_CLIENT_SECRET')
SMART_SCOPES = get_secret('SMART_SCOPES', 'openid fhirUser launch/patient patient/*.read')

if not CLIENT_ID or not REDIRECT_URI:
    app.logger.error("FATAL: SMART_CLIENT_ID and SMART_REDIRECT_URI must be set.")

# --- Helper Functions & Decorators ---

def is_session_valid():
    required_keys = ['server', 'token', 'client_id']
    fhir_data = session.get('fhir_data')
    return bool(fhir_data and all(key in fhir_data for key in required_keys))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_session_valid():
            app.logger.warning(f"Access to '{request.path}' denied. No valid session.")
            if request.path.startswith('/api/'):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def render_error_page(title="Error", message="An unexpected error has occurred."):
    app.logger.error(f"Rendering error page: {title} - {message}")
    return render_template('error.html', error_title=title, error_message=message), 500

# --- API Endpoints ---

@app.route('/api/calculate_risk', methods=['POST'])
@login_required
def calculate_risk_api():
    """API endpoint for risk score calculation."""
    try:
        data = request.get_json()
        if not data or 'patientId' not in data:
            return jsonify({'error': 'Patient ID is required.'}), 400
        patient_id = data['patientId']
        fhir_session_data = session['fhir_data']
        raw_data, error = fhir_data_service.get_fhir_data(
            fhir_server_url=fhir_session_data.get('server'),
            access_token=fhir_session_data.get('token'),
            patient_id=patient_id,
            client_id=fhir_session_data.get('client_id')
        )
        if error:
            raise Exception(f"FHIR data service failed: {error}")
        
        # Explicitly check if the patient data is missing after the call
        if not raw_data or not raw_data.get('patient'):
            raise Exception("Patient data could not be retrieved from FHIR server.")

        demographics = fhir_data_service.get_patient_demographics(raw_data.get('patient'))
        score_components, total_score = fhir_data_service.calculate_precise_hbr_score(raw_data, demographics)
        display_info = fhir_data_service.get_precise_hbr_display_info(total_score)
        final_response = {
            "patient_info": {"patient_id": patient_id, **demographics},
            "total_score": total_score,
            "risk_level": display_info.get('full_label'),
            "recommendation": display_info.get('recommendation'),
            "score_components": score_components
        }
        return jsonify(final_response)
    except Exception as e:
        app.logger.error(f"Error in calculate_risk_api: {str(e)}", exc_info=True)
        if "FHIR server is down" in str(e):
            return jsonify({'error': 'FHIR data service is unavailable.', 'details': str(e)}), 503
        return jsonify({'error': 'An internal server error occurred.'}), 500

@app.route('/api/exchange-code', methods=['POST'])
def exchange_code():
    """API to exchange authorization code for an access token."""
    try:
        data = request.get_json()
        code = data.get('code')
        if not code:
            return jsonify({"error": "Authorization code is missing."}), 400
        launch_params = session.get('launch_params')
        if not launch_params:
            return jsonify({"error": "Launch context not found in session."}), 400
        token_url = launch_params['token_url']
        code_verifier = launch_params['code_verifier']
        token_params = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'code_verifier': code_verifier
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
        if CLIENT_SECRET:
            auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            headers['Authorization'] = f"Basic {auth_b64}"
            token_params.pop('client_id', None)
        response = requests.post(token_url, data=token_params, headers=headers, timeout=15)
        response.raise_for_status()
        token_response = response.json()
        app.logger.info(f"Received token response: {token_response}")
        session['fhir_data'] = {
            'token': token_response.get('access_token'),
            'patient': token_response.get('patient'),
            'server': launch_params.get('iss'),
            'client_id': CLIENT_ID,
            'token_type': token_response.get('token_type', 'Bearer'),
            'expires_in': token_response.get('expires_in'),
            'scope': token_response.get('scope'),
            'refresh_token': token_response.get('refresh_token')
        }
        if 'patient' in token_response:
            session['patient_id'] = token_response['patient']
        return jsonify({"status": "ok", "redirect_url": url_for('main_page')})
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"Token exchange failed: {e.response.status_code} {e.response.text}")
        return jsonify({"error": "Failed to exchange code for token.", "details": e.response.text}), e.response.status_code
    except Exception as e:
        app.logger.error(f"Unexpected error during token exchange: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

# --- Frontend Routes ---

@app.route('/')
def index():
    if is_session_valid():
        return redirect(url_for('main_page'))
    return redirect(url_for('standalone_launch_page'))

@app.route('/standalone')
def standalone_launch_page():
    return render_template('standalone_launch.html')

@app.route('/initiate-launch', methods=['POST'])
def initiate_launch():
    iss = request.form.get('iss')
    if not iss:
        return render_error_page("Launch Error", "'iss' (FHIR Server URL) is missing.")
    return redirect(url_for('launch', iss=iss))

@app.route('/docs')
def docs_page():
    """Renders the documentation page."""
    return render_template('docs.html')

@app.route('/launch')
def launch():
    """SMART on FHIR launch sequence."""
    try:
        iss = request.args.get('iss')
        if not iss:
            return render_error_page("Launch Error", "Required 'iss' parameter is missing.")

        auth_url = None
        token_url = None

        # Cerner's sandbox environments (like fhir-ehr-code.cerner.com) may not
        # support .well-known/smart-configuration. We will manually provide the
        # endpoints if the iss domain is from Cerner, based on their /metadata response.
        # if CERNER_DOMAIN in iss:
        #     app.logger.info(f"Cerner domain detected in ISS '{iss}'. Using hardcoded configuration based on metadata.")
            
        #     # Extract tenant_id and hostname from the ISS URL
        #     tenant_match = re.search(r'/r4/([a-f0-9\-]+)', iss)
        #     parsed_iss = urlparse(iss)
        #     iss_hostname = parsed_iss.hostname

        #     if not tenant_match or not iss_hostname:
        #         return render_error_page("Configuration Error", "Could not extract tenant ID or hostname from Cerner ISS URL.")
            
        #     tenant_id = tenant_match.group(1)
        #     app.logger.info(f"Extracted Cerner tenant ID: {tenant_id}, Hostname: {iss_hostname}")
            
        #     # Construct the v1 URLs as specified in the metadata for fhir-ehr-code.cerner.com
        #     auth_url = f'https://authorization.cerner.com/tenants/{tenant_id}/protocols/oauth2/profiles/smart-v1/personas/provider/authorize'
        #     token_url = f'https://authorization.cerner.com/tenants/{tenant_id}/hosts/{iss_hostname}/protocols/oauth2/profiles/smart-v1/token'
        # else:
        # For other EHRs, use the discovery mechanism.
        smart_config_url = f"{iss.rstrip('/')}/.well-known/smart-configuration"
        try:
            config_response = requests.get(smart_config_url, headers={'Accept': 'application/json'}, timeout=10)
            config_response.raise_for_status()
            smart_config = config_response.json()
            auth_url = smart_config.get('authorization_endpoint')
            token_url = smart_config.get('token_endpoint')
        except (requests.exceptions.RequestException, ValueError) as e:
            app.logger.warning(f"Failed to fetch .well-known/smart-configuration: {e}. Falling back.")
            # Fallback for systems that might not have .well-known but fhirclient can discover.
            try:
                fhir_client = client.FHIRClient(settings={'app_id': 'my_app', 'api_base': iss})
                auth_url = fhir_client.server.auth_settings.get('authorize_uri')
                token_url = fhir_client.server.auth_settings.get('token_uri')
            except Exception as conf_e:
                return render_error_page("FHIR Config Error", f"Could not retrieve auth endpoints from {iss}. Details: {conf_e}")

        if not auth_url or not token_url:
            return render_error_page("FHIR Config Error", f"Could not determine authorization and token endpoints for ISS: {iss}")

        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=').decode('utf-8')
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).rstrip(b'=').decode('utf-8')
        session['launch_params'] = {'iss': iss, 'token_url': token_url, 'code_verifier': code_verifier}
        auth_params = {
            'response_type': 'code',
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'scope': SMART_SCOPES,
            'state': base64.urlsafe_b64encode(os.urandom(16)).rstrip(b'=').decode('utf-8'),
            'aud': iss,
            'launch': request.args.get('launch'),
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        full_auth_url = f"{auth_url}?{requests.compat.urlencode(auth_params)}"
        return redirect(full_auth_url)
    except Exception as e:
        app.logger.error(f"Unexpected error in /launch: {e}", exc_info=True)
        return render_error_page("Launch Error", f"An unexpected error occurred during launch: {e}")

@app.route('/callback')
def callback():
    return render_template('callback.html')

@app.route('/main')
@login_required
def main_page():
    patient_id = session.get('patient_id', 'N/A')
    return render_template('main.html', patient_id=patient_id)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- Main Execution ---

# Enable security headers with Flask-Talisman
# The CSP allows loading styles/scripts from trusted CDNs.
csp = {
    'default-src': '\'self\'',
    'script-src': [
        '\'self\'',
        'cdn.jsdelivr.net',
        'cdnjs.cloudflare.com'  # Allow scripts from Cloudflare CDN
    ],
    'style-src': [
        '\'self\'',
        'cdn.jsdelivr.net',
        'cdnjs.cloudflare.com'
    ],
    'font-src': 'cdnjs.cloudflare.com',
    'img-src': ['\'self\'', 'data:']  # Allow images from self and data URIs
}
Talisman(app, content_security_policy=csp)

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

app.register_blueprint(tradeoff_bp)

if __name__ == '__main__':
    # Debug mode should be controlled by an environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() in ['true', '1', 't']
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=8080, debug=debug_mode)

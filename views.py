import logging
import os
from datetime import datetime
from functools import wraps
import jwt
import requests
from flask import (Blueprint, redirect, render_template, request,
                   session, jsonify, url_for)
from fhir_data_service import (
    get_fhir_data,
    calculate_risk_components,
    get_patient_demographics,
    get_precise_hbr_display_info
)

views_bp = Blueprint('views', __name__)


# --- Session Validation ---

def is_token_expired(token_data):
    """Check if access token is expired or will expire soon."""
    if not token_data:
        return True
    expires_in = token_data.get('expires_in')
    if not expires_in:
        return False
    # Check if token expires within next 5 minutes
    return expires_in <= 300


def session_required(f):
    """Decorator to protect routes that require a valid session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        required_keys = ['patient', 'server', 'token', 'client_id']
        fhir_data = session.get('fhir_data', {})
        missing_keys = [
            key for key in required_keys if key not in fhir_data or not fhir_data[key]]
        if missing_keys:
            logging.error(f"Session check failed. Missing keys: {missing_keys}")
            return redirect(url_for('views.logout'))
        # Simple token expiration check, can be enhanced with refresh logic later
        if is_token_expired(fhir_data):
            logging.warning("Token expired or close to expiring.")
            # For now, just log out. A real app would implement token refresh.
            return redirect(url_for('views.logout'))

        return f(*args, **kwargs)
    return decorated_function


# --- Main Application Routes ---

@views_bp.route('/')
def index():
    """Handles the root access and routes to the correct page."""
    if 'iss' in request.args:
        # Pass to the auth blueprint to handle the launch
        return redirect(url_for('auth.launch', **request.args))
    if 'code' in request.args and 'state' in request.args:
        # Pass to auth blueprint to handle the callback
        return redirect(url_for('auth.callback', **request.args))
    if session.get('fhir_data'):
        return redirect(url_for('views.main_page'))
    return render_template('standalone_launch.html')


@views_bp.route("/main")
@session_required
def main_page():
    """Renders the main risk calculation page."""
    fhir_data = session['fhir_data']
    patient_id = fhir_data['patient']
    return render_template("main.html", patient_id=patient_id)


@views_bp.route('/api/calculate_risk')
@session_required
def calculate_risk_api():
    """API endpoint to fetch FHIR data and calculate risk."""
    fhir_data = session['fhir_data']
    patient_id = fhir_data['patient']
    fhir_server_url = fhir_data['server']
    access_token = fhir_data['token']
    client_id = fhir_data['client_id']

    try:
        raw_data, error = get_fhir_data(
            fhir_server_url, access_token, patient_id, client_id)
        if error:
            return jsonify(
                {"error": "Failed to retrieve data from FHIR server.", "details": str(error)}), 500

        demographics = get_patient_demographics(raw_data.get("patient"))
        components, total_score = calculate_risk_components(
            raw_data, demographics)
        display_info = get_precise_hbr_display_info(total_score)
        risk_level = display_info['full_label']
        recommendation = display_info['recommendation']

        response_data = {
            "patient_info": demographics,
            "score_components": components,
            "total_score": total_score,
            "risk_level": risk_level,
            "recommendation": recommendation
        }
        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error in /api/calculate_risk: {e}", exc_info=True)
        return jsonify(
            {"error": f"An unexpected error occurred: {str(e)}"}), 500


@views_bp.route("/logout")
def logout():
    """Clears the session and shows a logged-out message."""
    session.clear()
    return render_template("error.html", error_info={
        'title': "Logged Out",
        'message': "You have been successfully logged out.",
        'suggestions': ["You can now close this window."]
    })


@views_bp.route('/health')
def health_check():
    """Health check endpoint for container orchestration."""
    return jsonify({"status": "ok"}), 200



def check_production_access():
    """Check if we are in production environment and deny access to test routes."""
    is_production = (
        os.environ.get('FLASK_ENV') == 'production' or 
        os.environ.get('PRODUCTION') == 'true' or
        os.environ.get('GAE_ENV') == 'standard'
    )
    if is_production:
        logging.warning("Security: Attempted access to test route in production.")
        return True
    return False


@views_bp.route('/test-mode')
def test_mode():
    """
    Development/Test mode - Direct access without OAuth for testing.
    WARNING: Only use this in development environments!
    """
    # Security Check
    if check_production_access():
        return render_template('error.html', error_info={
            'title': "Access Denied", 
            'message': "Test mode is not available in production environment."
        }), 403

    # Allow custom FHIR server from URL parameter, or use default
    test_fhir_server = request.args.get('server', 'http://10.29.99.18:9091/fhir')
    
    # Allow custom patient ID from URL parameter, or use default
    test_patient_id = request.args.get('patient_id', 'smart-1288992')
    
    # Create a mock session for testing
    session['fhir_data'] = {
        'token': 'test-mode-no-auth',
        'patient': test_patient_id,
        'server': test_fhir_server,
        'client_id': 'test-mode',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'scope': 'patient/*.read',
        'test_mode': True  # Flag to indicate this is test mode
    }
    session['patient_id'] = test_patient_id
    
    logging.info(f"Test mode activated - Server: {test_fhir_server}, Patient: {test_patient_id}")
    
    return redirect(url_for('views.main_page'))


@views_bp.route('/test-patients')
def test_patients():
    """
    Display a form to input Patient ID for the internal FHIR server.
    """
    # Security Check
    if check_production_access():
        return render_template('error.html', error_info={
            'title': "Access Denied", 
            'message': "Test page is not available in production environment."
        }), 403

    # Default to the internal server
    default_server = 'http://10.29.99.18:9091/fhir'
    fhir_server = request.args.get('server', default_server)
    
    # We no longer fetch the patient list as requested, just show the form
    return render_template('test_patients.html', 
                         patients=[], 
                         fhir_server=fhir_server,
                         error=None)


@views_bp.route('/demo-patient')
def demo_patient():
    """
    Quick demo: Directly launch with a specific internal patient ID.
    Target: Patient ID 87902 on internal server.
    """
    # Security Check
    if check_production_access():
        return render_template('error.html', error_info={
            'title': "Access Denied", 
            'message': "Demo mode is not available in production environment."
        }), 403

    # Configuration
    target_server = 'http://10.29.99.18:9091/fhir'
    target_patient_id = '87902'

    # Create a mock session
    session['fhir_data'] = {
        'token': 'demo-mode-no-auth',
        'patient': target_patient_id,
        'server': target_server,
        'client_id': 'demo-mode',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'scope': 'patient/*.read',
        'test_mode': True
    }
    session['patient_id'] = target_patient_id
    
    logging.info(f"Demo mode activated - Server: {target_server}, Patient: {target_patient_id}")
    
    # Redirect directly to the main calculation page
    return redirect(url_for('views.main_page'))


@views_bp.route('/test-patients-list')
def test_patients_list():
    """
    Fetch and display a paginated list of patients (pool of 50).
    Shows 10 patients per page with complete error handling.
    """
    # Security Check
    if check_production_access():
        return render_template('error.html', error_info={
            'title': "Access Denied", 
            'message': "Test page is not available in production environment."
        }), 403

    # Default to the internal server
    default_server = 'http://10.29.99.18:9091/fhir'
    fhir_server = request.args.get('server', default_server)
    
    patients = []
    error = None
    
    try:
        # Fetch 50 patients from FHIR server
        response = requests.get(
            f"{fhir_server}/Patient",
            params={'_count': 50}, 
            headers={'Accept': 'application/fhir+json'},
            timeout=10
        )
        
        if response.status_code == 200:
            bundle = response.json()
            
            if bundle.get('resourceType') == 'Bundle' and 'entry' in bundle:
                for entry in bundle['entry']:
                    patient = entry.get('resource', {})
                    if patient.get('resourceType') == 'Patient':
                        # Extract patient information
                        patient_id = patient.get('id', 'Unknown')
                        
                        # Get name
                        names = patient.get('name', [])
                        if names and len(names) > 0:
                            name_obj = names[0]
                            if name_obj.get('text'):
                                full_name = name_obj.get('text')
                            else:
                                given = ' '.join(name_obj.get('given', []))
                                family = name_obj.get('family', '')
                                full_name = f"{given} {family}".strip()
                        else:
                            full_name = 'Unknown Name'
                        
                        # Get other details
                        gender = patient.get('gender', 'Unknown')
                        birth_date = patient.get('birthDate', 'Unknown')
                        
                        patients.append({
                            'id': patient_id,
                            'name': full_name,
                            'gender': gender.capitalize() if gender else 'Unknown',
                            'birthDate': birth_date,
                            'description': f'{gender.capitalize() if gender else "Unknown"} patient'
                        })
            else:
                # No entries found
                pass
        else:
            error = f"Failed to fetch patients: HTTP {response.status_code}"
            
    except requests.exceptions.ConnectTimeout:
        error = "連線逾時：無法連接到測試伺服器。請確認您已連接到內部網路 (VPN) 或伺服器是否正常運作。"
        logging.warning(f"Connection timeout fetching patients from {fhir_server}")
    except requests.exceptions.ConnectionError:
        error = "連線失敗：無法建立連線。請檢查伺服器位址是否正確或防火牆設定。"
        logging.warning(f"Connection error fetching patients from {fhir_server}")
    except requests.exceptions.RequestException as e:
        error = f"連線錯誤：{str(e)}"
        logging.error(f"Error fetching patients from {fhir_server}: {e}")
    except Exception as e:
        error = f"處理數據時發生錯誤：{str(e)}"
        logging.error(f"Error processing patients: {e}", exc_info=True)
    
    return render_template('test_patients_list.html', 
                         patients=patients, 
                         fhir_server=fhir_server,
                         error=error)

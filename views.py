import logging
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
    get_precise_hbr_display_info,
    CDSS_CONFIG
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

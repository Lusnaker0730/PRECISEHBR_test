import json
import logging
import os

from flask import Blueprint, jsonify, request

from fhir_data_service import (
    get_patient_demographics,
    calculate_precise_hbr_score,
    get_precise_hbr_display_info
)

hooks_bp = Blueprint('hooks', __name__)


def check_high_bleeding_risk_medications(medications):
    """
    Check if patient is on medications that increase bleeding risk.
    """
    # This function contains detailed logic for identifying specific medications
    # based on RxNorm codes and common names.
    aspirin_codes = {'rxnorm': ['1191'], 'names': ['aspirin']}
    antiplatelet_agents = {
        'clopidogrel': {'rxnorm': ['32968'], 'names': ['clopidogrel', 'plavix']},
        'prasugrel': {'rxnorm': ['861634'], 'names': ['prasugrel', 'effient']},
        'ticagrelor': {'rxnorm': ['1116632'], 'names': ['ticagrelor', 'brilinta']}
    }
    oral_anticoagulants = {
        'warfarin': {'rxnorm': ['11289'], 'names': ['warfarin', 'coumadin']},
        'apixaban': {'rxnorm': ['1364430'], 'names': ['apixaban', 'eliquis']},
        'rivaroxaban': {'rxnorm': ['1114195'], 'names': ['rivaroxaban', 'xarelto']}
    }

    found_meds = {'aspirin': False, 'antiplatelet': None, 'anticoagulant': None}
    medication_details = []

    for med in medications:
        if not med or 'medicationCodeableConcept' not in med:
            continue
        med_concept = med['medicationCodeableConcept']
        med_name = med_concept.get('text', '').lower()
        med_codes = [c.get('code') for c in med_concept.get('coding', [])
                     if c.get('system') == 'http://www.nlm.nih.gov/research/umls/rxnorm']

        # Simplified check logic for brevity
        if any(c in aspirin_codes['rxnorm'] for c in med_codes) or any(n in med_name for n in aspirin_codes['names']):
            found_meds['aspirin'] = True
            medication_details.append({'name': 'Aspirin'})
            continue

        for agent, details in antiplatelet_agents.items():
            if any(c in details['rxnorm'] for c in med_codes) or any(n in med_name for n in details['names']):
                found_meds['antiplatelet'] = agent
                medication_details.append({'name': agent.title()})
                break

        for agent, details in oral_anticoagulants.items():
            if any(c in details['rxnorm'] for c in med_codes) or any(n in med_name for n in details['names']):
                found_meds['anticoagulant'] = agent
                medication_details.append({'name': agent.title()})
                break

    has_dapt = found_meds['aspirin'] and found_meds['antiplatelet']
    has_anticoagulant = found_meds['anticoagulant']
    return has_dapt or has_anticoagulant, medication_details


def create_precise_hbr_warning_card(
        patient_name,
        precise_hbr_score,
        risk_category,
        bleeding_risk_percentage,
        medications_found):
    """Create a CDS Hooks card for PRECISE-HBR high bleeding risk warning."""

    medication_list = ", ".join([med['name'] for med in medications_found])

    # Determine alert level based on risk category
    if risk_category == "Very HBR":
        indicator = "critical"
    elif risk_category == "HBR":
        indicator = "warning"
    else:
        indicator = "info"

    card = {
        "summary": f"{risk_category}: Patient score {precise_hbr_score} ({bleeding_risk_percentage}% 1-yr risk)",
        "detail": f"Patient on {medication_list} has a PRECISE-HBR score of {precise_hbr_score}. "
                  "Consider shorter DAPT duration and enhanced monitoring.",
        "indicator": indicator,
        "source": {
            "label": "PRECISE-HBR Bleeding Risk Calculator",
            "url": "https://www.precisehbr.com"
        },
        "suggestions": [
            {
                "label": "View Detailed Assessment",
                "actions": [
                    {
                        "type": "create",
                        "description": "Launch detailed PRECISE-HBR risk calculator",
                        "resource": {
                            "resourceType": "ServiceRequest",
                            "status": "draft",
                            "intent": "proposal",
                            "code": {"coding": [{"system": "http://loinc.org", "code": "LA-PRECISE-HBR"}]},
                            "subject": {"reference": f"Patient/{{{{context.patientId}}}}"}
                        }
                    }
                ]
            },
        ]
    }
    return card


@hooks_bp.route('/cds-services', methods=['GET'])
def cds_services_discovery():
    """CDS Hooks service discovery endpoint."""
    try:
        with open('cds-services.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        return jsonify(config_data)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Could not load cds-services.json: {e}")
        # Fallback config
        fallback_config = {
            "services": [
                {
                    "hook": "medication-prescribe",
                    "id": "precise_hbr_bleeding_risk_alert",
                    "title": "PRECISE-HBR High Bleeding Risk Alert",
                    "description": "Alert for patients with high bleeding risk (PRECISE-HBR >= 23)"
                }
            ]
        }
        return jsonify(fallback_config)


@hooks_bp.route('/cds-services/precise_hbr_bleeding_risk_alert', methods=['POST'])
def handle_precise_hbr_bleeding_risk_hook():
    """
    Shared handler for PRECISE-HBR high bleeding risk alerts.
    """
    try:
        hook_request = request.get_json()
        if not hook_request:
            return jsonify({"cards": []}), 400

        context = hook_request.get('context', {})
        prefetch = hook_request.get('prefetch', {})
        patient_id = context.get('patientId')
        if not patient_id:
            return jsonify({"cards": []})

        patient_data = prefetch.get('patient')
        patient_name = "Patient"
        if patient_data:
            name_data = patient_data.get('name', [{}])[0]
            given = " ".join(name_data.get('given', []))
            family = name_data.get('family', "")
            patient_name = f"{given} {family}".strip() or patient_id

        medications = prefetch.get('medications', {}).get('entry', [])
        medication_resources = [
            entry.get('resource') for entry in medications if entry.get('resource')]

        has_high_risk_meds, high_risk_medications = check_high_bleeding_risk_medications(
            medication_resources)

        if not has_high_risk_meds:
            return jsonify({"cards": []})

        raw_data = {
            'patient': patient_data,
            'HEMOGLOBIN': [entry['resource'] for entry in prefetch.get('hemoglobin', {}).get('entry', [])],
            'CREATININE': [entry['resource'] for entry in prefetch.get('creatinine', {}).get('entry', [])],
            'EGFR': [entry['resource'] for entry in prefetch.get('egfr', {}).get('entry', [])],
            'WBC': [entry['resource'] for entry in prefetch.get('wbc', {}).get('entry', [])],
            'conditions': [entry['resource'] for entry in prefetch.get('conditions', {}).get('entry', [])]
        }

        demographics = get_patient_demographics(patient_data)
        _, total_score = calculate_precise_hbr_score(
            raw_data, demographics)

        if total_score >= 23:
            risk_category, bleeding_risk_percentage = get_precise_hbr_display_info(
                total_score)
            warning_card = create_precise_hbr_warning_card(
                patient_name, total_score, risk_category,
                bleeding_risk_percentage, high_risk_medications
            )
            return jsonify({"cards": [warning_card]})
        else:
            return jsonify({"cards": []})

    except Exception as e:
        logging.error(
            f"Error in PRECISE-HBR CDS Hook: {e}",
            exc_info=True)
        return jsonify({"cards": []}), 500

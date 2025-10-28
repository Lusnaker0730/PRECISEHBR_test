"""
Tests for FHIR data service module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import fhir_data_service


def test_fetch_patient_data_success(mock_fhir_client, mock_patient_data):
    """Test successful patient data fetching."""
    with patch('fhir_data_service.Patient') as mock_patient:
        mock_patient.read.return_value = Mock(as_json=lambda: mock_patient_data)
        
        result = fhir_data_service.fetch_patient_data('test-patient-123', mock_fhir_client)
        
        assert result is not None
        # Patient.read should be called with patient ID and smart client
        mock_patient.read.assert_called_once()


def test_fetch_observations_success(mock_fhir_client):
    """Test successful observations fetching."""
    mock_bundle = MagicMock()
    mock_bundle.entry = []
    
    with patch('fhir_data_service.Observation') as mock_obs:
        mock_obs.where.return_value.perform_resources.return_value = []
        
        result = fhir_data_service.fetch_observations('test-patient-123', mock_fhir_client)
        
        assert result is not None
        assert isinstance(result, list)


def test_calculate_hbr_score_basic():
    """Test basic HBR score calculation."""
    # Test with empty criteria
    major_criteria = []
    minor_criteria = []
    
    result = fhir_data_service.calculate_hbr_score(major_criteria, minor_criteria)
    
    assert 'is_high_risk' in result
    assert 'major_count' in result
    assert 'minor_count' in result
    assert result['major_count'] == 0
    assert result['minor_count'] == 0


def test_calculate_hbr_score_high_risk():
    """Test HBR score calculation for high risk patient."""
    major_criteria = [
        {'id': 'age', 'met': True},
        {'id': 'bleeding', 'met': True}
    ]
    minor_criteria = [
        {'id': 'anemia', 'met': True}
    ]
    
    result = fhir_data_service.calculate_hbr_score(major_criteria, minor_criteria)
    
    assert result['major_count'] == 2
    assert result['minor_count'] == 1
    # High risk if ≥1 major OR ≥2 minor
    assert result['is_high_risk'] is True


def test_age_criterion_evaluation():
    """Test age criterion evaluation."""
    # Patient over 75 years old
    birth_date = '1940-01-01'
    
    result = fhir_data_service.evaluate_age_criterion(birth_date)
    
    assert result is not None
    assert 'met' in result
    assert result['met'] is True


def test_hemoglobin_criterion_evaluation():
    """Test hemoglobin criterion evaluation."""
    observations = [
        {
            'code': {'coding': [{'code': '718-7'}]},
            'valueQuantity': {'value': 10.5, 'unit': 'g/dL'}
        }
    ]
    
    result = fhir_data_service.evaluate_hemoglobin_criterion(observations)
    
    assert result is not None
    assert 'met' in result
    # Hemoglobin < 11 g/dL is a criterion
    assert result['met'] is True


def test_error_handling_invalid_patient():
    """Test error handling for invalid patient ID."""
    mock_client = MagicMock()
    
    with patch('fhir_data_service.Patient.read', side_effect=Exception("Patient not found")):
        result = fhir_data_service.fetch_patient_data('invalid-id', mock_client)
        
        # Should handle error gracefully
        assert result is None or isinstance(result, dict)


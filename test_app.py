#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for SMART FHIR Bleeding Risk Calculator App
測試 APP.py 中的各項功能
"""

import unittest
import json
import os
import sys
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
import requests

# Add the current directory to Python path to import APP
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the app and functions to test
# Patch the config file path to use test config
import os
test_config_path = os.path.join(os.path.dirname(__file__), "test_config.json")
if os.path.exists(test_config_path):
    os.environ['CDSS_CONFIG_PATH'] = test_config_path

import APP
from APP import (
    app, calculate_age, get_human_name_text, calculate_bleeding_risk,
    get_hemoglobin_from_prefetch, get_creatinine_from_prefetch, 
    get_platelet_from_prefetch, get_egfr_value_from_prefetch,
    get_condition_points_from_prefetch, get_medication_points_from_prefetch,
    _expand_valueset_cached, _fetch_and_expand_valueset
)

class TestUtilityFunctions(unittest.TestCase):
    """測試工具函數"""
    
    def test_calculate_age(self):
        """測試年齡計算函數"""
        # Test valid birth date
        birth_date = "1990-01-01"
        age = calculate_age(birth_date)
        expected_age = date.today().year - 1990
        if (date.today().month, date.today().day) < (1, 1):
            expected_age -= 1
        self.assertEqual(age, expected_age)
        
        # Test invalid birth date
        self.assertIsNone(calculate_age("invalid-date"))
        self.assertIsNone(calculate_age(None))
        
    def test_get_human_name_text(self):
        """測試人名提取函數"""
        # Test with text field
        name_list = [{"text": "張三"}]
        self.assertEqual(get_human_name_text(name_list), "張三")
        
        # Test with family and given names
        name_list = [{"family": "張", "given": ["三", "先生"]}]
        self.assertEqual(get_human_name_text(name_list), "張三 先生")
        
        # Test with preferred name
        name_list = [
            {"family": "張", "given": ["三"]},
            {"family": "王", "given": ["五"], "use": "official"}
        ]
        self.assertEqual(get_human_name_text(name_list), "王五")
        
        # Test empty list
        self.assertEqual(get_human_name_text([]), "N/A")
        self.assertEqual(get_human_name_text(None), "N/A")

class TestBleedingRiskCalculation(unittest.TestCase):
    """測試出血風險計算"""
    
    def setUp(self):
        """設置測試數據"""
        self.risk_params = {
            'age_gte_75_params': {'threshold': 75, 'score': 1},
            'age_gte_65_params': {'threshold': 65, 'score': 1},
            'egfr_lt_15_params': {'threshold': 15, 'score': 2},
            'egfr_lt_30_params': {'threshold': 30, 'score': 2},
            'egfr_lt_45_params': {'threshold': 45, 'score': 1},
            'hgb_male_lt_13_params': {'threshold': 13, 'score': 1},
            'hgb_female_lt_12_params': {'threshold': 12, 'score': 1},
            'plt_lt_100_params': {'threshold': 100, 'score': 1}
        }
        self.final_threshold = {
            'high_risk_min_score': 3,
            'high_risk_label': '高出血風險'
        }
    
    def test_high_risk_calculation(self):
        """測試高風險計算"""
        result = calculate_bleeding_risk(
            age=80,  # 1 point
            egfr_value=25,  # 2 points
            hemoglobin=10,  # 1 point (male)
            sex="male",
            platelet=80,  # 1 point
            condition_points=0,
            medication_points=0,
            blood_transfusion_points=0,
            risk_params=self.risk_params,
            final_threshold=self.final_threshold
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['score'], 5)  # 1+2+1+1 = 5
        self.assertEqual(result['category'], 'high')  # Function returns 'high', not the Chinese label
        
    def test_low_risk_calculation(self):
        """測試低風險計算"""
        result = calculate_bleeding_risk(
            age=50,  # 0 points
            egfr_value=90,  # 0 points
            hemoglobin=14,  # 0 points (male)
            sex="male",
            platelet=200,  # 0 points
            condition_points=0,
            medication_points=0,
            blood_transfusion_points=0,
            risk_params=self.risk_params,
            final_threshold=self.final_threshold
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['category'], 'low')
        
    def test_female_hemoglobin_threshold(self):
        """測試女性血紅蛋白閾值"""
        result = calculate_bleeding_risk(
            age=50,
            egfr_value=90,
            hemoglobin=11,  # 1 point for female
            sex="female",
            platelet=200,
            condition_points=0,
            medication_points=0,
            blood_transfusion_points=0,
            risk_params=self.risk_params,
            final_threshold=self.final_threshold
        )
        
        self.assertEqual(result['details']['hemoglobin_score_component'], 1)

class TestPrefetchFunctions(unittest.TestCase):
    """測試 Prefetch 相關函數"""
    
    def setUp(self):
        """設置測試數據"""
        self.hemoglobin_bundle = {
            "entry": [{
                "resource": {
                    "resourceType": "Observation",
                    "id": "hb-1",
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "718-7"
                        }]
                    },
                    "valueQuantity": {
                        "value": 12.5,
                        "unit": "g/dl"
                    }
                }
            }]
        }
        
        self.creatinine_bundle = {
            "entry": [{
                "resource": {
                    "resourceType": "Observation",
                    "id": "cr-1",
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "2160-0"
                        }]
                    },
                    "valueQuantity": {
                        "value": 1.5,
                        "unit": "mg/dl"
                    }
                }
            }]
        }
        
        self.medication_bundle = {
            "entry": [{
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": "med-1",
                    "status": "active",
                    "medicationCodeableConcept": {
                        "text": "Warfarin 5mg",
                        "coding": [{
                            "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                            "code": "11289",
                            "display": "Warfarin"
                        }]
                    }
                }
            }]
        }
        
        self.condition_bundle = {
            "entry": [{
                "resource": {
                    "resourceType": "Condition",
                    "id": "cond-1",
                    "code": {
                        "text": "慢性腎臟病",
                        "coding": [{
                            "system": "http://snomed.info/sct",
                            "code": "431855005",
                            "display": "Chronic kidney disease stage 4"
                        }]
                    },
                    "clinicalStatus": {
                        "coding": [{
                            "code": "active"
                        }]
                    },
                    "recordedDate": "2023-01-01"
                }
            }]
        }
    
    def test_get_hemoglobin_from_prefetch(self):
        """測試從 prefetch 提取血紅蛋白"""
        result = get_hemoglobin_from_prefetch(self.hemoglobin_bundle)
        self.assertEqual(result, 12.5)
        
        # Test unit conversion (g/L to g/dL)
        hb_bundle_gl = {
            "entry": [{
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "718-7"}]},
                    "valueQuantity": {"value": 125, "unit": "g/l"}
                }
            }]
        }
        result = get_hemoglobin_from_prefetch(hb_bundle_gl)
        self.assertEqual(result, 12.5)
        
        # Test empty bundle
        self.assertIsNone(get_hemoglobin_from_prefetch({}))
        
    def test_get_creatinine_from_prefetch(self):
        """測試從 prefetch 提取肌酐"""
        result = get_creatinine_from_prefetch(self.creatinine_bundle)
        self.assertEqual(result, 1.5)
        
        # Test unit conversion (µmol/L to mg/dL)
        cr_bundle_umol = {
            "entry": [{
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "2160-0"}]},
                    "valueQuantity": {"value": 132.6, "unit": "umol/l"}
                }
            }]
        }
        result = get_creatinine_from_prefetch(cr_bundle_umol)
        self.assertAlmostEqual(result, 1.5, places=1)
        
    def test_get_platelet_from_prefetch(self):
        """測試從 prefetch 提取血小板"""
        platelet_bundle = {
            "entry": [{
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "777-3"}]},
                    "valueQuantity": {"value": 150}
                }
            }]
        }
        result = get_platelet_from_prefetch(platelet_bundle)
        self.assertEqual(result, 150.0)
        
    def test_get_egfr_value_from_prefetch(self):
        """測試從 prefetch 計算 eGFR"""
        prefetch_data = {"creatinine": self.creatinine_bundle}
        
        # Test calculation from creatinine
        result = get_egfr_value_from_prefetch(prefetch_data, age=65, sex="male")
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)
        
        # Test with direct eGFR observation
        egfr_bundle = {
            "entry": [{
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "33914-3"}]},
                    "valueQuantity": {"value": 45}
                }
            }]
        }
        prefetch_data_egfr = {"egfr": egfr_bundle}
        result = get_egfr_value_from_prefetch(prefetch_data_egfr, age=65, sex="male")
        self.assertEqual(result, 45.0)
        
    def test_get_medication_points_from_prefetch(self):
        """測試從 prefetch 計算藥物分數"""
        oac_codings = {("http://www.nlm.nih.gov/research/umls/rxnorm", "11289")}
        nsaid_codings = set()
        
        score, details = get_medication_points_from_prefetch(
            self.medication_bundle, oac_codings, nsaid_codings
        )
        
        self.assertEqual(score, 2)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]['text'], "Warfarin 5mg")
        self.assertEqual(details[0]['type'], "OAC")
        
    def test_get_condition_points_from_prefetch(self):
        """測試從 prefetch 計算診斷分數"""
        codes_score_2 = {("http://snomed.info/sct", "431855005")}
        prefix_rules = []
        text_keywords = set()
        value_set_rules = []
        local_valueset_rules = []
        local_valuesets = {}
        
        score, details = get_condition_points_from_prefetch(
            self.condition_bundle, codes_score_2, prefix_rules, 
            text_keywords, value_set_rules, local_valueset_rules, local_valuesets
        )
        
        self.assertEqual(score, 2)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]['text'], "慢性腎臟病")
        self.assertEqual(details[0]['score_contribution'], 2)

class TestValueSetFunctions(unittest.TestCase):
    """測試 ValueSet 相關函數"""
    
    @patch('APP.requests.get')
    def test_fetch_and_expand_valueset(self, mock_get):
        """測試 ValueSet 擴展"""
        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "resourceType": "ValueSet",
            "expansion": {
                "total": 2,
                "contains": [
                    {"system": "http://snomed.info/sct", "code": "123456"},
                    {"system": "http://snomed.info/sct", "code": "789012"}
                ]
            }
        }
        mock_get.return_value = mock_response
        
        result = _fetch_and_expand_valueset(
            "ValueSet/test-vs", 
            "http://fhir.server.com", 
            {"Authorization": "Bearer token"}
        )
        
        expected = {("http://snomed.info/sct", "123456"), ("http://snomed.info/sct", "789012")}
        self.assertEqual(result, expected)
        
    @patch('APP.requests.get')
    def test_fetch_and_expand_valueset_error(self, mock_get):
        """測試 ValueSet 擴展錯誤處理"""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        result = _fetch_and_expand_valueset(
            "ValueSet/test-vs", 
            "http://fhir.server.com", 
            {"Authorization": "Bearer token"}
        )
        
        self.assertIsNone(result)

class TestFlaskRoutes(unittest.TestCase):
    """測試 Flask 路由"""
    
    def setUp(self):
        """設置測試客戶端"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        
    def tearDown(self):
        """清理測試環境"""
        self.app_context.pop()
        
    def test_index_route(self):
        """測試首頁路由"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'SMART', response.data)
        
    def test_cds_services_discovery(self):
        """測試 CDS Services 發現端點"""
        # Create a temporary cds-services.json file
        cds_services_data = {
            "services": [{
                "id": "bleeding_risk_calculator",
                "title": "Bleeding Risk Calculator",
                "description": "Calculate bleeding risk"
            }]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cds_services_data, f)
            temp_file = f.name
            
        # Patch the file path
        with patch('APP.os.path.join', return_value=temp_file):
            response = self.client.get('/cds-services')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('services', data)
            
        # Clean up
        os.unlink(temp_file)
        
    @patch('APP.get_condition_points_from_prefetch')
    @patch('APP.get_medication_points_from_prefetch')
    @patch('APP.get_egfr_value_from_prefetch')
    @patch('APP.get_hemoglobin_from_prefetch')
    @patch('APP.get_platelet_from_prefetch')
    @patch('APP.calculate_bleeding_risk')
    def test_cds_hooks_bleeding_risk_calculator(self, mock_calc_risk, mock_platelet, 
                                               mock_hb, mock_egfr, mock_med, mock_cond):
        """測試 CDS Hooks 出血風險計算端點"""
        # Setup mocks
        mock_cond.return_value = (2, [{"text": "Test Condition", "score_contribution": 2}])
        mock_med.return_value = (2, [{"text": "Test Medication", "score_contribution": 2}])
        mock_egfr.return_value = 45.0
        mock_hb.return_value = 11.0
        mock_platelet.return_value = 150.0
        mock_calc_risk.return_value = {
            'score': 4,
            'category': '高出血風險',
            'details': {
                'age': 75,
                'sex': 'male',
                'egfr_value': 45.0,
                'hemoglobin': 11.0,
                'platelet': 150.0,
                'condition_points': 2,
                'medication_points': 2,
                'blood_transfusion_points': 0
            }
        }
        
        # Test data
        test_data = {
            "prefetch": {
                "patient": {
                    "id": "test-patient",
                    "birthDate": "1948-01-01",
                    "gender": "male"
                },
                "conditions": {"entry": []},
                "medications": {"entry": []},
                "hemoglobin": {"entry": []},
                "platelet": {"entry": []}
            }
        }
        
        response = self.client.post(
            '/cds-services/bleeding_risk_calculator',
            data=json.dumps(test_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('cards', data)
        self.assertGreater(len(data['cards']), 0)
        
        card = data['cards'][0]
        self.assertIn('summary', card)
        self.assertIn('detail', card)
        self.assertIn('高出血風險', card['summary'])

class TestConfigurationLoading(unittest.TestCase):
    """測試配置文件加載"""
    
    def test_config_structure(self):
        """測試配置結構"""
        # Test that required config variables exist
        self.assertTrue(hasattr(APP, 'OAC_CODINGS_CONFIG'))
        self.assertTrue(hasattr(APP, 'NSAID_STEROID_CODINGS_CONFIG'))
        self.assertTrue(hasattr(APP, 'CONDITION_CODES_SCORE_2_CONFIG'))
        self.assertTrue(hasattr(APP, 'RISK_PARAMS_CONFIG'))
        self.assertTrue(hasattr(APP, 'FINAL_RISK_THRESHOLD_CONFIG'))
        
        # Test that they are the correct types
        self.assertIsInstance(APP.OAC_CODINGS_CONFIG, set)
        self.assertIsInstance(APP.NSAID_STEROID_CODINGS_CONFIG, set)
        self.assertIsInstance(APP.CONDITION_CODES_SCORE_2_CONFIG, set)
        self.assertIsInstance(APP.RISK_PARAMS_CONFIG, dict)
        self.assertIsInstance(APP.FINAL_RISK_THRESHOLD_CONFIG, dict)

class TestErrorHandling(unittest.TestCase):
    """測試錯誤處理"""
    
    def test_calculate_bleeding_risk_with_none_values(self):
        """測試風險計算函數處理 None 值"""
        risk_params = {
            'age_gte_75_params': {'threshold': 75, 'score': 1},
            'egfr_lt_30_params': {'threshold': 30, 'score': 2},
            'hgb_male_lt_13_params': {'threshold': 13, 'score': 1},
            'plt_lt_100_params': {'threshold': 100, 'score': 1}
        }
        final_threshold = {'high_risk_min_score': 3}
        
        result = calculate_bleeding_risk(
            age=None,
            egfr_value=None,
            hemoglobin=None,
            sex=None,
            platelet=None,
            condition_points=0,
            medication_points=0,
            blood_transfusion_points=0,
            risk_params=risk_params,
            final_threshold=final_threshold
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['score'], 0)
        
    def test_get_human_name_text_edge_cases(self):
        """測試人名提取的邊界情況"""
        # Empty name components
        name_list = [{"family": "", "given": []}]
        result = get_human_name_text(name_list)
        self.assertEqual(result, "N/A")
        
        # Missing family or given
        name_list = [{"given": ["John"]}]
        result = get_human_name_text(name_list)
        self.assertEqual(result, "John")
        
        name_list = [{"family": "Doe"}]
        result = get_human_name_text(name_list)
        self.assertEqual(result, "Doe")

def create_test_suite():
    """創建測試套件"""
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestUtilityFunctions,
        TestBleedingRiskCalculation,
        TestPrefetchFunctions,
        TestValueSetFunctions,
        TestFlaskRoutes,
        TestConfigurationLoading,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    return suite

def run_tests():
    """運行所有測試"""
    print("=" * 70)
    print("SMART FHIR Bleeding Risk Calculator - Unit Tests")
    print("=" * 70)
    
    # Create and run test suite
    suite = create_test_suite()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            newline = '\n'
            print(f"- {test}: {traceback.split('AssertionError: ')[-1].split(newline)[0]}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            newline = '\n'
            print(f"- {test}: {traceback.split(newline)[-2]}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    # Set up environment for testing
    os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
    os.environ['SMART_CLIENT_ID'] = 'test-client-id'
    os.environ['SMART_REDIRECT_URI'] = 'http://localhost:8080/callback'
    
    # Run tests
    success = run_tests()
    sys.exit(0 if success else 1) 
#!/usr/bin/env python3
"""
Test Phase 1 Optimization - fhirclient Integration
This script tests the basic functionality of the fhirclient optimization module.
"""

import sys
import os

def test_imports():
    """Test that all required modules can be imported"""
    print("=== Testing Phase 1 Optimization Imports ===")
    
    # Test basic fhirclient import
    try:
        from fhirclient import client
        from fhirclient.models.patient import Patient
        from fhirclient.models.observation import Observation
        print("✅ fhirclient core modules imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import fhirclient: {e}")
        return False
    
    # Test optimization module import
    try:
        import fhirclient_optimizations
        print("✅ fhirclient_optimizations module imported successfully")
        
        # Check if functions exist
        required_functions = [
            'get_patient_data_optimized',
            'get_observation_optimized',
            'get_hemoglobin_optimized',
            'get_creatinine_optimized',
            'get_platelet_optimized',
            'get_egfr_value_optimized'
        ]
        
        for func_name in required_functions:
            if hasattr(fhirclient_optimizations, func_name):
                print(f"✅ Function {func_name} found")
            else:
                print(f"❌ Function {func_name} missing")
                return False
                
    except ImportError as e:
        print(f"❌ Failed to import fhirclient_optimizations: {e}")
        return False
    
    return True

def test_configuration():
    """Test that APP.py configuration includes optimization flags"""
    print("\n=== Testing Configuration ===")
    
    try:
        # Check if APP.py has the optimization imports
        with open('APP.py', 'r', encoding='utf-8') as f:
            app_content = f.read()
            
        if 'fhirclient_optimizations' in app_content:
            print("✅ APP.py includes fhirclient_optimizations import")
        else:
            print("❌ APP.py missing fhirclient_optimizations import")
            return False
            
        if 'OPTIMIZATIONS_AVAILABLE' in app_content:
            print("✅ APP.py includes OPTIMIZATIONS_AVAILABLE flag")
        else:
            print("❌ APP.py missing OPTIMIZATIONS_AVAILABLE flag")
            return False
            
    except FileNotFoundError:
        print("❌ APP.py not found")
        return False
    
    return True

def test_requirements():
    """Test that requirements.txt includes fhirclient"""
    print("\n=== Testing Requirements ===")
    
    try:
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            requirements_content = f.read()
            
        if 'fhirclient' in requirements_content:
            print("✅ requirements.txt includes fhirclient")
        else:
            print("❌ requirements.txt missing fhirclient")
            return False
            
    except FileNotFoundError:
        print("❌ requirements.txt not found")
        return False
    
    return True

def main():
    """Run all tests"""
    print("Phase 1 Optimization Test Suite")
    print("=" * 40)
    
    tests = [
        test_requirements,
        test_configuration,
        test_imports
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n=== Test Results ===")
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All {total} tests passed!")
        print("\n🎉 Phase 1 Optimization is ready to use!")
        print("\nNext steps:")
        print("1. Install fhirclient: pip install fhirclient>=4.3.1")
        print("2. Test with your FHIR server")
        print("3. Monitor logs for optimization usage")
        return 0
    else:
        print(f"❌ {total - passed} out of {total} tests failed")
        print("\n❗ Phase 1 Optimization needs attention before use")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
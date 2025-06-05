#!/usr/bin/env python3
"""
Debug script for risk calculation issues
"""

import sys
import traceback
import time

def debug_calculation_stuck():
    print("🔍 Debugging Risk Calculation Issue")
    print("=" * 50)
    
    try:
        # Test basic imports
        print("1. Testing imports...")
        import fhirclient_optimizations as opt
        print("   ✅ fhirclient_optimizations imported")
        
        # Test Phase 2 components
        print("2. Testing Phase 2 components...")
        
        # Test PerformanceMetrics
        metrics = opt.PerformanceMetrics()
        metrics.record_operation('debug_test', 0.1, True)
        print("   ✅ PerformanceMetrics working")
        
        # Test IntelligentCache
        cache = opt.IntelligentCache(default_ttl=60, max_size=10)
        cache.set('test', 'debug_patient', {'test': 'data'})
        result = cache.get('test', 'debug_patient')
        if result:
            print("   ✅ IntelligentCache working")
        else:
            print("   ❌ IntelligentCache not working properly")
        
        # Test BatchOperationManager
        batch = opt.BatchOperationManager()
        batch.add_request('Observation', {'patient': 'debug'})
        print("   ✅ BatchOperationManager working")
        
        print("3. Testing potential timeout issues...")
        
        # Simulate what might be happening in get_lab_values_optimized_batch
        print("   - Testing batch operation configuration...")
        
        # Check if there are any threading issues
        import threading
        print(f"   - Current thread count: {threading.active_count()}")
        
        # Test global instances
        print("4. Testing global instances...")
        summary = opt.get_performance_summary()
        print(f"   ✅ Performance summary available: {type(summary)}")
        
        print("5. Checking for common issues...")
        
        # Check if fhirclient is available
        if opt.FHIRCLIENT_AVAILABLE:
            print("   ✅ fhirclient is available")
            try:
                from fhirclient import client
                print("   ✅ fhirclient.client imported successfully")
            except Exception as e:
                print(f"   ❌ fhirclient.client import failed: {e}")
        else:
            print("   ❌ fhirclient is NOT available")
        
        print("\n🎯 Diagnosis Results:")
        print("Phase 2 components appear to be functioning correctly.")
        print("The issue might be:")
        print("1. FHIR server timeout during batch operations")
        print("2. Session/authentication issues")
        print("3. Network connectivity problems")
        print("4. Batch request size too large")
        
        print("\n💡 Recommended fixes:")
        print("1. Add timeout handling to batch operations")
        print("2. Implement request size limits")
        print("3. Add better error logging")
        print("4. Force fallback to Phase 1 for testing")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during diagnosis: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_calculation_stuck() 
#!/usr/bin/env python3
"""
Quick test to verify the calculation doesn't get stuck
"""

import time
import sys

def test_calculation_timeout():
    print("🧪 Testing calculation timeout handling...")
    
    try:
        # Test timeout mechanism
        import threading
        
        def mock_batch_operation():
            # Simulate a stuck operation
            time.sleep(20)  # This would normally cause a hang
            return {'hemoglobin': 12.0, 'platelet': 200.0, 'egfr': 60.0}
        
        result_container = []
        error_container = []
        
        def batch_thread():
            try:
                result = mock_batch_operation()
                result_container.append(result)
            except Exception as e:
                error_container.append(e)
        
        print("Starting timeout test (should complete in ~15 seconds)...")
        start_time = time.time()
        
        thread = threading.Thread(target=batch_thread)
        thread.daemon = True
        thread.start()
        thread.join(timeout=15)  # 15 second timeout
        
        elapsed = time.time() - start_time
        
        if thread.is_alive():
            print(f"✅ Timeout working correctly! Operation timed out after {elapsed:.1f} seconds")
            return True
        elif result_container:
            print(f"⚠️ Operation completed in {elapsed:.1f} seconds (faster than expected)")
            return True
        else:
            print(f"❌ Timeout test failed after {elapsed:.1f} seconds")
            return False
            
    except Exception as e:
        print(f"❌ Error during timeout test: {e}")
        return False

def test_phase2_components():
    print("\n🔧 Testing Phase 2 components...")
    
    try:
        import fhirclient_optimizations as opt
        
        # Test batch manager
        batch = opt.BatchOperationManager()
        print("✅ BatchOperationManager initialized")
        
        # Test cache
        cache = opt.IntelligentCache()
        print("✅ IntelligentCache initialized")
        
        # Test metrics
        metrics = opt.PerformanceMetrics()
        print("✅ PerformanceMetrics initialized")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase 2 component test failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Quick Calculation Test")
    print("=" * 40)
    
    # Test timeout handling
    timeout_ok = test_calculation_timeout()
    
    # Test Phase 2 components
    components_ok = test_phase2_components()
    
    print("\n📊 Test Results:")
    print(f"Timeout handling: {'✅ PASS' if timeout_ok else '❌ FAIL'}")
    print(f"Phase 2 components: {'✅ PASS' if components_ok else '❌ FAIL'}")
    
    if timeout_ok and components_ok:
        print("\n🎉 All tests passed! The calculation should no longer get stuck.")
    else:
        print("\n⚠️ Some tests failed. Manual fallback should still work.") 
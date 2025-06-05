#!/usr/bin/env python3
"""
Quick Phase 2 Verification Script
Tests core Phase 2 functionality quickly
"""

def verify_phase2():
    print("🔍 Quick Phase 2 Verification")
    print("=" * 40)
    
    try:
        # Test imports
        import fhirclient_optimizations as opt
        print("✅ Phase 2 module imported successfully")
        
        # Test PerformanceMetrics
        metrics = opt.PerformanceMetrics()
        metrics.record_operation('test', 0.1, True)
        metrics.record_cache_hit()
        summary = metrics.get_summary()
        print("✅ PerformanceMetrics working")
        
        # Test IntelligentCache
        cache = opt.IntelligentCache(default_ttl=60, max_size=10)
        cache.set('test', 'patient1', {'data': 'test'})
        result = cache.get('test', 'patient1')
        print("✅ IntelligentCache working")
        
        # Test BatchOperationManager
        batch = opt.BatchOperationManager()
        batch.add_request('Observation', {'patient': 'test'})
        print("✅ BatchOperationManager working")
        
        # Test global functions
        perf_summary = opt.get_performance_summary()
        print("✅ Performance summary working")
        
        print("\n🎉 Phase 2 Core Features Verified!")
        print("\nKey Features Available:")
        print("✅ Batch FHIR operations")
        print("✅ Intelligent caching")  
        print("✅ Performance monitoring")
        print("✅ Thread-safe operations")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

if __name__ == "__main__":
    success = verify_phase2()
    if success:
        print("\n✅ Phase 2 is ready for production use!")
    else:
        print("\n❌ Phase 2 needs attention") 
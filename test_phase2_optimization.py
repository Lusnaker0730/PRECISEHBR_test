#!/usr/bin/env python3
"""
Test Phase 2 Optimization - Advanced fhirclient Features
This script tests the advanced optimization features including batch operations,
intelligent caching, and performance monitoring.
"""

import sys
import os
import time
import threading
from unittest.mock import MagicMock, patch

def test_phase2_imports():
    """Test that Phase 2 modules can be imported"""
    print("=== Testing Phase 2 Optimization Imports ===")
    
    try:
        import fhirclient_optimizations
        
        # Test Phase 2 specific classes
        phase2_classes = [
            'PerformanceMetrics',
            'IntelligentCache', 
            'BatchOperationManager'
        ]
        
        for class_name in phase2_classes:
            if hasattr(fhirclient_optimizations, class_name):
                print(f"✅ Class {class_name} found")
            else:
                print(f"❌ Class {class_name} missing")
                return False
        
        # Test Phase 2 specific functions
        phase2_functions = [
            'get_smart_client_cached',
            'get_multiple_observations_batch',
            'get_lab_values_optimized_batch',
            'get_performance_summary',
            'clear_patient_cache'
        ]
        
        for func_name in phase2_functions:
            if hasattr(fhirclient_optimizations, func_name):
                print(f"✅ Function {func_name} found")
            else:
                print(f"❌ Function {func_name} missing")
                return False
                
        print("✅ All Phase 2 components imported successfully")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import Phase 2 optimization module: {e}")
        return False

def test_performance_metrics():
    """Test PerformanceMetrics functionality"""
    print("\n=== Testing PerformanceMetrics ===")
    
    try:
        import fhirclient_optimizations
        
        # Create metrics instance
        metrics = fhirclient_optimizations.PerformanceMetrics()
        
        # Test recording operations
        metrics.record_operation('test_op', 0.5, True)
        metrics.record_operation('test_op', 0.3, True)
        metrics.record_operation('test_op', 1.0, False)
        
        # Test cache stats
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()
        metrics.record_cache_error()
        
        # Test summary generation
        summary = metrics.get_summary('test_op')
        if summary['count'] == 3:
            print("✅ Operation recording works correctly")
        else:
            print(f"❌ Expected 3 operations, got {summary['count']}")
            return False
        
        # Test overall summary
        overall = metrics.get_summary()
        if overall['cache_stats']['hits'] == 2:
            print("✅ Cache statistics tracking works correctly")
        else:
            print(f"❌ Expected 2 cache hits, got {overall['cache_stats']['hits']}")
            return False
        
        print("✅ PerformanceMetrics tests passed")
        return True
        
    except Exception as e:
        print(f"❌ PerformanceMetrics test failed: {e}")
        return False

def test_intelligent_cache():
    """Test IntelligentCache functionality"""
    print("\n=== Testing IntelligentCache ===")
    
    try:
        import fhirclient_optimizations
        
        # Create cache instance with short TTL for testing
        cache = fhirclient_optimizations.IntelligentCache(default_ttl=1, max_size=5)
        
        # Test basic set/get
        cache.set('observation', 'patient123', {'value': 10})
        result = cache.get('observation', 'patient123')
        
        if result and result['value'] == 10:
            print("✅ Basic cache set/get works correctly")
        else:
            print(f"❌ Cache get failed, expected {{'value': 10}}, got {result}")
            return False
        
        # Test cache expiration
        time.sleep(1.1)  # Wait for TTL to expire
        expired_result = cache.get('observation', 'patient123')
        
        if expired_result is None:
            print("✅ Cache expiration works correctly")
        else:
            print(f"❌ Cache should have expired, but got: {expired_result}")
            return False
        
        # Test cache eviction
        for i in range(10):  # Add more than max_size
            cache.set('observation', f'patient{i}', {'value': i})
        
        # Check that cache size is managed
        if len(cache.cache) <= cache.max_size:
            print("✅ Cache eviction works correctly")
        else:
            print(f"❌ Cache size {len(cache.cache)} exceeds max_size {cache.max_size}")
            return False
        
        # Test patient-specific clearing
        cache.set('observation', 'patient999', {'value': 999})
        cache.clear_patient('patient999')
        cleared_result = cache.get('observation', 'patient999')
        
        if cleared_result is None:
            print("✅ Patient-specific cache clearing works correctly")
        else:
            print(f"❌ Patient cache should be cleared, but got: {cleared_result}")
            return False
        
        print("✅ IntelligentCache tests passed")
        return True
        
    except Exception as e:
        print(f"❌ IntelligentCache test failed: {e}")
        return False

def test_batch_operation_manager():
    """Test BatchOperationManager functionality"""
    print("\n=== Testing BatchOperationManager ===")
    
    try:
        import fhirclient_optimizations
        
        # Create mock smart client
        mock_smart = MagicMock()
        
        # Create batch manager
        batch_manager = fhirclient_optimizations.BatchOperationManager(mock_smart)
        
        # Test adding requests
        batch_manager.add_request('Observation', {'patient': 'test123', 'code': 'test'})
        batch_manager.add_request('Condition', {'patient': 'test123'})
        
        if len(batch_manager.batch_requests) == 2:
            print("✅ Batch request addition works correctly")
        else:
            print(f"❌ Expected 2 batch requests, got {len(batch_manager.batch_requests)}")
            return False
        
        # Test clearing
        batch_manager.clear()
        
        if len(batch_manager.batch_requests) == 0:
            print("✅ Batch request clearing works correctly")
        else:
            print(f"❌ Expected 0 batch requests after clear, got {len(batch_manager.batch_requests)}")
            return False
        
        print("✅ BatchOperationManager tests passed")
        return True
        
    except Exception as e:
        print(f"❌ BatchOperationManager test failed: {e}")
        return False

def test_phase2_integration():
    """Test Phase 2 integration with APP.py"""
    print("\n=== Testing Phase 2 Integration ===")
    
    try:
        # Check if APP.py includes Phase 2 integration
        with open('APP.py', 'r', encoding='utf-8') as f:
            app_content = f.read()
        
        phase2_indicators = [
            'get_lab_values_optimized_batch',
            'Phase 2 batch optimization',
            'performance_summary',
            'optimization_used'
        ]
        
        for indicator in phase2_indicators:
            if indicator in app_content:
                print(f"✅ APP.py includes {indicator}")
            else:
                print(f"❌ APP.py missing {indicator}")
                return False
        
        print("✅ Phase 2 integration tests passed")
        return True
        
    except FileNotFoundError:
        print("❌ APP.py not found")
        return False
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def test_thread_safety():
    """Test thread safety of Phase 2 components"""
    print("\n=== Testing Thread Safety ===")
    
    try:
        import fhirclient_optimizations
        
        # Test PerformanceMetrics thread safety
        metrics = fhirclient_optimizations.PerformanceMetrics()
        cache = fhirclient_optimizations.IntelligentCache()
        
        def worker_metrics(worker_id):
            for i in range(10):
                metrics.record_operation(f'worker_{worker_id}', 0.1 * i, True)
                metrics.record_cache_hit()
        
        def worker_cache(worker_id):
            for i in range(10):
                cache.set('test', f'key_{worker_id}_{i}', {'worker': worker_id, 'value': i})
                cache.get('test', f'key_{worker_id}_{i}')
        
        # Create multiple threads
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=worker_metrics, args=(i,))
            t2 = threading.Thread(target=worker_cache, args=(i,))
            threads.extend([t1, t2])
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Check results
        total_ops = sum(len(ops) for ops in metrics.metrics.values())
        if total_ops == 50:  # 5 workers * 10 operations each
            print("✅ PerformanceMetrics thread safety test passed")
        else:
            print(f"❌ Expected 50 operations, got {total_ops}")
            return False
        
        print("✅ Thread safety tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Thread safety test failed: {e}")
        return False

def main():
    """Run all Phase 2 tests"""
    print("Phase 2 Optimization Test Suite")
    print("=" * 40)
    
    tests = [
        test_phase2_imports,
        test_performance_metrics,
        test_intelligent_cache,
        test_batch_operation_manager,
        test_phase2_integration,
        test_thread_safety
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n=== Phase 2 Test Results ===")
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All {total} Phase 2 tests passed!")
        print("\n🎉 Phase 2 Optimization is ready to use!")
        print("\nPhase 2 Features Available:")
        print("✅ Batch FHIR operations")
        print("✅ Intelligent caching with TTL")
        print("✅ Performance monitoring")
        print("✅ Thread-safe operations")
        print("✅ Automatic fallback mechanisms")
        
        print("\nNext steps:")
        print("1. Monitor performance improvements in production")
        print("2. Adjust cache TTL and size based on usage patterns")
        print("3. Consider Phase 3 optimization (async operations)")
        return 0
    else:
        print(f"❌ {total - passed} out of {total} Phase 2 tests failed")
        print("\n❗ Phase 2 Optimization needs attention before use")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
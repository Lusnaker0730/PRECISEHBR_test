#!/usr/bin/env python3
"""
FHIR Performance Optimizer Test Suite
Tests all functionality of the performance optimization module

Test Components:
1. Cache functionality testing
2. Performance monitoring verification  
3. Batch processing validation
4. Query optimization testing
5. Integrated workflow testing
6. Error handling validation
7. Cleanup operations testing

Usage:
    python test_performance_optimizer.py
"""

import time
import asyncio
import json
import random
from typing import List, Dict, Any
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from fhir_performance_optimizer import (
        FHIRPerformanceOptimizer,
        PerformanceMonitor,
        IntelligentCache,
        BatchProcessor,
        QueryOptimizer,
        track_performance,
        get_performance_stats,
        cleanup_cache
    )
    print("✅ Successfully imported FHIR Performance Optimizer modules")
    OPTIMIZER_AVAILABLE = True
except ImportError as e:
    logger.error(f"Cannot import performance optimizer: {e}")
    OPTIMIZER_AVAILABLE = False
    exit(1)

class PerformanceTestSuite:
    """Performance optimization test suite"""
    
    def __init__(self):
        self.optimizer = FHIRPerformanceOptimizer(max_cache_size=100, max_workers=3)
        self.results = {}
    
    def test_cache_functionality(self):
        """Test cache functionality"""
        print("\n🧪 Testing Cache Functionality...")
        
        cache = self.optimizer.cache
        
        # Test basic cache operations
        cache.set("test_key_1", {"data": "test_value_1"}, ttl=300)
        cache.set("test_key_2", {"data": "test_value_2"}, ttl=300, priority=2)
        
        # Test cache retrieval
        result1 = cache.get("test_key_1")
        result2 = cache.get("test_key_2")
        
        assert result1 == {"data": "test_value_1"}, "Cache retrieval failed"
        assert result2 == {"data": "test_value_2"}, "Cache retrieval failed"
        
        # Test cache miss
        result3 = cache.get("non_existent_key")
        assert result3 is None, "Cache should return None for non-existent keys"
        
        # Test cache statistics
        stats = cache.get_cache_stats()
        assert stats['size'] == 2, f"Expected cache size 2, got {stats['size']}"
        assert stats['hit_count'] == 2, f"Expected 2 cache hits, got {stats['hit_count']}"
        assert stats['miss_count'] == 1, f"Expected 1 cache miss, got {stats['miss_count']}"
        
        print("✅ Cache functionality tests passed")
        self.results['cache_test'] = 'PASS'
    
    def test_performance_monitoring(self):
        """Test performance monitoring functionality"""
        print("\n📊 Testing Performance Monitoring...")
        
        monitor = self.optimizer.monitor
        
        @self.optimizer.performance_tracked("test_operation", "TestResource")
        def mock_operation(duration: float = 0.1):
            """Mock operation"""
            time.sleep(duration)
            return {"result": "success"}
        
        # Execute monitored operations
        for i in range(5):
            result = mock_operation(random.uniform(0.05, 0.2))
        
        # Check statistics
        stats = monitor.get_statistics("test_operation")
        assert stats, "Statistics should not be empty"
        assert 'count' in stats, "Statistics should contain 'count' key"
        assert stats['count'] == 5, f"Expected 5 operations, got {stats['count']}"
        assert stats['avg_duration_ms'] > 0, "Average duration should be positive"
        
        # Test global statistics
        global_stats = monitor.get_statistics()
        assert global_stats['total_operations'] >= 5, "Total operations count incorrect"
        assert global_stats['success_rate'] == 1.0, "Success rate should be 100%"
        
        print("✅ Performance monitoring tests passed")
        self.results['monitoring_test'] = 'PASS'
    
    def test_batch_processing(self):
        """Test batch processing functionality"""
        print("\n⚡ Testing Batch Processing...")
        
        batch_processor = self.optimizer.batch_processor
        
        def mock_process_chunk(items_chunk):
            """Mock process item chunk"""
            results = []
            for item in items_chunk:
                time.sleep(0.01)  # Simulate processing time
                results.append({"processed": item, "result": item * 2})
            return results
        
        # Test batch processing
        items = list(range(1, 21))  # 20 items
        start_time = time.time()
        results = batch_processor.process_batch(items, mock_process_chunk, chunk_size=5)
        end_time = time.time()
        
        assert len(results) == 20, f"Expected 20 results, got {len(results)}"
        
        # Sort results by processed value for comparison (since batch processing may not preserve order)
        results.sort(key=lambda x: x['processed'])
        
        # Verify results
        for i, result in enumerate(results):
            expected_item = i + 1
            assert result['processed'] == expected_item, f"Batch processing result mismatch: expected {expected_item}, got {result['processed']}"
            assert result['result'] == expected_item * 2, f"Batch processing calculation error: expected {expected_item * 2}, got {result['result']}"
        
        # Test FHIR bundle creation
        mock_resources = [
            {"resourceType": "Patient", "id": "1", "name": "Patient 1"},
            {"resourceType": "Observation", "id": "2", "value": 100}
        ]
        
        bundle = batch_processor.create_fhir_bundle(mock_resources, "batch")
        assert bundle['resourceType'] == 'Bundle', "Bundle resourceType incorrect"
        assert bundle['type'] == 'batch', "Bundle type incorrect"
        assert len(bundle['entry']) == 2, "Bundle entry count incorrect"
        
        print("✅ Batch processing tests passed")
        self.results['batch_test'] = 'PASS'
    
    def test_query_optimization(self):
        """Test query optimization functionality"""
        print("\n🔍 Testing Query Optimization...")
        
        optimizer = self.optimizer.query_optimizer
        
        # Test basic optimization
        params = {"patient": "123"}
        optimized = optimizer.optimize_query("Observation", params)
        
        # Should add date range and count
        assert "date" in optimized, "Date range should be added"
        assert "_count" in optimized, "Count parameter should be added"
        assert optimized["patient"] == "123", "Original parameters should be preserved"
        
        # Test with existing parameters
        params_with_count = {"patient": "123", "_count": "50"}
        optimized2 = optimizer.optimize_query("Observation", params_with_count)
        assert optimized2["_count"] == "50", "Existing count should be preserved"
        
        # Test sort optimization
        params_sort = {"patient": "123"}
        optimized3 = optimizer.optimize_query("Condition", params_sort)
        assert "_sort" in optimized3, "Sort parameter should be added"
        
        print("✅ Query optimization tests passed")
        self.results['optimization_test'] = 'PASS'
    
    def test_integrated_workflow(self):
        """Test integrated workflow"""
        print("\n🔄 Testing Integrated Workflow...")
        
        @self.optimizer.performance_tracked("integrated_test", "Patient")
        def mock_comprehensive_data_fetch(patient_id: str):
            """Mock comprehensive data fetch"""
            time.sleep(0.1)  # Simulate network delay
            
            return {
                "patient": {"id": patient_id, "name": "Test Patient"},
                "observations": [{"id": "obs1", "value": 100}],
                "conditions": [{"id": "cond1", "code": "diabetes"}],
                "medications": [{"id": "med1", "name": "Metformin"}]
            }
        
        # Test first call (should not hit cache)
        start_time = time.time()
        result1 = mock_comprehensive_data_fetch("patient123")
        first_call_time = time.time() - start_time
        
        # Test second call (should hit cache)
        start_time = time.time()
        result2 = mock_comprehensive_data_fetch("patient123")
        second_call_time = time.time() - start_time
        
        # Verify results are identical
        assert result1 == result2, "Cached result should match original"
        
        # Second call should be significantly faster (cache hit)
        assert second_call_time < first_call_time, "Cached call should be faster"
        
        # Check cache statistics
        cache_stats = self.optimizer.cache.get_cache_stats()
        assert cache_stats['hit_count'] > 0, "Should have cache hits"
        
        print("✅ Integrated workflow tests passed")
        self.results['integration_test'] = 'PASS'
    
    def test_error_handling(self):
        """Test error handling"""
        print("\n🛡️ Testing Error Handling...")
        
        @self.optimizer.performance_tracked("error_test", "TestResource")
        def failing_operation():
            """Intentionally failing operation"""
            raise Exception("Test error")
        
        # Test error tracking
        try:
            failing_operation()
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected
        
        # Check that error was recorded
        stats = self.optimizer.monitor.get_statistics("error_test")
        assert stats, "Error operation statistics should not be empty"
        assert 'count' in stats, "Error statistics should contain 'count' key"
        assert stats['count'] == 1, "Error operation should be counted"
        
        # Check success rate
        global_stats = self.optimizer.monitor.get_statistics()
        # Success rate should be less than 100% due to the error
        assert global_stats['success_rate'] < 1.0, f"Success rate should reflect errors, got {global_stats['success_rate']}"
        
        print("✅ Error handling tests passed")
        self.results['error_test'] = 'PASS'
    
    def test_cleanup_operations(self):
        """Test cleanup operations"""
        print("\n🧹 Testing Cleanup Operations...")
        
        # Add some expired entries
        cache = self.optimizer.cache
        cache.set("expired_key", {"data": "expired"}, ttl=0.001)  # Very short TTL
        time.sleep(0.01)  # Wait for expiration
        
        # Test cleanup
        expired_count = cache.clear_expired()
        assert expired_count >= 1, "Should clear at least one expired entry"
        
        # Test global cleanup function
        cleanup_result = cleanup_cache()
        assert isinstance(cleanup_result, int), "Cleanup should return count"
        
        print("✅ Cleanup operations tests passed")
        self.results['cleanup_test'] = 'PASS'
    
    def generate_performance_report(self):
        """Generate performance report"""
        print("\n📈 Generating Performance Report...")
        
        # Get comprehensive stats
        stats = get_performance_stats()
        
        report = {
            "test_summary": self.results,
            "performance_stats": stats,
            "test_timestamp": time.time(),
            "total_tests": len(self.results),
            "passed_tests": sum(1 for result in self.results.values() if result == 'PASS'),
            "failed_tests": sum(1 for result in self.results.values() if result == 'FAIL')
        }
        
        # Save report
        with open("performance_test_report.json", "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"📄 Performance report saved to: performance_test_report.json")
        return report
    
    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting FHIR Performance Optimizer Test Suite...")
        print("=" * 60)
        
        tests = [
            self.test_cache_functionality,
            self.test_performance_monitoring,
            self.test_batch_processing,
            self.test_query_optimization,
            self.test_integrated_workflow,
            self.test_error_handling,
            self.test_cleanup_operations
        ]
        
        failed_tests = []
        
        for test in tests:
            try:
                test()
            except Exception as e:
                test_name = test.__name__
                print(f"❌ {test_name} FAILED: {e}")
                self.results[test_name] = 'FAIL'
                failed_tests.append(test_name)
        
        print("\n" + "=" * 60)
        print("📊 Test Summary:")
        
        total_tests = len(tests)
        passed_tests = total_tests - len(failed_tests)
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {len(failed_tests)}")
        
        if failed_tests:
            print(f"Failed Tests: {', '.join(failed_tests)}")
        
        # Generate detailed report
        report = self.generate_performance_report()
        
        print("\n🎯 Performance Metrics Summary:")
        if 'performance_stats' in report:
            perf_stats = report['performance_stats']
            print(f"Cache Hit Rate: {perf_stats.get('cache_stats', {}).get('hit_rate', 0):.1%}")
            print(f"Total Operations: {perf_stats.get('performance_stats', {}).get('total_operations', 0)}")
            print(f"System Success Rate: {perf_stats.get('performance_stats', {}).get('success_rate', 0):.1%}")
        
        success = len(failed_tests) == 0
        if success:
            print("\n🎉 All tests passed! Performance optimizer is working correctly.")
        else:
            print(f"\n⚠️ {len(failed_tests)} test(s) failed. Please check the issues above.")
        
        return success

def main():
    """Main test function"""
    if not OPTIMIZER_AVAILABLE:
        print("❌ Performance optimizer not available. Please install required dependencies.")
        return False
    
    print("FHIR Performance Optimizer Test Suite")
    print("=====================================")
    
    test_suite = PerformanceTestSuite()
    success = test_suite.run_all_tests()
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 
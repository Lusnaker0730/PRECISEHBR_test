"""
FHIR Performance Optimizer Module
提供批量操作、智能緩存、性能監控和進階查詢優化功能

Features:
1. 批量操作 (Batch Operations)
2. 智能緩存 (Intelligent Caching)  
3. 性能監控 (Performance Monitoring)
4. 進階查詢優化 (Advanced Query Optimization)
"""

import time
import json
import threading
import hashlib
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from functools import wraps, lru_cache
import weakref

# Performance monitoring setup
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """性能指標數據類"""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error_message: Optional[str] = None
    resource_type: Optional[str] = None
    cache_hit: bool = False
    batch_size: Optional[int] = None
    
    @property
    def duration_ms(self) -> float:
        return self.duration * 1000

@dataclass
class CacheEntry:
    """緩存條目數據類"""
    data: Any
    timestamp: float
    access_count: int = 0
    ttl: float = 3600  # 默認1小時
    priority: int = 1  # 優先級，越高越重要
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl
    
    @property
    def age(self) -> float:
        return time.time() - self.timestamp

class PerformanceMonitor:
    """性能監控器"""
    
    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
        self._start_time = time.time()
        
    def record_metric(self, metric: PerformanceMetrics):
        """記錄性能指標"""
        with self.lock:
            self.metrics.append(metric)
            self.operation_stats[metric.operation_name].append(metric.duration)
            
        logger.info(f"Performance: {metric.operation_name} took {metric.duration_ms:.2f}ms "
                   f"(success: {metric.success}, cache_hit: {metric.cache_hit})")
    
    def get_statistics(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """獲取統計信息"""
        with self.lock:
            if operation_name:
                durations = self.operation_stats.get(operation_name, [])
                if not durations:
                    return {}
                    
                return {
                    'operation': operation_name,
                    'count': len(durations),
                    'avg_duration_ms': statistics.mean(durations) * 1000,
                    'min_duration_ms': min(durations) * 1000,
                    'max_duration_ms': max(durations) * 1000,
                    'median_duration_ms': statistics.median(durations) * 1000,
                    'p95_duration_ms': statistics.quantiles(durations, n=20)[18] * 1000 if len(durations) >= 20 else None
                }
            else:
                # 全局統計
                total_operations = len(self.metrics)
                success_count = sum(1 for m in self.metrics if m.success)
                cache_hits = sum(1 for m in self.metrics if m.cache_hit)
                
                operation_summary = {}
                for op, durations in self.operation_stats.items():
                    operation_summary[op] = {
                        'count': len(durations),
                        'avg_duration_ms': statistics.mean(durations) * 1000,
                        'success_rate': sum(1 for m in self.metrics if m.operation_name == op and m.success) / len(durations)
                    }
                
                return {
                    'total_operations': total_operations,
                    'success_rate': success_count / total_operations if total_operations > 0 else 0,
                    'cache_hit_rate': cache_hits / total_operations if total_operations > 0 else 0,
                    'uptime_seconds': time.time() - self._start_time,
                    'operations': operation_summary
                }

class IntelligentCache:
    """智能緩存系統"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
        self.hit_count = 0
        self.miss_count = 0
        
        # 預取策略配置
        self.prefetch_patterns: Dict[str, List[str]] = {}
        self.access_patterns: Dict[str, List[float]] = defaultdict(list)
        
    def _generate_key(self, *args, **kwargs) -> str:
        """生成緩存鍵"""
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """獲取緩存數據"""
        with self.lock:
            entry = self.cache.get(key)
            if entry is None:
                self.miss_count += 1
                return None
                
            if entry.is_expired:
                del self.cache[key]
                self.miss_count += 1
                return None
                
            entry.access_count += 1
            self.access_patterns[key].append(time.time())
            self.hit_count += 1
            
            # 觸發預取
            self._trigger_prefetch(key)
            
            return entry.data
    
    def set(self, key: str, data: Any, ttl: Optional[float] = None, priority: int = 1):
        """設置緩存數據"""
        with self.lock:
            if len(self.cache) >= self.max_size:
                self._evict_entries()
                
            self.cache[key] = CacheEntry(
                data=data,
                timestamp=time.time(),
                ttl=ttl or self.default_ttl,
                priority=priority
            )
    
    def _evict_entries(self):
        """緩存逐出策略 - LFU + 優先級"""
        if not self.cache:
            return
            
        # 計算每個條目的分數（考慮訪問頻率、優先級和年齡）
        scores = {}
        current_time = time.time()
        
        for key, entry in self.cache.items():
            # 頻率分數
            frequency_score = entry.access_count
            # 優先級分數
            priority_score = entry.priority * 10
            # 年齡懲罰（越老分數越低）
            age_penalty = entry.age / 3600  # 小時
            
            scores[key] = frequency_score + priority_score - age_penalty
        
        # 刪除分數最低的25%條目
        sorted_keys = sorted(scores.keys(), key=lambda k: scores[k])
        evict_count = max(1, len(self.cache) // 4)
        
        for key in sorted_keys[:evict_count]:
            del self.cache[key]
    
    def _trigger_prefetch(self, accessed_key: str):
        """觸發預取策略"""
        patterns = self.prefetch_patterns.get(accessed_key, [])
        for pattern_key in patterns:
            if pattern_key not in self.cache:
                # 這裡可以觸發異步預取
                logger.debug(f"Prefetch opportunity: {pattern_key}")
    
    def add_prefetch_pattern(self, base_key: str, related_keys: List[str]):
        """添加預取模式"""
        self.prefetch_patterns[base_key] = related_keys
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """獲取緩存統計"""
        with self.lock:
            total_requests = self.hit_count + self.miss_count
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate': self.hit_count / total_requests if total_requests > 0 else 0,
                'expired_entries': sum(1 for entry in self.cache.values() if entry.is_expired)
            }
    
    def clear_expired(self):
        """清理過期條目"""
        with self.lock:
            expired_keys = [key for key, entry in self.cache.items() if entry.is_expired]
            for key in expired_keys:
                del self.cache[key]
            return len(expired_keys)

class BatchProcessor:
    """批量處理器"""
    
    def __init__(self, max_workers: int = 5, max_batch_size: int = 100):
        self.max_workers = max_workers
        self.max_batch_size = max_batch_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    def process_batch(self, items: List[Any], processor_func, chunk_size: Optional[int] = None) -> List[Any]:
        """批量處理項目"""
        if chunk_size is None:
            chunk_size = min(len(items) // self.max_workers + 1, self.max_batch_size)
        
        chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
        
        futures = []
        for chunk in chunks:
            future = self.executor.submit(processor_func, chunk)
            futures.append(future)
        
        results = []
        for future in as_completed(futures):
            try:
                chunk_results = future.result()
                if isinstance(chunk_results, list):
                    results.extend(chunk_results)
                else:
                    results.append(chunk_results)
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
                
        return results
    
    def create_fhir_bundle(self, resources: List[Dict], bundle_type: str = "batch") -> Dict:
        """創建 FHIR Bundle"""
        entries = []
        for resource in resources:
            entry = {
                "resource": resource
            }
            
            if bundle_type == "batch":
                entry["request"] = {
                    "method": "POST",
                    "url": resource.get("resourceType", "")
                }
            elif bundle_type == "transaction":
                entry["request"] = {
                    "method": "POST",
                    "url": resource.get("resourceType", ""),
                    "ifNoneExist": f"identifier={resource.get('id', '')}"
                }
                
            entries.append(entry)
        
        return {
            "resourceType": "Bundle",
            "type": bundle_type,
            "entry": entries
        }

class QueryOptimizer:
    """查詢優化器"""
    
    def __init__(self):
        self.query_patterns: Dict[str, Dict] = {}
        self.optimization_rules: List[callable] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """設置默認優化規則"""
        self.optimization_rules.extend([
            self._optimize_date_ranges,
            self._optimize_includes,
            self._optimize_count_parameters,
            self._optimize_sort_parameters
        ])
    
    def optimize_query(self, resource_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """優化查詢參數"""
        optimized_params = params.copy()
        
        for rule in self.optimization_rules:
            try:
                optimized_params = rule(resource_type, optimized_params)
            except Exception as e:
                logger.warning(f"Query optimization rule failed: {e}")
        
        return optimized_params
    
    def _optimize_date_ranges(self, resource_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """優化日期範圍查詢"""
        # 自動添加合理的日期範圍
        if resource_type in ["Observation", "Condition", "MedicationRequest"]:
            if "date" not in params and "_lastUpdated" not in params:
                # 默認查詢過去2年的數據
                two_years_ago = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
                params["date"] = f"ge{two_years_ago}"
        
        return params
    
    def _optimize_includes(self, resource_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """優化 _include 參數"""
        include_recommendations = {
            "Patient": ["Patient:general-practitioner"],
            "Observation": ["Observation:subject", "Observation:encounter"],
            "Condition": ["Condition:subject"],
            "MedicationRequest": ["MedicationRequest:subject", "MedicationRequest:medication"]
        }
        
        if resource_type in include_recommendations and "_include" not in params:
            # 只添加最常用的 include
            params["_include"] = include_recommendations[resource_type][0]
        
        return params
    
    def _optimize_count_parameters(self, resource_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """優化計數參數"""
        if "_count" not in params:
            # 根據資源類型設置合理的默認計數
            default_counts = {
                "Patient": 50,
                "Observation": 200,
                "Condition": 100,
                "MedicationRequest": 100
            }
            params["_count"] = default_counts.get(resource_type, 100)
        
        return params
    
    def _optimize_sort_parameters(self, resource_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """優化排序參數"""
        if "_sort" not in params:
            # 添加默認排序
            default_sorts = {
                "Observation": "-date",
                "Condition": "-recordedDate",
                "MedicationRequest": "-authoredOn"
            }
            if resource_type in default_sorts:
                params["_sort"] = default_sorts[resource_type]
        
        return params

class FHIRPerformanceOptimizer:
    """FHIR 性能優化器主類"""
    
    def __init__(self, max_cache_size: int = 1000, max_workers: int = 5):
        self.monitor = PerformanceMonitor()
        self.cache = IntelligentCache(max_size=max_cache_size)
        self.batch_processor = BatchProcessor(max_workers=max_workers)
        self.query_optimizer = QueryOptimizer()
        
        # 設置預取模式
        self._setup_prefetch_patterns()
    
    def _setup_prefetch_patterns(self):
        """設置預取模式"""
        # 當訪問患者時，預取其基本觀察值
        self.cache.add_prefetch_pattern(
            "patient_", 
            ["observations_recent_", "conditions_active_", "medications_active_"]
        )
    
    def performance_tracked(self, operation_name: str, resource_type: Optional[str] = None):
        """性能追蹤裝飾器"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error_message = None
                cache_hit = False
                
                # 檢查緩存
                cache_key = self.cache._generate_key(operation_name, *args, **kwargs)
                cached_result = self.cache.get(cache_key)
                
                if cached_result is not None:
                    cache_hit = True
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    metric = PerformanceMetrics(
                        operation_name=operation_name,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        success=True,
                        resource_type=resource_type,
                        cache_hit=True
                    )
                    self.monitor.record_metric(metric)
                    return cached_result
                
                try:
                    result = func(*args, **kwargs)
                    
                    # 緩存結果
                    if result is not None:
                        self.cache.set(cache_key, result, priority=2 if resource_type == "Patient" else 1)
                    
                except Exception as e:
                    success = False
                    error_message = str(e)
                    result = None
                    raise
                finally:
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    metric = PerformanceMetrics(
                        operation_name=operation_name,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        success=success,
                        error_message=error_message,
                        resource_type=resource_type,
                        cache_hit=cache_hit
                    )
                    self.monitor.record_metric(metric)
                
                return result
            return wrapper
        return decorator
    
    def batch_fetch_resources(self, fhir_server: str, headers: Dict, requests_data: List[Tuple[str, Dict]]) -> List[Dict]:
        """批量獲取 FHIR 資源"""
        def fetch_single(request_data):
            resource_type, params = request_data
            optimized_params = self.query_optimizer.optimize_query(resource_type, params)
            
            url = f"{fhir_server}/{resource_type}"
            try:
                response = requests.get(url, headers=headers, params=optimized_params, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error fetching {resource_type}: {e}")
                return None
        
        start_time = time.time()
        results = self.batch_processor.process_batch(requests_data, fetch_single)
        
        # 記錄批量操作指標
        metric = PerformanceMetrics(
            operation_name="batch_fetch_resources",
            start_time=start_time,
            end_time=time.time(),
            duration=time.time() - start_time,
            success=len([r for r in results if r is not None]) > 0,
            batch_size=len(requests_data)
        )
        self.monitor.record_metric(metric)
        
        return results
    
    def get_comprehensive_patient_data(self, fhir_server: str, headers: Dict, patient_id: str) -> Dict[str, Any]:
        """綜合獲取患者數據（使用所有優化技術）"""
        
        # 定義需要獲取的資源類型和參數
        resource_requests = [
            ("Patient", {"_id": patient_id}),
            ("Observation", {"patient": patient_id, "_sort": "-date", "_count": "50"}),
            ("Condition", {"patient": patient_id, "_sort": "-recordedDate", "_count": "50"}),
            ("MedicationRequest", {"patient": patient_id, "status": "active", "_count": "50"}),
            ("Procedure", {"patient": patient_id, "_sort": "-performedDateTime", "_count": "20"})
        ]
        
        # 批量獲取數據
        results = self.batch_fetch_resources(fhir_server, headers, resource_requests)
        
        # 組織返回數據
        comprehensive_data = {
            "patient": None,
            "observations": [],
            "conditions": [], 
            "medications": [],
            "procedures": []
        }
        
        resource_keys = ["patient", "observations", "conditions", "medications", "procedures"]
        for i, result in enumerate(results):
            if result and "entry" in result:
                key = resource_keys[i]
                if key == "patient" and result["entry"]:
                    comprehensive_data[key] = result["entry"][0]["resource"]
                else:
                    comprehensive_data[key] = [entry["resource"] for entry in result["entry"]]
        
        return comprehensive_data
    
    def cleanup_cache(self):
        """清理緩存"""
        expired_count = self.cache.clear_expired()
        logger.info(f"Cleaned up {expired_count} expired cache entries")
        return expired_count
    
    def get_performance_report(self) -> Dict[str, Any]:
        """獲取綜合性能報告"""
        return {
            "performance_stats": self.monitor.get_statistics(),
            "cache_stats": self.cache.get_cache_stats(),
            "optimization_active": True,
            "generated_at": datetime.now().isoformat()
        }

# 全局實例
global_optimizer = FHIRPerformanceOptimizer()

# 便捷裝飾器
def track_performance(operation_name: str, resource_type: Optional[str] = None):
    """便捷的性能追蹤裝飾器"""
    return global_optimizer.performance_tracked(operation_name, resource_type)

# 便捷函數
def get_performance_stats():
    """獲取性能統計"""
    return global_optimizer.get_performance_report()

def cleanup_cache():
    """清理緩存"""
    return global_optimizer.cleanup_cache() 
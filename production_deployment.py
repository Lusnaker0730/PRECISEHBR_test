# 生產環境部署配置
import os
import logging
import ssl
import certifi
from datetime import timedelta
from flask import Flask, request, redirect
import redis
from werkzeug.middleware.proxy_fix import ProxyFix

def create_production_app():
    """創建生產環境 Flask 應用"""
    app = Flask(__name__)
    
    # 生產環境配置
    configure_production_settings(app)
    configure_security_headers(app)
    configure_logging(app)
    configure_caching(app)
    configure_monitoring(app)
    
    return app

def configure_production_settings(app):
    """配置生產環境設定"""
    # 基本安全配置
    app.config.update(
        SECRET_KEY=os.environ.get('FLASK_SECRET_KEY'),
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_TIME_LIMIT=3600,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max file size
    )
    
    # 代理配置 (如果在負載平衡器後面)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # HTTPS 強制執行
    @app.before_request
    def force_https():
        if not request.is_secure and not app.debug:
            return redirect(request.url.replace('http://', 'https://'), code=301)

def configure_security_headers(app):
    """配置安全標頭"""
    @app.after_request
    def add_security_headers(response):
        # 內容安全政策
        csp = (
            "default-src 'self'; "
            "script-src 'self' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "style-src 'self' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "font-src cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "frame-ancestors 'self'; "
            "form-action 'self'; "
        )
        
        response.headers.update({
            'Content-Security-Policy': csp,
            'X-Frame-Options': 'SAMEORIGIN',
            'X-Content-Type-Options': 'nosniff',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'
        })
        
        return response

def configure_logging(app):
    """配置結構化日誌"""
    import json
    from datetime import datetime
    
    # 設定日誌格式
    class StructuredFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # 添加額外的上下文資訊
            if hasattr(record, 'patient_id'):
                log_entry['patient_id'] = record.patient_id
            if hasattr(record, 'user_id'):
                log_entry['user_id'] = record.user_id
            if hasattr(record, 'request_id'):
                log_entry['request_id'] = record.request_id
                
            return json.dumps(log_entry)
    
    # 配置日誌處理器
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    
    # 設定日誌等級
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    app.logger.setLevel(getattr(logging, log_level))
    app.logger.addHandler(handler)
    
    # 禁用 Werkzeug 的預設日誌
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

def configure_caching(app):
    """配置快取系統"""
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        try:
            app.redis = redis.from_url(redis_url, decode_responses=True)
            app.logger.info("Redis cache configured successfully")
        except Exception as e:
            app.logger.error(f"Failed to configure Redis: {e}")
            app.redis = None
    else:
        app.redis = None
        app.logger.warning("Redis URL not configured, using in-memory cache")

def configure_monitoring(app):
    """配置監控和健康檢查"""
    import time
    import psutil
    from flask import jsonify
    
    @app.route('/health')
    def health_check():
        """健康檢查端點"""
        try:
            # 檢查基本系統資源
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 檢查 Redis 連接 (如果配置了)
            redis_status = "not_configured"
            if hasattr(app, 'redis') and app.redis:
                try:
                    app.redis.ping()
                    redis_status = "healthy"
                except:
                    redis_status = "unhealthy"
            
            health_data = {
                'status': 'healthy',
                'timestamp': time.time(),
                'version': os.environ.get('APP_VERSION', 'unknown'),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'disk_percent': (disk.used / disk.total) * 100
                },
                'services': {
                    'redis': redis_status
                }
            }
            
            # 判斷整體健康狀態
            if cpu_percent > 90 or memory.percent > 90:
                health_data['status'] = 'degraded'
                return jsonify(health_data), 503
            
            return jsonify(health_data), 200
            
        except Exception as e:
            app.logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }), 503
    
    @app.route('/metrics')
    def metrics():
        """Prometheus 格式的指標端點"""
        try:
            # 基本系統指標
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            metrics_text = f"""# HELP cpu_usage_percent CPU usage percentage
# TYPE cpu_usage_percent gauge
cpu_usage_percent {cpu_percent}

# HELP memory_usage_percent Memory usage percentage
# TYPE memory_usage_percent gauge
memory_usage_percent {memory.percent}

# HELP app_info Application information
# TYPE app_info gauge
app_info{{version="{os.environ.get('APP_VERSION', 'unknown')}"}} 1
"""
            
            return metrics_text, 200, {'Content-Type': 'text/plain'}
            
        except Exception as e:
            app.logger.error(f"Metrics collection failed: {e}")
            return "# Metrics collection failed", 500, {'Content-Type': 'text/plain'}

class ProductionLogger:
    """生產環境日誌記錄器"""
    
    def __init__(self, app):
        self.app = app
    
    def log_fhir_access(self, patient_id, resource_type, action, response_time=None):
        """記錄 FHIR 資源存取"""
        extra = {
            'patient_id': patient_id,
            'resource_type': resource_type,
            'action': action,
            'event_type': 'fhir_access'
        }
        
        if response_time:
            extra['response_time_ms'] = response_time
            
        self.app.logger.info(f"FHIR access: {action} {resource_type}", extra=extra)
    
    def log_calculation(self, patient_id, risk_score, risk_category, calculation_time=None):
        """記錄風險計算"""
        extra = {
            'patient_id': patient_id,
            'risk_score': risk_score,
            'risk_category': risk_category,
            'event_type': 'risk_calculation'
        }
        
        if calculation_time:
            extra['calculation_time_ms'] = calculation_time
            
        self.app.logger.info(f"Risk calculation completed: {risk_category} (score: {risk_score})", extra=extra)
    
    def log_error(self, error_type, error_message, patient_id=None, user_id=None):
        """記錄錯誤"""
        extra = {
            'error_type': error_type,
            'event_type': 'error'
        }
        
        if patient_id:
            extra['patient_id'] = patient_id
        if user_id:
            extra['user_id'] = user_id
            
        self.app.logger.error(f"Application error: {error_type} - {error_message}", extra=extra)

class RateLimiter:
    """API 頻率限制器"""
    
    def __init__(self, app):
        self.app = app
        self.redis = getattr(app, 'redis', None)
    
    def is_allowed(self, key, limit=60, window=60):
        """檢查是否允許請求"""
        if not self.redis:
            return True  # 如果沒有 Redis，不限制
        
        try:
            current = self.redis.get(key)
            if current is None:
                self.redis.setex(key, window, 1)
                return True
            elif int(current) < limit:
                self.redis.incr(key)
                return True
            else:
                return False
        except Exception as e:
            self.app.logger.error(f"Rate limiting error: {e}")
            return True  # 發生錯誤時允許請求

def configure_ssl_context():
    """配置 SSL 上下文"""
    context = ssl.create_default_context(cafile=certifi.where())
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context

# 環境變數驗證
REQUIRED_ENV_VARS = [
    'FLASK_SECRET_KEY',
    'SMART_CLIENT_ID',
    'SMART_REDIRECT_URI',
    'APP_BASE_URL'
]

def validate_environment():
    """驗證必要的環境變數"""
    missing_vars = []
    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# 生產環境啟動檢查
def production_startup_checks():
    """生產環境啟動檢查"""
    checks = []
    
    # 環境變數檢查
    try:
        validate_environment()
        checks.append(("Environment variables", "PASS"))
    except ValueError as e:
        checks.append(("Environment variables", f"FAIL: {e}"))
    
    # SSL 憑證檢查
    try:
        configure_ssl_context()
        checks.append(("SSL configuration", "PASS"))
    except Exception as e:
        checks.append(("SSL configuration", f"FAIL: {e}"))
    
    # Redis 連接檢查
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        try:
            r = redis.from_url(redis_url)
            r.ping()
            checks.append(("Redis connection", "PASS"))
        except Exception as e:
            checks.append(("Redis connection", f"FAIL: {e}"))
    else:
        checks.append(("Redis connection", "SKIP: Not configured"))
    
    # 輸出檢查結果
    print("=== Production Startup Checks ===")
    for check_name, result in checks:
        print(f"{check_name}: {result}")
    print("=================================")
    
    # 如果有關鍵檢查失敗，停止啟動
    failed_checks = [check for check in checks if check[1].startswith("FAIL")]
    if failed_checks:
        raise RuntimeError("Critical startup checks failed")

if __name__ == "__main__":
    # 執行啟動檢查
    production_startup_checks()
    
    # 創建生產環境應用
    app = create_production_app()
    
    # 啟動應用
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8080))
    app.run(host=host, port=port, debug=False)
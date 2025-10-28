# 生產環境安全配置檢查清單

## 1. 應用程式註冊與認證
- [ ] **在 Cerner 開發者平台註冊應用程式**
  - 獲取正式的 Client ID 和 Client Secret
  - 配置正確的 Redirect URI (HTTPS)
  - 申請所需的 FHIR 資源存取權限

- [ ] **HTTPS 強制執行**
  ```python
  # 在 Flask 應用中強制 HTTPS
  @app.before_request
  def force_https():
      if not request.is_secure and app.env != 'development':
          return redirect(request.url.replace('http://', 'https://'))
  ```

- [ ] **環境變數安全管理**
  ```bash
  # 生產環境必須設定的環境變數
  FLASK_SECRET_KEY=<強密碼>
  SMART_CLIENT_ID=<Cerner提供的Client ID>
  SMART_CLIENT_SECRET=<Cerner提供的Secret>
  SMART_REDIRECT_URI=https://yourdomain.com/callback
  APP_BASE_URL=https://yourdomain.com
  ```

## 2. 內容安全政策 (CSP)
- [ ] **完整的 CSP 標頭**
  ```python
  @app.after_request
  def add_security_headers(response):
      response.headers['Content-Security-Policy'] = (
          "default-src 'self'; "
          "script-src 'self' 'unsafe-inline' https://stackpath.bootstrapcdn.com; "
          "style-src 'self' 'unsafe-inline' https://stackpath.bootstrapcdn.com; "
          "img-src 'self' data:; "
          "connect-src 'self' https://*.cerner.com; "
          "frame-ancestors 'self' https://*.cerner.com"
      )
      response.headers['X-Frame-Options'] = 'SAMEORIGIN'
      response.headers['X-Content-Type-Options'] = 'nosniff'
      response.headers['X-XSS-Protection'] = '1; mode=block'
      response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
      return response
  ```

## 3. 日誌與監控
- [ ] **結構化日誌**
  ```python
  import logging
  import json
  from datetime import datetime
  
  class StructuredLogger:
      def __init__(self, logger):
          self.logger = logger
      
      def log_fhir_access(self, patient_id, resource_type, action):
          log_entry = {
              'timestamp': datetime.utcnow().isoformat(),
              'event_type': 'fhir_access',
              'patient_id': patient_id,
              'resource_type': resource_type,
              'action': action,
              'user_id': current_user.id if current_user.is_authenticated else None
          }
          self.logger.info(json.dumps(log_entry))
  ```

- [ ] **錯誤監控與告警**
  - 整合 Sentry 或類似服務
  - 設定關鍵錯誤的即時告警

## 4. 資料保護與隱私
- [ ] **HIPAA 合規性**
  - 實施資料加密 (傳輸中和靜態)
  - 建立存取日誌稽核機制
  - 實施最小權限原則

- [ ] **Session 安全**
  ```python
  app.config.update(
      SESSION_COOKIE_SECURE=True,
      SESSION_COOKIE_HTTPONLY=True,
      SESSION_COOKIE_SAMESITE='Lax',
      PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
  )
  ```

## 5. 效能與可靠性
- [ ] **快取策略**
  - 實施 Redis 或 Memcached
  - ValueSet 快取優化
  - 實施適當的快取失效策略

- [ ] **資料庫連接池**
  - 如果使用資料庫，配置連接池
  - 實施健康檢查端點

- [ ] **負載平衡與高可用性**
  - 配置多個應用實例
  - 實施健康檢查
  - 設定自動擴展

## 6. 法規遵循
- [ ] **FDA 軟體醫療器材考量**
  - 如果提供臨床決策支援，可能需要 FDA 審查
  - 建立軟體版本控制和變更管理流程

- [ ] **臨床驗證**
  - 建立臨床驗證流程
  - 記錄演算法的臨床證據基礎

## 7. 部署與維護
- [ ] **容器化部署**
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  EXPOSE 8080
  CMD ["gunicorn", "--bind", "0.0.0.0:8080", "APP:app"]
  ```

- [ ] **CI/CD 管道**
  - 自動化測試
  - 安全掃描
  - 自動部署到測試和生產環境

- [ ] **備份與災難恢復**
  - 定期備份配置和資料
  - 建立災難恢復計畫 
# 免費部署方案指南 (Free Deployment Options Guide)

## 🚀 適合您的 SMART FHIR 應用程序的免費部署選項

### 推薦方案 (Recommended Options)

#### 1. **Google Cloud Platform (GCP) - 最推薦**
- **免費額度**: $300 信用額度 + Always Free 層級
- **App Engine**: 免費層級包含足夠的資源
- **優點**:
  - 已有 Google Secret Manager 整合
  - 支援 Python/Flask
  - 自動擴展
  - 已有 `app.yaml` 配置文件
- **限制**: 信用額度用完後需付費
- **部署命令**:
  ```bash
  gcloud app deploy
  ```

#### 2. **Railway** - 簡單易用
- **免費額度**: $5/月 免費使用額度
- **優點**:
  - 支援 Python/Flask
  - 自動從 GitHub 部署
  - 內建數據庫選項
  - 簡單的環境變量管理
- **限制**: 資源有限，適合小型應用
- **部署**: 連接 GitHub 倉庫自動部署

#### 3. **Render** - Heroku 替代方案
- **免費方案**: 
  - Web Services: 750小時/月
  - 自動休眠機制
- **優點**:
  - 支援 Python/Flask
  - 自動 HTTPS
  - 從 Git 自動部署
  - 支援環境變量
- **限制**: 15分鐘無活動後會休眠

#### 4. **Fly.io** - 現代化部署
- **免費額度**: 
  - 3個共享 CPU-1x 256MB 應用
  - 160GB 出站流量
- **優點**:
  - 全球邊緣部署
  - 支援 Docker
  - 快速啟動
- **限制**: 需要信用卡驗證

### 不太適合的選項

#### ❌ **Vercel/Netlify**
- 主要為靜態網站和前端應用設計
- 對 Python Flask 後端支援有限

#### ❌ **GitHub Pages**
- 只支援靜態網站
- 不支援 Python 後端

## 🔧 為不同平台準備部署文件

### 1. Google App Engine 部署

您已經有 `app.yaml`，只需要確保環境變量設置：

```yaml
# app.yaml (已存在，可能需要調整)
runtime: python39

env_variables:
  FLASK_ENV: "production"
  PRODUCTION: "true"
  FLASK_SECRET_KEY: "projects/your-project/secrets/flask-secret-key/versions/latest"
  SMART_CLIENT_ID: "projects/your-project/secrets/smart-client-id/versions/latest"
  SMART_REDIRECT_URI: "https://your-app.appspot.com/callback"

automatic_scaling:
  min_instances: 0
  max_instances: 10
```

**部署步驟**:
```bash
# 安裝 Google Cloud CLI
# 設置項目
gcloud config set project YOUR_PROJECT_ID

# 部署
gcloud app deploy
```

### 2. Railway 部署

創建 `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn APP:app",
    "healthcheckPath": "/",
    "healthcheckTimeout": 100
  }
}
```

**環境變量設置** (在 Railway Dashboard):
```
FLASK_ENV=production
PRODUCTION=true
FLASK_SECRET_KEY=your-secret-key
SMART_CLIENT_ID=your-client-id
SMART_REDIRECT_URI=https://your-app.up.railway.app/callback
```

### 3. Render 部署

創建 `render.yaml`:

```yaml
services:
  - type: web
    name: smart-fhir-app
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn APP:app
    envVars:
      - key: FLASK_ENV
        value: production
      - key: PRODUCTION
        value: true
      - key: FLASK_SECRET_KEY
        generateValue: true
      - key: SMART_CLIENT_ID
        sync: false
      - key: SMART_REDIRECT_URI
        value: https://smart-fhir-app.onrender.com/callback
```

### 4. Fly.io 部署

創建 `fly.toml`:

```toml
app = "smart-fhir-app"
primary_region = "nrt"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  FLASK_ENV = "production"
  PRODUCTION = "true"

[[services]]
  http_checks = []
  internal_port = 8080
  processes = ["app"]
  protocol = "tcp"
  script_checks = []

  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
    type = "connections"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.tcp_checks]]
    grace_period = "1s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"
```

## 📝 部署前準備清單

### 1. 更新 requirements.txt
確保包含 gunicorn:

```txt
gunicorn==21.2.0
```

### 2. 創建 Procfile (for Render/Railway)

```
web: gunicorn APP:app
```

### 3. 環境變量準備

**必需的環境變量**:
```bash
FLASK_SECRET_KEY=your-strong-secret-key
SMART_CLIENT_ID=your-fhir-client-id
SMART_REDIRECT_URI=https://your-domain.com/callback
FLASK_ENV=production
PRODUCTION=true
```

**可選環境變量**:
```bash
SMART_CLIENT_SECRET=your-client-secret
SMART_SCOPES="openid fhirUser launch/patient patient/*.read"
```

### 4. 生成強密鑰

```bash
python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

## 🎯 推薦部署流程

### 選項 1: Google App Engine (推薦給醫療應用)
```bash
# 1. 設置 GCP 項目
gcloud projects create your-project-id
gcloud config set project your-project-id

# 2. 啟用必要的 API
gcloud services enable appengine.googleapis.com
gcloud services enable secretmanager.googleapis.com

# 3. 創建 secrets
echo "your-secret-key" | gcloud secrets create flask-secret-key --data-file=-
echo "your-client-id" | gcloud secrets create smart-client-id --data-file=-

# 4. 部署
gcloud app deploy
```

### 選項 2: Railway (最簡單)
```bash
# 1. 連接到 GitHub
# 2. 在 Railway 中從 GitHub 創建新項目
# 3. 設置環境變量
# 4. 自動部署
```

### 選項 3: Render (穩定免費選項)
```bash
# 1. 連接到 GitHub
# 2. 在 Render 中創建新 Web Service
# 3. 設置環境變量
# 4. 部署
```

## 💡 成本比較

| 平台 | 免費額度 | 適用場景 | 限制 |
|------|----------|----------|------|
| **Google Cloud** | $300 + Always Free | 生產環境、醫療應用 | 需要信用卡 |
| **Railway** | $5/月 | 開發、小型應用 | 資源限制 |
| **Render** | 750小時/月 | 個人項目、演示 | 會休眠 |
| **Fly.io** | 3個應用 | 現代化應用 | 需要信用卡 |

## 🔒 醫療應用考慮事項

對於 SMART FHIR 醫療應用，建議：

1. **Google Cloud Platform**: 
   - 符合 HIPAA 要求
   - 企業級安全性
   - 已有整合配置

2. **避免使用**:
   - 共享主機
   - 不支援 HTTPS 的平台
   - 無法控制數據位置的服務

## 📚 部署後檢查清單

- [ ] HTTPS 正常工作
- [ ] 環境變量正確設置
- [ ] Session timeout 功能正常
- [ ] 安全警告橫幅顯示
- [ ] FHIR 服務器連接正常
- [ ] 日誌過濾器正常工作
- [ ] 性能測試通過

---

**建議**: 對於您的 SMART FHIR 應用程序，我強烈推薦使用 **Google App Engine**，因為您已經有相關配置，且它提供企業級的安全性和合規性，適合醫療應用。

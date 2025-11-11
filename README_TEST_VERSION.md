# PRECISE-HBR Test Version

🔗 **Repository**: [https://github.com/Lusnaker0730/PRECISEHBR_test](https://github.com/Lusnaker0730/PRECISEHBR_test)

## 📋 版本說明

這是 PRECISE-HBR 應用的測試版本，包含了 standalone launch 和開發測試模式的增強功能。

## 🆕 新增功能

### 1. Standalone Launch 支持
- ✅ 完整的 SMART on FHIR standalone launch 流程
- ✅ 自動 scope 調整（移除 EHR launch 專用的 `launch` scope）
- ✅ PKCE (Proof Key for Code Exchange) 支持
- ✅ 支持 SMART Health IT Launcher 測試

**訪問端點**: `/standalone`

### 2. 開發測試模式
- ✅ 無需 OAuth 授權即可測試應用
- ✅ 支持公開 FHIR 服務器（如 SMART Health IT）
- ✅ 快速進入主應用進行功能測試

**訪問端點**: `/test-mode`

### 3. 動態患者列表
- ✅ 從真實 FHIR 服務器實時獲取患者數據
- ✅ 支持切換不同的 FHIR 服務器
- ✅ 顯示患者詳細信息（姓名、ID、性別、出生日期）
- ✅ 點擊患者卡片直接進入測試

**訪問端點**: `/test-patients`

### 4. 架構改進
- ✅ 重命名 `auth.py` → `smart_auth.py` 避免與 fhirclient 包衝突
- ✅ 完整的 Blueprint 架構實現
- ✅ 改進的錯誤處理和日誌記錄

## 🚀 快速開始

### 使用 Docker（推薦）

```bash
# 克隆倉庫
git clone https://github.com/Lusnaker0730/PRECISEHBR_test.git
cd PRECISEHBR_test

# 設置環境變量
cp local.env.template .env
# 編輯 .env 文件，設置必要的變量

# 啟動應用
docker-compose up -d --build

# 查看日誌
docker logs -f smart_fhir_app
```

### 訪問應用

應用啟動後，訪問 `http://localhost:8080`

## 🧪 測試選項

### 選項 1: 快速測試模式（最快）
直接訪問，無需任何配置：
```
http://localhost:8080/test-mode
```

### 選項 2: 選擇測試患者
從真實 FHIR 服務器選擇患者：
```
http://localhost:8080/test-patients
```

### 選項 3: Standalone Launch（完整 OAuth）
完整的 SMART on FHIR 授權流程：
```
http://localhost:8080/standalone
```

## 🔧 環境變量

### 必需變量
```env
FLASK_SECRET_KEY=your-secret-key-here
SMART_CLIENT_ID=your-client-id
SMART_REDIRECT_URI=http://localhost:8080/callback
```

### 可選變量
```env
SMART_CLIENT_SECRET=your-client-secret  # 公共客戶端不需要
FLASK_DEBUG=true  # 開發環境
PORT=8080
```

## 📝 主要修改文件

### 核心文件
- `smart_auth.py` (原 `auth.py`) - SMART on FHIR 認證邏輯
- `views.py` - 主應用視圖和測試模式端點
- `fhir_data_service.py` - FHIR 數據獲取，支持測試模式
- `APP.py` - 應用主文件，Blueprint 註冊

### 模板文件
- `templates/standalone_launch.html` - Standalone launch 頁面
- `templates/test_patients.html` - 測試患者列表頁面
- `templates/callback.html` - OAuth 回調頁面

### 配置文件
- `config.py` - 應用配置
- `docker-compose.yml` - Docker 配置
- `requirements.txt` - Python 依賴

## 🔒 安全注意事項

⚠️ **重要**: 測試模式僅供開發使用

- `/test-mode` 和 `/test-patients` 端點繞過 OAuth 認證
- 在生產環境中必須禁用或添加訪問控制
- 建議在生產環境中完全移除這些端點

### 生產環境建議

```python
# 在 views.py 中添加環境檢查
import os

@views_bp.route('/test-mode')
def test_mode():
    # 僅在開發環境啟用
    if os.environ.get('FLASK_ENV') == 'production':
        abort(404)
    # ... 測試模式邏輯
```

## 🐛 已知問題和限制

1. **測試模式訪問限制**
   - 僅適用於公開 FHIR 服務器
   - 需要認證的服務器會返回 401/403 錯誤

2. **SMART Health IT Launcher**
   - 需要使用公共客戶端模式
   - Redirect URI 必須完全匹配

3. **Docker 容器重啟**
   - Session 數據會丟失（存儲在文件系統）
   - 需要重新登錄

## 📚 技術棧

- **Backend**: Python 3.11, Flask
- **FHIR Client**: fhirclient (smart-on-fhir/client-py)
- **Container**: Docker, Docker Compose
- **Frontend**: Bootstrap 5, vanilla JavaScript
- **Session**: Server-side session storage

## 🔗 相關資源

- [SMART Health IT Launcher](https://launch.smarthealthit.org/)
- [SMART on FHIR Documentation](http://hl7.org/fhir/smart-app-launch/)
- [FHIR R4 Specification](http://hl7.org/fhir/R4/)

## 📧 支持

如有問題或建議，請在 [GitHub Issues](https://github.com/Lusnaker0730/PRECISEHBR_test/issues) 中提出。

## 📄 授權

本項目為測試版本，請遵守原專案的授權條款。

---

**最後更新**: 2025-11-11
**版本**: Test v1.0


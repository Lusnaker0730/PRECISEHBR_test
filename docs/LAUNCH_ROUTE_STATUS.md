# SMART on FHIR Launch 路由狀態報告

## ✅ `/launch` 路由實作狀態

### 總結
**是的，目前的 SMART on FHIR `/launch` 路由是完整且可以正常作用的。**

---

## 📋 完整實作檢查清單

### 1. ✅ Blueprint 註冊
- **位置**: `APP.py` 第 597 行
- **狀態**: ✅ 已正確註冊
```python
app.register_blueprint(smart_auth.auth_bp)  # Authentication routes
```

### 2. ✅ Launch 路由實作
- **位置**: `smart_auth.py` 第 115-171 行
- **路由**: `@auth_bp.route('/launch')`
- **狀態**: ✅ 完整實作

#### 支援的功能：

##### a. EHR Launch（從 EHR 內部啟動）
- ✅ 接收 `iss` 參數（FHIR Server URL）
- ✅ 接收 `launch` 參數（EHR 提供的 launch token）
- ✅ 將 `launch` scope 包含在授權請求中
- ✅ 將 launch token 傳遞給 EHR 授權伺服器

##### b. Standalone Launch（獨立啟動）
- ✅ 接收 `iss` 參數
- ✅ **不需要** `launch` 參數
- ✅ 自動移除 `launch` scope
- ✅ 支援用戶選擇患者

#### 實作細節：

```python
@auth_bp.route('/launch')
def launch():
    # 1. 取得參數
    iss = request.args.get('iss')           # FHIR Server URL
    launch_token = request.args.get('launch')  # Launch token（可選）
    
    # 2. 驗證必要參數
    if not iss:
        return render_error_page(...)
    
    # 3. 儲存 launch 參數到 session
    session['launch_params'] = {'iss': iss, 'launch': launch_token}
    
    # 4. 自動發現 SMART configuration
    smart_config = get_smart_config(iss)
    
    # 5. 生成 PKCE 參數（SMART 2.0 支援）
    code_verifier, code_challenge = generate_pkce_parameters()
    
    # 6. 調整 scopes（standalone vs EHR launch）
    scopes = Config.SCOPES
    if not launch_token:
        # Standalone launch: 移除 'launch' scope
        scopes = ' '.join([s for s in scopes.split() if s != 'launch'])
    
    # 7. 構建授權 URL
    auth_params = {
        "response_type": "code",
        "client_id": Config.CLIENT_ID,
        "redirect_uri": Config.REDIRECT_URI,
        "scope": scopes,
        "state": state,
        "aud": iss,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    if launch_token:
        auth_params["launch"] = launch_token
    
    # 8. 重定向到 EHR 授權伺服器
    return redirect(full_auth_url)
```

### 3. ✅ SMART Configuration 自動發現
- **位置**: `smart_auth.py` 第 55-94 行
- **功能**: `get_smart_config(fhir_server_url)`
- **狀態**: ✅ 完整實作

#### 支援的發現方法：
1. **優先**: `.well-known/smart-configuration`（SMART 2.0 標準）
2. **降級**: `/metadata` 的 CapabilityStatement（FHIR 標準）

### 4. ✅ PKCE 支援（SMART 2.0）
- **位置**: `smart_auth.py` 第 20-50 行
- **狀態**: ✅ 完整實作
- **符合標準**: RFC 7636

#### 功能：
- ✅ 生成 code_verifier（43 字符，URL-safe）
- ✅ 生成 code_challenge（SHA256 雜湊）
- ✅ 使用 S256 方法
- ✅ 驗證 PKCE 參數

### 5. ✅ Callback 處理
- **位置**: `smart_auth.py` 第 203-252 行
- **路由**: `@auth_bp.route('/callback')`
- **狀態**: ✅ 完整實作，已改進錯誤處理

#### 功能：
- ✅ 處理授權碼
- ✅ State 參數驗證（防止 CSRF）
- ✅ 錯誤處理（包含 standalone launch 失敗的特殊處理）
- ✅ 重定向到 callback.html 進行 token exchange

### 6. ✅ Token Exchange
- **位置**: `smart_auth.py` 第 255-293 行
- **路由**: `@auth_bp.route('/api/exchange-code', methods=['POST'])`
- **狀態**: ✅ 完整實作

#### 功能：
- ✅ 用授權碼交換 access token
- ✅ PKCE 驗證
- ✅ State 參數驗證
- ✅ 儲存 FHIR context（patient ID, token, server）
- ✅ 返回重定向 URL

---

## 🎯 使用方式

### EHR Launch（從 EHR 啟動）
```
https://yourdomain.com/launch?iss=https://fhir.ehr.com&launch=abc123xyz
```

### Standalone Launch（獨立啟動）
```
https://yourdomain.com/launch?iss=https://fhir.ehr.com
```

### 從首頁表單啟動
1. 訪問 `/` 或 `/standalone`
2. 輸入 FHIR Server URL
3. 點擊 "Launch"
4. 系統會重定向到 `/launch?iss=...`

---

## ⚠️ Standalone Launch 常見失敗原因

根據最新的錯誤處理改進（smart_auth.py 第 210-247 行），系統現在會智能偵測並提供詳細的失敗原因：

### 1. EHR 系統不支援 standalone launch
**症狀**: 錯誤訊息包含 "Invalid launch options" 或 JSON 解析錯誤

**原因**: 
- 某些 EHR 系統（特別是舊版本）只支援 EHR launch
- 系統要求必須有 launch token

**解決方案**:
- 使用「測試模式」繞過 OAuth（推薦）
- 聯繫 EHR 管理員啟用 standalone launch
- 使用 EHR launch 方式

### 2. Client ID 註冊問題
**症狀**: "invalid_client" 或 "unauthorized_client"

**原因**:
- Client ID 未註冊
- 註冊時未勾選 "standalone launch" 選項
- Client type 設定錯誤（應為 "Public Client"）

**解決方案**:
- 在 EHR 系統中重新註冊 Client
- 確認啟用 standalone launch 功能
- 確認 Client type 為 "Public" 或 "Confidential"（根據需求）

### 3. Redirect URI 不匹配
**症狀**: "redirect_uri_mismatch"

**原因**:
- `.env` 中的 `SMART_REDIRECT_URI` 與 EHR 註冊的不一致
- 協議不匹配（http vs https）
- 尾部斜線不一致

**解決方案**:
```bash
# .env 檔案
SMART_REDIRECT_URI=https://yourdomain.com/callback

# 必須與 EHR 系統註冊的完全一致（包含 https、端口、路徑）
```

### 4. Scope 限制
**症狀**: "invalid_scope" 或授權頁面異常

**原因**:
- 請求的 scopes 超出 EHR 系統允許的範圍
- Standalone launch 可能不允許 `launch` scope
- 某些系統不允許同時請求 `patient/*` 和 `user/*`

**當前配置**（config.py 第 27 行）:
```python
SCOPES = "launch patient/Patient.read patient/Observation.read patient/Condition.read patient/MedicationRequest.read patient/Procedure.read fhirUser openid profile online_access user/Patient.read user/Observation.read user/Condition.read user/MedicationRequest.read user/Procedure.read"
```

**解決方案**:
- 根據 EHR 系統要求調整 scopes
- Standalone launch 會自動移除 `launch` scope
- 考慮分別測試 `patient/*` 和 `user/*` scopes

---

## 🧪 測試建議

### 1. 快速測試（推薦）
使用測試模式，無需 OAuth 設定：
```
https://yourdomain.com/test-patients
```

### 2. SMART Health IT Launcher 測試
使用公開的測試伺服器：
```
https://yourdomain.com/launch?iss=https://launch.smarthealthit.org/v/r4/fhir
```

### 3. Cerner Sandbox 測試
```
https://yourdomain.com/launch/cerner-sandbox
```

---

## 🔧 配置檢查清單

在嘗試 standalone launch 前，請確認以下設定：

### 環境變數（.env 檔案）
```bash
# 必要
FLASK_SECRET_KEY=<隨機長字串>
SMART_CLIENT_ID=<在EHR註冊的Client ID>
SMART_REDIRECT_URI=https://yourdomain.com/callback

# 可選
FLASK_DEBUG=true  # 僅開發環境
```

### EHR 系統註冊
- [ ] Client ID 已註冊
- [ ] 啟用 "Standalone Launch" 功能
- [ ] Redirect URI 與 `.env` 完全一致
- [ ] Scopes 已授權
- [ ] Client Type 正確設定

### 網路要求
- [ ] HTTPS（生產環境）
- [ ] 可從 EHR 系統訪問 callback URL
- [ ] 防火牆允許連接

---

## 📊 路由流程圖

```
用戶輸入 FHIR Server URL
         ↓
    /initiate-launch (POST)
         ↓
    /launch?iss=...
         ↓
   自動發現 SMART Configuration
         ↓
   生成 PKCE 參數
         ↓
   構建授權 URL
         ↓
   重定向到 EHR 授權伺服器
         ↓
   用戶授權/登入
         ↓
   EHR 重定向到 /callback?code=...&state=...
         ↓
   callback.html 頁面載入
         ↓
   JavaScript 呼叫 /api/exchange-code
         ↓
   Token Exchange（後端）
         ↓
   儲存 FHIR context 到 session
         ↓
   重定向到 /main（主頁面）
```

---

## ✨ 最新改進（本次更新）

### 1. 增強的錯誤處理
- 智能偵測 standalone launch 失敗
- 提供中文錯誤訊息和詳細建議
- 自動顯示測試模式選項

### 2. 改進的 UI
- Standalone launch 頁面增加警告提示
- 錯誤頁面增加醒目的測試模式按鈕
- 更友善的用戶引導

### 3. 完整的說明文件
- 詳細的故障排除指南
- 配置檢查清單
- 流程圖說明

---

## 🎉 結論

**`/launch` 路由是完整且可正常運作的**，支援：
- ✅ EHR Launch
- ✅ Standalone Launch  
- ✅ SMART 2.0（PKCE）
- ✅ 自動配置發現
- ✅ 完整的錯誤處理
- ✅ 安全性驗證（State, PKCE）

如果 standalone launch 失敗，通常是由於：
1. EHR 系統限制（不支援 standalone launch）
2. 配置問題（Client ID、Redirect URI、Scopes）

**建議**: 使用測試模式快速驗證應用程式功能，然後再處理 OAuth 配置問題。

---

## 📞 獲取協助

如需進一步協助，請檢查：
1. 應用程式日誌（查看詳細錯誤訊息）
2. EHR 系統的開發者文件
3. SMART on FHIR 規範：https://hl7.org/fhir/smart-app-launch/


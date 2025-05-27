# SMART FHIR Bleeding Risk Calculator - 單元測試

這個測試套件為 SMART FHIR 出血風險計算器應用程式提供全面的單元測試。

## 📁 測試文件結構

```
├── test_app.py          # 主要測試文件
├── run_tests.py         # 測試運行腳本
├── test_config.json     # 測試配置文件
└── TEST_README.md       # 本說明文件
```

## 🧪 測試覆蓋範圍

### 1. TestUtilityFunctions - 工具函數測試
- `calculate_age()` - 年齡計算函數
- `get_human_name_text()` - FHIR 人名提取函數

### 2. TestBleedingRiskCalculation - 出血風險計算測試
- 高風險情境計算
- 低風險情境計算
- 性別特定閾值測試
- 各項評分組件驗證

### 3. TestPrefetchFunctions - Prefetch 函數測試
- `get_hemoglobin_from_prefetch()` - 血紅蛋白提取
- `get_creatinine_from_prefetch()` - 肌酐提取
- `get_platelet_from_prefetch()` - 血小板提取
- `get_egfr_value_from_prefetch()` - eGFR 計算
- `get_medication_points_from_prefetch()` - 藥物評分
- `get_condition_points_from_prefetch()` - 診斷評分

### 4. TestValueSetFunctions - ValueSet 函數測試
- ValueSet 擴展功能
- 錯誤處理機制

### 5. TestFlaskRoutes - Flask 路由測試
- 首頁路由
- CDS Services 發現端點
- CDS Hooks 出血風險計算端點

### 6. TestConfigurationLoading - 配置加載測試
- 配置文件結構驗證
- 配置變數類型檢查

### 7. TestErrorHandling - 錯誤處理測試
- None 值處理
- 邊界情況測試

## 🚀 如何運行測試

### 方法 1: 使用測試運行腳本（推薦）

```bash
# 運行所有測試
python run_tests.py

# 列出所有可用的測試類別
python run_tests.py --list

# 運行特定測試類別
python run_tests.py --class TestBleedingRiskCalculation

# 運行特定測試方法
python run_tests.py --class TestUtilityFunctions --method test_calculate_age
```

### 方法 2: 直接使用 unittest

```bash
# 運行所有測試
python -m unittest test_app -v

# 運行特定測試類別
python -m unittest test_app.TestBleedingRiskCalculation -v

# 運行特定測試方法
python -m unittest test_app.TestUtilityFunctions.test_calculate_age -v
```

### 方法 3: 直接執行測試文件

```bash
python test_app.py
```

## 📋 測試前準備

### 必要文件
確保以下文件存在於同一目錄：
- `APP.py` - 主應用程式文件
- `test_config.json` - 測試配置文件（或 `cdss_config.json`）

### 環境變數
測試腳本會自動設置以下環境變數：
- `FLASK_SECRET_KEY`
- `SMART_CLIENT_ID`
- `SMART_REDIRECT_URI`
- `SMART_SCOPES`
- `APP_BASE_URL`
- `FLASK_ENV`

### Python 依賴
確保安裝了以下 Python 套件：
```bash
pip install flask flask-login flask-cors authlib requests python-dotenv PyJWT
```

## 🔧 測試配置

測試使用 `test_config.json` 作為配置文件，包含：
- 藥物編碼（OAC、NSAID/類固醇）
- 診斷規則（直接編碼、前綴規則、文字關鍵字）
- ValueSet 規則
- 風險評分參數
- 風險閾值設定

## 📊 測試結果解讀

### 成功輸出示例
```
======================================================================
SMART FHIR Bleeding Risk Calculator - Unit Tests
======================================================================
test_calculate_age (test_app.TestUtilityFunctions) ... ok
test_get_human_name_text (test_app.TestUtilityFunctions) ... ok
...

======================================================================
TEST SUMMARY
======================================================================
Tests run: 25
Failures: 0
Errors: 0
Success rate: 100.0%

✅ 所有測試通過!
```

### 失敗輸出示例
```
FAILURES:
- test_high_risk_calculation: Expected 5 but got 4

ERRORS:
- test_cds_hooks_endpoint: ModuleNotFoundError: No module named 'APP'
```

## 🐛 常見問題排解

### 1. 模組導入錯誤
```
ModuleNotFoundError: No module named 'APP'
```
**解決方案**: 確保 `APP.py` 文件在同一目錄下

### 2. 配置文件錯誤
```
FileNotFoundError: cdss_config.json not found
```
**解決方案**: 確保 `test_config.json` 或 `cdss_config.json` 存在

### 3. Flask 應用程式錯誤
```
RuntimeError: Working outside of application context
```
**解決方案**: 測試腳本會自動處理應用程式上下文

## 📝 新增測試

### 新增測試方法
```python
def test_new_function(self):
    """測試新功能"""
    # 準備測試數據
    test_input = "test_data"
    
    # 執行測試
    result = your_function(test_input)
    
    # 驗證結果
    self.assertEqual(result, expected_output)
```

### 新增測試類別
```python
class TestNewFeature(unittest.TestCase):
    """測試新功能"""
    
    def setUp(self):
        """設置測試數據"""
        self.test_data = {}
    
    def test_feature_function(self):
        """測試功能函數"""
        pass
```

## 🔄 持續整合

這些測試可以整合到 CI/CD 流程中：

```yaml
# GitHub Actions 示例
- name: Run Unit Tests
  run: |
    python run_tests.py
```

## 📈 測試覆蓋率

要檢查測試覆蓋率，可以使用 `coverage` 套件：

```bash
pip install coverage
coverage run test_app.py
coverage report
coverage html  # 生成 HTML 報告
```

## 🤝 貢獻指南

1. 為新功能編寫對應的測試
2. 確保所有測試通過
3. 保持測試代碼的可讀性
4. 添加適當的測試文檔

---

**注意**: 這些測試主要針對業務邏輯和數據處理功能。對於需要真實 FHIR 伺服器連接的整合測試，請參考其他測試文檔。 
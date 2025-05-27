# 測試運行快速指南

## 🚀 快速開始

### 1. 最簡單的方式 - 使用簡單測試運行器
```bash
python simple_test.py
```

### 2. 快速驗證環境設置
```bash
python quick_test.py
```

### 3. 使用功能完整的測試運行器
```bash
python run_tests.py
```

### 4. 直接運行測試文件
```bash
python test_app.py
```

## 📋 運行前檢查清單

確保以下文件存在：
- ✅ `APP.py` - 主應用程式
- ✅ `test_app.py` - 測試文件
- ✅ `test_config.json` - 測試配置

## 🔧 不同的運行方式

### 運行特定測試類別
```bash
# 只測試工具函數
python -m unittest test_app.TestUtilityFunctions -v

# 只測試風險計算
python -m unittest test_app.TestBleedingRiskCalculation -v

# 只測試 Prefetch 函數
python -m unittest test_app.TestPrefetchFunctions -v
```

### 運行特定測試方法
```bash
# 只測試年齡計算
python -m unittest test_app.TestUtilityFunctions.test_calculate_age -v

# 只測試高風險計算
python -m unittest test_app.TestBleedingRiskCalculation.test_high_risk_calculation -v
```

## 🐛 常見問題解決

### 問題 1: SyntaxError: f-string expression part cannot include a backslash
**解決方案**: 已修復，使用 `simple_test.py` 避免此問題

### 問題 2: ModuleNotFoundError: No module named 'APP'
**解決方案**: 
```bash
# 確保在正確的目錄下
cd /path/to/your/smart_fhir_app
python simple_test.py
```

### 問題 3: FileNotFoundError: cdss_config.json not found
**解決方案**: 測試會自動使用 `test_config.json`，確保該文件存在

### 問題 4: 測試失敗
**檢查步驟**:
1. 確認所有依賴已安裝: `pip install flask flask-login flask-cors authlib requests python-dotenv PyJWT`
2. 檢查 Python 版本: `python --version` (建議 3.7+)
3. 查看詳細錯誤信息

## 📊 測試結果解讀

### 成功示例
```
============================================================
SMART FHIR Bleeding Risk Calculator - 單元測試
============================================================
✓ 測試配置已設置
✓ 所有必要文件存在

test_calculate_age (test_app.TestUtilityFunctions) ... ok
test_get_human_name_text (test_app.TestUtilityFunctions) ... ok
...

============================================================
測試結果摘要
============================================================
測試總數: 20
失敗數量: 0
錯誤數量: 0
成功率: 100.0%

✅ 所有測試通過!
```

### 失敗示例
```
測試總數: 20
失敗數量: 2
錯誤數量: 1
成功率: 85.0%

失敗的測試:
  - test_high_risk_calculation (test_app.TestBleedingRiskCalculation)

錯誤的測試:
  - test_cds_hooks_endpoint (test_app.TestFlaskRoutes)

❌ 部分測試失敗
```

## 🎯 推薦的測試流程

1. **首次運行**: `python quick_test.py` - 驗證環境
2. **日常開發**: `python simple_test.py` - 快速測試
3. **完整驗證**: `python run_tests.py` - 全面測試
4. **特定功能**: `python -m unittest test_app.TestXXX -v` - 針對性測試

## 💡 提示

- 使用 `-v` 參數獲得詳細輸出
- 測試失敗時，檢查具體的錯誤信息
- 修改代碼後，重新運行相關測試
- 定期運行完整測試套件確保代碼品質

## 📞 需要幫助？

如果遇到問題：
1. 檢查本指南的常見問題部分
2. 查看 `TEST_README.md` 獲得更詳細的信息
3. 確認所有文件和依賴都正確安裝 
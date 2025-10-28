# PRECISE-HBR 安全掃描指南

## 概述

使用 Bandit 工具對 Python 代碼進行安全漏洞掃描。Bandit 是由 OpenStack 開發的安全檢測工具，專門用於查找 Python 代碼中的常見安全問題。

## 快速開始

### 1. 安裝 Bandit

```powershell
pip install bandit
```

### 2. 運行掃描

#### Windows (CMD):
```cmd
run_security_scan.bat
```

#### PowerShell:
```powershell
.\run_security_scan.ps1
```

#### Linux/Mac:
```bash
chmod +x run_security_scan.sh
./run_security_scan.sh
```

## 手動運行掃描

### 基本掃描

```bash
# 掃描所有 Python 文件
bandit -r .

# 排除虛擬環境
bandit -r . --exclude .venv,venv,env
```

### 生成報告

```bash
# HTML 報告（推薦）
bandit -r . -f html -o security_report.html --exclude .venv

# JSON 報告
bandit -r . -f json -o security_report.json --exclude .venv

# CSV 報告
bandit -r . -f csv -o security_report.csv --exclude .venv

# 文本報告
bandit -r . -f txt -o security_report.txt --exclude .venv
```

### 設置嚴重程度

```bash
# 只顯示高嚴重度問題
bandit -r . -ll --exclude .venv

# 只顯示中等及以上嚴重度
bandit -r . -l --exclude .venv

# 顯示所有問題
bandit -r . --exclude .venv
```

## 嚴重程度級別

### Severity (嚴重度)
- **HIGH**: 高危險，必須立即修復
- **MEDIUM**: 中等危險，應該盡快修復
- **LOW**: 低危險，建議修復

### Confidence (置信度)
- **HIGH**: 很確定是安全問題
- **MEDIUM**: 可能是安全問題
- **LOW**: 不太確定是安全問題

## 常見安全問題

### 1. 硬編碼密碼 (B105, B106, B107)
```python
# ❌ 不好
password = "my_secret_password"

# ✅ 好
password = os.environ.get("PASSWORD")
```

### 2. SQL 注入風險 (B608)
```python
# ❌ 不好
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ 好
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
```

### 3. 使用不安全的隨機數 (B311)
```python
# ❌ 不好
import random
token = random.randint(1000, 9999)

# ✅ 好
import secrets
token = secrets.token_hex(16)
```

### 4. 使用 eval() 或 exec() (B307, B102)
```python
# ❌ 不好
result = eval(user_input)

# ✅ 好
import ast
result = ast.literal_eval(user_input)
```

### 5. 不安全的 pickle 使用 (B301, B403)
```python
# ❌ 不好
import pickle
data = pickle.loads(untrusted_data)

# ✅ 好
import json
data = json.loads(trusted_data)
```

### 6. 不安全的 YAML 載入 (B506)
```python
# ❌ 不好
import yaml
data = yaml.load(file)

# ✅ 好
import yaml
data = yaml.safe_load(file)
```

### 7. 不安全的哈希算法 (B303, B324)
```python
# ❌ 不好
import hashlib
hash = hashlib.md5(data).hexdigest()

# ✅ 好
import hashlib
hash = hashlib.sha256(data).hexdigest()
```

### 8. 不安全的臨時文件 (B108)
```python
# ❌ 不好
import tempfile
tmp = open('/tmp/myfile.txt', 'w')

# ✅ 好
import tempfile
with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp.write(data)
```

## 配置文件

項目根目錄的 `.bandit` 文件用於配置掃描選項：

```ini
[bandit]
exclude_dirs = ['.venv', 'venv', 'env', '__pycache__']
tests = []  # 要運行的測試，空白表示全部
skips = []  # 要跳過的測試
```

### 跳過特定檢查

如果某個檢查產生了誤報，可以在代碼中添加註釋：

```python
# 跳過單行
result = eval(safe_input)  # nosec

# 跳過特定檢查
result = eval(safe_input)  # nosec B307

# 跳過整個函數
# nosec
def my_function():
    dangerous_operation()
```

## 掃描報告結構

### HTML 報告
- 📊 圖表化的統計信息
- 🎯 按嚴重程度分類
- 📝 詳細的代碼片段
- 💡 修復建議

### JSON 報告
- 🤖 機器可讀格式
- 🔄 易於集成到 CI/CD
- 📊 適合自動化處理

### CSV 報告
- 📈 適合在 Excel 中分析
- 📋 表格化數據
- 📊 便於生成統計圖表

## CI/CD 集成

### GitHub Actions

```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install Bandit
        run: pip install bandit
      - name: Run Bandit
        run: bandit -r . --exclude .venv -f json -o bandit-report.json
      - name: Upload Report
        uses: actions/upload-artifact@v2
        with:
          name: bandit-report
          path: bandit-report.json
```

### 本地 Git Hook

在 `.git/hooks/pre-commit` 添加：

```bash
#!/bin/bash
echo "Running Bandit security scan..."
bandit -r . --exclude .venv -ll
if [ $? -ne 0 ]; then
    echo "Security issues found! Please fix before committing."
    exit 1
fi
```

## 最佳實踐

### 1. 定期掃描
- 每次提交前掃描
- 每週完整掃描
- 發布前必須掃描

### 2. 優先級處理
1. 先修復 **HIGH severity + HIGH confidence**
2. 再修復 **HIGH severity + MEDIUM confidence**
3. 然後處理 **MEDIUM severity**
4. 最後考慮 **LOW severity**

### 3. 文檔記錄
- 記錄所有安全問題
- 記錄修復措施
- 記錄跳過的檢查原因

### 4. 團隊協作
- 與團隊分享掃描結果
- 建立安全編碼規範
- 定期安全培訓

## 常用命令參考

```bash
# 掃描單個文件
bandit filename.py

# 掃描特定目錄
bandit -r ./app

# 只顯示高危問題
bandit -r . -ll

# 生成詳細報告
bandit -r . -f html -o report.html -v

# 跳過特定測試
bandit -r . -s B101,B601

# 只運行特定測試
bandit -r . -t B201,B301

# 顯示所有可用測試
bandit -h | grep "B[0-9]"
```

## 解讀掃描結果

### 示例輸出

```
>> Issue: [B105:hardcoded_password_string] Possible hardcoded password: 'secret123'
   Severity: Low   Confidence: Medium
   Location: auth.py:42
   More Info: https://bandit.readthedocs.io/en/latest/plugins/b105_hardcoded_password_string.html
```

**解讀：**
- **Issue ID**: B105 - 硬編碼密碼字符串
- **Severity**: 嚴重程度
- **Confidence**: 置信度
- **Location**: 文件和行號
- **More Info**: 詳細說明鏈接

## 故障排除

### 問題：掃描太慢
**解決：** 排除不必要的目錄
```bash
bandit -r . --exclude .venv,node_modules,tests
```

### 問題：誤報太多
**解決：** 調整置信度和嚴重度
```bash
bandit -r . -ll  # 只顯示高嚴重度
```

### 問題：某些檢查不適用
**解決：** 在 `.bandit` 配置文件中跳過
```ini
skips = ['B101', 'B601']
```

## 參考資源

- [Bandit 官方文檔](https://bandit.readthedocs.io/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [CWE (Common Weakness Enumeration)](https://cwe.mitre.org/)

## 下一步

完成安全掃描後：
1. 查看 HTML 報告
2. 按優先級修復問題
3. 重新掃描驗證
4. 更新安全文檔
5. 向團隊分享結果


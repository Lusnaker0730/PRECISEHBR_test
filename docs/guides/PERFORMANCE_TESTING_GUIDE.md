# SMART FHIR App Performance Testing Guide

This guide explains how to run comprehensive performance tests comparing application behavior with 1, 10, and 100 concurrent users using Locust.

## 概述 (Overview)

我們的性能測試套件使用 Locust 來模擬不同數量的並發用戶（1人、10人、100人），並比較應用程序在不同負載下的性能表現。

Our performance testing suite uses Locust to simulate different numbers of concurrent users (1, 10, 100) and compare application performance under various loads.

## 預先準備 (Prerequisites)

### 1. 安裝依賴套件 (Install Dependencies)

```bash
pip install -r requirements.txt
```

### 2. 啟動應用程序 (Start the Application)

確保您的 SMART FHIR 應用程序正在運行：

```bash
python APP.py
```

預設應用程序會在 `http://localhost:8080` 運行。

### 3. 獲取認證信息 (Get Authentication Information)

在運行測試之前，您需要獲取有效的會話 cookie 和患者 ID：

1. **登入應用程序**：在瀏覽器中打開應用程序並完成 SMART on FHIR 認證流程
2. **獲取 Session Cookie**：
   - 打開瀏覽器開發者工具 (F12)
   - 進入 Application/Storage 標籤
   - 找到 Cookies 部分
   - 複製 `session` cookie 的值
3. **獲取 Patient ID**：從應用程序界面或 URL 中獲取當前患者 ID

## 運行測試 (Running Tests)

### Windows 用戶

1. **設置環境變量**：
```cmd
set LOCUST_SESSION_COOKIE=your_session_cookie_value_here
set LOCUST_TEST_PATIENT_ID=your_patient_id_here
set LOCUST_HOST=http://localhost:8080
```

2. **運行測試腳本**：
```cmd
run_performance_tests.bat
```

### Linux/Mac 用戶

1. **設置環境變量**：
```bash
export LOCUST_SESSION_COOKIE="your_session_cookie_value_here"
export LOCUST_TEST_PATIENT_ID="your_patient_id_here"
export LOCUST_HOST="http://localhost:8080"
```

2. **運行測試腳本**：
```bash
chmod +x run_performance_tests.sh
./run_performance_tests.sh
```

## 測試配置 (Test Configuration)

### 測試場景 (Test Scenarios)

| 測試 | 用戶數 | 持續時間 | 啟動速率 | 目的 |
|------|--------|----------|----------|------|
| Test 1 | 1 user | 60 seconds | 1 user/sec | 基準測試 |
| Test 2 | 10 users | 120 seconds | 2 users/sec | 中等負載 |
| Test 3 | 100 users | 180 seconds | 5 users/sec | 壓力測試 |

### 測試的端點 (Tested Endpoints)

1. **`/api/calculate_risk`** (主要功能) - 權重: 5
   - 計算 PRECISE-HBR 風險評分
   - 包含 FHIR 數據檢索和處理

2. **`/main`** (主頁面) - 權重: 2
   - 加載主應用程序頁面
   - 檢查會話有效性

3. **`/docs`** (文檔頁面) - 權重: 1
   - 靜態內容服務
   - 基本響應測試

4. **`/`** (健康檢查) - 權重: 1
   - 應用程序可用性檢查
   - 重定向處理

## 結果分析 (Results Analysis)

### 輸出文件 (Output Files)

測試完成後，在 `performance_results/` 目錄中會生成以下文件：

#### HTML 報告 (HTML Reports)
- `test_1_user.html` - 1用戶測試的詳細報告
- `test_10_users.html` - 10用戶測試的詳細報告  
- `test_100_users.html` - 100用戶測試的詳細報告

#### CSV 數據 (CSV Data)
- `test_*_users_stats.csv` - 詳細統計數據
- `test_*_users_failures.csv` - 錯誤記錄
- `test_*_users_exceptions.csv` - 異常記錄

#### JSON 報告 (JSON Reports)
- `performance_test_*users_*.json` - 自定義性能指標

#### 比較分析 (Comparison Analysis)
- `comparison_report_*.txt` - 綜合比較報告
- `performance_comparison_charts.png` - 性能圖表

### 關鍵指標 (Key Metrics)

#### 響應時間 (Response Time)
- **平均響應時間** (Average Response Time)
- **最小/最大響應時間** (Min/Max Response Time)
- **百分位數** (Percentiles: 50th, 90th, 95th, 99th)

#### 吞吐量 (Throughput)
- **每秒請求數** (Requests Per Second - RPS)
- **總請求數** (Total Requests)
- **成功請求數** (Successful Requests)

#### 錯誤率 (Error Rate)
- **失敗請求百分比** (Failure Percentage)
- **錯誤類型分布** (Error Type Distribution)
- **HTTP 狀態碼分布** (HTTP Status Code Distribution)

#### 可擴展性 (Scalability)
- **線性擴展效率** (Linear Scaling Efficiency)
- **性能降級點** (Performance Degradation Point)
- **資源利用率** (Resource Utilization)

## 性能基準 (Performance Benchmarks)

### 預期性能目標 (Expected Performance Targets)

| 指標 | 1 用戶 | 10 用戶 | 100 用戶 |
|------|--------|---------|----------|
| 平均響應時間 | < 500ms | < 1000ms | < 2000ms |
| 錯誤率 | < 1% | < 2% | < 5% |
| 吞吐量 | 基準 | > 8x 基準 | > 50x 基準 |

### 警告閾值 (Warning Thresholds)

- 🟡 **注意** (Warning): 響應時間 > 1000ms 或 錯誤率 > 2%
- 🔴 **嚴重** (Critical): 響應時間 > 2000ms 或 錯誤率 > 5%

## 故障排除 (Troubleshooting)

### 常見問題 (Common Issues)

#### 1. 認證失敗 (Authentication Failures)
```
ERROR: LOCUST_SESSION_COOKIE environment variable is not set
```
**解決方案**：確保正確設置環境變量，並且 session cookie 仍然有效。

#### 2. 連接錯誤 (Connection Errors)
```
ConnectionError: Failed to establish a new connection
```
**解決方案**：
- 確認應用程序正在運行
- 檢查 `LOCUST_HOST` 環境變量設置
- 驗證防火牆設置

#### 3. 高錯誤率 (High Error Rate)
**可能原因**：
- 會話過期
- 服務器過載
- 數據庫連接問題
- FHIR 服務器不可用

**解決方案**：
- 更新 session cookie
- 檢查服務器資源使用情況
- 驗證 FHIR 服務器連接

#### 4. 性能下降 (Performance Degradation)
**可能原因**：
- 內存泄漏
- 數據庫查詢效率低
- 網絡延遲
- 並發處理瓶頸

**解決方案**：
- 監控系統資源
- 優化數據庫查詢
- 檢查網絡配置
- 調整並發設置

## 高級配置 (Advanced Configuration)

### 自定義測試參數 (Custom Test Parameters)

您可以直接使用 Locust 命令行進行更靈活的測試：

```bash
# 自定義用戶數和持續時間
locust -f locustfile.py --headless --users 50 --spawn-rate 3 --run-time 300s --host http://localhost:8080

# 使用 Web UI 進行交互式測試
locust -f locustfile.py --host http://localhost:8080

# 壓力測試模式
LOCUST_TEST_MODE=stress locust -f locustfile.py --headless --users 200 --spawn-rate 10 --run-time 600s --host http://localhost:8080
```

### 分布式測試 (Distributed Testing)

對於更大規模的測試，可以使用多台機器：

```bash
# 主節點 (Master)
locust -f locustfile.py --master --host http://your-app-host:8080

# 工作節點 (Workers)
locust -f locustfile.py --worker --master-host master-machine-ip
```

### 監控和分析 (Monitoring and Analysis)

#### 實時監控 (Real-time Monitoring)
- 使用 Locust Web UI (http://localhost:8089) 進行實時監控
- 監控系統資源使用情況 (CPU, 內存, 網絡)
- 觀察應用程序日誌

#### 深度分析 (Deep Analysis)
- 分析響應時間分布
- 識別性能瓶頸
- 比較不同負載下的行為
- 評估擴展性能力

## 最佳實踐 (Best Practices)

### 測試環境 (Test Environment)
1. **使用專用測試環境**：避免在生產環境運行負載測試
2. **數據一致性**：使用一致的測試數據集
3. **網絡條件**：在穩定的網絡環境下運行測試
4. **資源監控**：同時監控客戶端和服務器資源

### 測試策略 (Testing Strategy)
1. **漸進式負載**：從低負載開始，逐步增加
2. **多次運行**：進行多次測試以獲得可靠結果
3. **基線建立**：建立性能基線用於比較
4. **定期測試**：定期運行性能測試以檢測回歸

### 結果解釋 (Result Interpretation)
1. **關注趨勢**：比較不同負載水平之間的趨勢
2. **識別拐點**：找到性能開始下降的負載點
3. **考慮業務需求**：將結果與實際業務需求對比
4. **制定優化計劃**：基於結果制定性能優化計劃

## 支持和幫助 (Support and Help)

如果您在運行性能測試時遇到問題，請檢查：

1. **日誌文件**：查看應用程序和測試日誌
2. **環境變量**：確認所有必需的環境變量都已設置
3. **網絡連接**：驗證測試機器與應用程序之間的連接
4. **資源限制**：檢查系統資源是否足夠

更多信息請參考：
- [Locust 官方文檔](https://docs.locust.io/)
- [SMART on FHIR 規範](http://hl7.org/fhir/smart-app-launch/)
- [Flask 性能優化指南](https://flask.palletsprojects.com/en/2.3.x/deploying/)

# PRECISE-HBR 負載測試指南

## 概述

本指南說明如何對 PRECISE-HBR 應用程式執行負載測試，測試在1人、10人和30人同時使用下的系統反應。

## 測試場景

- **測試1**: 1個並發用戶 (持續1分鐘)
- **測試2**: 10個並發用戶 (持續2分鐘)
- **測試3**: 30個並發用戶 (持續3分鐘)

## 前置準備

### 1. 安裝 Locust

```bash
pip install locust
```

### 2. 獲取 Session Cookie

測試需要有效的 session cookie 來模擬已認證的用戶：

1. 在瀏覽器中登入應用程式
2. 打開開發者工具 (F12)
3. 前往 **Application** (Chrome) 或 **Storage** (Firefox) 標籤
4. 選擇 **Cookies**
5. 複製 `session` cookie 的值

### 3. 設定環境變數

#### Windows (PowerShell):
```powershell
$env:LOCUST_SESSION_COOKIE="your_session_cookie_value"
$env:LOCUST_TEST_PATIENT_ID="your_patient_id"
$env:LOCUST_TARGET_HOST="http://localhost:8080"  # 可選，預設為 localhost:8080
```

#### Windows (CMD):
```cmd
set LOCUST_SESSION_COOKIE=your_session_cookie_value
set LOCUST_TEST_PATIENT_ID=your_patient_id
set LOCUST_TARGET_HOST=http://localhost:8080
```

#### Linux/Mac:
```bash
export LOCUST_SESSION_COOKIE="your_session_cookie_value"
export LOCUST_TEST_PATIENT_ID="your_patient_id"
export LOCUST_TARGET_HOST="http://localhost:8080"
```

## 執行測試

### 自動化測試 (推薦)

#### Windows:
```cmd
run_load_tests.bat
```

#### Linux/Mac:
```bash
chmod +x run_load_tests.sh
./run_load_tests.sh
```

這會自動執行所有三個測試並生成比較報告。

### 手動執行個別測試

#### 1個用戶測試:
```bash
locust -f locustfile.py --headless --users 1 --spawn-rate 1 --run-time 60s --host http://localhost:8080 --html test_1user.html
```

#### 10個用戶測試:
```bash
locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 120s --host http://localhost:8080 --html test_10users.html
```

#### 30個用戶測試:
```bash
locust -f locustfile.py --headless --users 30 --spawn-rate 5 --run-time 180s --host http://localhost:8080 --html test_30users.html
```

### 使用 Web UI 進行測試

如果想要即時監控測試進度：

```bash
locust -f locustfile.py --host http://localhost:8080
```

然後在瀏覽器中打開 http://localhost:8089

## 測試結果

### 輸出檔案

測試完成後會在 `load_test_results/` 目錄中產生以下檔案：

1. **HTML 報告**: `test_Xusers_TIMESTAMP.html`
   - 圖表化的測試結果
   - 包含響應時間分布圖

2. **CSV 統計**: `test_Xusers_TIMESTAMP_stats.csv`
   - 詳細的統計數據
   - 每個端點的性能指標

3. **CSV 失敗記錄**: `test_Xusers_TIMESTAMP_failures.csv`
   - 記錄所有失敗的請求

4. **JSON 報告**: `performance_test_Xusers_TIMESTAMP.json`
   - 結構化的測試結果
   - 便於程式處理

5. **比較報告**: `load_test_comparison_TIMESTAMP.txt`
   - 三個測試的並排比較
   - 性能分析和建議

### 關鍵指標

#### 1. 響應時間 (Response Time)
- **Avg (平均)**: 平均響應時間
- **Median (中位數)**: 50% 的請求在此時間內完成
- **95th percentile**: 95% 的請求在此時間內完成
- **目標**: < 1000ms (1秒)

#### 2. 請求吞吐量 (Throughput)
- **Requests/sec**: 每秒處理的請求數
- **目標**: 隨用戶數線性增長

#### 3. 錯誤率 (Failure Rate)
- **Percentage**: 失敗請求的百分比
- **目標**: < 1%

#### 4. 並發性能 (Concurrency)
- 測試系統在多用戶同時訪問時的表現
- **目標**: 30用戶時響應時間增加 < 50%

## 性能基準

### 優秀 (Excellent)
- 平均響應時間 < 500ms
- 錯誤率 < 1%
- 30用戶時吞吐量 > 20 req/s

### 良好 (Good)
- 平均響應時間 < 1000ms
- 錯誤率 < 5%
- 30用戶時吞吐量 > 15 req/s

### 可接受 (Acceptable)
- 平均響應時間 < 2000ms
- 錯誤率 < 10%
- 30用戶時吞吐量 > 10 req/s

### 需要優化 (Needs Improvement)
- 平均響應時間 > 2000ms
- 錯誤率 > 10%
- 頻繁超時或連接錯誤

## 測試的 API 端點

測試會模擬以下使用者操作：

1. **計算風險分數** (`/api/calculate_risk`) - 權重: 5
   - 主要的 PRECISE-HBR 計算功能
   - 最重要的性能指標

2. **載入主頁面** (`/main`) - 權重: 2
   - 用戶界面載入時間

3. **查看文檔** (`/docs`) - 權重: 1
   - 靜態內容載入

4. **健康檢查** (`/`) - 權重: 1
   - 基本連接測試

## 故障排除

### Session Cookie 過期
- **症狀**: 401 Unauthorized 錯誤
- **解決**: 重新登入並更新 cookie

### 連接超時
- **症狀**: 大量超時錯誤
- **原因**: 伺服器負載過高或網路問題
- **解決**: 降低並發用戶數或增加伺服器資源

### 高錯誤率
- **症狀**: > 10% 失敗率
- **原因**: 可能的後端問題或資源限制
- **解決**: 檢查伺服器日誌，分析錯誤類型

## 進階測試

### 壓力測試 (Stress Testing)
測試系統的極限：

```bash
locust -f locustfile.py --user-classes StressTestUser --headless --users 50 --spawn-rate 10 --run-time 300s
```

### 持續測試 (Endurance Testing)
長時間運行測試：

```bash
locust -f locustfile.py --headless --users 20 --spawn-rate 5 --run-time 3600s
```

### 尖峰測試 (Spike Testing)
快速增加負載：

```bash
locust -f locustfile.py --headless --users 100 --spawn-rate 20 --run-time 120s
```

## 分析測試結果

### 使用分析工具

```bash
python analyze_load_tests.py load_test_results
```

這會生成：
- 並排比較表
- 性能縮放分析
- 建議和優化方向

### 重點關注

1. **響應時間趨勢**: 是否隨用戶數線性增長？
2. **錯誤模式**: 哪些端點最容易失敗？
3. **瓶頸識別**: 哪個資源（CPU、記憶體、網路）是限制因素？
4. **縮放效率**: 增加資源是否改善性能？

## 最佳實踐

1. **隔離測試環境**: 在專用環境中測試，避免影響生產
2. **多次運行**: 至少運行3次取平均值
3. **監控伺服器**: 同時監控 CPU、記憶體、網路使用
4. **逐步增加負載**: 從小負載開始，逐步增加
5. **記錄基線**: 建立性能基線以便比較
6. **定期測試**: 每次重大更新後都進行測試

## 參考資源

- [Locust 官方文檔](https://docs.locust.io/)
- [性能測試最佳實踐](https://www.guru99.com/performance-testing.html)
- [負載測試指南](https://www.loadview-testing.com/blog/load-testing-best-practices/)

## 支援

如有問題，請查看：
- 應用程式日誌
- Locust 輸出
- 伺服器監控指標


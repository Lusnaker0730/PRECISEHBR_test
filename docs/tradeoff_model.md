
# ARC-HBR 風險權衡模型

這份文件說明了根據《JAMA Cardiology》期刊中 "Assessing the Risks of Bleeding vs Thrombotic Events in Patients at High Bleeding Risk After Coronary Stent Implantation: The ARC-High Bleeding Risk Trade-off Model" 這篇論文所建立的風險權衡模型。

此模型旨在預測高出血風險 (High Bleeding Risk, HBR) 患者在接受經皮冠狀動脈介入治療 (PCI) 後一年內，發生以下兩種事件的風險：

1.  **出血事件**: BARC (Bleeding Academic Research Consortium) 分類為 3 至 5 型的出血事件。
2.  **血栓事件**: 心肌梗塞 (Myocardial Infarction, MI) 或支架內血栓 (Stent Thrombosis, ST)。

## 邏輯與權重

模型使用了多個臨床變數作為預測因子，每個因子都有其對應的風險比 (Hazard Ratio, HR)，此數值即為其權重。

### 出血事件 (BARC types 3-5) 的預測因子與權重

| 預測因子 | 風險比 (HR) (95% CI) | P 值 |
| :--- | :--- | :--- |
| 年齡 ≥ 65 歲 | 1.50 (1.08-2.08) | .01 |
| 肝病、癌症或手術 | 1.63 (1.27-2.09) | .0001 |
| 慢性阻塞性肺病 (COPD) | 1.39 (1.05-1.83) | .02 |
| 目前吸菸者 | 1.47 (1.08-1.99) | .01 |
| **血紅素 (g/dL)** | | |
| &emsp;11-12.9 | 1.69 (1.30-2.20) | <.001 |
| &emsp;<11 | 3.99 (3.06-5.20) | |
| **eGFR (mL/min)** | | |
| &emsp;<30 | 1.43 (1.04-1.96) | .02 |
| 複雜的 PCI 手術 | 1.32 (1.07-1.61) | .008 |
| 出院時使用口服抗凝血劑 (OAC) | 2.00 (1.62-2.48) | <.001 |

**模型鑑別度 (C-statistic): 0.68**

### 血栓事件 (MI and/or ST) 的預測因子與權重

| 預測因子 | 風險比 (HR) (95% CI) | P 值 |
| :--- | :--- | :--- |
| 糖尿病 | 1.56 (1.26-1.93) | <.001 |
| 曾有心肌梗塞 (Prior MI) | 1.89 (1.52-2.35) | <.001 |
| 目前吸菸者 | 1.48 (1.09-2.01) | .009 |
| NSTEMI 或 STEMI | 1.82 (1.46-2.25) | <.001 |
| **血紅素 (g/dL)** | | |
| &emsp;11-12.9 | 1.27 (0.99-1.63) | .005 |
| &emsp;<11 | 1.50 (1.12-1.99) | |
| **eGFR (mL/min)** | | |
| &emsp;30-59 | 1.30 (1.03-1.66) | .001 |
| &emsp;<30 | 1.69 (1.20-2.37) | |
| 複雜的 PCI 手術 | 1.50 (1.21-1.85) | <.001 |
| 使用裸金屬支架 (BMS) | 1.53 (1.23-1.89) | <.001 |

**模型鑑別度 (C-statistic): 0.69**

---

**注意**:

*   **NA** (Not Applicable) 表示該因子在此模型中不適用或未被選入。
*   **HR (Hazard Ratio)**: 風險比。HR > 1 表示風險增加，HR < 1 表示風險降低。
*   **CI (Confidence Interval)**: 信賴區間。
*   **eGFR**: 估計腎絲球過濾率 (estimated Glomerular Filtration Rate)。
*   **PCI**: 經皮冠狀動脈介入治療 (Percutaneous Coronary Intervention)。
*   **OAC**: 口服抗凝血劑 (Oral Anticoagulants)。
*   **NSTEMI/STEMI**: 非ST段抬高心肌梗塞/ST段抬高心肌梗塞。
*   **BMS**: 裸金屬支架 (Bare Metal Stent)。

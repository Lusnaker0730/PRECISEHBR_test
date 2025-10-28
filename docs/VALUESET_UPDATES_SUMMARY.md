# ValueSet 更新摘要 (ValueSet Updates Summary)

## 概述 (Overview)

根據新的臨床需求，我們已經更新了所有相關的 FHIR ValueSet 定義和相應的代碼邏輯，以更準確地識別和分類患者的風險因素。

## 更新的 ValueSet

### 1. 慢性出血性體質 (Bleeding Diathesis)

**文件**: `bleeding_diathesis_valueset.json`

**更新內容**:
- **SNOMED-CT 代碼**: `64779008` (Bleeding diathesis) - 使用父級概念涵蓋所有子集
- **實施方式**: 使用 FHIR filter 語法 `is-a` 來包含所有後代概念
- **代碼邏輯**: `check_bleeding_diathesis_updated()` 函數

**包含的條件**:
- 64779008 - Bleeding diathesis (disorder) 及其所有子概念
- 文本匹配: bleeding disorder, bleeding diathesis, hemorrhagic diathesis, hemophilia, von willebrand, coagulation disorder

### 2. 既往出血史 (Prior Bleeding History)

**文件**: `prior_bleeding_valueset.json`

**更新內容**:
- **多個 SNOMED-CT 父級代碼**: 使用多個特定的出血類型作為父級概念
- **代碼邏輯**: `check_prior_bleeding_updated()` 函數

**包含的 SNOMED-CT 代碼**:
- `74474003` - Gastrointestinal hemorrhage (涵蓋所有子集)
- `50960005` - Hemopericardium (涵蓋所有子集)
- `1386000` - Intracranial hemorrhage (涵蓋所有子集)
- `236002003` - Retroperitoneal hematoma (涵蓋所有子集)
- `443826006` - Hemoperitoneum (涵蓋所有子集)
- `233703007` - Pulmonary hemorrhage (涵蓋所有子集)
- `59282003` - Hemarthrosis (涵蓋所有子集)
- `3298000` - Gross hematuria (涵蓋所有子集)
- `9957009` - Renal hemorrhage (涵蓋所有子集)
- `17338001` - Hemothorax (涵蓋所有子集)

### 3. 肝硬化合併門脈高壓 (Liver Cirrhosis with Portal Hypertension)

**文件**: `portal_hypertension_valueset.json`

**更新內容**:
- **基礎 SNOMED-CT 代碼**: `19943007` (Cirrhosis of liver)
- **額外文本邏輯**: 需要同時滿足肝硬化 AND 以下任一條件
- **代碼邏輯**: `check_liver_cirrhosis_portal_hypertension_updated()` 函數

**必需的額外條件** (文本匹配):
- Ascites (腹水)
- Portal hypertension (門脈高壓)
- Esophageal varices (食道靜脈曲張)
- Hepatic encephalopathy (肝性腦病變)

**邏輯**: 必須同時具備肝硬化診斷 **AND** 至少一個額外條件

### 4. 活動性癌症 (Active Cancer)

**文件**: `cancer_snomed_valueset.json`

**更新內容**:
- **包含**: `363346000` (Malignant neoplastic disease) 及其所有後代
- **排除**: 特定皮膚癌類型
- **狀態要求**: `Condition.clinicalStatus = active`
- **代碼邏輯**: `check_active_cancer_updated()` 函數

**包含條件**:
- 363346000 - Malignant neoplastic disease (涵蓋所有子集)
- 必須具有 `clinicalStatus = active`

**排除條件**:
- `254637007` - Basal cell carcinoma of skin
- `254632001` - Squamous cell carcinoma of skin

## 技術實施詳情

### FHIR ValueSet 結構更新

1. **使用 Filter 語法**: 改用 `is-a` filter 來包含概念層次結構
2. **排除邏輯**: 在 cancer valueset 中實施排除特定概念
3. **擴展參數**: 添加額外的參數說明複雜的邏輯需求

### 代碼邏輯更新

**新增函數**:
- `check_bleeding_diathesis_updated()` - 檢查慢性出血性體質
- `check_prior_bleeding_updated()` - 檢查既往出血史  
- `check_liver_cirrhosis_portal_hypertension_updated()` - 檢查肝硬化合併門脈高壓
- `check_active_cancer_updated()` - 檢查活動性癌症
- `get_condition_text()` - 提取條件的所有文本用於匹配

**更新的主要函數**:
- `check_arc_hbr_factors()` - 使用新的檢查函數
- `calculate_precise_hbr_score()` - 在既往出血史檢查中使用新邏輯

### 匹配邏輯

#### SNOMED-CT 代碼匹配
```python
# 檢查 SNOMED-CT 代碼
for coding in condition.get('code', {}).get('coding', []):
    if (coding.get('system') == 'http://snomed.info/sct' and 
        coding.get('code') in target_codes):
        return True, coding.get('display', 'Found condition')
```

#### 文本匹配
```python
# 檢查文本描述
condition_text = get_condition_text(condition).lower()
for keyword in keywords:
    if keyword in condition_text:
        return True, condition_text
```

#### 臨床狀態檢查 (癌症)
```python
# 檢查臨床狀態
clinical_status = condition.get('clinicalStatus', {})
for coding in clinical_status.get('coding', []):
    if coding.get('system') == 'http://terminology.hl7.org/CodeSystem/condition-clinical':
        status_code = coding.get('code')
        if status_code == 'active':
            # 處理活動性條件
```

#### 複合邏輯 (肝硬化)
```python
# 需要同時滿足兩個條件
has_cirrhosis = check_for_cirrhosis(conditions)
has_additional_criteria = check_for_portal_hypertension_signs(conditions)
return (has_cirrhosis and has_additional_criteria)
```

## 驗證和測試

### 測試案例建議

1. **慢性出血性體質**:
   - 測試 64779008 及其子概念
   - 測試文本匹配 "bleeding disorder", "hemophilia" 等

2. **既往出血史**:
   - 測試各種出血類型的 SNOMED-CT 代碼
   - 測試文本匹配 "hemorrhage", "bleeding" 等

3. **肝硬化合併門脈高壓**:
   - 測試只有肝硬化但無額外條件 (應為 false)
   - 測試肝硬化 + 腹水 (應為 true)
   - 測試肝硬化 + 食道靜脈曲張 (應為 true)

4. **活動性癌症**:
   - 測試活動性惡性腫瘤 (應為 true)
   - 測試非活動性癌症 (應為 false)
   - 測試皮膚基底細胞癌 (應為 false，被排除)

### 日誌監控

所有新函數都包含詳細的日誌記錄，可以監控匹配過程：

```python
logging.info(f"Checking bleeding diathesis: found {result}")
logging.info(f"Prior bleeding check: {found_conditions}")
logging.info(f"Liver cirrhosis check: cirrhosis={has_cirrhosis}, additional={has_additional_criteria}")
logging.info(f"Active cancer check: status={clinical_status}, excluded={is_excluded}")
```

## 向後兼容性

- 保留了原有的檢查函數作為後備
- 新邏輯通過專門的函數實施
- 不會影響現有的 PRECISE-HBR 計算流程

## 部署注意事項

1. **更新 ValueSet 文件**: 確保所有 JSON 文件已更新
2. **測試新邏輯**: 使用已知的測試案例驗證
3. **監控日誌**: 部署後監控匹配結果的準確性
4. **效能考量**: 新的文本匹配邏輯可能略微增加處理時間

---

**更新日期**: 2025-09-29  
**版本**: 2.0  
**狀態**: 已完成並可部署

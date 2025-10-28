# PRECISE-HBR Scope 配置指南

## ❌ 当前问题

**500 错误**: "An error occurred while retrieving patient data from the health record system."

这通常表示 **权限不足** 或 **Scope 配置不正确**。

---

## ✅ 正确的 Scope 配置

### 您的应用需要的完整 Scope：

```
launch
patient/Patient.read
patient/Observation.read
patient/Condition.read
patient/MedicationRequest.read
patient/Procedure.read
fhirUser
openid
profile
online_access
```

### 如果是 User Scopes（用户启动），还需要：

```
user/Patient.read
user/Observation.read
user/Condition.read
user/MedicationRequest.read
user/Procedure.read
```

---

## 🔧 在 EHR 系统中的配置

### Epic (您的截图)

根据您的截图，您需要确保：

#### ✅ Standard Capabilities
- [x] **launch** - SMART Launch 支持
- [x] **profile** - 用户配置文件访问
- [x] **fhirUser** - 用户识别
- [x] **openid** - OpenID Connect

#### ✅ User Product APIs

对于每个 API，您需要勾选：
- [x] **Read** - 读取单个资源
- [x] **Search** - 搜索多个资源

| API | Read | Search | Create | Update |
|-----|------|--------|--------|--------|
| **Patient** | ✅ | ✅ | ❌ | ❌ |
| **Observation** | ✅ | ✅ | ❌ | ❌ |
| **Condition** | ✅ | ✅ | ❌ | ❌ |
| **MedicationRequest** | ✅ | ✅ | ❌ | ❌ |
| **Procedure** | ✅ | ✅ | ❌ | ❌ |

**注意**: 不需要 Create 和 Update 权限，因为这是只读应用。

---

## 🐛 常见问题排查

### 问题 1: 403 Forbidden Error
**症状**: "Access denied. The application may not have permission to access this patient's data."

**原因**: 
- Scope 权限不足
- 未勾选正确的资源类型
- 未勾选 Read 或 Search 权限

**解决方案**:
1. 检查是否勾选了所有 5 个 FHIR 资源（Patient, Observation, Condition, MedicationRequest, Procedure）
2. 确保每个资源都勾选了 **Read** 和 **Search**
3. 重新保存配置并重新启动应用

---

### 问题 2: 401 Unauthorized Error
**症状**: "Authentication failed. Please re-launch the application from your EHR."

**原因**:
- Access Token 过期
- Client ID 配置错误
- 未勾选 `launch` 或 `openid` scope

**解决方案**:
1. 重新从 EHR 启动应用
2. 检查 Client ID 是否正确
3. 确保勾选了 `launch`, `openid`, `fhirUser`, `profile`

---

### 问题 3: 404 Not Found Error
**症状**: "Patient not found in the FHIR server."

**原因**:
- Patient ID 不正确
- 测试患者数据不存在

**解决方案**:
1. 使用正确的测试患者 ID
2. 在 Epic Sandbox 中，使用官方测试患者（如：Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB）

---

### 问题 4: 500 Internal Server Error
**症状**: "An error occurred while retrieving patient data from the health record system."

**可能原因**:
1. **Scope 配置不完整** ⚠️ (最常见)
2. FHIR 服务器内部错误
3. 查询参数不支持
4. 数据格式问题

**解决方案**:

#### Step 1: 检查 Scope 配置
确保在 Epic 应用配置中勾选了所有必要的权限（见上表）。

#### Step 2: 验证测试患者
使用 Epic 官方推荐的测试患者 ID。

#### Step 3: 检查应用日志
查看服务器日志中的详细错误信息：
```bash
# 查看最近的日志
tail -f app.log
```

查找类似这样的错误信息：
- "Error fetching patient resource"
- "Permission denied"
- "Authentication failed"
- "Patient not found"

#### Step 4: 测试 FHIR API 直接访问
使用 Postman 或 curl 测试 FHIR API：

```bash
curl -X GET \
  "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/Patient/{patient-id}" \
  -H "Authorization: Bearer {your-access-token}" \
  -H "Accept: application/fhir+json"
```

---

## 🔍 详细诊断步骤

### 1. 检查浏览器控制台

打开浏览器开发者工具 (F12)，查看：

**Network Tab**:
- 查找 `/api/calculate_risk` 请求
- 查看 **Response** 标签页中的详细错误信息
- 特别注意 `error_type` 和 `details` 字段

**Console Tab**:
- 查找完整的错误堆栈
- 记录错误消息

### 2. 检查服务器日志

如果您有访问服务器的权限：

```bash
# 查看应用日志
grep "Error" app.log | tail -20

# 查找特定患者的错误
grep "patient_id: {YOUR_PATIENT_ID}" app.log
```

### 3. 验证配置

检查您的 `.env` 文件：

```bash
# 必需的环境变量
FLASK_SECRET_KEY=xxxxx
SMART_CLIENT_ID=xxxxx
SMART_REDIRECT_URI=https://your-app-url/callback
```

---

## ✅ 推荐配置流程

### Step 1: 在 Epic App Orchard 中配置

1. 登录 [Epic App Orchard](https://appmarket.epic.com/)
2. 找到您的应用
3. 进入 **App Details** → **API Access**

### Step 2: 配置 Standard Capabilities

勾选以下所有项：
- [x] launch
- [x] profile
- [x] fhirUser
- [x] openid

### Step 3: 配置 User Product APIs

对于以下每个 API，勾选 **Read** 和 **Search**：
- [x] Patient
- [x] Observation
- [x] Condition
- [x] MedicationRequest
- [x] Procedure

### Step 4: 保存并验证

1. 点击 **Save** 保存配置
2. 等待几分钟让配置生效
3. 重新启动应用进行测试

---

## 🧪 测试 Scope 配置

### 测试脚本

创建一个简单的测试页面验证 scope：

```python
# test_scope.py
import requests

def test_fhir_access(base_url, access_token, patient_id):
    """测试 FHIR API 访问权限"""
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/fhir+json'
    }
    
    resources = ['Patient', 'Observation', 'Condition', 'MedicationRequest', 'Procedure']
    
    for resource in resources:
        url = f"{base_url}/{resource}"
        if resource == 'Patient':
            url += f"/{patient_id}"
        else:
            url += f"?patient={patient_id}&_count=1"
        
        print(f"\n测试 {resource}...")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            print(f"✅ {resource}: 成功")
        elif response.status_code == 403:
            print(f"❌ {resource}: 权限不足 (403 Forbidden)")
            print(f"   请检查 scope 配置中是否包含 patient/{resource}.read")
        elif response.status_code == 401:
            print(f"❌ {resource}: 认证失败 (401 Unauthorized)")
            print(f"   Access token 可能已过期")
        else:
            print(f"⚠️  {resource}: {response.status_code} - {response.text[:200]}")

# 使用方法：
# test_fhir_access(
#     base_url="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
#     access_token="your-access-token",
#     patient_id="your-patient-id"
# )
```

---

## 📊 Epic Sandbox 测试患者

### 推荐的测试患者 ID

Epic 提供了这些测试患者用于开发：

| 患者 ID | 姓名 | 特点 |
|---------|------|------|
| `Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB` | Jason Argonaut | 完整的测试数据 |
| `erXuFYUfucBZaryVksYEcMg3` | Nancy Smart | 多个观察值 |
| `eq081-VQEgP8drUUqCWzHfw3` | Derrick Lin | 药物数据 |

使用方法：
1. 在应用中使用这些 Patient ID
2. 或者让 Epic 通过 launch context 自动传递

---

## 🔒 安全最佳实践

### 最小权限原则

只请求应用实际需要的权限：

**PRECISE-HBR 需要**:
- ✅ Patient.read - 获取患者基本信息
- ✅ Observation.read - 获取实验室检查值（Hb, eGFR, WBC, Platelet, Creatinine）
- ✅ Condition.read - 获取诊断（出血史、癌症、肝硬化等）
- ✅ MedicationRequest.read - 获取药物（抗凝剂、NSAIDs、类固醇）
- ✅ Procedure.read - 获取手术史（透析、PCI）

**不需要**:
- ❌ Create 权限 - 只读应用
- ❌ Update 权限 - 只读应用
- ❌ Delete 权限 - 只读应用
- ❌ 其他资源类型（如 Encounter, AllergyIntolerance 等）

---

## 🆘 仍然无法解决？

### 收集诊断信息

请提供以下信息以便进一步诊断：

1. **浏览器控制台完整错误**:
   - Network 标签中 `/api/calculate_risk` 的完整 Response
   - Console 标签中的错误堆栈

2. **服务器日志**:
   ```bash
   grep "Error" app.log | tail -50
   ```

3. **配置信息**:
   - Epic 应用 ID
   - 勾选的 Scope（截图）
   - 使用的测试患者 ID

4. **FHIR 端点**:
   - FHIR Base URL
   - Authorization Endpoint
   - Token Endpoint

### 联系支持

- **Epic 支持**: 通过 App Orchard 提交支持票
- **GitHub Issues**: 在项目仓库中创建 issue
- **社区论坛**: FHIR Zulip Chat, HL7 FHIR Chat

---

## 📝 配置检查清单

使用这个清单确保所有配置正确：

### Epic 应用配置
- [ ] Client ID 已配置
- [ ] Redirect URI 已配置（精确匹配，包括 https://）
- [ ] 勾选了 `launch`
- [ ] 勾选了 `profile`
- [ ] 勾选了 `fhirUser`
- [ ] 勾选了 `openid`

### FHIR 资源权限
- [ ] Patient: Read + Search
- [ ] Observation: Read + Search
- [ ] Condition: Read + Search
- [ ] MedicationRequest: Read + Search
- [ ] Procedure: Read + Search

### 环境变量
- [ ] `FLASK_SECRET_KEY` 已设置
- [ ] `SMART_CLIENT_ID` 已设置
- [ ] `SMART_REDIRECT_URI` 已设置

### 应用测试
- [ ] 可以从 EHR 成功启动
- [ ] OAuth 授权流程完成
- [ ] Access Token 已获取
- [ ] 患者上下文已传递

---

## 🎯 快速修复建议

### 最可能的解决方案：

**如果您看到 500 错误，90% 的情况下是因为**:

1. **Scope 不完整** → 检查是否所有 5 个资源都勾选了 Read 和 Search
2. **Token 过期** → 重新从 EHR 启动应用
3. **Patient ID 错误** → 使用 Epic 官方测试患者

**立即尝试**:
1. 在 Epic App Orchard 中，确认 **所有 5 个 User Product APIs** 都勾选了 **Read** 和 **Search**
2. **保存配置**
3. **等待 5 分钟**让配置生效
4. **重新从 EHR 启动应用**（不是刷新页面，而是重新 launch）
5. 使用 Epic 推荐的测试患者 ID

---

**最后更新**: 2025年10月7日  
**适用版本**: PRECISE-HBR v1.0+  
**EHR 系统**: Epic (适用于大多数 SMART on FHIR 实现)


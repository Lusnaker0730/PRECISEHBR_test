# Docker 部署指南

## 📋 目录

1. [快速开始](#快速开始)
2. [开发环境](#开发环境)
3. [生产环境](#生产环境)
4. [配置说明](#配置说明)
5. [常见问题](#常见问题)

---

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 1.29+

### 安装 Docker

**Windows/Mac:**
下载并安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

---

## 💻 开发环境

### 1. 配置环境变量

```bash
# 复制环境变量模板
cp .env.docker.template .env

# 编辑 .env 文件，填入你的配置
nano .env  # 或使用其他编辑器
```

**必须配置的变量：**
```env
FLASK_SECRET_KEY=<生成安全密钥>
SMART_CLIENT_ID=<你的客户端ID>
SMART_CLIENT_SECRET=<你的客户端密钥>
SMART_REDIRECT_URI=http://localhost:8080/callback
```

**生成安全密钥：**
```bash
# 方法1：使用 openssl
openssl rand -base64 32

# 方法2：使用 python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. 构建并启动容器

```bash
# 构建 Docker 镜像
docker-compose build

# 启动容器（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f smart-app
```

### 3. 访问应用

打开浏览器访问：
- **应用主页：** http://localhost:8080
- **健康检查：** http://localhost:8080/health
- **CDS Services：** http://localhost:8080/cds-services

### 4. 停止容器

```bash
# 停止容器
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

---

## 🏭 生产环境

### 1. 准备生产配置

```bash
# 复制生产环境模板
cp production.env.template production.env

# 编辑生产环境配置
nano production.env
```

**生产环境必须配置：**
```env
FLASK_ENV=production
FLASK_SECRET_KEY=<强密钥>
SMART_CLIENT_ID=<生产客户端ID>
SMART_CLIENT_SECRET=<生产客户端密钥>
SMART_REDIRECT_URI=https://your-domain.com/callback
SMART_EHR_BASE_URL=<生产FHIR服务器>
```

### 2. 使用生产配置启动

```bash
# 使用生产配置构建和启动
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 查看状态
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

### 3. 健康检查

```bash
# 检查容器健康状态
docker ps

# 测试健康检查端点
curl http://localhost:8080/health
```

### 4. 生产环境最佳实践

**使用 HTTPS：**
- 配置 Nginx 反向代理
- 使用 Let's Encrypt SSL 证书
- 启用 HSTS

**安全配置：**
- 使用强密钥
- 启用 CSRF 保护
- 配置适当的 CORS 策略
- 限制资源访问

**监控和日志：**
- 配置日志轮转
- 设置资源限制
- 监控容器健康状态

---

## ⚙️ 配置说明

### Docker Compose 文件

**docker-compose.yml** - 基础配置（开发环境）
```yaml
services:
  smart-app:
    build: .
    ports:
      - "8080:8080"
    env_file:
      - .env
    volumes:
      - .:/app  # 挂载代码以支持热重载
```

**docker-compose.prod.yml** - 生产覆盖配置
```yaml
services:
  smart-app:
    env_file:
      - production.env
    volumes: []  # 不挂载代码
    restart: always  # 自动重启
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```

### Dockerfile 说明

```dockerfile
FROM python:3.11-slim          # 使用轻量级基础镜像
WORKDIR /app                   # 设置工作目录
COPY requirements.txt .        # 先复制依赖文件
RUN pip install --no-cache-dir -r requirements.txt  # 安装依赖
COPY . .                       # 复制应用代码
EXPOSE 8080                    # 声明端口
CMD ["gunicorn", "-b", ":8080", "--timeout", "120", "APP:app"]
```

### 环境变量说明

| 变量名 | 说明 | 必需 | 默认值 |
|--------|------|------|--------|
| `FLASK_ENV` | Flask 环境 | 是 | development |
| `FLASK_SECRET_KEY` | Flask 密钥 | 是 | - |
| `SMART_CLIENT_ID` | SMART 客户端 ID | 是 | - |
| `SMART_CLIENT_SECRET` | SMART 客户端密钥 | 是 | - |
| `SMART_REDIRECT_URI` | OAuth 回调 URI | 是 | - |
| `SMART_EHR_BASE_URL` | FHIR 服务器 URL | 是 | - |
| `LOG_LEVEL` | 日志级别 | 否 | INFO |
| `TESTING` | 测试模式 | 否 | false |

---

## 🔧 常用命令

### 查看容器状态
```bash
docker-compose ps
docker-compose logs smart-app
docker-compose logs -f smart-app  # 实时日志
```

### 进入容器
```bash
docker-compose exec smart-app bash
docker-compose exec smart-app python
```

### 重启服务
```bash
docker-compose restart smart-app
```

### 重新构建
```bash
docker-compose build --no-cache
docker-compose up -d --force-recreate
```

### 清理资源
```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi smart_fhir_app_smart-app

# 清理未使用的镜像和容器
docker system prune -a
```

---

## 🐛 常见问题

### 1. 端口已被占用

**错误：** `Error: port is already allocated`

**解决：**
```bash
# 查找占用 8080 端口的进程
lsof -i :8080  # Mac/Linux
netstat -ano | findstr :8080  # Windows

# 修改 docker-compose.yml 中的端口
ports:
  - "8081:8080"  # 使用不同的主机端口
```

### 2. 权限问题

**错误：** `Permission denied`

**解决：**
```bash
# Linux 添加用户到 docker 组
sudo usermod -aG docker $USER
newgrp docker

# 或使用 sudo
sudo docker-compose up
```

### 3. 容器无法连接到 FHIR 服务器

**检查：**
1. 确认 `SMART_EHR_BASE_URL` 配置正确
2. 检查网络连接
3. 查看容器日志

```bash
docker-compose logs smart-app | grep -i error
```

### 4. 环境变量未生效

**解决：**
```bash
# 重新构建容器
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 验证环境变量
docker-compose exec smart-app env | grep FLASK
```

### 5. 代码更改未反映

**开发环境：**
- 检查 `volumes` 配置是否正确
- 重启容器：`docker-compose restart`

**生产环境：**
- 需要重新构建镜像：
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📊 监控和维护

### 查看资源使用

```bash
# 查看容器资源使用
docker stats smart_fhir_app

# 查看容器详细信息
docker inspect smart_fhir_app
```

### 日志管理

```bash
# 查看最近 100 行日志
docker-compose logs --tail=100 smart-app

# 导出日志
docker-compose logs smart-app > app.log
```

### 备份和恢复

```bash
# 备份容器
docker commit smart_fhir_app smart_fhir_app:backup

# 导出镜像
docker save smart_fhir_app:backup -o backup.tar

# 导入镜像
docker load -i backup.tar
```

---

## 🚀 高级配置

### 使用 Docker Swarm

```bash
# 初始化 Swarm
docker swarm init

# 部署服务栈
docker stack deploy -c docker-compose.yml -c docker-compose.prod.yml smart-fhir

# 查看服务
docker service ls
docker service logs smart-fhir_smart-app
```

### 使用 Kubernetes

参考 `.github/workflows/` 中的 Kubernetes 部署配置。

---

## 📚 相关文档

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [项目 CI/CD 文档](README_CI_CD.md)
- [部署指南](docs/deployment/)

---

## 🆘 需要帮助？

- 查看[项目文档](docs/)
- 提交 [GitHub Issue](https://github.com/Lusnaker0730/smart_fhir_app/issues)
- 联系开发团队

---

**最后更新：** 2025年10月


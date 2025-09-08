# --- STAGE 1: Builder ---
# This stage installs build dependencies and Python packages
FROM python:3.11-slim as builder

# 優化：建議固定基礎映像的版本以確保可重現性
# 例如：FROM python:3.11.9-slim-bookworm@sha256:....

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 (僅用於建置)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix="/install" -r requirements.txt

# --- STAGE 2: Final Image ---
# This stage creates the final, lean production image
FROM python:3.11-slim

# 優化：建議固定基礎映像的版本以確保可重現性
# 例如：FROM python:3.11.9-slim-bookworm@sha256:....

# 設定工作目錄
WORKDIR /app

# 創建非 root 使用者
RUN useradd --create-home --shell /bin/bash app

# 從 builder 階段複製已安裝的套件
COPY --from=builder /install /usr/local

# 複製應用程式代碼
COPY --chown=app:app . .

# 設定環境變數
ENV FLASK_APP=APP.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# 切換到非 root 使用者
USER app

# 暴露端口
EXPOSE 8080

# 健康檢查 (現在 APP.py 中有 /health 端點了)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 使用 Gunicorn 運行應用程式
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "APP:app"] 
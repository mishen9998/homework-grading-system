FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# 安装依赖（利用层缓存）
COPY requirements.txt requirements-embeddings.txt ./
ARG INSTALL_EMBEDDINGS=false
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_EMBEDDINGS" = "true" ]; then pip install --no-cache-dir -r requirements-embeddings.txt; fi

COPY . .

# 持久化目录由 docker-compose 挂载
VOLUME ["/app/instance", "/app/app/tupian", "/app/app/uploads", "/app/logs"]

EXPOSE 5000

# 生产使用 gunicorn，长超时兼容 AI 批改请求
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "120", "run:app"]

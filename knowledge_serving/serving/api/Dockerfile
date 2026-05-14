# KS-CD-003 · diyu-serving 容器镜像 / sidecar serving container image
#
# 红线 / red lines（不可变更）：
#  1. 只 COPY knowledge_serving/ 子树 + requirements.txt；禁止 COPY . . / COPY src/ / COPY diyu-agent/
#  2. 最终 USER 非 root（least-privilege）
#  3. 默认端口 8000（宿主侧 -p 127.0.0.1:8005:8000 映射，与既有 diyu-agent:8004 隔离）
#  4. 不带任何 secret；env 在 docker run --env-file /opt/diyu-serving/.env 注入

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# 系统层：仅装运行 psycopg2 / httpx 必需 libs；不装 build tools
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1: 依赖（缓存友好）
COPY knowledge_serving/serving/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Layer 2: 业务代码 —— 只 COPY knowledge_serving/ 子树
# T-S1 守门：本指令源路径必须以 knowledge_serving/ 开头
COPY knowledge_serving/ /app/knowledge_serving/

# Layer 3: 非 root 用户
RUN groupadd -r serving --gid 10001 \
 && useradd -r -g serving --uid 10001 --home-dir /app --shell /sbin/nologin serving \
 && chown -R serving:serving /app

USER serving

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["uvicorn", "knowledge_serving.serving.api.retrieve_context:app", \
            "--host", "0.0.0.0", "--port", "8000", \
            "--proxy-headers", "--forwarded-allow-ips=*"]

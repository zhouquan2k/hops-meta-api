FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai 

# 安装基本工具和Oracle客户端依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libaio1 \
    wget \
    unzip \
    gcc \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

COPY requirements.txt .
RUN pip install --proxy=http://proxy.my:11081 --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 添加入口点脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# 切换到api目录作为工作目录
WORKDIR /app/api

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers", "4", "--timeout", "120"] 
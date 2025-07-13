FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# 安装基本工具和Oracle客户端依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    vim \
    libaio1 \
    wget \
    unzip \
    gcc \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Oracle即时客户端 (19.3.0.0.0，兼容Oracle 11g)
RUN mkdir -p /opt/oracle
WORKDIR /opt/oracle
RUN wget https://download.oracle.com/otn_software/linux/instantclient/193000/instantclient-basic-linux.x64-19.3.0.0.0dbru.zip -O instantclient.zip && \
    wget https://download.oracle.com/otn_software/linux/instantclient/193000/instantclient-sdk-linux.x64-19.3.0.0.0dbru.zip -O instantclient-sdk.zip && \
    unzip instantclient.zip && \
    unzip instantclient-sdk.zip && \
    rm instantclient.zip instantclient-sdk.zip && \
    cd /opt/oracle/instantclient_19_3 && \
    rm -f libclntsh.so libocci.so && \
    ln -s libclntsh.so.19.1 libclntsh.so && \
    ln -s libocci.so.19.1 libocci.so && \
    echo /opt/oracle/instantclient_19_3 > /etc/ld.so.conf.d/oracle-instantclient.conf && \
    ldconfig

# 设置Oracle环境变量
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_19_3:$LD_LIBRARY_PATH \
    ORACLE_HOME=/opt/oracle/instantclient_19_3 \
    NLS_LANG=AMERICAN_AMERICA.AL32UTF8 \
    PATH=$PATH:/opt/oracle/instantclient_19_3

WORKDIR /app

# 安装Python开发工具
RUN pip install --no-cache-dir \
    ipython \
    pytest \
    black \
    flake8 \
    mypy \
    isort \
    cx_Oracle==7.3.0 \
    pandas==2.0.3 \
    markdown==3.4.3 \
    numpy==1.24.3

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# VS Code运行所需用户设置
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# 创建非root用户（VSCode推荐）
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# 创建测试Oracle连接的脚本
RUN echo '#!/bin/bash\n\
    echo "Oracle客户端版本检查:"\n\
    ls -la $ORACLE_HOME\n\
    echo "Python版本:"\n\
    python --version\n\
    echo "cx_Oracle版本:"\n\
    python -c "import cx_Oracle; print(cx_Oracle.version)"\n\
    ' > /usr/local/bin/check_oracle.sh && chmod +x /usr/local/bin/check_oracle.sh

# 容器启动命令
CMD ["sleep", "infinity"] 
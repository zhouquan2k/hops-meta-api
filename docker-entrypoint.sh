#!/bin/bash
set -e

# 打印环境信息
echo "容器启动中..."
echo "Python版本: $(python --version)"
echo "Flask版本: $(pip show flask | grep Version)"
echo "时区设置为: $TZ"

# 显示代理设置
if [ -n "$HTTP_PROXY" ]; then
  echo "HTTP代理已配置: $HTTP_PROXY"
fi
if [ -n "$HTTPS_PROXY" ]; then
  echo "HTTPS代理已配置: $HTTPS_PROXY"
fi

# 执行传入的命令
exec "$@" 
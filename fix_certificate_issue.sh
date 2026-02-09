#!/bin/bash
# 修复 OpenCode 技能加载证书问题
# 使用方法: source fix_certificate_issue.sh 或 ./fix_certificate_issue.sh

echo "🔧 修复 OpenCode 技能加载证书问题"
echo "=================================="

# 方法1: 设置 Python SSL 环境变量
echo "1. 设置 Python SSL 环境变量..."
export PYTHONHTTPSVERIFY=0
export SSL_CERT_FILE="/Users/felix/miniconda3/envs/stock_env_cpython/ssl/cert.pem"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"

# 方法2: 设置 Node.js SSL 环境变量 (如果 OpenCode 使用 Node.js)
echo "2. 设置 Node.js SSL 环境变量..."
export NODE_TLS_REJECT_UNAUTHORIZED=0
export NODE_EXTRA_CA_CERTS="$SSL_CERT_FILE"

# 方法3: 更新 conda 证书包
echo "3. 更新 conda 证书包..."
conda install -y -n stock_env_cpython certifi ca-certificates openssl 2>/dev/null || echo "⚠️  conda 更新失败或跳过"

# 方法4: 创建 Python 修复脚本
echo "4. 创建 Python SSL 修复脚本..."
cat > /tmp/fix_ssl.py << 'EOF'
import ssl
import os
import certifi

# 禁用 SSL 验证 (不安全，仅用于开发)
ssl._create_default_https_context = ssl._create_unverified_context

# 设置证书路径
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

print(f"✅ SSL 证书路径设置为: {certifi.where()}")
print("⚠️  注意: SSL 验证已禁用，仅用于开发环境")
EOF

# 检查证书文件
echo "5. 检查证书文件..."
if [ -f "$SSL_CERT_FILE" ]; then
    echo "✅ 证书文件存在: $SSL_CERT_FILE"
else
    echo "❌ 证书文件不存在: $SSL_CERT_FILE"
    echo "   尝试重新安装 certifi: pip install --upgrade certifi"
fi

# 显示当前环境变量
echo ""
echo "📋 当前环境变量设置:"
echo "   PYTHONHTTPSVERIFY=$PYTHONHTTPSVERIFY"
echo "   SSL_CERT_FILE=$SSL_CERT_FILE"
echo "   REQUESTS_CA_BUNDLE=$REQUESTS_CA_BUNDLE"
echo "   NODE_TLS_REJECT_UNAUTHORIZED=$NODE_TLS_REJECT_UNAUTHORIZED"
echo ""
echo "💡 使用方法:"
echo "   1. 在当前终端运行: source fix_certificate_issue.sh"
echo "   2. 重新启动 OpenCode 会话"
echo "   3. 如果问题仍然存在，尝试重启终端"
echo ""
echo "⚠️  注意: 禁用 SSL 验证存在安全风险，仅建议在开发环境中使用。"
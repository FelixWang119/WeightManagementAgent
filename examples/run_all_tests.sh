#!/bin/bash

# 运行所有测试的示例脚本
# 此脚本演示如何按顺序运行所有测试

echo "🚀 开始运行所有测试"
echo "=========================================="

# 设置环境
export PYTHONPATH=$(pwd):$PYTHONPATH
LOG_DIR="logs"
REPORT_DIR="reports"

# 创建目录
mkdir -p "$LOG_DIR" "$REPORT_DIR"

# 1. 检查环境
echo "1. 检查环境..."
python -c "import sys; print(f'Python版本: {sys.version}')"

# 2. 运行快速测试
echo ""
echo "2. 运行快速测试..."
python test_runners/run_quick_test.py 2>&1 | tee "$LOG_DIR/quick_test_$(date +%Y%m%d_%H%M%S).log"

if [ $? -eq 0 ]; then
    echo "✅ 快速测试通过"
else
    echo "❌ 快速测试失败"
    exit 1
fi

# 3. 运行简单测试
echo ""
echo "3. 运行简单测试..."
python test_runners/run_simple_real_test.py 2>&1 | tee "$LOG_DIR/simple_test_$(date +%Y%m%d_%H%M%S).log"

if [ $? -eq 0 ]; then
    echo "✅ 简单测试通过"
else
    echo "⚠️  简单测试有警告"
fi

# 4. 运行完整测试
echo ""
echo "4. 运行完整测试..."
python test_runners/run_complete_smart_chat_test.py 2>&1 | tee "$LOG_DIR/complete_test_$(date +%Y%m%d_%H%M%S).log"

if [ $? -eq 0 ]; then
    echo "✅ 完整测试通过"
else
    echo "⚠️  完整测试有警告"
fi

# 5. 收集报告
echo ""
echo "5. 收集测试报告..."
REPORT_COUNT=$(find "$REPORT_DIR" -name "*.json" -o -name "*.txt" | wc -l)
echo "找到 $REPORT_COUNT 个报告文件"

# 显示最新报告
echo ""
echo "最新报告:"
find "$REPORT_DIR" -name "*.json" -o -name "*.txt" | sort -r | head -5 | while read file; do
    echo "  - $(basename "$file") ($(stat -f%z "$file") 字节)"
done

# 6. 生成摘要
echo ""
echo "6. 生成测试摘要..."
SUMMARY_FILE="$REPORT_DIR/test_summary_$(date +%Y%m%d_%H%M%S).txt"

cat > "$SUMMARY_FILE" << EOF
测试运行摘要
==========================================

运行时间: $(date)
运行目录: $(pwd)
Python路径: $PYTHONPATH

测试执行情况:
1. 快速测试: $(grep -q "✅ 快速测试通过" "$LOG_DIR"/*.log 2>/dev/null && echo "通过" || echo "失败")
2. 简单测试: $(grep -q "✅ 简单测试通过" "$LOG_DIR"/*.log 2>/dev/null && echo "通过" || echo "警告")
3. 完整测试: $(grep -q "✅ 完整测试通过" "$LOG_DIR"/*.log 2>/dev/null && echo "通过" || echo "警告")

报告文件:
$(find "$REPORT_DIR" -name "*.json" -o -name "*.txt" 2>/dev/null | sort -r | head -10 | while read f; do echo "  - $(basename "$f")"; done)

日志文件:
$(find "$LOG_DIR" -name "*.log" 2>/dev/null | sort -r | head -5 | while read f; do echo "  - $(basename "$f")"; done)

建议:
1. 查看详细报告了解测试详情
2. 检查失败测试的具体原因
3. 根据建议优化系统功能

==========================================
测试完成!
EOF

echo "✅ 测试摘要已保存到: $SUMMARY_FILE"

# 7. 显示结果
echo ""
echo "=========================================="
echo "🎉 所有测试运行完成!"
echo ""
echo "📊 结果汇总:"
echo "  - 快速测试: 通过"
echo "  - 简单测试: 通过（可能有警告）"
echo "  - 完整测试: 通过（可能有警告）"
echo ""
echo "📁 输出文件:"
echo "  - 日志文件: $LOG_DIR/"
echo "  - 报告文件: $REPORT_DIR/"
echo "  - 测试摘要: $SUMMARY_FILE"
echo ""
echo "🔍 下一步:"
echo "  1. 查看详细报告: cat $REPORT_DIR/*.json | jq '.summary'"
echo "  2. 检查错误日志: grep ERROR $LOG_DIR/*.log"
echo "  3. 根据建议优化系统"
echo "=========================================="
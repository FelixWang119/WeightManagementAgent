#!/bin/bash

# 清理日志文件的示例脚本
# 此脚本演示如何安全地清理旧日志文件

echo "🧹 开始清理日志文件"
echo "=========================================="

LOG_DIR="logs"
REPORT_DIR="reports"
BACKUP_DIR="backups"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 1. 显示当前状态
echo "1. 显示当前状态..."
echo ""
echo "日志目录 ($LOG_DIR):"
find "$LOG_DIR" -name "*.log" -type f 2>/dev/null | wc -l | xargs echo "  日志文件数量:"
du -sh "$LOG_DIR" 2>/dev/null | awk '{print "  总大小: "$1}'

echo ""
echo "报告目录 ($REPORT_DIR):"
find "$REPORT_DIR" -name "*.json" -o -name "*.txt" 2>/dev/null | wc -l | xargs echo "  报告文件数量:"
du -sh "$REPORT_DIR" 2>/dev/null | awk '{print "  总大小: "$1}'

# 2. 备份重要文件
echo ""
echo "2. 备份重要文件..."
BACKUP_FILE="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).tar.gz"

# 备份最近7天的日志和报告
find "$LOG_DIR" -name "*.log" -mtime -7 2>/dev/null > /tmp/files_to_backup.txt
find "$REPORT_DIR" -name "*.json" -o -name "*.txt" -mtime -7 2>/dev/null >> /tmp/files_to_backup.txt

if [ -s /tmp/files_to_backup.txt ]; then
    echo "  备份最近7天的文件..."
    tar -czf "$BACKUP_FILE" -T /tmp/files_to_backup.txt 2>/dev/null
    BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || echo "0")
    echo "  ✅ 备份完成: $BACKUP_FILE ($((BACKUP_SIZE/1024)) KB)"
else
    echo "  ⚠️  没有需要备份的文件"
fi

# 3. 清理旧日志文件（保留最近30天）
echo ""
echo "3. 清理旧日志文件（保留最近30天）..."
OLD_LOG_COUNT=$(find "$LOG_DIR" -name "*.log" -mtime +30 2>/dev/null | wc -l)

if [ "$OLD_LOG_COUNT" -gt 0 ]; then
    echo "  找到 $OLD_LOG_COUNT 个30天前的日志文件"
    
    # 显示将要删除的文件
    if [ "$OLD_LOG_COUNT" -le 10 ]; then
        echo "  将要删除的文件:"
        find "$LOG_DIR" -name "*.log" -mtime +30 2>/dev/null | while read file; do
            echo "    - $(basename "$file") ($(stat -f%z "$file" 2>/dev/null || echo "0") 字节)"
        done
    else
        echo "  将要删除 $OLD_LOG_COUNT 个文件（显示前10个）:"
        find "$LOG_DIR" -name "*.log" -mtime +30 2>/dev/null | head -10 | while read file; do
            echo "    - $(basename "$file")"
        done
        echo "    ... 还有 $((OLD_LOG_COUNT - 10)) 个文件"
    fi
    
    # 确认删除
    read -p "  是否确认删除这些文件？ (y/N): " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null
        echo "  ✅ 已删除 $OLD_LOG_COUNT 个旧日志文件"
    else
        echo "  ⚠️  跳过删除操作"
    fi
else
    echo "  ✅ 没有30天前的日志文件需要清理"
fi

# 4. 清理旧报告文件（保留最近14天）
echo ""
echo "4. 清理旧报告文件（保留最近14天）..."
OLD_REPORT_COUNT=$(find "$REPORT_DIR" -name "*.json" -o -name "*.txt" -mtime +14 2>/dev/null | wc -l)

if [ "$OLD_REPORT_COUNT" -gt 0 ]; then
    echo "  找到 $OLD_REPORT_COUNT 个14天前的报告文件"
    
    # 确认删除
    read -p "  是否确认删除这些报告文件？ (y/N): " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        find "$REPORT_DIR" -name "*.json" -o -name "*.txt" -mtime +14 -delete 2>/dev/null
        echo "  ✅ 已删除 $OLD_REPORT_COUNT 个旧报告文件"
    else
        echo "  ⚠️  跳过删除操作"
    fi
else
    echo "  ✅ 没有14天前的报告文件需要清理"
fi

# 5. 清理空目录
echo ""
echo "5. 清理空目录..."
find "$LOG_DIR" "$REPORT_DIR" -type d -empty 2>/dev/null | while read dir; do
    if [ "$(basename "$dir")" != ".gitkeep" ]; then
        echo "  删除空目录: $dir"
        rmdir "$dir" 2>/dev/null
    fi
done

# 6. 显示清理后状态
echo ""
echo "6. 清理后状态..."
echo ""
echo "日志目录 ($LOG_DIR):"
find "$LOG_DIR" -name "*.log" -type f 2>/dev/null | wc -l | xargs echo "  剩余日志文件数量:"
du -sh "$LOG_DIR" 2>/dev/null | awk '{print "  剩余大小: "$1}'

echo ""
echo "报告目录 ($REPORT_DIR):"
find "$REPORT_DIR" -name "*.json" -o -name "*.txt" 2>/dev/null | wc -l | xargs echo "  剩余报告文件数量:"
du -sh "$REPORT_DIR" 2>/dev/null | awk '{print "  剩余大小: "$1}'

echo ""
echo "备份目录 ($BACKUP_DIR):"
find "$BACKUP_DIR" -name "*.tar.gz" -type f 2>/dev/null | wc -l | xargs echo "  备份文件数量:"
du -sh "$BACKUP_DIR" 2>/dev/null | awk '{print "  备份大小: "$1}'

# 7. 生成清理报告
echo ""
echo "7. 生成清理报告..."
CLEANUP_REPORT="$BACKUP_DIR/cleanup_report_$(date +%Y%m%d_%H%M%S).txt"

cat > "$CLEANUP_REPORT" << EOF
日志清理报告
==========================================

清理时间: $(date)
清理目录: $(pwd)

清理操作:
1. 备份最近7天的文件: $BACKUP_FILE
2. 删除30天前的日志文件: $OLD_LOG_COUNT 个
3. 删除14天前的报告文件: $OLD_REPORT_COUNT 个

清理后状态:
- 日志目录: $(find "$LOG_DIR" -name "*.log" -type f 2>/dev/null | wc -l) 个文件
- 报告目录: $(find "$REPORT_DIR" -name "*.json" -o -name "*.txt" 2>/dev/null | wc -l) 个文件
- 备份目录: $(find "$BACKUP_DIR" -name "*.tar.gz" -type f 2>/dev/null | wc -l) 个备份

建议:
1. 定期运行此脚本清理旧文件
2. 重要报告手动备份
3. 监控磁盘使用情况

==========================================
清理完成!
EOF

echo "✅ 清理报告已保存到: $CLEANUP_REPORT"

# 8. 显示总结
echo ""
echo "=========================================="
echo "🎉 日志清理完成!"
echo ""
echo "📊 清理统计:"
echo "  - 备份文件: 1 个 ($((BACKUP_SIZE/1024)) KB)"
echo "  - 删除日志: $OLD_LOG_COUNT 个"
echo "  - 删除报告: $OLD_REPORT_COUNT 个"
echo ""
echo "📁 当前状态:"
echo "  - 日志文件: $(find "$LOG_DIR" -name "*.log" -type f 2>/dev/null | wc -l) 个"
echo "  - 报告文件: $(find "$REPORT_DIR" -name "*.json" -o -name "*.txt" 2>/dev/null | wc -l) 个"
echo ""
echo "🔍 下一步:"
echo "  1. 检查备份文件: ls -la $BACKUP_DIR/"
echo "  2. 查看清理报告: cat $CLEANUP_REPORT"
echo "  3. 设置定期清理: 添加此脚本到crontab"
echo "=========================================="

# 清理临时文件
rm -f /tmp/files_to_backup.txt
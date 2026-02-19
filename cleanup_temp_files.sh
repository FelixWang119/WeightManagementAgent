#!/bin/bash
# 体重管理助手 - 临时文件清理脚本
# 适用于 v1.1.0 版本整理

set -e

echo "================================"
echo "体重管理助手 - 临时文件清理工具"
echo "版本: v1.1.0"
echo "================================"
echo ""

# 项目根目录
PROJECT_DIR="/Users/felix/open_workdspace"
cd "$PROJECT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 统计变量
DELETED_COUNT=0
ARCHIVED_COUNT=0

# 1. 清理 temp/ 目录中的测试文件
echo -e "${BLUE}[1/6] 清理 temp/ 测试目录...${NC}"
if [ -d "temp/" ]; then
    FILE_COUNT=$(find temp/ -type f | wc -l)
    echo "  发现 $FILE_COUNT 个测试文件"
    
    # 创建归档目录
    ARCHIVE_DIR="docs/archive/temp_files_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$ARCHIVE_DIR"
    
    # 移动temp目录到归档
    mv temp/ "$ARCHIVE_DIR/"
    echo -e "  ${GREEN}✓ temp/ 目录已归档到: $ARCHIVE_DIR${NC}"
    ARCHIVED_COUNT=$((ARCHIVED_COUNT + 1))
else
    echo -e "  ${YELLOW}⚠ temp/ 目录不存在，跳过${NC}"
fi
echo ""

# 2. 清理测试数据库文件
echo -e "${BLUE}[2/6] 清理测试数据库文件...${NC}"
TEST_DBS=$(find . -maxdepth 1 -name "test_*.db" -type f 2>/dev/null || true)
if [ ! -z "$TEST_DBS" ]; then
    echo "$TEST_DBS" | while read -r db_file; do
        if [ ! -z "$db_file" ]; then
            rm -f "$db_file"
            echo -e "  ${GREEN}✓ 删除: $db_file${NC}"
            DELETED_COUNT=$((DELETED_COUNT + 1))
        fi
    done
else
    echo -e "  ${YELLOW}⚠ 未发现测试数据库文件${NC}"
fi
echo ""

# 3. 清理备份数据库文件
echo -e "${BLUE}[3/6] 清理数据库备份文件...${NC}"
BACKUP_DBS=$(find . -maxdepth 1 -name "weight_management.db.backup.*" -type f 2>/dev/null || true)
if [ ! -z "$BACKUP_DBS" ]; then
    echo "$BACKUP_DBS" | while read -r db_file; do
        if [ ! -z "$db_file" ]; then
            rm -f "$db_file"
            echo -e "  ${GREEN}✓ 删除: $db_file${NC}"
            DELETED_COUNT=$((DELETED_COUNT + 1))
        fi
    done
else
    echo -e "  ${YELLOW}⚠ 未发现数据库备份文件${NC}"
fi
echo ""

# 4. 清理测试结果文件
echo -e "${BLUE}[4/6] 清理测试结果文件...${NC}"
TEST_RESULTS=$(find . -maxdepth 1 -name "20_day_test_results_*.json" -type f 2>/dev/null || true)
if [ ! -z "$TEST_RESULTS" ]; then
    echo "$TEST_RESULTS" | while read -r result_file; do
        if [ ! -z "$result_file" ]; then
            rm -f "$result_file"
            echo -e "  ${GREEN}✓ 删除: $result_file${NC}"
            DELETED_COUNT=$((DELETED_COUNT + 1))
        fi
    done
else
    echo -e "  ${YELLOW}⚠ 未发现测试结果文件${NC}"
fi
echo ""

# 5. 归档测试总结文档
echo -e "${BLUE}[5/6] 归档测试总结文档...${NC}"
TEST_DOCS=("smart_chat_test_implementation_summary.md" "agent_comparison_report.md")
for doc in "${TEST_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        ARCHIVE_SUBDIR="docs/archive/test_docs_$(date +%Y%m%d)"
        mkdir -p "$ARCHIVE_SUBDIR"
        mv "$doc" "$ARCHIVE_SUBDIR/"
        echo -e "  ${GREEN}✓ 归档: $doc → $ARCHIVE_SUBDIR/${NC}"
        ARCHIVED_COUNT=$((ARCHIVED_COUNT + 1))
    fi
done
echo ""

# 6. 清理临时HTML测试文件
echo -e "${BLUE}[6/6] 清理临时HTML测试文件...${NC}"
TEST_HTML=$(find . -maxdepth 1 -name "test_*.html" -type f 2>/dev/null || true)
if [ ! -z "$TEST_HTML" ]; then
    echo "$TEST_HTML" | while read -r html_file; do
        if [ ! -z "$html_file" ]; then
            rm -f "$html_file"
            echo -e "  ${GREEN}✓ 删除: $html_file${NC}"
            DELETED_COUNT=$((DELETED_COUNT + 1))
        fi
    done
else
    echo -e "  ${YELLOW}⚠ 未发现临时HTML文件${NC}"
fi
echo ""

# 总结
echo "================================"
echo -e "${GREEN}清理完成！${NC}"
echo "================================"
echo ""
echo -e "${GREEN}已删除文件: $DELETED_COUNT 个${NC}"
echo -e "${BLUE}已归档目录/文件: $ARCHIVED_COUNT 个${NC}"
echo ""

if [ $DELETED_COUNT -gt 0 ] || [ $ARCHIVED_COUNT -gt 0 ]; then
    echo -e "${GREEN}✓ 项目已整理完毕！${NC}"
    echo ""
    echo "保留的有用工具:"
    echo "  - create_test_users.py - 创建测试用户"
    echo "  - check_users.py - 检查和清理用户"
    echo "  - docs/PRD_v1.1.0.md - 产品需求文档"
    echo ""
    echo "归档的内容在 docs/archive/ 目录下"
else
    echo -e "${YELLOW}⚠ 未找到需要清理的临时文件${NC}"
fi

echo ""
echo "当前版本: v1.1.0 - 简洁稳定的体重管理助手"
echo "================================"

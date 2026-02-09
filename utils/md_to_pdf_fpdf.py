#!/usr/bin/env python3
"""
Markdown 转 PDF 工具（使用 fpdf2，完美支持中文）
"""

import markdown
from fpdf import FPDF
from pathlib import Path
import re
import sys


class PDF(FPDF):
    def __init__(self, font_path):
        super().__init__()
        self.font_path = font_path
        # 添加中文字体
        self.add_font('NotoSansCJK', '', font_path, uni=True)
        self.add_font('NotoSansCJK', 'B', font_path, uni=True)  # 粗体用同一字体
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        # 页眉（可选）
        pass
    
    def footer(self):
        # 页码
        self.set_y(-15)
        self.set_font('NotoSansCJK', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'{self.page_no()}', 0, 0, 'C')


class MarkdownToPDF:
    def __init__(self, md_file_path, output_path=None, font_path=None):
        self.md_path = Path(md_file_path)
        if output_path is None:
            self.output_path = self.md_path.with_suffix('.pdf')
        else:
            self.output_path = Path(output_path)
        
        # 字体路径
        if font_path is None:
            # 尝试常见位置
            possible_paths = [
                '/tmp/NotoSansCJKsc-Regular.otf',
                '/usr/share/fonts/noto/NotoSansCJKsc-Regular.otf',
                'NotoSansCJKsc-Regular.otf',
            ]
            for path in possible_paths:
                if Path(path).exists():
                    self.font_path = path
                    break
            else:
                print("错误：未找到中文字体文件")
                print("请下载 NotoSansCJKsc-Regular.otf 字体")
                sys.exit(1)
        else:
            self.font_path = font_path
    
    def parse_markdown(self, content):
        """解析 Markdown 为结构化数据"""
        lines = content.split('\n')
        elements = []
        current_code_block = []
        in_code_block = False
        current_table = []
        in_table = False
        
        for line in lines:
            stripped = line.strip()
            
            # 代码块
            if stripped.startswith('```'):
                if in_code_block:
                    elements.append(('code', '\n'.join(current_code_block)))
                    current_code_block = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue
            
            if in_code_block:
                current_code_block.append(line)
                continue
            
            # 表格
            if '|' in stripped and not stripped.startswith('#'):
                if not in_table:
                    in_table = True
                    current_table = []
                cells = [cell.strip() for cell in stripped.split('|') if cell.strip()]
                # 跳过分隔行（全是 - 的行）
                if cells and not all(set(c) <= set('-:| ') for c in cells):
                    current_table.append(cells)
                continue
            else:
                if in_table:
                    if len(current_table) > 0:
                        elements.append(('table', current_table))
                    current_table = []
                    in_table = False
            
            # 标题
            if stripped.startswith('# '):
                elements.append(('h1', stripped[2:]))
            elif stripped.startswith('## '):
                elements.append(('h2', stripped[3:]))
            elif stripped.startswith('### '):
                elements.append(('h3', stripped[4:]))
            elif stripped.startswith('#### '):
                elements.append(('h4', stripped[4:]))
            # 列表
            elif stripped.startswith('- ') or stripped.startswith('* '):
                elements.append(('list', stripped[2:]))
            elif re.match(r'^\d+\.', stripped):
                elements.append(('list', re.sub(r'^\d+\.', '', stripped).strip(), 'ordered'))
            # 分隔线
            elif stripped == '---' or stripped == '***':
                elements.append(('hr', ''))
            # 普通段落
            elif stripped:
                elements.append(('p', stripped))
            # 空行
            else:
                elements.append(('spacer', 1))
        
        # 处理最后的代码块或表格
        if in_code_block and current_code_block:
            elements.append(('code', '\n'.join(current_code_block)))
        if in_table and current_table:
            elements.append(('table', current_table))
        
        return elements
    
    def create_pdf(self):
        """创建 PDF"""
        print(f"正在读取: {self.md_path}")
        with open(self.md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        print("正在解析 Markdown...")
        elements = self.parse_markdown(md_content)
        
        print(f"使用字体: {self.font_path}")
        pdf = PDF(self.font_path)
        pdf.add_page()
        
        # 页面设置
        pdf.set_margins(20, 20, 20)
        
        print("正在生成 PDF 内容...")
        for elem_type, content in elements:
            if elem_type == 'h1':
                pdf.set_font('NotoSansCJK', 'B', 18)
                pdf.set_text_color(44, 62, 80)  # #2c3e50
                pdf.ln(10)
                pdf.cell(0, 12, content, ln=True)
                pdf.set_draw_color(52, 152, 219)  # #3498db
                pdf.line(20, pdf.get_y(), 190, pdf.get_y())
                pdf.ln(5)
            
            elif elem_type == 'h2':
                pdf.set_font('NotoSansCJK', 'B', 14)
                pdf.set_text_color(52, 73, 94)  # #34495e
                pdf.ln(8)
                pdf.cell(0, 10, content, ln=True)
                pdf.ln(3)
            
            elif elem_type == 'h3':
                pdf.set_font('NotoSansCJK', 'B', 12)
                pdf.set_text_color(85, 85, 85)  # #555
                pdf.ln(6)
                pdf.cell(0, 8, content, ln=True)
                pdf.ln(2)
            
            elif elem_type == 'h4':
                pdf.set_font('NotoSansCJK', 'B', 11)
                pdf.set_text_color(100, 100, 100)
                pdf.ln(4)
                pdf.cell(0, 7, content, ln=True)
            
            elif elem_type == 'p':
                pdf.set_font('NotoSansCJK', '', 10)
                pdf.set_text_color(0, 0, 0)
                # 处理行内格式
                text = content
                text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # 移除粗体标记
                text = re.sub(r'`([^`]+)`', r'\1', text)  # 移除代码标记
                pdf.multi_cell(0, 6, text)
                pdf.ln(2)
            
            elif elem_type == 'list':
                pdf.set_font('NotoSansCJK', '', 10)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(5)  # 缩进
                pdf.cell(0, 6, f'• {content}', ln=True)
            
            elif elem_type == 'code':
                pdf.set_font('NotoSansCJK', '', 8)
                pdf.set_text_color(50, 50, 50)
                pdf.set_fill_color(244, 244, 244)  # #f4f4f4
                pdf.set_draw_color(52, 152, 219)
                
                # 代码块背景
                code_lines = content.split('\n')[:40]  # 限制行数
                code_text = '\n'.join(code_lines)
                if len(content.split('\n')) > 40:
                    code_text += '\n... (代码已截断)'
                
                pdf.multi_cell(0, 5, code_text, border=1, fill=True)
                pdf.ln(3)
            
            elif elem_type == 'table':
                self._add_table(pdf, content)
            
            elif elem_type == 'hr':
                pdf.ln(5)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(30, pdf.get_y(), 180, pdf.get_y())
                pdf.ln(5)
            
            elif elem_type == 'spacer':
                pdf.ln(3)
        
        print(f"正在保存 PDF: {self.output_path}")
        pdf.output(str(self.output_path))
        
        print(f"✅ 转换完成！")
        print(f"📄 PDF 文件: {self.output_path.absolute()}")
        
        return self.output_path
    
    def _add_table(self, pdf, table_data):
        """添加表格"""
        if not table_data:
            return
        
        # 标准化列数
        max_cols = max(len(row) for row in table_data)
        normalized_data = []
        for row in table_data:
            new_row = list(row)
            while len(new_row) < max_cols:
                new_row.append('')
            normalized_data.append(new_row)
        
        # 计算列宽
        page_width = 170  # A4 宽度减去边距
        col_width = page_width / max_cols
        
        # 绘制表格
        pdf.set_font('NotoSansCJK', '', 8)
        
        for i, row in enumerate(normalized_data):
            # 表头样式
            if i == 0:
                pdf.set_fill_color(52, 152, 219)  # #3498db
                pdf.set_text_color(255, 255, 255)
                pdf.set_font('NotoSansCJK', 'B', 8)
            else:
                # 隔行变色
                if i % 2 == 0:
                    pdf.set_fill_color(249, 249, 249)
                else:
                    pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('NotoSansCJK', '', 8)
            
            # 计算行高
            max_height = 6
            for cell in row:
                lines = len(cell) // 20 + 1  # 估算行数
                max_height = max(max_height, lines * 5)
            
            # 检查是否需要分页
            if pdf.get_y() + max_height > 270:
                pdf.add_page()
            
            # 绘制单元格
            x_start = pdf.get_x()
            y_start = pdf.get_y()
            
            for j, cell in enumerate(row):
                # 绘制背景
                pdf.rect(x_start + j * col_width, y_start, col_width, max_height, style='DF' if i == 0 or i % 2 == 0 else 'D')
                # 绘制文字
                pdf.set_xy(x_start + j * col_width + 2, y_start + 2)
                pdf.cell(col_width - 4, max_height - 4, cell[:50], ln=0)  # 限制长度
            
            pdf.ln(max_height)
        
        pdf.ln(5)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='将 Markdown 转换为 PDF（支持中文）')
    parser.add_argument('input', help='输入 Markdown 文件路径')
    parser.add_argument('-o', '--output', help='输出 PDF 文件路径（可选）')
    parser.add_argument('-f', '--font', help='中文字体文件路径（可选）')
    
    args = parser.parse_args()
    
    converter = MarkdownToPDF(args.input, args.output, args.font)
    converter.create_pdf()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Markdown 转 PDF 工具（支持中文）
使用 reportlab + 系统字体
"""

import markdown
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import re
import sys
import platform


def register_chinese_fonts():
    """注册系统中文字体"""
    system = platform.system()
    fonts_registered = []
    
    if system == "Darwin":  # macOS
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    elif system == "Linux":
        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
    else:  # Windows
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
        ]
    
    # 尝试注册字体
    for font_path in font_paths:
        if Path(font_path).exists():
            try:
                font_name = Path(font_path).stem.replace(" ", "_")
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                fonts_registered.append(font_name)
                print(f"✓ 已注册字体: {font_name}")
                if len(fonts_registered) >= 2:  # 注册2个就够了
                    break
            except Exception as e:
                print(f"✗ 注册字体失败 {font_path}: {e}")
    
    return fonts_registered[0] if fonts_registered else None


class MarkdownToPDF:
    def __init__(self, md_file_path, output_path=None):
        self.md_path = Path(md_file_path)
        if output_path is None:
            self.output_path = self.md_path.with_suffix('.pdf')
        else:
            self.output_path = Path(output_path)
        
        # 注册中文字体
        self.chinese_font = register_chinese_fonts()
        if not self.chinese_font:
            print("警告：未找到中文字体，PDF可能显示异常")
            self.chinese_font = "Helvetica"
        
        # 设置页面样式
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """设置自定义样式（使用中文）"""
        font_name = self.chinese_font
        
        # 标题样式
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontName=font_name,
            fontSize=18,
            spaceAfter=20,
            spaceBefore=20,
            textColor=colors.HexColor('#2c3e50'),
            borderColor=colors.HexColor('#3498db'),
            borderWidth=2,
            borderPadding=10,
            leftIndent=0,
            alignment=TA_LEFT
        ))
        
        # H2 样式
        self.styles.add(ParagraphStyle(
            name='CustomH2',
            parent=self.styles['Heading2'],
            fontName=font_name,
            fontSize=14,
            spaceAfter=12,
            spaceBefore=16,
            textColor=colors.HexColor('#34495e'),
            leftIndent=0
        ))
        
        # H3 样式
        self.styles.add(ParagraphStyle(
            name='CustomH3',
            parent=self.styles['Heading3'],
            fontName=font_name,
            fontSize=12,
            spaceAfter=10,
            spaceBefore=12,
            textColor=colors.HexColor('#555555')
        ))
        
        # 正文样式
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=8,
            alignment=TA_LEFT,
            leading=16
        ))
        
        # 代码样式
        self.styles.add(ParagraphStyle(
            name='CustomCode',
            parent=self.styles['Code'],
            fontName='Courier',
            fontSize=8,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=10,
            spaceBefore=10,
            backColor=colors.HexColor('#f4f4f4'),
            borderColor=colors.HexColor('#3498db'),
            borderWidth=1,
            borderPadding=8
        ))
        
        # 列表样式
        self.styles.add(ParagraphStyle(
            name='CustomList',
            parent=self.styles['BodyText'],
            fontName=font_name,
            fontSize=10,
            leftIndent=30,
            spaceAfter=5,
            leading=14
        ))
    
    def parse_markdown(self, content):
        """解析 Markdown 内容"""
        lines = content.split('\n')
        elements = []
        current_code_block = []
        in_code_block = False
        current_table = []
        in_table = False
        
        for line in lines:
            stripped = line.strip()
            
            # 代码块处理
            if stripped.startswith('```'):
                if in_code_block:
                    code_text = '\n'.join(current_code_block)
                    elements.append(('code', code_text))
                    current_code_block = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue
            
            if in_code_block:
                current_code_block.append(line)
                continue
            
            # 表格处理
            if '|' in stripped and not stripped.startswith('#'):
                if not in_table:
                    in_table = True
                    current_table = []
                cells = [cell.strip() for cell in stripped.split('|') if cell.strip()]
                if cells and not all(c.replace('-', '').replace(':', '') == '' for c in cells):
                    current_table.append(cells)
                continue
            else:
                if in_table:
                    if len(current_table) > 1:
                        elements.append(('table', current_table))
                    current_table = []
                    in_table = False
            
            # 标题处理
            if stripped.startswith('# '):
                elements.append(('h1', stripped[2:]))
            elif stripped.startswith('## '):
                elements.append(('h2', stripped[3:]))
            elif stripped.startswith('### '):
                elements.append(('h3', stripped[4:]))
            elif stripped.startswith('- ') or stripped.startswith('* '):
                elements.append(('list', stripped[2:]))
            elif re.match(r'^\d+\.', stripped):
                elements.append(('list', re.sub(r'^\d+\.', '', stripped).strip()))
            elif stripped == '---' or stripped == '***':
                elements.append(('hr', ''))
            elif stripped:
                text = self._process_inline_formatting(stripped)
                elements.append(('p', text))
            else:
                elements.append(('spacer', 1))
        
        # 处理最后的代码块或表格
        if in_code_block and current_code_block:
            code_text = '\n'.join(current_code_block)
            elements.append(('code', code_text))
        if in_table and len(current_table) > 1:
            elements.append(('table', current_table))
        
        return elements
    
    def _process_inline_formatting(self, text):
        """处理行内格式"""
        # 先转义HTML特殊字符
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # 代码（先处理，避免被其他规则影响）
        text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="9" color="#c7254e">\1</font>', text)
        # 粗体
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__([^_]+)__', r'<b>\1</b>', text)
        # 斜体
        text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
        text = re.sub(r'_([^_]+)_', r'<i>\1</i>', text)
        
        return text
    
    def create_pdf(self):
        """创建 PDF 文件"""
        print(f"正在读取: {self.md_path}")
        with open(self.md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        print("正在解析 Markdown...")
        elements = self.parse_markdown(md_content)
        
        # 创建 PDF 文档
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        print("正在生成 PDF 内容...")
        for elem_type, content in elements:
            if elem_type == 'h1':
                story.append(Paragraph(content, self.styles['CustomTitle']))
                story.append(Spacer(1, 0.3*cm))
            
            elif elem_type == 'h2':
                story.append(Paragraph(content, self.styles['CustomH2']))
                story.append(Spacer(1, 0.2*cm))
            
            elif elem_type == 'h3':
                story.append(Paragraph(content, self.styles['CustomH3']))
                story.append(Spacer(1, 0.1*cm))
            
            elif elem_type == 'p':
                story.append(Paragraph(content, self.styles['CustomBody']))
                story.append(Spacer(1, 0.1*cm))
            
            elif elem_type == 'code':
                code_lines = content.split('\n')
                for line in code_lines[:50]:
                    escaped_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(escaped_line, self.styles['CustomCode']))
                if len(code_lines) > 50:
                    story.append(Paragraph('... (代码已截断)', self.styles['CustomCode']))
                story.append(Spacer(1, 0.2*cm))
            
            elif elem_type == 'list':
                story.append(Paragraph(f'• {content}', self.styles['CustomList']))
            
            elif elem_type == 'table':
                self._add_table(story, content)
            
            elif elem_type == 'hr':
                story.append(Spacer(1, 0.5*cm))
            
            elif elem_type == 'spacer':
                story.append(Spacer(1, 0.2*cm))
        
        print(f"正在保存 PDF: {self.output_path}")
        doc.build(story)
        
        print(f"✅ 转换完成！")
        print(f"📄 PDF 文件: {self.output_path.absolute()}")
        
        return self.output_path
    
    def _add_table(self, story, table_data):
        """添加表格"""
        if not table_data or len(table_data) < 2:
            return
        
        # 确保所有行有相同数量的列
        max_cols = max(len(row) for row in table_data)
        normalized_data = []
        for row in table_data:
            new_row = list(row)
            while len(new_row) < max_cols:
                new_row.append('')
            normalized_data.append(new_row)
        
        # 使用标准化后的数据创建表格
        table = Table(normalized_data, repeatRows=1)
        
        style = TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.chinese_font),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        for i in range(1, len(normalized_data)):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), colors.white)
        
        table.setStyle(style)
        story.append(table)
        story.append(Spacer(1, 0.3*cm))


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='将 Markdown 转换为 PDF（支持中文）')
    parser.add_argument('input', help='输入 Markdown 文件路径')
    parser.add_argument('-o', '--output', help='输出 PDF 文件路径（可选）')
    
    args = parser.parse_args()
    
    converter = MarkdownToPDF(args.input, args.output)
    converter.create_pdf()


if __name__ == "__main__":
    main()

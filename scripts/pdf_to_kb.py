#!/usr/bin/env python3
"""
PDF 数据手册转知识库工具

自动将 PDF 数据手册转换为 Markdown 并添加到知识库

用法:
    python pdf_to_kb.py /path/to/SD3031.pdf
    python pdf_to_kb.py /path/to/pdf_folder/ --batch
"""

import os
import sys
import re
import argparse
from pathlib import Path
import subprocess

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

KB_CHIPS_DIR = Path(__file__).parent.parent / "knowledge_base" / "chips"


def pdf_to_text(pdf_path: Path) -> str:
    """将 PDF 转换为纯文本"""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except Exception as e:
        print(f"❌ PDF 转换失败: {e}")
        return ""


def extract_chip_name(pdf_path: Path) -> str:
    """从文件名或内容提取芯片型号"""
    # 从文件名提取
    filename = pdf_path.stem
    # 匹配常见芯片型号格式
    patterns = [
        r'(SD\d{4})',
        r'(DS\d{4})',
        r'(STM\w+)',
        r'(ESP\d{2})',
        r'(AT\d+)',
        r'([A-Z]{2,4}\d{3,4}[A-Z]?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return filename.upper()


def clean_text(text: str) -> str:
    """清理文本内容"""
    # 移除多余的空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 移除页眉页脚常见的数字
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
    # 移除孤立字符
    text = re.sub(r'\n\s*[a-zA-Z]\s*\n', '\n', text)
    return text.strip()


def structure_to_markdown(chip_name: str, text: str) -> str:
    """将文本结构化为 Markdown"""
    lines = text.split('\n')
    md_lines = []
    
    # 添加标题
    md_lines.append(f"# {chip_name} 数据手册")
    md_lines.append("")
    md_lines.append("## 简介")
    md_lines.append(f"{chip_name} 是一款常用芯片。")
    md_lines.append("")
    
    # 尝试识别章节
    current_section = None
    section_buffer = []
    
    for line in lines[:200]:  # 只处理前200行，避免太长
        line = line.strip()
        if not line:
            continue
        
        # 识别章节标题
        if re.match(r'^(FEATURES|DESCRIPTION|APPLICATIONS|PIN|BLOCK DIAGRAM|ELECTRICAL)', line, re.I):
            if section_buffer:
                md_lines.append("")
            section_title = line.title()
            md_lines.append(f"## {section_title}")
            md_lines.append("")
            section_buffer = []
        
        # 识别寄存器表格
        elif re.match(r'^[\s]*[0-9A-F]{2}[\s]+', line) and len(line) < 50:
            if "寄存器" not in str(md_lines[-5:]):
                md_lines.append("### 寄存器列表")
                md_lines.append("")
                md_lines.append("| 地址 | 名称 | 说明 |")
                md_lines.append("|------|------|------|")
            # 尝试解析寄存器行
            parts = line.split()
            if len(parts) >= 2:
                addr = parts[0]
                name = parts[1] if len(parts) > 1 else ""
                desc = " ".join(parts[2:]) if len(parts) > 2 else ""
                md_lines.append(f"| {addr} | {name} | {desc} |")
        
        # 普通段落
        elif len(line) > 10 and not line.startswith('http'):
            section_buffer.append(line)
            if len(section_buffer) >= 3:
                md_lines.append(" ".join(section_buffer))
                section_buffer = []
    
    # 添加常见问题章节（模板）
    md_lines.append("")
    md_lines.append("## 常见问题")
    md_lines.append("")
    md_lines.append("### 初始化失败")
    md_lines.append("- 检查 I2C/SPI 连接")
    md_lines.append("- 检查地址是否正确")
    md_lines.append("- 检查供电电压")
    md_lines.append("")
    md_lines.append("### 通信异常")
    md_lines.append("- 检查上拉电阻")
    md_lines.append("- 降低通信速率")
    md_lines.append("- 检查是否有干扰")
    md_lines.append("")
    
    return '\n'.join(md_lines)


def convert_pdf(pdf_path: Path, force: bool = False) -> Path:
    """转换单个 PDF 到 Markdown"""
    chip_name = extract_chip_name(pdf_path)
    output_path = KB_CHIPS_DIR / f"{chip_name}.md"
    
    # 检查是否已存在
    if output_path.exists() and not force:
        print(f"⚠️  {output_path.name} 已存在，跳过（使用 --force 覆盖）")
        return output_path
    
    print(f"🔄 转换 {pdf_path.name} -> {output_path.name}")
    
    # 转换 PDF
    text = pdf_to_text(pdf_path)
    if not text:
        return None
    
    # 清理和结构化
    text = clean_text(text)
    markdown = structure_to_markdown(chip_name, text)
    
    # 保存
    output_path.write_text(markdown, encoding='utf-8')
    print(f"✅ 已保存: {output_path}")
    
    return output_path


def batch_convert(pdf_folder: Path, force: bool = False):
    """批量转换文件夹中的 PDF"""
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ 未找到 PDF 文件: {pdf_folder}")
        return
    
    print(f"📁 找到 {len(pdf_files)} 个 PDF 文件")
    print("=" * 50)
    
    success = 0
    for pdf_file in pdf_files:
        if convert_pdf(pdf_file, force):
            success += 1
        print()
    
    print("=" * 50)
    print(f"✅ 成功转换: {success}/{len(pdf_files)}")
    print(f"📚 知识库位置: {KB_CHIPS_DIR}")
    print(f"\n🚀 重启服务后生效:")
    print(f"   ./scripts/start.sh --port 8080")


def main():
    parser = argparse.ArgumentParser(
        description="PDF 数据手册转知识库工具"
    )
    parser.add_argument(
        "input",
        help="PDF 文件或文件夹路径"
    )
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="批量处理文件夹中的所有 PDF"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制覆盖已存在的文件"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input).expanduser().resolve()
    
    if not input_path.exists():
        print(f"❌ 路径不存在: {input_path}")
        return
    
    # 确保输出目录存在
    KB_CHIPS_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.batch or input_path.is_dir():
        batch_convert(input_path, args.force)
    else:
        result = convert_pdf(input_path, args.force)
        if result:
            print(f"\n🚀 重启服务后生效:")
            print(f"   ./scripts/start.sh --port 8080")


if __name__ == "__main__":
    main()

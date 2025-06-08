#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path

class ScriptBase:
    """所有脚本的基类，自动处理根目录定位"""
    def __init__(self):
        self.setup_paths()
        
    def setup_paths(self):
        """初始化路径系统"""
        try:
            # 获取脚本绝对路径并确定根目录
            self.script_dir = Path(__file__).parent.absolute()
            self.root_dir = self.script_dir.parent
            
            # 验证根目录结构
            required_dirs = ['content']  # 可根据需要修改
            for d in required_dirs:
                if not (self.root_dir / d).exists():
                    raise FileNotFoundError(f"缺少必要目录: {d}")
                    
            print(f"[INFO] 工作根目录: {self.root_dir}")
            
        except Exception as e:
            print(f"[ERROR] 初始化失败: {str(e)}")
            sys.exit(1)

    def run(self):
        """主逻辑入口"""
        raise NotImplementedError("子类必须实现此方法")

class MarkdownProcessor(ScriptBase):
    """处理Markdown文件的示例类"""
    def __init__(self):
        super().__init__()
        
    def process_file(self, md_file: Path):
        """处理单个Markdown文件"""
        try:
            with open(md_file, 'r+', encoding='utf-8') as f:
                content = f.read()
                
                # 示例处理：添加Front Matter（保持缩进对齐）
                if not content.startswith('---\n'):
                    filename = md_file.stem
                    front_matter = (
                        "---\n"
                        f"title: {filename}\n"
                        "type: docs\n"
                        "---\n\n"
                    )
                    f.seek(0)
                    f.write(front_matter + content)
                    print(f"[SUCCESS] 已处理: {md_file.relative_to(self.root_dir)}")
                    
        except UnicodeDecodeError:
            print(f"[WARNING] 跳过非UTF-8文件: {md_file.name}")
        except Exception as e:
            print(f"[ERROR] 处理失败 {md_file.name}: {str(e)}")

    def run(self):
        """递归处理所有Markdown文件"""
        print("\n开始扫描Markdown文件...")
        md_count = 0
        
        for md_file in self.root_dir.rglob('*.md'):
            if md_file.is_file():
                self.process_file(md_file)
                md_count += 1
                
        print(f"\n处理完成！共扫描到 {md_count} 个Markdown文件")

if __name__ == '__main__':
    try:
        processor = MarkdownProcessor()
        processor.run()
    except KeyboardInterrupt:
        print("\n用户中断操作")
        sys.exit(0)

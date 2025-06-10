import os
import re
from pathlib import Path

def convert_img_tags_in_md_files(root_dir):
    """
    递归处理目录下所有.md文件，将<img>标签转换为Markdown图片语法
    优化后：只要包含src和alt属性即可匹配，不检查style
    """
    # 新正则：匹配<img后跟src和alt属性，忽略顺序和其他属性
    img_tag_pattern = re.compile(
        r'<img\s+.*?src="([^"]+)".*?alt="([^"]+)".*?>',
        re.IGNORECASE | re.DOTALL
    )

    for foldername, subfolders, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.md'):
                filepath = Path(foldername) / filename
                process_md_file(filepath, img_tag_pattern)

def process_md_file(filepath, pattern):
    """
    处理单个Markdown文件
    """
    with open(filepath, 'r+', encoding='utf-8') as f:
        content = f.read()
        modified_content = pattern.sub(
            lambda match: f'![{match.group(2)}]({match.group(1)})',
            content
        )
        
        if modified_content != content:
            f.seek(0)
            f.write(modified_content)
            f.truncate()
            print(f'Processed: {filepath}')

if __name__ == '__main__':
    # 获取脚本所在目录的上级目录作为根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    print(f'Starting processing from root directory: {root_dir}')
    convert_img_tags_in_md_files(root_dir)
    print('Processing complete!')

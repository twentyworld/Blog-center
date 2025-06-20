import os
import re
from pathlib import Path

def clean_markdown_image_links(directory):
    """递归清理 Markdown 文件中的图片链接格式"""
    pattern = re.compile(r'!\[(.*?)\]\(([^%]+)%20[0-9a-fA-F]{32}(/[^)]+)\)')
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.md'):
                filepath = Path(root) / file
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 替换匹配的图片链接
                    new_content = pattern.sub(r'![\1](\2\3)', content)
                    
                    if new_content != content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"Updated: {filepath}")
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python clean_md_images.py <directory>")
        sys.exit(1)
    
    target_dir = sys.argv[1]
    if not os.path.isdir(target_dir):
        print(f"Error: Directory not found - {target_dir}")
        sys.exit(1)
    
    clean_markdown_image_links(target_dir)
    print("Processing complete.")

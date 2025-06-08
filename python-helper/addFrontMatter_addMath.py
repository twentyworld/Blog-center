import os
import re
from pathlib import Path

def process_markdown_frontmatter(directory):
    """递归处理 Markdown 文件中的 YAML Front Matter"""
    pattern = re.compile(
        r'^---\s*\n'
        r'title:\s*.+\n'
        r'type:\s*docs\s*\n'
        r'(?:.+\n)*?'
        r'---\s*',
        re.MULTILINE
    )
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.md'):
                filepath = Path(root) / file
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 插入 math: true
                    new_content = pattern.sub(
                        lambda match: match.group(0).rstrip() + '\nmath: true\n---',
                        content,
                        count=1
                    )
                    
                    if new_content != content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        print(f"Updated: {filepath}")
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    # === 直接在这里修改目标路径 ===
    target_dir = "/Users/temperlee/git-repo/knowledge-repo/Blog-center/content/business"  # 替换为你的Markdown文件目录（如："/Users/name/my_markdowns"）
    
    if not os.path.isdir(target_dir):
        print(f"错误：目录不存在 - {target_dir}")
    else:
        process_markdown_frontmatter(target_dir)
        print("处理完成！")

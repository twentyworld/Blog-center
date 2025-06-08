import os
import re

def rename_files_and_dirs(root_path):
    md5_pattern = re.compile(r'\s[a-f0-9]{32}')  # 匹配32位MD5哈希值（前面有空格）
    
    for root, dirs, files in os.walk(root_path, topdown=False):
        # 先处理文件
        for name in files:
            old_path = os.path.join(root, name)
            
            # 分割文件名和扩展名
            basename, ext = os.path.splitext(name)
            
            # 去除MD5部分
            new_basename = md5_pattern.sub('', basename).strip()
            new_name = new_basename + ext
            new_path = os.path.join(root, new_name)
            
            # 如果新的路径与旧的不同，则重命名
            if new_path != old_path:
                try:
                    os.rename(old_path, new_path)
                    print(f"重命名文件: {old_path} -> {new_path}")
                except Exception as e:
                    print(f"无法重命名文件 {old_path}: {e}")
        
        # 处理子文件夹
        for name in dirs:
            old_dir_path = os.path.join(root, name)
            
            # 去除MD5部分
            new_dir_name = md5_pattern.sub('', name).strip()
            new_dir_path = os.path.join(root, new_dir_name)
            
            # 如果新的路径与旧的不同，则重命名
            if new_dir_path != old_dir_path:
                try:
                    os.rename(old_dir_path, new_dir_path)
                    print(f"重命名文件夹: {old_dir_path} -> {new_dir_path}")
                except Exception as e:
                    print(f"无法重命名文件夹 {old_dir_path}: {e}")

if __name__ == "__main__":
    # 在这里直接填写你的文件夹路径
    folder_path = r"/Users/temperlee/Downloads"  # 替换为你的实际路径
    
    # Windows路径示例（使用原始字符串）:
    # folder_path = r"C:\Users\YourName\Documents\需要处理的文件夹"
    
    # Mac/Linux路径示例:
    # folder_path = "/Users/yourname/Documents/需要处理的文件夹"
    
    if os.path.isdir(folder_path):
        rename_files_and_dirs(folder_path)
        print("处理完成!")
    else:
        print(f"错误: 路径 '{folder_path}' 不是一个有效文件夹")

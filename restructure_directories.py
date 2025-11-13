# 处理从 notion 导出的包含子页的文件，快速将 notion 中的数据导入博客

#!/usr/bin/env python3
import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, quote
from datetime import datetime, timezone, timedelta

def process_md_files(root_dir):
    """
    遍历目录，处理md文件，将其移动到对应的文件夹中，并更新引用路径
    """
    root_path = Path(root_dir)
    
    # 首先收集所有需要处理的md文件
    md_files = []
    for md_file in root_path.rglob("*.md"):
        # 检查文件名是否符合 "name md5sum.md" 格式
        match = re.match(r'^(.+?) [a-f0-9]{32}\.md$', md_file.name)
        if match:
            name = match.group(1)
            md_files.append((md_file, name))
    
    print(f"找到 {len(md_files)} 个需要处理的md文件")
    
    # 处理每个md文件
    for md_file, name in md_files:
        print(f"\n处理文件: {md_file}")
        
        # 检查同级目录下是否存在对应的文件夹
        parent_dir = md_file.parent
        target_dir = parent_dir / name
        
        if target_dir.exists() and target_dir.is_dir():
            print(f"  找到对应文件夹: {target_dir}")
            
            # 新的md文件名（去掉md5sum）
            new_md_name = f"{name}.md"
            new_md_path = root_path / new_md_name
            
            # 移动md文件到目标文件夹并重命名
            shutil.move(str(md_file), str(new_md_path))
            print(f"  已移动并重命名: {md_file.name} -> {new_md_path}")
            
            # 更新md文件中的引用路径
            update_md_references_no_md(new_md_path, parent_dir)
            
            # 将目标文件夹移动到第一级目录
            move_to_root(target_dir, root_path)
        
            return True
        else:
            print(f"  未找到对应文件夹: {target_dir}")
            
            # 新的md文件名（去掉md5sum）
            new_md_name = f"{name}.md"
            new_md_path = root_path / new_md_name
            
            # 移动md文件到目标文件夹并重命名
            shutil.move(str(md_file), str(new_md_path))
            print(f"  已移动并重命名: {md_file.name} -> {new_md_path}")

    return False

def update_md_references_no_md(md_file_path, old_parent):
    """
    更新md文件中的引用路径
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 更新相对路径引用
        # 这里我们假设引用的是相对路径，需要根据新的位置调整
        # 由于文件被移动到子目录，原来的相对路径可能需要添加 ../
        
        # 简单的路径更新逻辑，根据实际情况可能需要调整
        def update_path(match):
            path = match.group(1)
            # 如果路径是相对路径且不包含 ../，可能需要调整
            if not path.startswith(('http://', 'https://', '/', '../')):
                path_match = re.match(r'.*.md$', path)
                if path_match:
                    return match.group(0)

                # 检查文件是否存在于新位置
                old_file_path = Path(unquote(str(old_parent / path))) # URL 解码
                # print(f"old_file_path: {old_file_path}")
                if old_file_path.exists():
                    # 如果原文件还在原位置，需要添加 ../
                    target_md_name = str(path).split("/")[-1]
                    return f']({target_md_name})'
            return match.group(0)
        
        # 更新markdown链接和图片引用
        updated_content = re.sub(r'\]\(([^)]+)\)', update_path, content)
        
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
            
        print(f"  已更新文件中的引用路径: {md_file_path}")
        
    except Exception as e:
        print(f"  更新文件引用时出错: {e}")

def update_md_references(root_dir, tags, categories):
    """
    遍历目录，找到所有 md 文件
    """
    root_path = Path(root_dir)
    
    # 首先收集所有需要处理的md文件
    md_files = {}
    for md_file in root_path.rglob("*.md"):
        # 检查文件名是否符合 "name md5sum.md" 格式
        name = md_file.name.replace(".md", "")
        md_files[name] = md_file

    root_directories = {}
    for dir in root_path.iterdir():
        if dir.is_dir():
            root_directories[dir.name] = dir

    # 处理每个md文件
    for name, md_file_path in md_files.items():
        """
        更新 md文件中的 md 文件引用路径
        """
        try:
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新相对路径引用
            # 这里我们假设引用的是相对路径，需要根据新的位置调整
            # 由于文件被移动到子目录，原来的相对路径可能需要添加 ../
            
            # 简单的路径更新逻辑，根据实际情况可能需要调整
            def update_path(match):
                path = match.group(1)
                # 如果路径是相对路径且不包含 ../，可能需要调整
                if not path.startswith(('http://', 'https://', '/', '../')):
                    path_match = re.match(r'.*.md$', path)
                    if path_match == None:
                        return match.group(0)

                    # 检查文件名是否符合 "name md5sum.md" 格式
                    unquote_path = unquote(path)
                    path_match = re.match(r'^(.+?) [a-f0-9]{32}\.md$', unquote_path)
                    if path_match == None:
                        return match.group(0)
                    target_md_name = path_match.group(1).split("/")[-1]
                    if (md_files.get(target_md_name) == None) :
                        return match.group(0)
                    new_file_path = str(md_files[target_md_name]).replace(str(root_path), "")
                    # if (root_directories.get(target_md_name)):
                    #    new_file_path = new_file_path.replace(target_md_name + ".md","index.md")

                    # 如果原文件还在原位置，需要添加 ./
                    return f'](./{quote(new_file_path)})'
                return match.group(0)
            
            # 更新markdown链接和图片引用
            updated_content = re.sub(r'\]\(([^)]+)\)', update_path, content)
            title_content = f"+++\ntitle = \"{name}\"\ndate = {(datetime.now().astimezone()).isoformat()}\ntags = [{tags}]\ncategories = [{categories}]\n+++\n"
            
            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(title_content + updated_content)

            if (root_directories.get(name)):
                new_file_path = str(md_file_path).replace(name + ".md","index.md") 
                # shutil.move(str(md_file_path), str(new_file_path))
            print(f"  已更新文件中的 md 文件引用路径: {md_file_path}")
            
        except Exception as e:
            print(f"  更新文件 md 引用时出错: {e}")

def move_to_root(directory, root_path):
    """
    将目录移动到第一级目录
    """
    target_path = root_path / directory.name
    
    # 如果目标位置已存在，处理冲突
    if target_path.exists():
        # if target_path.is_dir():
        #     # 如果是目录，合并内容
        #     merge_directories(directory, target_path)
        #     print(f"  已合并到现有目录: {target_path}")
        #     return
        # else:
        #     # 如果是文件，重命名
        #     counter = 1
        #     while True:
        #         new_name = f"{directory.name}_{counter}"
        #         new_target = root_path / new_name
        #         if not new_target.exists():
        #             target_path = new_target
        #             break
        #         counter += 1
        return
    
    # 移动目录到根目录
    shutil.move(str(directory), str(target_path))
    print(f"  已移动到第一级目录: {target_path}")

def merge_directories(src_dir, dst_dir):
    """
    合并两个目录的内容
    """
    for item in src_dir.iterdir():
        target_item = dst_dir / item.name
        
        if item.is_dir():
            if target_item.exists() and target_item.is_dir():
                merge_directories(item, target_item)
            else:
                shutil.move(str(item), str(target_item))
        else:
            if target_item.exists():
                # 处理文件重名冲突
                name_parts = item.name.rsplit('.', 1)
                if len(name_parts) == 2:
                    base_name, ext = name_parts
                    counter = 1
                    while True:
                        new_name = f"{base_name}_{counter}.{ext}"
                        new_target = dst_dir / new_name
                        if not new_target.exists():
                            shutil.move(str(item), str(new_target))
                            break
                        counter += 1
                else:
                    counter = 1
                    while True:
                        new_name = f"{item.name}_{counter}"
                        new_target = dst_dir / new_name
                        if not new_target.exists():
                            shutil.move(str(item), str(new_target))
                            break
                        counter += 1
            else:
                shutil.move(str(item), str(target_item))
    
    # 删除空源目录
    try:
        src_dir.rmdir()
    except OSError:
        pass  # 目录不为空，不删除

def main():
    import sys
    tags = ""
    categories = ""
    
    if len(sys.argv) < 2:
        print("用法: python script.py <目录路径>")
        print("示例: python script.py /path/to/your/directory")
        sys.exit(1)

    if len(sys.argv) > 2:
        tags = sys.argv[2]

    if len(sys.argv) > 3:
        categories = sys.argv[3]

    directory = sys.argv[1]
    
    if not os.path.isdir(directory):
        print(f"错误: {directory} 不是一个有效的目录")
        sys.exit(1)
    
    print(f"开始处理目录: {directory}")
    while (process_md_files(directory)):
        print("ok")
    update_md_references(directory, tags, categories)
    print("\n处理完成！")

if __name__ == "__main__":
    main()

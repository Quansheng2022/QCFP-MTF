import os
import fnmatch

def collect_files(root_dir, output_file, project_root):
    """
    遍历指定目录，将所有文件内容合并到一个输出文件中
    
    Args:
        root_dir: 要遍历的根目录
        output_file: 输出文件路径
        project_root: 项目根目录（用于计算相对路径）
    """
    
    # 需要排除的目录和文件模式
    exclude_dirs = {
        '__pycache__', 
        '.git', 
        '.idea', 
        '.vscode',
        'node_modules',
        '.pytest_cache',
        '.mypy_cache',
        'dist',
        'build',
        'venv',
        'env',
        '.venv'
    }
    
    exclude_extensions = {
        '.pyc', '.pyo', '.pyd',  # Python编译文件
        '.exe', '.dll', '.so', '.dylib',  # 二进制文件
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',  # 图片
        '.mp4', '.avi', '.mov', '.mkv',  # 视频
        '.mp3', '.wav', '.flac',  # 音频
        '.zip', '.tar', '.gz', '.rar', '.7z',  # 压缩包
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # 文档
        '.db', '.sqlite', '.sqlite3',  # 数据库
        '.log', '.tmp', '.cache',  # 日志和缓存
        '.ico', '.svg',  # 图标
        '.min.js', '.min.css',  # 压缩的js/css
    }
    
    # 要包含的代码文件扩展名（可根据需要调整）
    include_extensions = {
        '.py', '.js', '.ts', '.jsx', '.tsx',  # 脚本
        '.java', '.cpp', '.c', '.h', '.hpp',  # C/C++/Java
        '.go', '.rs', '.rb', '.php',  # 其他语言
        '.html', '.css', '.scss', '.less',  # 前端
        '.json', '.xml', '.yaml', '.yml', '.toml',  # 配置文件
        '.txt', '.md', '.rst',  # 文档
        '.sql',  # SQL
        '.sh', '.bat', '.ps1',  # 脚本
        '.ini', '.cfg', '.conf',  # 配置文件
        '.dockerfile',  # Dockerfile
        '.gitignore', '.gitattributes',  # Git文件
        '.env.example', '.env.sample',  # 环境变量示例
    }
    
    # 收集所有文件
    all_files = []
    
    # 遍历目录
    for root, dirs, files in os.walk(root_dir):
        # 移除排除的目录（原地修改）
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        # 计算相对路径（相对于项目根目录）
        rel_path = os.path.relpath(root, project_root)
        if rel_path == '.':
            rel_path = ''
        
        for file in files:
            # 获取文件扩展名
            _, ext = os.path.splitext(file)
            
            # 检查是否应该包含该文件
            should_include = False
            
            # 检查扩展名
            if ext.lower() in include_extensions:
                should_include = True
            # 检查是否为无扩展名的特殊文件（如Dockerfile, .gitignore等）
            elif file in ['.gitignore', '.gitattributes', 'Dockerfile', 'docker-compose.yml']:
                should_include = True
            # 检查是否以点开头（隐藏配置文件）
            elif file.startswith('.') and '.' not in file[1:]:  # 如 .env, .flake8
                should_include = True
            
            # 排除特定扩展名
            if ext.lower() in exclude_extensions:
                should_include = False
            
            # 排除特殊文件
            if file.startswith('~') or file.endswith('.tmp'):
                should_include = False
            
            if should_include:
                full_path = os.path.join(root, file)
                rel_file_path = os.path.join(rel_path, file) if rel_path else file
                all_files.append((full_path, rel_file_path))
    
    # 按路径排序，使输出更有条理
    all_files.sort(key=lambda x: x[1])
    
    # 写入输出文件
    total_files = 0
    total_chars = 0
    
    with open(output_file, 'w', encoding='utf-8') as out_f:
        out_f.write("=" * 80 + "\n")
        out_f.write("项目文件合并\n")
        out_f.write(f"项目根目录: {project_root}\n")
        out_f.write(f"扫描路径: {root_dir}\n")
        out_f.write(f"总计文件数: {len(all_files)}\n")
        out_f.write("=" * 80 + "\n\n")
        
        for full_path, rel_path in all_files:
            try:
                # 读取文件内容
                with open(full_path, 'r', encoding='utf-8') as in_f:
                    content = in_f.read()
                
                # 写入文件分隔标记
                out_f.write(f"==== {rel_path} ====\n")
                out_f.write(content)
                
                # 确保文件末尾有换行
                if not content.endswith('\n'):
                    out_f.write('\n')
                out_f.write('\n')  # 文件之间的空行
                
                total_files += 1
                total_chars += len(content)
                
                print(f"已处理: {rel_path}")
                
            except UnicodeDecodeError:
                # 如果遇到编码问题，尝试其他编码
                try:
                    with open(full_path, 'r', encoding='gbk') as in_f:
                        content = in_f.read()
                    
                    out_f.write(f"==== {rel_path} ====\n")
                    out_f.write(content)
                    if not content.endswith('\n'):
                        out_f.write('\n')
                    out_f.write('\n')
                    
                    total_files += 1
                    total_chars += len(content)
                    print(f"已处理 (GBK编码): {rel_path}")
                    
                except Exception as e:
                    print(f"跳过文件 (编码问题): {rel_path} - {e}")
                    
            except Exception as e:
                print(f"跳过文件 (读取错误): {rel_path} - {e}")
    
    print("\n" + "=" * 80)
    print(f"合并完成!")
    print(f"处理文件数: {total_files}")
    print(f"输出文件: {output_file}")
    print(f"总字符数: {total_chars:,}")
    print(f"预估Token数: ~{total_chars // 3:,} (粗略估算)")
    print("=" * 80)

def main():
    # 配置路径
    project_root = r"C:\Users\Quansheng\Documents\projects\TA_Workflow"
    scan_path = r"C:\Users\Quansheng\Documents\projects\TA_Workflow\Core\QCFP_MTF"
    output_file = r"C:\Users\Quansheng\Documents\projects\TA_Workflow\Merged_Code\merged_code_QCFP-MTF.txt"
    
    # 检查路径是否存在
    if not os.path.exists(scan_path):
        print(f"错误: 路径不存在 - {scan_path}")
        return
    
    # 执行文件合并
    collect_files(scan_path, output_file, project_root)
    
    # 提示文件大小
    if os.path.exists(output_file):
        size = os.path.getsize(output_file)
        if size > 1024 * 1024:
            print(f"\n输出文件大小: {size / (1024*1024):.2f} MB")
        elif size > 1024:
            print(f"\n输出文件大小: {size / 1024:.2f} KB")
        else:
            print(f"\n输出文件大小: {size} 字节")
        
        # 提示如何上传
        print("\n" + "=" * 80)
        print("📤 上传建议:")
        print(f"1. 在DeepSeek对话框中，点击回形针上传: {output_file}")
        print("2. 然后在对话框中输入: '请审查上传文件中的所有代码'")
        print("3. 如果文件太大(>100万Token)，建议分批审查")
        print("=" * 80)

if __name__ == "__main__":
    main()
	
	
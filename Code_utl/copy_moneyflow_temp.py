import os
import glob
import shutil

def copy_moneyflow_files():
    # 定义目录路径
    directory = r"C:\Users\Quansheng\Documents\projects\TA_Workflow\Temp"
    
    # 搜索匹配 *moneyflow_20260713.txt 的文件
    search_pattern = os.path.join(directory, "*moneyflow_20260713.txt")
    
    # 找到所有匹配的文件
    files_to_copy = glob.glob(search_pattern)
    
    if not files_to_copy:
        print("未找到匹配 '*moneyflow_20260713.txt' 的文件。")
        return
    
    print(f"找到 {len(files_to_copy)} 个文件需要复制:")
    
    for file_path in files_to_copy:
        # 获取目录和文件名
        dir_name = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # 生成新的文件名（去掉日期部分）
        new_file_name = file_name.replace("_20260713", "")
        new_file_path = os.path.join(dir_name, new_file_name)
        
        # 检查目标文件是否已存在
        if os.path.exists(new_file_path):
            print(f"警告: {new_file_name} 已存在。跳过 {file_name}")
            continue
        
        try:
            # 复制文件
            shutil.copy2(file_path, new_file_path)  # copy2 会保留元数据
            print(f"已复制: {file_name} -> {new_file_name}")
        except Exception as e:
            print(f"复制 {file_name} 时出错: {e}")

if __name__ == "__main__":
    copy_moneyflow_files()
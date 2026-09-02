"""
synch_folders.py
Take disk backup before clone to Github.
只有星期五才上传sqlite db to github.

Changelog:
- Added global cache cleanup for all __pycache__ directories and .pyc files under projects root
- Added cache cleanup for __pycache__ directories in MD_Converter folder using PowerShell
- Added SQLite database VACUUM and cleanup of -shm and -wal files
- Improved error handling and logging
"""

import os
import shutil
import zipfile
import sqlite3
import subprocess
from datetime import datetime

# ========== 新增全局清理函数 ==========
def cleanup_all_pycache(root_path):
    """
    递归删除 root_path 下所有 __pycache__ 目录和 .pyc 文件
    """
    print("\n" + "="*50)
    print(f"Cleaning up all __pycache__ directories and .pyc files under: {root_path}")
    
    if not os.path.exists(root_path):
        print(f"Warning: Path {root_path} does not exist!")
        return

    pycache_count = 0
    pyc_count = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        # 删除 __pycache__ 目录
        if '__pycache__' in dirnames:
            pycache_path = os.path.join(dirpath, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
                print(f"Removed __pycache__: {pycache_path}")
                pycache_count += 1
            except Exception as e:
                print(f"Error removing {pycache_path}: {e}")

        # 删除 .pyc 文件
        for file in filenames:
            if file.endswith('.pyc'):
                pyc_file = os.path.join(dirpath, file)
                try:
                    os.remove(pyc_file)
                    print(f"Removed .pyc: {pyc_file}")
                    pyc_count += 1
                except Exception as e:
                    print(f"Error removing {pyc_file}: {e}")

    print(f"Cleaned up {pycache_count} __pycache__ directories and {pyc_count} .pyc files.")
    print("="*50 + "\n")

# ========== 原有函数（保留） ==========
def cleanup_pycache(project_root):
    """
    Remove all __pycache__ directories recursively from project root
    （此函数保留但主程序不再调用，因为已使用全局清理）
    """
    print("\n" + "="*50)
    print("Cleaning up __pycache__ directories...")
    
    if not os.path.exists(project_root):
        print(f"Warning: Project root {project_root} does not exist!")
        return
    
    try:
        original_dir = os.getcwd()
        os.chdir(project_root)
        
        pycache_dirs = []
        for root, dirs, files in os.walk('.'):
            if '__pycache__' in dirs:
                dir_path = os.path.join(root, '__pycache__')
                pycache_dirs.append(dir_path)
        
        for dir_path in pycache_dirs:
            try:
                shutil.rmtree(dir_path)
                print(f"Removed: {dir_path}")
            except Exception as e:
                print(f"Error removing {dir_path}: {str(e)}")
        
        os.chdir(original_dir)
        print(f"Cleaned up {len(pycache_dirs)} __pycache__ directories")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"Error during pycache cleanup: {str(e)}")
        try:
            os.chdir(original_dir)
        except:
            pass

def cleanup_md_converter_cache_powershell():
    """
    Clean up cache files in the MD_Converter folder using PowerShell
    Equivalent to: Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
    Also removes all .pyc files
    Windows only - uses PowerShell commands
    """
    print("\n" + "="*50)
    print("Cleaning up MD_Converter cache using PowerShell...")
    
    md_converter_path = r"C:\Users\Quansheng\Documents\projects\MD_Converter"
    
    if not os.path.exists(md_converter_path):
        print(f"Warning: MD_Converter folder {md_converter_path} does not exist!")
        return
    
    try:
        # Step 1: Remove all __pycache__ directories
        print("Removing __pycache__ directories...")
        ps_command = f'''
        $count = 0
        Get-ChildItem -Path "{md_converter_path}" -Recurse -Directory -Filter "__pycache__" | ForEach-Object {{
            $count++
            Write-Host "Removed: $($_.FullName)"
            Remove-Item -Path $_.FullName -Recurse -Force
        }}
        Write-Host "Removed $count __pycache__ directories"
        '''
        
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            if result.stdout:
                print(result.stdout.strip())
        else:
            print(f"Error in PowerShell command: {result.stderr}")
        
        # Step 2: Remove all .pyc files
        print("\nRemoving .pyc files...")
        ps_command_pyc = f'''
        $count = 0
        Get-ChildItem -Path "{md_converter_path}" -Recurse -File -Filter "*.pyc" | ForEach-Object {{
            $count++
            Write-Host "Removed: $($_.FullName)"
            Remove-Item -Path $_.FullName -Force
        }}
        Write-Host "Removed $count .pyc files"
        '''
        
        result_pyc = subprocess.run(
            ["powershell", "-Command", ps_command_pyc],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result_pyc.returncode == 0:
            if result_pyc.stdout:
                print(result_pyc.stdout.strip())
        else:
            print(f"Error removing .pyc files: {result_pyc.stderr}")
        
        print("="*50 + "\n")
        
    except subprocess.CalledProcessError as e:
        print(f"PowerShell command failed with error: {str(e)}")
        print(f"Error output: {e.stderr}")
    except Exception as e:
        print(f"Error during PowerShell cache cleanup: {str(e)}")

def cleanup_md_converter_cache_powershell_alternative():
    """
    Alternative cleaner version using single PowerShell command
    """
    print("\n" + "="*50)
    print("Cleaning up MD_Converter cache using PowerShell (alternative)...")
    
    md_converter_path = r"C:\Users\Quansheng\Documents\projects\MD_Converter"
    
    if not os.path.exists(md_converter_path):
        print(f"Warning: MD_Converter folder {md_converter_path} does not exist!")
        return
    
    try:
        ps_command = f'''
        $total = 0
        $pycacheCount = 0
        $pycCount = 0
        
        # Remove __pycache__ directories
        Get-ChildItem -Path "{md_converter_path}" -Recurse -Directory -Filter "__pycache__" | ForEach-Object {{
            $pycacheCount++
            $total++
            Write-Host "Removed __pycache__: $($_.FullName)"
            Remove-Item -Path $_.FullName -Recurse -Force
        }}
        
        # Remove .pyc files
        Get-ChildItem -Path "{md_converter_path}" -Recurse -File -Filter "*.pyc" | ForEach-Object {{
            $pycCount++
            $total++
            Write-Host "Removed .pyc: $($_.FullName)"
            Remove-Item -Path $_.FullName -Force
        }}
        
        Write-Host "`nCleanup Summary:"
        Write-Host "  __pycache__ directories removed: $pycacheCount"
        Write-Host "  .pyc files removed: $pycCount"
        Write-Host "  Total items removed: $total"
        '''
        
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            if result.stdout:
                print(result.stdout.strip())
        else:
            print(f"Error in PowerShell command: {result.stderr}")
        
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"Error during PowerShell cache cleanup: {str(e)}")

def vacuum_sqlite_db(db_path):
    """
    Perform VACUUM on SQLite database and remove -wal and -shm files
    """
    print("\n" + "="*50)
    print(f"Performing SQLite VACUUM on {db_path}...")
    
    if not os.path.exists(db_path):
        print(f"Warning: Database file {db_path} does not exist!")
        return
    
    try:
        original_size = os.path.getsize(db_path)
        original_size_mb = original_size / (1024 * 1024)
        print(f"Original database size: {original_size_mb:.2f} MB")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = DELETE")
        print("Switched journal mode to DELETE")
        
        print("Running VACUUM... (this may take a while)")
        cursor.execute("VACUUM")
        conn.commit()
        
        new_size = os.path.getsize(db_path)
        new_size_mb = new_size / (1024 * 1024)
        print(f"Database after VACUUM: {new_size_mb:.2f} MB")
        
        if original_size > 0:
            savings = (1 - new_size / original_size) * 100
            print(f"Space saved: {savings:.1f}% ({ (original_size - new_size) / (1024*1024):.2f} MB)")
        
        conn.close()
        
        for ext in ['-wal', '-shm']:
            wal_file = f"{db_path}{ext}"
            if os.path.exists(wal_file):
                try:
                    os.remove(wal_file)
                    print(f"Removed: {wal_file}")
                except Exception as e:
                    print(f"Error removing {wal_file}: {str(e)}")
        
        print("SQLite VACUUM and cleanup completed successfully")
        print("="*50 + "\n")
        
    except sqlite3.Error as e:
        print(f"SQLite error during VACUUM: {str(e)}")
    except Exception as e:
        print(f"Unexpected error during VACUUM: {str(e)}")

def sync_folders(source, destination, remove_obsolete=True):
    """
    Synchronize source folder to destination folder with optional deletion handling
    """
    if not os.path.exists(destination):
        os.makedirs(destination)
        print(f"Created destination folder: {destination}")

    for root, dirs, files in os.walk(source):
        rel_path = os.path.relpath(root, source)
        dest_dir = os.path.join(destination, rel_path)

        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            print(f"Created directory: {dest_dir}")

        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest_dir, file)

            copy_file = False
            if not os.path.exists(dest_file):
                copy_file = True
                reason = "new file"
            else:
                src_mtime = os.path.getmtime(src_file)
                dest_mtime = os.path.getmtime(dest_file)
                src_size = os.path.getsize(src_file)
                dest_size = os.path.getsize(dest_file)

                if src_mtime > dest_mtime or src_size != dest_size:
                    copy_file = True
                    reason = "modified" if src_mtime > dest_mtime else "size changed"

            if copy_file:
                shutil.copy2(src_file, dest_file)
                print(f"Copied {src_file} to {dest_file} ({reason})")

    if remove_obsolete:
        for root, dirs, files in os.walk(destination):
            rel_path = os.path.relpath(root, destination)
            src_dir = os.path.join(source, rel_path)

            if not os.path.exists(src_dir):
                shutil.rmtree(root)
                print(f"Removed directory {root} (source no longer exists)")
                continue

            for file in files:
                dest_file = os.path.join(root, file)
                src_file = os.path.join(src_dir, file)

                if not os.path.exists(src_file):
                    os.remove(dest_file)
                    print(f"Removed {dest_file} (no longer in source)")

            if not os.listdir(root):
                os.rmdir(root)
                print(f"Removed empty directory: {root}")

    print("Synchronization complete!")

def compress_and_cleanup_hk_stock():
    """
    Compress HK_Stock.db to HK_Stock.zip and delete the original .db file
    """
    db_path = r"C:\All for QS\Backup2Github\projects\TA_Workflow\SQLiteDB\HK_Stock.db"
    zip_path = r"C:\All for QS\Backup2Github\projects\TA_Workflow\SQLiteDB\HK_Stock.zip"
    
    if os.path.exists(db_path):
        try:
            file_size = os.path.getsize(db_path)
            file_size_mb = file_size / (1024 * 1024)
            print(f"HK_Stock.db size: {file_size_mb:.2f} MB")
            
            print(f"Compressing {db_path} to {zip_path}...")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(db_path, os.path.basename(db_path))
            
            if os.path.exists(zip_path):
                zip_size = os.path.getsize(zip_path)
                zip_size_mb = zip_size / (1024 * 1024)
                print(f"HK_Stock.zip created successfully. Size: {zip_size_mb:.2f} MB")
                
                os.remove(db_path)
                print(f"Deleted original file: {db_path}")
                
                compression_ratio = (1 - zip_size / file_size) * 100
                print(f"Compression ratio: {compression_ratio:.1f}% reduction")
            else:
                print(f"Error: Zip file was not created at {zip_path}")
                
        except Exception as e:
            print(f"Error compressing HK_Stock.db: {str(e)}")
    else:
        print(f"HK_Stock.db not found at {db_path}. Skipping compression.")

def delete_hk_stock_zip_if_not_friday():
    """
    Delete HK_Stock.zip if today is not Friday
    """
    zip_path = r"C:\All for QS\Backup2Github\projects\TA_Workflow\SQLiteDB\HK_Stock.zip"
    
    today = datetime.now()
    is_friday = today.weekday() == 4  # Friday is 4
    
    if os.path.exists(zip_path):
        if is_friday:
            print(f"Today is Friday ({today.strftime('%Y-%m-%d')}). Keeping HK_Stock.zip.")
        else:
            try:
                print("temporarily keep HK_Stock.zip.")
                # os.remove(zip_path)  # 原代码注释掉了，保留一致
                print(f"Today is not Friday ({today.strftime('%Y-%m-%d')}). Deleted HK_Stock.zip.")
            except Exception as e:
                print(f"Error deleting HK_Stock.zip: {str(e)}")
    else:
        print(f"HK_Stock.zip not found at {zip_path}. No action needed.")

# ========== 主程序 ==========
if __name__ == "__main__":
    print("="*60)
    print("SYNCHRONIZATION PROCESS STARTED")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # ====== 第一步（新增）：全局清理所有 __pycache__ 和 .pyc ======
    projects_root = r"C:\Users\Quansheng\Documents\projects"
    cleanup_all_pycache(projects_root)

    # ====== 第二步：专门清理 MD_Converter（PowerShell） ======
    cleanup_md_converter_cache_powershell()
    # 如果需要替代版本，可取消注释下行：
    # cleanup_md_converter_cache_powershell_alternative()

    # ====== 第三步：VACUUM SQLite ======
    db_path = r"C:\Users\Quansheng\Documents\projects\TA_Workflow\SQLiteDB\HK_Stock.db"
    vacuum_sqlite_db(db_path)

    # ====== 第四步：同步文件夹 ======
    folder_pairs = {
        r"C:\Users\Quansheng\Documents\projects": r"C:\All for QS\Backup2Github\projects",
        r"C:\All for QS\ZQS\Share": r"C:\All for QS\Backup2Github\Share",
        r"C:\All for QS\ZQS\Cycling": r"C:\All for QS\Backup2Github\Cycling",
        r"C:\All for QS\ZQS\Confidential": r"C:\All for QS\Backup2Github\Confidential"
    }
    
    for source, destination in folder_pairs.items():
        print("\n" + "="*50)
        print(f"Synchronizing from {source} to {destination}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            sync_folders(source, destination, remove_obsolete=True)
        except Exception as e:
            print(f"Error synchronizing {source} to {destination}: {str(e)}")
        
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50 + "\n")

    # ====== 第五步：压缩 HK_Stock.db ======
    print("\n" + "="*50)
    print("Processing HK_Stock database file...")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    compress_and_cleanup_hk_stock()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50 + "\n")

    # ====== 第六步：根据星期决定保留或删除 HK_Stock.zip ======
    print("\n" + "="*50)
    print("Checking HK_Stock.zip retention policy...")
    delete_hk_stock_zip_if_not_friday()
    print("="*50 + "\n")

    print("="*60)
    print("SYNCHRONIZATION PROCESS COMPLETED")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
#!/usr/bin/env python3
"""
Pre-installation Check for Markdown to DOCX Converter
Checks all required software and provides installation instructions
Run this before using convert_md_docx.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

class SoftwareChecker:
    """Check if required software is installed"""
    
    def __init__(self):
        self.results = {
            'pandoc': {'installed': False, 'version': None, 'path': None},
            'nodejs': {'installed': False, 'version': None, 'path': None},
            'npm': {'installed': False, 'version': None, 'path': None},
            'mermaid': {'installed': False, 'version': None, 'path': None},
            'pypandoc': {'installed': False, 'version': None, 'path': None},
        }
        self.colors = {
            'green': '\033[92m',
            'red': '\033[91m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'cyan': '\033[96m',
            'reset': '\033[0m',
            'bold': '\033[1m'
        }
    
    def print_header(self, text):
        """Print a formatted header"""
        print(f"\n{self.colors['cyan']}{'='*60}{self.colors['reset']}")
        print(f"{self.colors['bold']}{self.colors['cyan']}{text}{self.colors['reset']}")
        print(f"{self.colors['cyan']}{'='*60}{self.colors['reset']}")
    
    def print_result(self, name, status, version=None, path=None, message=None):
        """Print a formatted result"""
        if status:
            icon = f"{self.colors['green']}✓{self.colors['reset']}"
            status_text = f"{self.colors['green']}INSTALLED{self.colors['reset']}"
        else:
            icon = f"{self.colors['red']}✗{self.colors['reset']}"
            status_text = f"{self.colors['red']}MISSING{self.colors['reset']}"
        
        print(f"{icon} {name:15} [{status_text:10}]", end="")
        
        if version:
            print(f" version: {version}", end="")
        if path:
            print(f"\n{ ' '*22}Path: {path}", end="")
        if message:
            print(f"\n{ ' '*22}Message: {message}", end="")
        print()
    
    def check_pandoc(self):
        """Check if Pandoc is installed"""
        try:
            # Check in PATH
            pandoc_path = shutil.which('pandoc')
            if pandoc_path:
                result = subprocess.run(['pandoc', '--version'], 
                                      capture_output=True, text=True, check=True)
                version_line = result.stdout.splitlines()[0] if result.stdout else "Unknown"
                self.results['pandoc']['installed'] = True
                self.results['pandoc']['version'] = version_line.replace('pandoc ', '')
                self.results['pandoc']['path'] = pandoc_path
                return True
        except:
            pass
        
        # Check common Windows paths
        common_paths = [
            Path("C:/Program Files/Pandoc/pandoc.exe"),
            Path("C:/Program Files (x86)/Pandoc/pandoc.exe"),
            Path(os.path.expanduser("~/AppData/Local/Pandoc/pandoc.exe")),
            Path(os.path.expanduser("~/AppData/Local/Pandoc/pandoc.EXE")),
            Path(os.path.expanduser("~/AppData/Roaming/Pandoc/pandoc.exe")),
            Path("C:/Pandoc/pandoc.exe"),
        ]
        
        for path in common_paths:
            if path.exists():
                try:
                    result = subprocess.run([str(path), '--version'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        version_line = result.stdout.splitlines()[0] if result.stdout else "Unknown"
                        self.results['pandoc']['installed'] = True
                        self.results['pandoc']['version'] = version_line.replace('pandoc ', '')
                        self.results['pandoc']['path'] = str(path)
                        return True
                except:
                    pass
        
        return False
    
    def check_nodejs(self):
        """Check if Node.js is installed"""
        try:
            node_path = shutil.which('node')
            if node_path:
                result = subprocess.run(['node', '--version'], 
                                      capture_output=True, text=True, check=True)
                version = result.stdout.strip()
                self.results['nodejs']['installed'] = True
                self.results['nodejs']['version'] = version.replace('v', '')
                self.results['nodejs']['path'] = node_path
                return True
        except:
            pass
        
        # Check common Windows paths
        common_paths = [
            "C:/Program Files/nodejs/node.exe",
            "C:/Program Files (x86)/nodejs/node.exe",
            os.path.expanduser("~/AppData/Local/Programs/nodejs/node.exe"),
            os.path.expanduser("~/AppData/Local/Programs/nodejs/node.cmd"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                try:
                    result = subprocess.run([path, '--version'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        self.results['nodejs']['installed'] = True
                        self.results['nodejs']['version'] = version.replace('v', '')
                        self.results['nodejs']['path'] = path
                        return True
                except:
                    pass
        
        return False
    
    def check_npm(self):
        """Check if npm is installed (including .cmd on Windows)"""
        # 方法 1: 使用 shutil.which（Windows 可能需要 .cmd）
        try:
            # shutil.which 在 Windows 上可能不找 .cmd
            npm_path = shutil.which('npm')
            if not npm_path:
                # 尝试带 .cmd 后缀
                npm_path = shutil.which('npm.cmd')
            
            if npm_path:
                result = subprocess.run([npm_path, '--version'], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    version = result.stdout.strip()
                    self.results['npm']['installed'] = True
                    self.results['npm']['version'] = version
                    self.results['npm']['path'] = npm_path
                    return True
        except:
            pass
        
        # 方法 2: 检查常见 Node.js 目录
        node_dirs = [
            Path("C:/Program Files/nodejs/npm.cmd"),
            Path("C:/Program Files/nodejs/npm"),
            Path("C:/Program Files (x86)/nodejs/npm.cmd"),
            Path(os.path.expanduser("~/AppData/Local/Programs/nodejs/npm.cmd")),
        ]
        for path in node_dirs:
            if path.exists():
                try:
                    result = subprocess.run([str(path), '--version'], 
                                          capture_output=True, text=True, check=False)
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        self.results['npm']['installed'] = True
                        self.results['npm']['version'] = version
                        self.results['npm']['path'] = str(path)
                        return True
                except:
                    pass
        
        # 方法 3: 使用 node 执行 npm 版本检查
        try:
            result = subprocess.run(['node', '-e', 'console.log(require("child_process").execSync("npm --version").toString().trim())'],
                                  capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
                self.results['npm']['installed'] = True
                self.results['npm']['version'] = version
                self.results['npm']['path'] = "npm (via node)"
                return True
        except:
            pass
        
        return False
    
    def check_mermaid(self):
        """Check if Mermaid CLI is installed"""
        # Check in PATH (including .cmd on Windows)
        mmdc_path = shutil.which('mmdc')
        if not mmdc_path:
            mmdc_path = shutil.which('mmdc.cmd')
        
        if mmdc_path:
            try:
                result = subprocess.run([mmdc_path, '--version'], 
                                      capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    version_line = result.stdout.splitlines()[0] if result.stdout else "Unknown"
                    self.results['mermaid']['installed'] = True
                    self.results['mermaid']['version'] = version_line.replace('mmdc ', '').strip()
                    self.results['mermaid']['path'] = mmdc_path
                    return True
            except:
                pass
        
        # Check npm global bin locations
        npm_bin_locations = [
            Path(os.path.expanduser("~/AppData/Roaming/npm/mmdc.cmd")),
            Path(os.path.expanduser("~/AppData/Roaming/npm/mmdc")),
            Path(os.path.expanduser("~/AppData/Local/npm/mmdc.cmd")),
            Path("C:/Program Files/nodejs/node_modules/@mermaid-js/mermaid-cli/bin/mmdc.cmd"),
            Path("C:/Program Files (x86)/nodejs/node_modules/@mermaid-js/mermaid-cli/bin/mmdc.cmd"),
        ]
        for path in npm_bin_locations:
            if path.exists():
                try:
                    result = subprocess.run([str(path), '--version'], 
                                          capture_output=True, text=True, check=False)
                    if result.returncode == 0:
                        version_line = result.stdout.splitlines()[0] if result.stdout else "Unknown"
                        self.results['mermaid']['installed'] = True
                        self.results['mermaid']['version'] = version_line.replace('mmdc ', '').strip()
                        self.results['mermaid']['path'] = str(path)
                        return True
                except:
                    pass
        
        return False
    
    def check_pypandoc(self):
        """Check if pypandoc Python package is installed"""
        try:
            import pypandoc
            version = pypandoc.__version__
            self.results['pypandoc']['installed'] = True
            self.results['pypandoc']['version'] = version
            self.results['pypandoc']['path'] = "Python package"
            return True
        except ImportError:
            return False
    
    def print_installation_instructions(self):
        """Print installation instructions for missing software"""
        print(f"\n{self.colors['yellow']}📋 Installation Instructions:{self.colors['reset']}")
        print("-" * 60)
        
        if not self.results['pandoc']['installed']:
            print(f"\n{self.colors['yellow']}📦 Install Pandoc:{self.colors['reset']}")
            print("  - Winget:   winget install JohnMacFarlane.Pandoc")
            print("  - Conda:    conda install -c conda-forge pandoc")
            print("  - Manual:   https://pandoc.org/installing.html")
        
        if not self.results['nodejs']['installed']:
            print(f"\n{self.colors['yellow']}📦 Install Node.js:{self.colors['reset']}")
            print("  - Winget:   winget install OpenJS.NodeJS")
            print("  - Conda:    conda install -c conda-forge nodejs")
            print("  - Manual:   https://nodejs.org/")
        
        if self.results['nodejs']['installed'] and not self.results['mermaid']['installed']:
            print(f"\n{self.colors['yellow']}📦 Install Mermaid CLI:{self.colors['reset']}")
            print("  - npm:      npm install -g @mermaid-js/mermaid-cli")
            print("  - After install, add to PATH:")
            print("              $env:Path += `;$env:APPDATA\npm")
        
        if not self.results['pypandoc']['installed']:
            print(f"\n{self.colors['yellow']}📦 Install pypandoc (Python):{self.colors['reset']}")
            print("  - pip:      pip install pypandoc")
        
        print("-" * 60)
    
    def print_path_fix_instructions(self):
        """Print instructions to fix PATH issues"""
        print(f"\n{self.colors['yellow']}🔧 PATH Fix Instructions:{self.colors['reset']}")
        print("-" * 60)
        
        if self.results['mermaid']['installed'] and not shutil.which('mmdc'):
            print("Mermaid CLI is installed but not in PATH. Add it:")
            print("  [Environment]::SetEnvironmentVariable('Path',")
            print("      [Environment]::GetEnvironmentVariable('Path', 'User') +")
            print("      ';C:\\Users\\Quansheng\\AppData\\Roaming\\npm', 'User')")
            print("Then restart PowerShell.")
        
        if self.results['pandoc']['installed'] and not shutil.which('pandoc'):
            print("Pandoc is installed but not in PATH.")
            print("Check if it's in: C:\\Users\\Quansheng\\AppData\\Local\\Pandoc\\")
            print("Add it to PATH using System Properties > Environment Variables.")
        
        print("-" * 60)
    
    def run_all_checks(self):
        """Run all checks and display results"""
        self.print_header("🔍 Pre-installation Software Check")
        
        print(f"\n{self.colors['bold']}Checking required software...{self.colors['reset']}\n")
        
        # Run all checks
        self.check_pandoc()
        self.check_nodejs()
        self.check_npm()
        self.check_mermaid()
        self.check_pypandoc()
        
        # Display results
        self.print_result("Pandoc", 
                         self.results['pandoc']['installed'],
                         self.results['pandoc']['version'],
                         self.results['pandoc']['path'])
        
        self.print_result("Node.js", 
                         self.results['nodejs']['installed'],
                         self.results['nodejs']['version'],
                         self.results['nodejs']['path'])
        
        self.print_result("npm", 
                         self.results['npm']['installed'],
                         self.results['npm']['version'],
                         self.results['npm']['path'])
        
        self.print_result("Mermaid CLI", 
                         self.results['mermaid']['installed'],
                         self.results['mermaid']['version'],
                         self.results['mermaid']['path'])
        
        self.print_result("pypandoc", 
                         self.results['pypandoc']['installed'],
                         self.results['pypandoc']['version'],
                         self.results['pypandoc']['path'])
        
        # Summary
        all_installed = all([
            self.results['pandoc']['installed'],
            self.results['nodejs']['installed'],
            self.results['npm']['installed'],
            self.results['mermaid']['installed'],
            self.results['pypandoc']['installed']
        ])
        
        print(f"\n{self.colors['bold']}Summary:{self.colors['reset']}")
        if all_installed:
            print(f"{self.colors['green']}✅ All required software is installed!{self.colors['reset']}")
            print(f"{self.colors['green']}You can now run convert_md_docx.py{self.colors['reset']}")
        else:
            missing = []
            if not self.results['pandoc']['installed']: missing.append("Pandoc")
            if not self.results['nodejs']['installed']: missing.append("Node.js")
            if not self.results['npm']['installed']: missing.append("npm")
            if not self.results['mermaid']['installed']: missing.append("Mermaid CLI")
            if not self.results['pypandoc']['installed']: missing.append("pypandoc")
            
            print(f"{self.colors['red']}❌ Missing: {', '.join(missing)}{self.colors['reset']}")
            self.print_installation_instructions()
            
            # Check for PATH issues
            if self.results['mermaid']['installed'] and not shutil.which('mmdc'):
                self.print_path_fix_instructions()
        
        print(f"\n{self.colors['cyan']}{'='*60}{self.colors['reset']}")
        
        return all_installed

def main():
    """Main function"""
    checker = SoftwareChecker()
    success = checker.run_all_checks()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
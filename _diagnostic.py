#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断工具：用于检查dailySum插件的环境配置和依赖状态
"""

import os
import sys
import traceback
import importlib.util
import datetime
import platform

def check_dependency(module_name):
    """检查依赖模块是否已安装"""
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False, None
    
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, '__version__', '未知')
        return True, version
    except ImportError:
        return True, '未知'

def check_file_exists(file_path):
    """检查文件是否存在"""
    return os.path.exists(file_path)

def check_directory_exists(dir_path):
    """检查目录是否存在"""
    return os.path.isdir(dir_path)

def check_file_writable(file_path):
    """检查文件是否可写"""
    if not os.path.exists(file_path):
        try:
            with open(file_path, 'w') as f:
                f.write('test')
            os.remove(file_path)
            return True
        except:
            return False
    else:
        return os.access(file_path, os.W_OK)

def check_directory_writable(dir_path):
    """检查目录是否可写"""
    if not os.path.exists(dir_path):
        return False
    
    test_file = os.path.join(dir_path, 'test_write.tmp')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except:
        return False

def load_config():
    """尝试加载配置文件"""
    try:
        import config
        return True, config
    except ImportError:
        return False, None
    except Exception as e:
        return False, str(e)

def run_diagnostic():
    """运行诊断程序"""
    print("=== dailySum插件诊断工具 ===")
    print(f"运行时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"系统信息: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version}")
    print("\n")
    
    # 检查依赖模块
    print("=== 依赖模块检查 ===")
    dependencies = ['httpx', 'PIL', 'html2image', 'apscheduler']
    for dep in dependencies:
        installed, version = check_dependency(dep)
        status = "✓ 已安装" if installed else "✗ 未安装"
        version_str = f"(版本: {version})" if version else ""
        print(f"{dep}: {status} {version_str}")
    
    # 检查文件结构
    print("\n=== 文件结构检查 ===")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 检查必要文件
    required_files = [
        '__init__.py', 
        'dailysum.py', 
        'config.py', 
        'logger_helper.py'
    ]
    for file in required_files:
        file_path = os.path.join(current_dir, file)
        exists = check_file_exists(file_path)
        status = "✓ 存在" if exists else "✗ 不存在"
        print(f"{file}: {status}")
    
    # 检查目录
    required_dirs = ['data', 'logs']
    for dir_name in required_dirs:
        dir_path = os.path.join(current_dir, dir_name)
        exists = check_directory_exists(dir_path)
        status = "✓ 存在" if exists else "✗ 不存在"
        
        writable = "不可写" if not exists else ("可写" if check_directory_writable(dir_path) else "不可写")
        print(f"{dir_name}目录: {status} ({writable})")
    
    # 检查配置
    print("\n=== 配置检查 ===")
    config_loaded, config = load_config()
    if not config_loaded:
        print(f"配置文件加载失败: {config}")
    else:
        print("配置文件加载成功")
        print(f"LOG_PATH: {getattr(config, 'LOG_PATH', '未设置')}")
        log_path_exists = check_file_exists(getattr(config, 'LOG_PATH', ''))
        print(f"  日志文件存在: {'✓ 是' if log_path_exists else '✗ 否'}")
        
        api_key = getattr(config, 'AI_API_KEY', '')
        print(f"AI_API_KEY: {'✓ 已设置' if api_key else '✗ 未设置'}")
        
        enable_scheduler = getattr(config, 'ENABLE_SCHEDULER', False)
        print(f"定时任务: {'✓ 已启用' if enable_scheduler else '✗ 未启用'}")
        
        afternoon_hour = getattr(config, 'SUMMARY_HOUR_AFTERNOON', 18)
        night_hour = getattr(config, 'SUMMARY_HOUR_NIGHT', 0)
        print(f"定时任务时间: 下午 {afternoon_hour}:00, 晚上 {night_hour}:00")
    
    # 测试日志系统
    print("\n=== 日志系统测试 ===")
    try:
        from logger_helper import log_info
        log_info("诊断工具测试日志")
        print("✓ 日志系统测试成功")
    except Exception as e:
        print(f"✗ 日志系统测试失败: {str(e)}")
        print(traceback.format_exc())
    
    print("\n=== 诊断完成 ===")
    print("如有问题，请检查上述输出并修复相关配置。")
    print("更多帮助请参考README.md文件。")

if __name__ == "__main__":
    try:
        run_diagnostic()
    except Exception as e:
        print(f"诊断工具运行出错: {str(e)}")
        print(traceback.format_exc()) 
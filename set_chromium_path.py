import os
import sys
import json
from pathlib import Path

# 配置文件路径
CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'data')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'browser_config.json')

def save_config(browser_path):
    """保存浏览器路径到配置文件"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    config = {
        'browser_path': browser_path
    }
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    return True

def load_config():
    """从配置文件加载浏览器路径"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('browser_path', '')
        except Exception as e:
            print(f"加载配置失败: {str(e)}")
    return ''

def set_browser_path():
    """交互式设置浏览器路径"""
    print("=== Chromium浏览器路径设置 ===")
    print("请输入Chromium可执行文件的完整路径")
    print("示例: /home/username/.cache/ms-playwright/chromium-1140/chrome-linux/chrome")
    print("提示: 在解压的chromium-linux目录中，可执行文件通常是chrome-linux/chrome")
    print()
    
    # 尝试查找一些常见的Chromium路径
    home_dir = os.path.expanduser("~")
    possible_paths = [
        os.path.join(home_dir, ".cache", "ms-playwright", "chromium-1140", "chrome-linux", "chrome"),
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/lib/chromium-browser/chromium-browser",
    ]
    
    found_paths = []
    for path in possible_paths:
        if os.path.exists(path):
            found_paths.append(path)
    
    if found_paths:
        print("找到以下可能的Chromium路径:")
        for i, path in enumerate(found_paths, 1):
            print(f"{i}. {path}")
        print("0. 手动输入其他路径")
        
        try:
            choice = int(input("请选择一个路径 (输入数字): ").strip())
            if 1 <= choice <= len(found_paths):
                browser_path = found_paths[choice-1]
            else:
                browser_path = input("请输入Chromium可执行文件的完整路径: ").strip()
        except ValueError:
            browser_path = input("请输入Chromium可执行文件的完整路径: ").strip()
    else:
        browser_path = input("请输入Chromium可执行文件的完整路径: ").strip()
    
    if browser_path and os.path.exists(browser_path):
        if os.access(browser_path, os.X_OK):
            save_config(browser_path)
            print(f"浏览器路径设置成功: {browser_path}")
            print("现在可以使用'日报 测试2'命令生成HTML版日报了")
        else:
            print(f"错误: {browser_path} 不是可执行文件")
    else:
        print(f"错误: 路径不存在 {browser_path}")

def main():
    """主函数"""
    current_path = load_config()
    if current_path:
        print(f"当前设置的浏览器路径: {current_path}")
        if os.path.exists(current_path):
            print("路径有效")
        else:
            print("警告: 路径不存在!")
    
    set_browser_path()

if __name__ == "__main__":
    main() 
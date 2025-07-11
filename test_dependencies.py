import sys
import os

def check_dependencies():
    """检查依赖是否安装"""
    dependencies = {
        'PIL': 'Pillow',
        'httpx': 'httpx',
        'apscheduler': 'APScheduler',
    }
    
    missing = []
    installed = []
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            print(f"✓ {package} 已安装")
            installed.append(package)
        except ImportError:
            print(f"✗ {package} 未安装")
            missing.append(package)
    
    if missing:
        print("\n缺少以下依赖:")
        for package in missing:
            print(f"  - {package}")
        print("\n请使用以下命令安装:")
        print(f"pip install {' '.join(missing)}")
    else:
        print("\n所有依赖已安装!")
    
    # 尝试初始化PIL字体
    try:
        from PIL import ImageFont
        font = ImageFont.load_default()
        print("PIL字体初始化成功!")
    except Exception as e:
        print(f"PIL字体初始化失败: {str(e)}")

    # 检查当前目录下是否有字体文件
    print("\n检查字体文件...")
    font_files = [f for f in os.listdir('.') if f.endswith(('.ttf', '.ttc', '.otf'))]
    if font_files:
        print(f"找到字体文件: {', '.join(font_files)}")
    else:
        print("当前目录下没有找到字体文件")
    
    # 检查Windows字体目录
    win_font_dir = 'C:/Windows/Fonts'
    if os.path.exists(win_font_dir):
        print(f"\n检查Windows字体目录: {win_font_dir}")
        common_fonts = ['msyh.ttc', 'simhei.ttf', 'simsun.ttc']
        for font in common_fonts:
            font_path = os.path.join(win_font_dir, font)
            if os.path.exists(font_path):
                print(f"✓ 找到系统字体: {font}")
            else:
                print(f"✗ 系统字体不存在: {font}")
    

if __name__ == "__main__":
    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {os.getcwd()}")
    print("\n检查依赖项...\n")
    check_dependencies() 
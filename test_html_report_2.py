import os
import json
import base64
import shutil
import asyncio
from datetime import datetime
import traceback
from pathlib import Path

# 导入第三方库
try:
    from PIL import Image
    from playwright.async_api import async_playwright
    from nonebot.message import MessageSegment
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .logger_helper import log_info, log_warning, log_error_msg

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 用于存储自定义浏览器路径
CUSTOM_BROWSER_PATH = ""

# 浏览器配置文件路径
BROWSER_CONFIG_PATH = os.path.join(DATA_DIR, 'browser_config.json')

# 加载浏览器配置
def load_browser_config():
    global CUSTOM_BROWSER_PATH
    try:
        if os.path.exists(BROWSER_CONFIG_PATH):
            with open(BROWSER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                browser_path = config.get('browser_path', '')
                if browser_path and os.path.exists(browser_path):
                    CUSTOM_BROWSER_PATH = browser_path
                    log_info(f"已加载自定义浏览器路径: {CUSTOM_BROWSER_PATH}")
                    return True
    except Exception as e:
        log_warning(f"加载浏览器配置失败: {str(e)}")
    return False

# 尝试加载浏览器配置
load_browser_config()

# 优雅的HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        @font-face {{
            font-family: 'CustomFont';
            src: url('file://{font_path}') format('truetype');
            font-weight: normal;
            font-style: normal;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'CustomFont', 'Microsoft YaHei', '微软雅黑', 'SimHei', '黑体', sans-serif;
        }}
        
        body {{
            background-color: #f7f7f7;
            padding: 20px;
            color: #333;
            line-height: 1.6;
        }}
        
        .report-container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        
        .report-header {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 20px 30px;
            position: relative;
        }}
        
        .report-title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .report-subtitle {{
            font-size: 14px;
            opacity: 0.8;
        }}
        
        .report-body {{
            padding: 30px;
        }}
        
        .section {{
            margin-bottom: 25px;
        }}
        
        .section-title {{
            font-size: 18px;
            font-weight: bold;
            color: #2980b9;
            margin-bottom: 10px;
            padding-bottom: 5px;
            border-bottom: 1px solid #eee;
        }}
        
        .section-content {{
            font-size: 15px;
            color: #444;
        }}
        
        .section-content p {{
            margin-bottom: 10px;
        }}
        
        ul {{
            padding-left: 20px;
            margin-top: 5px;
            margin-bottom: 10px;
        }}
        
        li {{
            margin-bottom: 5px;
        }}
        
        .highlight {{
            background-color: #f8f9fa;
            border-left: 3px solid #2980b9;
            padding: 10px 15px;
            margin: 10px 0;
        }}
        
        .report-footer {{
            padding: 15px 30px;
            background-color: #f9f9f9;
            color: #777;
            font-size: 13px;
            text-align: center;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <div class="report-title">{title}</div>
            <div class="report-subtitle">AI生成的群聊分析报告</div>
        </div>
        
        <div class="report-body">
            {content_html}
        </div>
        
        <div class="report-footer">
            由AI生成 · {date}
        </div>
    </div>
</body>
</html>
"""

async def install_playwright_deps():
    """安装Playwright依赖"""
    try:
        log_info("检查Playwright浏览器依赖...")
        
        # 如果设置了自定义路径，直接使用
        global CUSTOM_BROWSER_PATH
        if CUSTOM_BROWSER_PATH and os.path.exists(CUSTOM_BROWSER_PATH):
            log_info(f"使用自定义浏览器路径: {CUSTOM_BROWSER_PATH}")
            return True
        
        # 检查是否已经有浏览器安装
        home_dir = os.path.expanduser("~")
        browser_path = os.path.join(home_dir, ".cache", "ms-playwright")
        
        # 如果浏览器目录存在，检查是否已有Chromium
        if os.path.exists(browser_path):
            chromium_dirs = [d for d in os.listdir(browser_path) if d.startswith("chromium-")]
            if chromium_dirs:
                log_info(f"找到已安装的Chromium: {chromium_dirs}")
                return True
        
        # 如果没有找到浏览器，尝试安装
        log_info("未找到已安装的Chromium，尝试安装...")
        
        # 设置环境变量，跳过浏览器下载（如果已手动放置）
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browser_path
        
        process = await asyncio.create_subprocess_shell(
            "playwright install chromium --force",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            log_info("Playwright依赖安装成功")
            return True
        else:
            # 安装失败，查看是否已手动解压
            if os.path.exists(browser_path):
                chromium_dirs = [d for d in os.listdir(browser_path) if d.startswith("chromium-")]
                if chromium_dirs:
                    log_info(f"找到手动安装的Chromium: {chromium_dirs}")
                    return True
            
            log_error_msg(f"Playwright依赖安装失败: {stderr.decode() if stderr else '未知错误'}")
            return False
    except Exception as e:
        log_error_msg(f"安装Playwright依赖时出错: {str(e)}")
        return False

def convert_text_to_html(content):
    """将纯文本转换为HTML格式"""
    if not content:
        return ""
    
    sections = []
    current_section = None
    current_content = []
    
    # 按行处理内容
    lines = content.split('\n')
    for line in lines:
        # 检测是否是章节标题 (形如【标题】)
        if line.startswith('【') and '】' in line:
            # 如果已有章节，先保存
            if current_section:
                sections.append((current_section, current_content))
            
            # 提取新章节标题
            current_section = line.strip('【】')
            current_content = []
        elif line.strip() == '' and current_content:
            # 空行，但确保前面有内容才添加
            current_content.append('')
        elif line.strip() and current_section is not None:
            # 普通内容行
            current_content.append(line)
        elif line.strip() and current_section is None:
            # 没有章节标题的内容
            current_section = "概述"
            current_content.append(line)
    
    # 添加最后一个章节
    if current_section:
        sections.append((current_section, current_content))
    
    # 转换为HTML
    html_content = []
    for section, content in sections:
        section_html = f'<div class="section"><div class="section-title">【{section}】</div><div class="section-content">'
        
        # 处理内容
        paragraph = []
        for line in content:
            # 检测列表项
            if line.strip().startswith(('- ', '* ', '1. ', '• ')):
                # 如果有待处理的段落，先处理
                if paragraph:
                    section_html += f"<p>{'<br>'.join(paragraph)}</p>"
                    paragraph = []
                
                # 创建列表
                if not section_html.endswith('<ul>') and not section_html.endswith('</li>'):
                    section_html += '<ul>'
                
                list_item = line.strip()
                for prefix in ['- ', '* ', '1. ', '• ']:
                    if list_item.startswith(prefix):
                        list_item = list_item[len(prefix):]
                        break
                
                section_html += f"<li>{list_item}</li>"
            else:
                # 如果刚结束列表，闭合它
                if section_html.endswith('</li>'):
                    section_html += '</ul>'
                
                # 处理常规段落
                if line.strip() == '':
                    if paragraph:
                        section_html += f"<p>{'<br>'.join(paragraph)}</p>"
                        paragraph = []
                else:
                    paragraph.append(line)
        
        # 处理最后一个段落
        if paragraph:
            section_html += f"<p>{'<br>'.join(paragraph)}</p>"
        
        # 检查是否需要闭合列表标签
        if section_html.endswith('</li>'):
            section_html += '</ul>'
        
        section_html += '</div></div>'
        html_content.append(section_html)
    
    return ''.join(html_content)

async def generate_text_report(title, content, date_str):
    """
    当无法生成图片时，生成美观的文本报告
    :param title: 标题
    :param content: 内容
    :param date_str: 日期字符串
    :return: 文本报告
    """
    separator = "=" * 30
    text_report = f"{separator}\n{title}\n{separator}\n\n{content}\n\n{separator}\n由AI生成 · {date_str}"
    return text_report

async def html_to_screenshot(html_path, output_path):
    """
    使用Playwright将HTML转换为图片
    :param html_path: HTML文件路径
    :param output_path: 输出图片路径
    :return: 是否成功
    """
    if not PLAYWRIGHT_AVAILABLE:
        log_warning("缺少Playwright库，无法进行HTML转图片，请安装: pip install playwright")
        return False
    
    try:
        log_info("使用Playwright将HTML转换为图片...")
        async with async_playwright() as p:
            # 检查是否有自定义浏览器路径
            if CUSTOM_BROWSER_PATH and os.path.exists(CUSTOM_BROWSER_PATH):
                log_info(f"使用自定义Chromium: {CUSTOM_BROWSER_PATH}")
                browser = await p.chromium.launch(executable_path=CUSTOM_BROWSER_PATH)
            else:
                browser = await p.chromium.launch()
                
            page = await browser.new_page()
            
            # 加载HTML文件
            await page.goto(f"file://{html_path}")
            
            # 等待内容加载
            await page.wait_for_load_state("networkidle")
            
            # 截图
            await page.screenshot(path=output_path, full_page=True)
            
            await browser.close()
            
        log_info(f"HTML转图片成功，输出到: {output_path}")
        return True
    except Exception as e:
        log_error_msg(f"HTML转图片失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        return False

async def init_playwright():
    """初始化Playwright"""
    if not PLAYWRIGHT_AVAILABLE:
        log_warning("Playwright未安装，请运行: pip install playwright")
        return False
    
    try:
        # 不再尝试获取版本号，直接安装依赖
        log_info("初始化Playwright并检查依赖...")
        await install_playwright_deps()
        return True
    except Exception as e:
        log_error_msg(f"初始化Playwright失败: {str(e)}")
        return False

async def get_font_path():
    """获取字体路径"""
    # 尝试使用项目中的字体
    font_paths = [
        os.path.join(os.path.dirname(__file__), 'msyh.ttc'),
        os.path.join(os.path.dirname(__file__), 'wqy-microhei.ttc'),
        os.path.join(os.path.dirname(__file__), 'simhei.ttf'),
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            return os.path.abspath(path)
    
    # 尝试项目中其他模块的字体
    other_module_fonts = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'yaowoyizhi', 'msyh.ttc'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pcr_calendar', 'wqy-microhei.ttc'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'generator', 'simhei.ttf'),
    ]
    
    for path in other_module_fonts:
        if os.path.exists(path):
            target_path = os.path.join(os.path.dirname(__file__), os.path.basename(path))
            if not os.path.exists(target_path):
                shutil.copy2(path, target_path)
            return os.path.abspath(target_path)
    
    # 系统字体
    system_fonts = [
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simhei.ttf',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    ]
    
    for path in system_fonts:
        if os.path.exists(path):
            target_path = os.path.join(os.path.dirname(__file__), os.path.basename(path))
            if not os.path.exists(target_path):
                shutil.copy2(path, target_path)
            return os.path.abspath(target_path)
    
    return ""  # 找不到字体

async def html_to_image(title, content, date_str):
    """
    将内容转换为HTML，然后使用Playwright生成图片
    :param title: 标题
    :param content: 内容
    :param date_str: 日期字符串
    :return: HTML文件路径和图片路径
    """
    try:
        log_info("开始生成HTML并转换为图片...")
        
        # 获取字体路径
        font_path = await get_font_path()
        if not font_path:
            log_warning("找不到可用的中文字体")
        
        # 将内容转换为HTML
        content_html = convert_text_to_html(content)
        
        # 生成完整的HTML
        html_content = HTML_TEMPLATE.format(
            title=title,
            content_html=content_html,
            date=date_str,
            font_path=font_path
        )
        
        # 保存HTML文件
        temp_html_path = os.path.join(DATA_DIR, f"report_{date_str}.html")
        with open(temp_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        log_info(f"HTML内容已保存到: {temp_html_path}")
        
        # 初始化Playwright
        if not await init_playwright():
            log_warning("初始化Playwright失败，无法生成图片")
            return temp_html_path, None
        
        # HTML转换为图片
        temp_img_path = os.path.join(DATA_DIR, f"report_{date_str}.png")
        if await html_to_screenshot(os.path.abspath(temp_html_path), temp_img_path):
            return temp_html_path, temp_img_path
        else:
            return temp_html_path, None
    except Exception as e:
        log_error_msg(f"HTML转图片过程中出错: {str(e)}")
        log_error_msg(traceback.format_exc())
        return None, None

# 测试日报摘要文本
TEST_SUMMARY = """【聊天活跃度】
今日共有3位成员参与聊天，总消息量为7条。
最活跃的时段是上午8点到9点，共有4条消息。

【话题分析】
今日主要讨论了以下话题：
- 天气和户外活动：讨论了天气好适合去公园，但因工作原因改为周末出行。
- 午餐选择：讨论了午餐吃什么，有成员提议点外卖。
- 工作状态：有成员表达了工作结束后的疲惫感。

【情感分析】
整体聊天氛围积极正面，大家互动友好。
早上的交流充满活力，午间讨论热情，下午略显疲惫但仍保持良好状态。

【互动亮点】
最具互动性的话题是关于天气和户外活动的讨论，吸引了所有活跃成员参与。

【总结】
今天是一个平静而普通的工作日，成员们在工作之余保持着轻松愉快的交流氛围。"""

# 检查依赖是否已安装
def check_dependencies():
    """检查必要的依赖是否已安装"""
    try:
        import playwright
        from PIL import Image
        return True
    except ImportError as e:
        log_warning(f"缺少必要的依赖: {str(e)}")
        log_warning("请安装必要的依赖: pip install playwright pillow")
        log_warning("安装后需要执行: playwright install chromium")
        return False

# 处理测试命令
async def handle_test_report_2(bot, ev):
    """
    处理测试日报2命令 - 使用HTML+CSS方式
    :param bot: 机器人实例
    :param ev: 事件对象
    :return: None
    """
    try:
        group_id = ev.get('group_id', '未知群')
        user_id = ev.get('user_id', '未知用户')
        log_info(f"收到测试日报2命令，群号:{group_id}, 用户:{user_id}")
        
        # 检查依赖
        if not check_dependencies():
            await bot.send(ev, "生成图片所需的依赖未安装，请联系管理员安装playwright和pillow库")
            return
            
        # 发送正在处理的提示
        await bot.send(ev, "正在生成HTML版测试日报图片，请稍候...")
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 使用预设的摘要文本
        title = f"{today} 群聊日报测试"
        content = TEST_SUMMARY
        
        log_info(f"使用预设摘要生成HTML图片，标题: {title}")
        
        # 尝试生成图片
        html_path, image_path = await html_to_image(title, content, today)
        
        if image_path and os.path.exists(image_path):
            # 发送图片
            log_info(f"准备发送图片: {image_path}")
            success = False
            
            # 尝试不同方法发送图片
            try:
                # 方法1：base64编码
                with open(image_path, 'rb') as f:
                    img_bytes = f.read()
                b64_str = base64.b64encode(img_bytes).decode()
                await bot.send(ev, MessageSegment.image(f'base64://{b64_str}'))
                log_info("使用base64编码发送图片成功")
                success = True
            except Exception as e1:
                log_warning(f"使用base64编码发送图片失败: {str(e1)}")
                
                try:
                    # 方法2：file路径
                    await bot.send(ev, MessageSegment.image(f'file:///{image_path}'))
                    log_info("使用file:///路径发送图片成功")
                    success = True
                except Exception as e2:
                    log_warning(f"使用file:///路径发送图片失败: {str(e2)}")
                    
                    try:
                        # 方法3：直接发送本地路径
                        await bot.send(ev, MessageSegment.image(image_path))
                        log_info("直接发送本地图片路径成功")
                        success = True
                    except Exception as e3:
                        log_error_msg(f"所有图片发送方法都失败: {str(e3)}")
            
            if not success:
                if html_path and os.path.exists(html_path):
                    # 尝试发送HTML文件
                    try:
                        await bot.send(ev, f"图片发送失败，但HTML页面已生成：{os.path.basename(html_path)}")
                        success = True
                    except:
                        pass
                
                if not success:
                    # 所有方法都失败，发送文本版本
                    log_warning("所有发送方法都失败，使用文本版本")
                    text_report = await generate_text_report(title, content, today)
                    await bot.send(ev, text_report)
        elif html_path and os.path.exists(html_path):
            # 图片生成失败但HTML成功，发送HTML路径
            await bot.send(ev, f"图片生成失败，但HTML页面已生成：{os.path.basename(html_path)}")
        else:
            # HTML也生成失败，发送文本
            log_warning("HTML和图片都生成失败，发送文本版本")
            text_report = await generate_text_report(title, content, today)
            await bot.send(ev, text_report)
    except Exception as e:
        log_error_msg(f"处理测试日报2命令失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        try:
            await bot.send(ev, f"处理测试日报2命令失败: {str(e)}")
        except:
            pass 
import os
import json
import base64
import shutil
import asyncio
from datetime import datetime
import traceback
from pathlib import Path
import re # Added for preprocess_content

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
            background-color: #000;
            margin: 0;
            padding: 0;
            color: #fff;
            line-height: 1.6;
        }}
        
        .bento-container {{
            width: 800px;
            padding: 20px;
            background-color: #000;
            margin: 0;
        }}
        
        .bento-title {{
            font-size: 28px;
            font-weight: bold;
            color: #fff;
            margin-bottom: 24px;
            text-align: center;
        }}
        
        .bento-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            grid-auto-rows: auto;
            gap: 16px;
        }}
        
        .bento-item {{
            background-color: #1c1c1e;
            border-radius: 20px;
            padding: 20px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            position: relative;
            transition: all 0.3s ease;
        }}
        
        .bento-item-large {{
            grid-column: span 2;
        }}
        
        .bento-item-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 12px;
            color: #0a84ff;
            display: flex;
            align-items: center;
        }}
        
        .bento-item-icon {{
            width: 24px;
            height: 24px;
            margin-right: 8px;
            background-color: #0a84ff;
            border-radius: 6px;
            display: inline-flex;
            justify-content: center;
            align-items: center;
            font-weight: bold;
            color: white;
        }}
        
        .bento-item-content {{
            color: #eee;
            font-size: 15px;
        }}
        
        ul {{
            padding-left: 20px;
            margin-top: 10px;
        }}
        
        li {{
            margin-bottom: 8px;
        }}
        
        .bento-footer {{
            margin-top: 16px;
            text-align: center;
            font-size: 13px;
            color: #888;
        }}
        
        .highlight {{
            color: #0a84ff;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="bento-container">
        <div class="bento-title">{title}</div>
        
        <div class="bento-grid">
            <div class="bento-item bento-item-large">
                <div class="bento-item-title">
                    <div class="bento-item-icon">🔥</div>
                    今日热点话题
                </div>
                <div class="bento-item-content" id="topics-content"></div>
            </div>
            
            <div class="bento-item">
                <div class="bento-item-title">
                    <div class="bento-item-icon">📢</div>
                    重要消息
                </div>
                <div class="bento-item-content" id="important-content"></div>
            </div>
            
            <div class="bento-item">
                <div class="bento-item-title">
                    <div class="bento-item-icon">💬</div>
                    金句
                </div>
                <div class="bento-item-content" id="quotes-content"></div>
            </div>
            
            <div class="bento-item bento-item-large">
                <div class="bento-item-title">
                    <div class="bento-item-icon">📝</div>
                    总结
                </div>
                <div class="bento-item-content" id="summary-content"></div>
            </div>
        </div>
        
        <div class="bento-footer">由AI生成 · {date}</div>
    </div>
    
    <script>
        // 分析内容并填充到对应区块
        function fillContent() {{
            const content = `{content_escaped}`;
            const sections = {{}};
            
            let currentSection = null;
            let currentContent = [];
            
            // 解析内容分段 - 增强版，支持多种标题格式
            content.split('\\n').forEach(line => {{
                // 匹配【标题】格式
                let titleMatch = line.match(/^\s*【(.+?)】\s*$/);
                // 匹配**【标题】**格式（markdown格式）
                if (!titleMatch) titleMatch = line.match(/^\s*\*\*【(.+?)】\*\*\s*$/);
                
                if (titleMatch) {{
                    const sectionName = titleMatch[1];
                    currentSection = sectionName;
                    currentContent = [];
                    sections[sectionName] = currentContent;
                }} else if (line.trim() && currentSection) {{
                    // 去除Markdown格式的**标记和一些特殊格式
                    let cleanLine = line.replace(/\*\*/g, '');
                    currentContent.push(cleanLine);
                }}
            }});
            
            // 如果没有找到任何标题部分，则尝试按不同格式再解析一遍
            if (Object.keys(sections).length === 0) {{
                // 处理整段式的内容，按照明显的分隔来处理
                let allContent = content.split('\\n');
                let fullText = allContent.join('\\n');
                
                // 尝试查找标题模式
                let matches = fullText.match(/今日热点话题[：:]([\s\S]*?)(?=重要消息[：:]|金句[：:]|总结[：:]|$)/i);
                if (matches) sections["今日热点话题"] = [matches[1].trim()];
                
                matches = fullText.match(/重要消息[：:]([\s\S]*?)(?=金句[：:]|总结[：:]|$)/i);
                if (matches) sections["重要消息"] = [matches[1].trim()];
                
                matches = fullText.match(/金句[：:]([\s\S]*?)(?=总结[：:]|$)/i);
                if (matches) sections["金句"] = [matches[1].trim()];
                
                matches = fullText.match(/总结[：:]([\s\S]*)/i);
                if (matches) sections["总结"] = [matches[1].trim()];
                
                // 如果仍然没有找到任何标题，把整个内容作为摘要
                if (Object.keys(sections).length === 0) {{
                    sections["聊天摘要"] = [content];
                }}
            }}
            
            // 映射标题到HTML元素ID
            const mappings = {{
                '今日热点话题': 'topics-content',
                '热点话题': 'topics-content',
                '今日话题': 'topics-content',
                '重要消息': 'important-content',
                '金句': 'quotes-content',
                '总结': 'summary-content',
                '今日总结': 'summary-content',
                '聊天摘要': 'topics-content',
                '聊天活跃度': 'topics-content',
                '话题分析': 'topics-content',
                '情感分析': 'important-content',
                '互动亮点': 'quotes-content'
            }};
            
            // 填充各区块内容
            Object.entries(sections).forEach(([section, lines]) => {{
                const elementId = mappings[section] || 'topics-content';  // 默认放到话题区块
                let element = document.getElementById(elementId);
                
                if (element) {{
                    // 格式化内容为HTML
                    let htmlContent = lines.join('\\n');
                    
                    // 处理列表
                    // 将"1. "或"- "或"* "格式的行转换为HTML列表
                    htmlContent = htmlContent.split('\\n').map(line => {{
                        let trimmedLine = line.trim();
                        if (trimmedLine.match(/^\d+\.\s/)) {{
                            return '<li>' + trimmedLine.replace(/^\d+\.\s/, '') + '</li>';
                        }} else if (trimmedLine.startsWith('- ')) {{
                            return '<li>' + trimmedLine.substring(2) + '</li>';
                        }} else if (trimmedLine.startsWith('* ')) {{
                            return '<li>' + trimmedLine.substring(2) + '</li>';
                        }} else if (trimmedLine.startsWith('• ')) {{
                            return '<li>' + trimmedLine.substring(2) + '</li>';
                        }} else {{
                            return line;
                        }}
                    }}).join('\\n');
                    
                    // 将连续的<li>标签包装在<ul>中
                    let inList = false;
                    htmlContent = htmlContent.split('\\n').map(line => {{
                        if (line.trim().startsWith('<li>')) {{
                            if (!inList) {{
                                inList = true;
                                return '<ul>' + line;
                            }}
                            return line;
                        }} else {{
                            if (inList) {{
                                inList = false;
                                return '</ul>' + line;
                            }}
                            return line;
                        }}
                    }}).join('\\n');
                    
                    // 确保最后一个列表被正确关闭
                    if (inList) {{
                        htmlContent += '</ul>';
                    }}
                    
                    // 处理段落，使内容更易读
                    htmlContent = htmlContent.replace(/\\n{2,}/g, '</p><p>');
                    htmlContent = '<p>' + htmlContent + '</p>';
                    htmlContent = htmlContent.replace(/<p>\\s*<\/p>/g, '');
                    
                    // 高亮关键词（在总结部分）
                    if (elementId === 'summary-content') {{
                        htmlContent = htmlContent.replace(/(重要|关键|值得注意|热点|关注)/g, '<span class="highlight">$1</span>');
                    }}
                    
                    element.innerHTML = htmlContent;
                }}
            }});
        }}
        
        // 页面加载后执行填充
        window.onload = fillContent;
    </script>
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
            await page.wait_for_timeout(1000)  # 额外等待1秒确保JavaScript执行完毕
            
            # 只截取报告容器部分，去掉周围的白边
            container = await page.query_selector('.bento-container')
            if container:
                await container.screenshot(path=output_path)
                log_info("成功截取Bento Grid容器部分")
            else:
                # 如果找不到容器，则截取整个页面
                await page.screenshot(path=output_path, full_page=True)
                log_info("未找到Bento容器，截取整个页面")
            
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
    生成HTML报告并转换为图片
    :param title: 标题
    :param content: 内容
    :param date_str: 日期字符串
    :return: HTML文件路径和图片文件路径的元组
    """
    try:
        log_info("开始生成HTML并转换为图片...")
        
        # 获取字体路径
        font_path = await get_font_path()
        if not font_path:
            log_warning("找不到可用的中文字体")
        
        # 预处理内容，确保能被正确解析
        processed_content = preprocess_content(content)
        
        # 转义内容中的大括号，防止格式化错误
        processed_content = processed_content.replace("{", "{{").replace("}", "}}")
        
        # 内容需要转义，供JavaScript处理
        content_escaped = processed_content.replace('\\', '\\\\').replace('`', '\\`')
        
        # 生成完整的HTML
        html_content = HTML_TEMPLATE.format(
            title=title,
            content_escaped=content_escaped,
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

def preprocess_content(content):
    """
    预处理内容，确保能被JavaScript正确解析
    :param content: 原始内容
    :return: 处理后的内容
    """
    # 如果内容没有明确的【】分段，尝试进行格式化
    if "【今日热点话题】" not in content and "【热点话题】" not in content and "【今日话题】" not in content:
        # 尝试从内容中提取各部分
        processed = ""
        
        # 提取聊天活跃度/热点话题
        activity_match = re.search(r'(活跃度|热点话题|今日话题)[：:]?([\s\S]*?)(?=重要消息|金句|总结|$)', content, re.IGNORECASE)
        if activity_match:
            processed += "【今日热点话题】\n" + activity_match.group(2).strip() + "\n\n"
        
        # 提取重要消息
        topics_match = re.search(r'重要消息[：:]?([\s\S]*?)(?=金句|总结|$)', content, re.IGNORECASE)
        if topics_match:
            processed += "【重要消息】\n" + topics_match.group(1).strip() + "\n\n"
        
        # 提取金句
        sentiment_match = re.search(r'金句[：:]?([\s\S]*?)(?=总结|$)', content, re.IGNORECASE)
        if sentiment_match:
            processed += "【金句】\n" + sentiment_match.group(1).strip() + "\n\n"
        
        # 提取总结
        summary_match = re.search(r'总结[：:]?([\s\S]*)', content, re.IGNORECASE)
        if summary_match:
            processed += "【总结】\n" + summary_match.group(1).strip() + "\n\n"
        
        # 如果仍然没有合适的分段，使用fallback方式分割内容
        if not processed or "【" not in processed:
            lines = content.split('\n')
            # 跳过前两行（通常是标题和空行）
            start_idx = 0
            for i in range(min(3, len(lines))):
                if "日报" in lines[i] or "字数" in lines[i] or not lines[i].strip():
                    start_idx = i + 1
            
            # 强制分段
            chunks = []
            current_chunk = []
            for line in lines[start_idx:]:
                if line.strip() and (line.startswith('**') or line.strip().startswith('-')):
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = []
                current_chunk.append(line)
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            
            if len(chunks) >= 4:  # 尝试匹配我们的4个部分
                processed = "【今日热点话题】\n" + chunks[0] + "\n\n"
                processed += "【重要消息】\n" + chunks[1] + "\n\n"
                processed += "【金句】\n" + chunks[2] + "\n\n"
                processed += "【总结】\n" + '\n'.join(chunks[3:]) + "\n\n"
            else:
                # 最后的fallback：把所有内容放到一起
                processed = "【聊天摘要】\n" + content
        
        return processed
    return content

# 测试日报摘要文本
TEST_SUMMARY = """【今日热点话题】
1. 用户讨论了最新的软件更新和功能改进
2. 关于周末团建活动的地点选择讨论
3. 新项目进度和技术选型讨论
4. 分享了几个有趣的技术文章和视频
5. 讨论了最新的行业动态和市场变化

【重要消息】
1. 项目经理宣布下周一将召开项目评审会议
2. 团队新成员张三将于下周加入
3. 本月绩效考核时间调整到月底最后一周

【金句】
1. "不要用战术上的勤奋掩盖战略上的懒惰"
2. "写代码要像写诗一样优雅"
3. "调试困难的根本原因在于程序员不知道他们在做什么"

【今日总结】
今天群内讨论热烈，主要围绕项目进展和团队建设，技术分享内容丰富，对问题的解决提供了多角度思路。"""

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
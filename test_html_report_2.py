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
            
            // 首先，清理内容，去除分隔符和前言
            let cleanedContent = content;
            
            // 1. 尝试找到正文内容（通常在分隔符 "---" 之后）
            const separatorPattern = /---\s*\n/g;
            const contentParts = content.split(separatorPattern);
            
            if (contentParts.length > 1) {{
                // 选择分隔符后的第一部分作为主要内容
                cleanedContent = contentParts[1];
                // 如果后面还有分隔符，只取到下一个分隔符之前
                const nextSeparatorIndex = cleanedContent.indexOf('---');
                if (nextSeparatorIndex > 0) {{
                    cleanedContent = cleanedContent.substring(0, nextSeparatorIndex).trim();
                }}
            }}
            
            // 2. 删除"注："开头的注释部分
            cleanedContent = cleanedContent.replace(/\n注[:：][\s\S]*$/, '');
            
            // 3. 替换内容中的反引号
            cleanedContent = cleanedContent.replace(/`([^`]+)`/g, '$1');
            
            // 调试输出清理后的内容（你可以稍后删除这行）
            console.log("清理后的内容:", cleanedContent);
            
            let currentSection = null;
            let currentContent = [];
            
            // 解析内容分段 - 增强版，支持多种标题格式
            cleanedContent.split('\\n').forEach(line => {{
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
                let allContent = cleanedContent.split('\\n');
                let fullText = allContent.join('\\n');
                
                // 尝试查找标题模式
                let matches;
                
                // 更灵活的模式匹配，捕获标题后的所有内容直到下一个标题
                const regexPatterns = [
                    {{ pattern: /(聊天活跃度|活跃度|话题分析|今日热点|热点话题)[：:：]?\s*([\s\S]*?)(?=(?:话题分析|重要消息|情感分析|互动亮点|总结|$))/i, section: "聊天活跃度" }},
                    {{ pattern: /(话题分析)[：:：]?\s*([\s\S]*?)(?=(?:情感分析|互动亮点|重要消息|总结|$))/i, section: "话题分析" }},
                    {{ pattern: /(重要消息|重要通知)[：:：]?\s*([\s\S]*?)(?=(?:情感分析|互动亮点|总结|$))/i, section: "重要消息" }},
                    {{ pattern: /(情感分析|互动亮点)[：:：]?\s*([\s\S]*?)(?=(?:总结|$))/i, section: "情感分析" }},
                    {{ pattern: /(总结)[：:：]?\s*([\s\S]*?)(?=$)/i, section: "总结" }}
                ];
                
                for (const {{ pattern, section }} of regexPatterns) {{
                    matches = fullText.match(pattern);
                    if (matches && matches[2] && matches[2].trim()) {{
                        sections[section] = [matches[2].trim()];
                    }}
                }}
                
                // 如果还是没有找到合适的部分，尝试根据整段文本进行划分
                if (Object.keys(sections).length === 0) {{
                    // 尝试基于行的启发式划分
                    let lines = cleanedContent.split('\\n').filter(line => line.trim());
                    let currentSection = null;
                    let currentSectionContent = [];
                    
                    for (const line of lines) {{
                        // 检查行是否可能是标题
                        if (line.trim().length < 30 && 
                            (line.includes('活跃度') || 
                             line.includes('话题') || 
                             line.includes('重要') || 
                             line.includes('情感') || 
                             line.includes('互动') || 
                             line.includes('总结'))) {{
                            
                            // 保存之前的部分
                            if (currentSection && currentSectionContent.length > 0) {{
                                sections[currentSection] = currentSectionContent;
                            }}
                            
                            // 设置新的部分
                            if (line.includes('活跃度') || line.includes('热点')) {{
                                currentSection = "聊天活跃度";
                            }} else if (line.includes('话题')) {{
                                currentSection = "话题分析";
                            }} else if (line.includes('重要')) {{
                                currentSection = "重要消息";
                            }} else if (line.includes('情感') || line.includes('互动')) {{
                                currentSection = "情感分析";
                            }} else if (line.includes('总结')) {{
                                currentSection = "总结";
                            }}
                            
                            currentSectionContent = [];
                        }} else if (currentSection) {{
                            currentSectionContent.push(line);
                        }}
                    }}
                    
                    // 保存最后一个部分
                    if (currentSection && currentSectionContent.length > 0) {{
                        sections[currentSection] = currentSectionContent;
                    }}
                }}
                
                // 最后的回退：如果真的没找到，就全部作为一个部分处理
                if (Object.keys(sections).length === 0) {{
                    sections["内容摘要"] = [cleanedContent];
                }}
            }}
            
            // 处理内容分发 - 支持更灵活的标题映射
            const contentMapping = {{
                '今日热点话题': document.getElementById('topics-content'),
                '热点话题': document.getElementById('topics-content'),
                '活跃度': document.getElementById('topics-content'),
                '聊天活跃度': document.getElementById('topics-content'),
                '话题分析': document.getElementById('topics-content'),
                
                '重要消息': document.getElementById('important-content'),
                '重要通知': document.getElementById('important-content'),
                '重要事项': document.getElementById('important-content'),
                
                '金句': document.getElementById('quotes-content'),
                '精彩发言': document.getElementById('quotes-content'),
                '情感分析': document.getElementById('quotes-content'),
                '互动亮点': document.getElementById('quotes-content'),
                '经典语录': document.getElementById('quotes-content'),
                '内容摘要': document.getElementById('quotes-content'),
                
                '总结': document.getElementById('summary-content'),
                '聊天总结': document.getElementById('summary-content'),
                '日报总结': document.getElementById('summary-content')
            }};
            
            // 如果没有找到任何部分，显示一个"未能分析"消息
            if (Object.keys(sections).length === 0) {{
                document.getElementById('topics-content').innerHTML = '<p>未能正确识别内容格式</p>';
                document.getElementById('summary-content').innerHTML = '<p>' + content + '</p>';
                return;
            }}
            
            // 填充内容到对应区块
            for (let sectionName in sections) {{
                const element = contentMapping[sectionName];
                if (element) {{
                    element.innerHTML = formatContent(sections[sectionName].join('\\n\\n'));
                }}
            }}
            
            // 检查并填充空白区块
            for (const elementId of ['topics-content', 'important-content', 'quotes-content', 'summary-content']) {{
                const element = document.getElementById(elementId);
                if (!element.innerHTML.trim()) {{
                    element.innerHTML = '<em>无内容</em>';
                }}
            }}
            
            // 如果content_check函数查找不到内容，我们强制在这里设置一个标记
            // 这样即使内容无法正确解析，也不会导致截图失败
            window.hasValidContent = true;
        }}
        
        // 格式化内容，支持简单的Markdown格式
        function formatContent(text) {{
            if (!text) return '<em>无内容</em>';
            
            // 转换Markdown风格的列表
            let html = text.replace(/^\s*[-*•]\s+(.+?)$/gm, '<li>$1</li>')
                           .replace(/^\s*(\d+)[.)、]\s+(.+?)$/gm, '<li>$2</li>');
            
            // 将连续的<li>元素包裹在<ul>中
            let parts = html.split(/(<li>.*?<\/li>)/g);
            let result = '';
            let inList = false;
            
            for (let part of parts) {{
                if (part.startsWith('<li>')) {{
                    if (!inList) {{
                        result += '<ul>';
                        inList = true;
                    }}
                    result += part;
                }} else {{
                    if (inList) {{
                        result += '</ul>';
                        inList = false;
                    }}
                    // 处理普通段落
                    if (part.trim()) {{
                        // 分割成段落
                        const paragraphs = part.split(/\n\s*\n/);
                        for (let p of paragraphs) {{
                            if (p.trim()) {{
                                result += '<p>' + p.trim() + '</p>';
                            }}
                        }}
                    }}
                }}
            }}
            
            if (inList) {{
                result += '</ul>';
            }}
            
            // 如果没有添加任何HTML标签，则作为单个段落处理
            if (!result.includes('<')) {{
                result = '<p>' + text + '</p>';
            }}
            
            return result;
        }}
        
        // 页面加载后执行
        window.onload = function() {{
            fillContent();
        }};
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
            try:
                await page.goto(f"file://{html_path}", timeout=30000)  # 增加超时时间到30秒
            except Exception as e:
                log_error_msg(f"加载HTML文件失败: {str(e)}")
                await browser.close()
                return False
            
            # 等待内容加载
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
                await page.wait_for_timeout(2000)  # 额外等待2秒确保JavaScript执行完毕
            except Exception as e:
                log_warning(f"等待页面加载时出错: {str(e)}，尝试继续...")
            
            # 验证页面内容是否有实际内容
            try:
                content_check = await page.evaluate("""() => {
                    // 如果页面上设置了标记，直接认为有内容
                    if (window.hasValidContent) {
                        return true;
                    }
                    
                    // 检查所有内容区块
                    const contentElements = document.querySelectorAll('.bento-item-content');
                    let hasContent = false;
                    for(let el of contentElements) {
                        // 排除"无内容"占位文本
                        if(el.innerText.trim().length > 10 && !el.innerText.includes('无内容')) {
                            hasContent = true;
                            break;
                        }
                    }
                    return hasContent;
                }""")
                
                if not content_check:
                    log_warning("页面内容验证失败，未找到有效的内容区块")
                    # 不要立即返回失败，尝试继续生成图片
                    log_warning("尝试继续生成图片，即使内容区块可能为空")
            except Exception as e:
                log_warning(f"验证页面内容时出错: {str(e)}，尝试继续...")
            
            screenshot_success = False
            
            # 只截取报告容器部分，去掉周围的白边
            try:
                container = await page.query_selector('.bento-container')
                if container:
                    await container.screenshot(path=output_path)
                    log_info("成功截取Bento Grid容器部分")
                    screenshot_success = True
                else:
                    # 如果找不到容器，则截取整个页面
                    log_warning("未找到Bento容器，将尝试截取整个页面")
            except Exception as e:
                log_warning(f"截取容器时出错: {str(e)}，尝试截取整个页面...")
            
            # 如果容器截图失败，尝试截取整个页面
            if not screenshot_success:
                try:
                    await page.screenshot(path=output_path, full_page=True)
                    log_info("成功截取整个页面")
                    screenshot_success = True
                except Exception as e:
                    log_error_msg(f"截取整个页面失败: {str(e)}")
                    screenshot_success = False
            
            await browser.close()
            
        if screenshot_success and os.path.exists(output_path):
            log_info(f"HTML转图片成功，输出到: {output_path}")
            return True
        else:
            log_warning("HTML转图片失败，未能生成有效的图片文件")
            return False
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
        
        # 检查内容是否为空
        if not content or not content.strip():
            log_error_msg("内容为空，无法生成HTML")
            return None, None
        
        # 获取字体路径
        font_path = await get_font_path()
        if not font_path:
            log_warning("找不到可用的中文字体")
        
        # 预处理内容，确保能被正确解析
        processed_content = preprocess_content(content)
        
        # 如果预处理失败，则使用文本方式生成报告
        if not processed_content:
            log_warning("预处理内容失败，使用文本方式生成报告")
            return None, None
        
        # 转义内容中的大括号，防止格式化错误 - 更彻底的处理
        processed_content = processed_content.replace("{", "{{").replace("}", "}}")
        
        # 内容需要转义，供JavaScript处理
        content_escaped = processed_content.replace('\\', '\\\\').replace('`', '\\`')
        
        # 使用更安全的方式构建HTML内容，避免直接使用format
        try:
            # 尝试生成完整的HTML - 显式指定所有参数
            html_content = HTML_TEMPLATE.format(
                title=title,
                content_escaped=content_escaped,
                date=date_str,
                font_path=font_path
            )
        except KeyError as ke:
            log_error_msg(f"格式化HTML时发生KeyError错误: {ke}")
            log_error_msg(f"尝试的参数: title={title[:20]}..., date={date_str}, font_path={font_path}")
            # 第二种尝试方法 - 手动替换
            html_content = HTML_TEMPLATE
            html_content = html_content.replace("{title}", title)
            html_content = html_content.replace("{content_escaped}", content_escaped)
            html_content = html_content.replace("{date}", date_str)
            html_content = html_content.replace("{font_path}", font_path)
            log_info("使用手动替换方法构建HTML成功")
        
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
            # 检查生成的图片文件是否合理
            try:
                if os.path.exists(temp_img_path):
                    file_size = os.path.getsize(temp_img_path)
                    if file_size < 5000:  # 小于5KB的图片可能是空白或错误
                        log_warning(f"生成的图片大小异常: {file_size} 字节，可能是空白图片")
                        return temp_html_path, None
                    
                    # 尝试用PIL打开检查图片是否有效
                    from PIL import Image
                    try:
                        with Image.open(temp_img_path) as img:
                            width, height = img.size
                            if width < 100 or height < 100:
                                log_warning(f"生成的图片尺寸异常: {width}x{height}，可能是无效图片")
                                return temp_html_path, None
                            log_info(f"图片检查成功: 大小 {file_size/1024:.2f} KB, 尺寸 {width}x{height}")
                    except Exception as e:
                        log_warning(f"图片验证失败: {str(e)}")
                        return temp_html_path, None
                    
                    return temp_html_path, temp_img_path
                else:
                    log_warning("图片生成函数返回成功，但文件不存在")
                    return temp_html_path, None
            except Exception as e:
                log_warning(f"验证图片时出错: {str(e)}")
                return temp_html_path, None
        else:
            return temp_html_path, None
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        log_error_msg(f"HTML转图片过程中出错: {str(e)}")
        log_error_msg(f"完整错误堆栈:\n{error_msg}")
        return None, None

def preprocess_content(content):
    """
    预处理内容，确保能被JavaScript正确解析
    :param content: 原始内容
    :return: 处理后的内容或None（表示无法解析，应使用文本方式）
    """
    # 如果内容为空，直接返回None表示无法处理
    if not content or not content.strip():
        return None
    
    # 清理分隔符和特殊格式
    # 移除分隔线如 "---"
    content = re.sub(r'\n-{3,}\n', '\n\n', content)
    # 移除注释部分
    content = re.sub(r'\n注[:：].*?$', '', content, flags=re.MULTILINE)
    
    # 标题映射表 - 将各种可能的标题格式统一
    title_mappings = {
        # 热点/活跃度
        r'【今日热点话题】': "【今日热点话题】",
        r'【热点话题】': "【今日热点话题】",
        r'【今日话题】': "【今日热点话题】",
        r'【聊天活跃度】': "【今日热点话题】",
        r'【活跃度】': "【今日热点话题】",
        r'【话题分析】': "【今日热点话题】",
        r'【群聊热点】': "【今日热点话题】",
        r'【主要话题】': "【今日热点话题】",
        
        # 重要消息
        r'【重要消息】': "【重要消息】",
        r'【重要通知】': "【重要消息】",
        r'【重要事项】': "【重要消息】",
        r'【关键信息】': "【重要消息】",
        r'【重点内容】': "【重要消息】",
        
        # 金句部分
        r'【金句】': "【金句】",
        r'【精彩发言】': "【金句】",
        r'【经典语录】': "【金句】",
        r'【情感分析】': "【金句】",
        r'【互动亮点】': "【金句】",
        r'【精彩语录】': "【金句】",
        r'【群聊金句】': "【金句】",
        r'【有趣发言】': "【金句】",
        
        # 总结部分
        r'【总结】': "【总结】",
        r'【聊天总结】': "【总结】",
        r'【日报总结】': "【总结】",
        r'【整体总结】': "【总结】",
        r'【今日总结】': "【总结】"
    }
    
    # 检查是否已经有标准化的标题格式
    normalized_content = content
    for original, standard in title_mappings.items():
        if re.search(original, content, re.IGNORECASE):
            normalized_content = re.sub(original, standard, normalized_content, flags=re.IGNORECASE)
    
    # 如果已经标准化了标题，则使用标准化后的内容
    if "【今日热点话题】" in normalized_content and "【重要消息】" in normalized_content or \
       "【今日热点话题】" in normalized_content and "【金句】" in normalized_content or \
       "【今日热点话题】" in normalized_content and "【总结】" in normalized_content:
        return normalized_content
    
    # 处理标记语法，去掉backticks和其他markdown标记
    normalized_content = re.sub(r'`([^`]+)`', r'\1', normalized_content)
    normalized_content = re.sub(r'\*\*([^*]+)\*\*', r'\1', normalized_content)
    
    # 尝试从内容中提取各部分 - 使用更宽松的模式
    processed = ""
    
    # 改进的正则表达式，更灵活的匹配方式
    sections_patterns = [
        # 热点话题/活跃度部分的多种可能表述
        (r'(?:今日热点话题|热点话题|今日话题|主要话题|群聊热点|讨论热点|活跃度|聊天主题|聊天活跃度|话题分析)[：:：]?\s*([\s\S]*?)(?=(?:重要消息|重要通知|重要事项|金句|精彩发言|经典语录|情感分析|互动亮点|总结|聊天总结|日报总结|$))', "【今日热点话题】"),
        
        # 重要消息部分的多种可能表述
        (r'(?:重要消息|重要通知|重要事项|关键信息|重点内容)[：:：]?\s*([\s\S]*?)(?=(?:金句|精彩发言|经典语录|情感分析|互动亮点|总结|聊天总结|日报总结|$))', "【重要消息】"),
        
        # 金句部分的多种可能表述
        (r'(?:金句|精彩发言|经典语录|精彩语录|群聊金句|有趣发言|情感分析|互动亮点)[：:：]?\s*([\s\S]*?)(?=(?:总结|聊天总结|日报总结|$))', "【金句】"),
        
        # 总结部分的多种可能表述
        (r'(?:总结|聊天总结|日报总结|整体总结|今日总结)[：:：]?\s*([\s\S]*)', "【总结】"),
    ]
    
    # 应用所有正则表达式进行匹配
    section_contents = {}
    for pattern, section_title in sections_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # 在新的正则表达式中，内容在组索引1
            section_content = match.group(1).strip()
            if section_content:
                section_contents[section_title] = section_content
                break  # 只取第一个匹配的内容
    
    # 构建格式化内容
    for section_title in ["【今日热点话题】", "【重要消息】", "【金句】", "【总结】"]:
        if section_title in section_contents:
            processed += f"{section_title}\n{section_contents[section_title]}\n\n"
    
    # 如果至少找到一个部分，则认为处理成功（条件放宽）
    if processed and len(section_contents) >= 1:
        return processed
    
    # 尝试使用结构化分析 - 基于行的分析
    lines = content.split('\n')
    
    # 跳过可能的标题行和分隔符行
    start_idx = 0
    for i in range(min(10, len(lines))):  # 扩大搜索范围
        if not lines[i].strip() or "日报" in lines[i] or "群聊" in lines[i] or "总结" in lines[i].lower() or lines[i].strip() == '---':
            start_idx = i + 1
            continue
        # 如果找到了标题形式的行，从这里开始
        if re.search(r'^[-•*] ', lines[i].strip()) or re.search(r'^\d+[\.\)、]', lines[i].strip()):
            break
    
    # 更智能的分段：识别标题行和列表开始
    chunks = []
    current_chunk = []
    current_title = ""
    in_list = False
    
    for i, line in enumerate(lines[start_idx:]):
        line_stripped = line.strip()
        
        # 跳过空行
        if not line_stripped:
            continue
        
        # 检测标题行（以"-"开头的列表项不算标题）
        if not line_stripped.startswith('-') and not line_stripped.startswith('•') and not line_stripped.startswith('*') and not re.match(r'^\d+[\.\)、]', line_stripped):
            is_title = False
            
            # 检查是否是标题行
            for keyword in ['活跃', '热点', '话题', '主要', '重要', '关键', '金句', '发言', '语录', '总结', '情感', '互动', '亮点']:
                if keyword in line_stripped.lower():
                    is_title = True
                    break
            
            if is_title:
                # 保存之前的块
                if current_chunk:
                    if current_title:
                        title_content = current_title + "\n" + "\n".join(current_chunk)
                    else:
                        title_content = "\n".join(current_chunk)
                    chunks.append(title_content)
                    current_chunk = []
                
                current_title = line_stripped
                continue
        
        # 将行添加到当前块
        current_chunk.append(line_stripped)
    
    # 添加最后一个块
    if current_chunk:
        if current_title:
            title_content = current_title + "\n" + "\n".join(current_chunk)
        else:
            title_content = "\n".join(current_chunk)
        chunks.append(title_content)
    
    # 如果能够分割出块，尝试构建标准格式
    if len(chunks) >= 1:
        # 映射块到标准部分
        standard_sections = ["【今日热点话题】", "【重要消息】", "【金句】", "【总结】"]
        mapped_sections = {}
        
        # 根据内容特征进行映射
        for chunk in chunks:
            chunk_lower = chunk.lower()
            
            if any(keyword in chunk_lower for keyword in ['活跃度', '热点', '话题分析', '今日话题']):
                mapped_sections["【今日热点话题】"] = chunk
            elif any(keyword in chunk_lower for keyword in ['重要消息', '通知', '事项']):
                mapped_sections["【重要消息】"] = chunk
            elif any(keyword in chunk_lower for keyword in ['金句', '发言', '情感', '互动', '亮点']):
                mapped_sections["【金句】"] = chunk
            elif any(keyword in chunk_lower for keyword in ['总结', '总体']):
                mapped_sections["【总结】"] = chunk
            else:
                # 如果无法分类，根据位置进行分配
                for i, section in enumerate(standard_sections):
                    if section not in mapped_sections and i < len(chunks):
                        mapped_sections[section] = chunk
                        break
        
        # 构建最终格式
        processed = ""
        for section in standard_sections:
            if section in mapped_sections:
                processed += f"{section}\n{mapped_sections[section]}\n\n"
        
        if processed:
            return processed
    
    # 最后的回退机制：创建一个单一的"聊天摘要"部分
    processed = f"【聊天摘要】\n{content.strip()}"
    return processed

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
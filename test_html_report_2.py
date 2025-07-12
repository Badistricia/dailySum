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
        // 全局状态管理
        window.dailySumState = {
            debugMode: true,
            contentFound: false,
            processingComplete: false,
            sectionStatus: {
                "today-topics": false,
                "important-msgs": false,
                "quotes": false,
                "summary": false
            },
            log: function(msg, data) {
                if (this.debugMode) {
                    if (data) {
                        console.log(`[日报解析] ${msg}`, data);
                    } else {
                        console.log(`[日报解析] ${msg}`);
                    }
                }
            }
        };

        // 初始化函数 - 页面加载后调用
        function initializeContent() {
            window.dailySumState.log("开始解析日报内容...");
            const content = `{content_escaped}`;
            
            // 执行内容提取
            extractAndFillContent(content);
            
            // 标记处理完成
            window.dailySumState.processingComplete = true;
            window.hasValidContent = window.dailySumState.contentFound;
            
            // 调试信息
            window.dailySumState.log("处理状态:", window.dailySumState);
            window.dailySumState.log("内容提取完成. 有效内容:", window.dailySumState.contentFound);
        }

        // 主要提取函数
        function extractAndFillContent(content) {
            if (!content || content.trim() === '') {
                window.dailySumState.log("内容为空，无法处理");
                return;
            }

            window.dailySumState.log("原始内容长度:", content.length);
            
            // 清理内容
            let cleanedContent = content
                .replace(/`([^`]+)`/g, '$1') // 移除反引号
                .replace(/---/g, '')         // 移除分隔线
                .trim();

            // 多种方法依次尝试提取内容
            const extractionMethods = [
                extractByExplicitSections,    // 方法1: 通过明确的章节标题提取
                extractByTextPatterns,        // 方法2: 通过文本模式匹配提取
                extractByContentSplitting,    // 方法3: 通过内容分割提取
                createFromWholeText          // 方法4: 使用整个文本创建内容
            ];

            // 依次尝试各种提取方法
            for (const method of extractionMethods) {
                try {
                    window.dailySumState.log(`尝试使用提取方法: ${method.name}`);
                    const sections = method(cleanedContent);
                    
                    // 如果提取成功，填充内容并结束
                    if (fillContentSections(sections)) {
                        window.dailySumState.log(`使用 ${method.name} 成功提取内容`);
                        return;
                    }
                } catch (error) {
                    window.dailySumState.log(`使用 ${method.name} 提取失败: ${error.message}`);
                }
            }

            // 如果所有方法都失败，使用整个内容作为摘要
            window.dailySumState.log("所有提取方法均失败，使用整个内容作为摘要");
            fillEmergencyContent(cleanedContent);
        }

        // 方法1: 通过明确的章节标题提取
        function extractByExplicitSections(text) {
            const sections = {
                "today-topics": [],
                "important-msgs": [],
                "quotes": [],
                "summary": []
            };
            
            // 定义各种可能的节标题及其映射
            const sectionKeywords = {
                "today-topics": ["聊天活跃度", "活跃度", "今日热点话题", "热点话题", "今日话题", "话题分析", "群聊热点"],
                "important-msgs": ["重要消息", "重要通知", "重要事项", "关键信息"],
                "quotes": ["金句", "精彩发言", "经典语录", "情感分析", "互动亮点", "精彩语录"],
                "summary": ["总结", "聊天总结", "日报总结", "整体总结", "今日总结"]
            };

            // 将文本分割成行
            const lines = text.split('\n');
            let currentSection = null;
            let currentContent = [];
            
            // 遍历每行寻找节标题和内容
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (!line) continue;
                
                // 检查是否是节标题
                let matchedSection = null;
                for (const [section, keywords] of Object.entries(sectionKeywords)) {
                    for (const keyword of keywords) {
                        // 寻找【关键词】格式或者以关键词开头的行
                        if (line.includes(`【${keyword}】`) || line.startsWith(keyword)) {
                            matchedSection = section;
                            break;
                        }
                    }
                    if (matchedSection) break;
                }
                
                // 如果找到新节，保存之前的内容并重置
                if (matchedSection) {
                    if (currentSection && currentContent.length > 0) {
                        sections[currentSection] = sections[currentSection].concat(currentContent);
                    }
                    currentSection = matchedSection;
                    currentContent = [];
                } 
                // 否则添加到当前节内容
                else if (currentSection) {
                    currentContent.push(line);
                }
            }
            
            // 处理最后一个节的内容
            if (currentSection && currentContent.length > 0) {
                sections[currentSection] = sections[currentSection].concat(currentContent);
            }
            
            return sections;
        }
        
        // 方法2: 通过文本模式匹配提取
        function extractByTextPatterns(text) {
            const sections = {
                "today-topics": [],
                "important-msgs": [],
                "quotes": [],
                "summary": []
            };
            
            // 尝试匹配各种模式
            const patterns = {
                "today-topics": [/(聊天活跃度|活跃度|今日热点话题|热点话题|今日话题|话题分析)[\s\S]*?((?=重要消息|重要通知|金句|精彩发言|情感分析|互动亮点|总结|$))/i],
                "important-msgs": [/(重要消息|重要通知|重要事项)[\s\S]*?((?=金句|精彩发言|情感分析|互动亮点|总结|$))/i],
                "quotes": [/(金句|精彩发言|经典语录|情感分析|互动亮点)[\s\S]*?((?=总结|$))/i],
                "summary": [/(总结|今日总结|聊天总结)[\s\S]*?$/i]
            };
            
            // 对每个节应用模式
            for (const [section, sectionPatterns] of Object.entries(patterns)) {
                for (const pattern of sectionPatterns) {
                    const match = text.match(pattern);
                    if (match && match[0]) {
                        const content = match[0].replace(new RegExp(match[1], 'i'), '').trim();
                        if (content) {
                            sections[section] = [content];
                            window.dailySumState.log(`模式匹配提取到 ${section} 内容`);
                        }
                    }
                }
            }
            
            return sections;
        }
        
        // 方法3: 通过内容分割提取
        function extractByContentSplitting(text) {
            const sections = {
                "today-topics": [],
                "important-msgs": [],
                "quotes": [],
                "summary": []
            };
            
            // 提取项目符号列表（以-或•开头的行）
            const listItems = text.match(/(?:^|\n)[\s]*[-•*][\s]+.+(?:\n|$)/g) || [];
            
            // 提取段落（非列表项的文本块）
            const paragraphs = text
                .split('\n')
                .filter(line => line.trim() && !line.trim().match(/^[\s]*[-•*]/))
                .map(line => line.trim());
            
            // 根据内容量分配到不同部分
            if (listItems.length >= 3) {
                // 如果有足够的列表项，分配给不同部分
                const chunks = Math.ceil(listItems.length / 3);
                sections["today-topics"] = listItems.slice(0, chunks);
                sections["important-msgs"] = listItems.slice(chunks, chunks * 2);
                sections["quotes"] = listItems.slice(chunks * 2);
            } else if (paragraphs.length >= 3) {
                // 如果有足够的段落，分配给不同部分
                const chunks = Math.ceil(paragraphs.length / 3);
                sections["today-topics"] = paragraphs.slice(0, chunks);
                sections["important-msgs"] = paragraphs.slice(chunks, chunks * 2);
                sections["quotes"] = paragraphs.slice(chunks * 2);
            } else {
                // 内容不足，尽量分配
                if (listItems.length > 0) sections["today-topics"] = listItems;
                if (paragraphs.length > 0) {
                    sections["important-msgs"] = paragraphs.slice(0, Math.ceil(paragraphs.length / 2));
                    sections["quotes"] = paragraphs.slice(Math.ceil(paragraphs.length / 2));
                }
            }
            
            // 总是添加一个总结
            sections["summary"] = ["今日群聊内容已整理完毕。"];
            
            return sections;
        }
        
        // 方法4: 使用整个文本创建内容
        function createFromWholeText(text) {
            return {
                "today-topics": [text],
                "important-msgs": ["请参考今日热点话题部分。"],
                "quotes": ["内容较少，无法提取特定引言。"],
                "summary": ["今日群聊内容较为简单，详见上方内容。"]
            };
        }
        
        // 紧急填充 - 当所有方法都失败时使用
        function fillEmergencyContent(text) {
            document.getElementById('topics-content').innerHTML = formatContent(text);
            document.getElementById('important-content').innerHTML = "<p>内容解析失败，请查看第一部分</p>";
            document.getElementById('quotes-content').innerHTML = "<p>内容解析失败，请查看第一部分</p>";
            document.getElementById('summary-content').innerHTML = "<p>内容解析失败，请查看第一部分</p>";
            
            window.dailySumState.contentFound = true;
            window.dailySumState.log("使用紧急填充方法");
        }
        
        // 填充内容到各部分
        function fillContentSections(sections) {
            let hasContent = false;
            
            // 映射到HTML中的ID
            const sectionToId = {
                "today-topics": 'topics-content',
                "important-msgs": 'important-content',
                "quotes": 'quotes-content',
                "summary": 'summary-content'
            };
            
            // 填充各个部分
            for (const [section, content] of Object.entries(sections)) {
                if (content && content.length > 0) {
                    const elementId = sectionToId[section];
                    const element = document.getElementById(elementId);
                    
                    if (element) {
                        element.innerHTML = formatContent(content.join('\n'));
                        window.dailySumState.sectionStatus[section] = true;
                        hasContent = true;
                    }
                }
            }
            
            // 处理空白区块
            for (const [section, id] of Object.entries(sectionToId)) {
                const element = document.getElementById(id);
                if (!element.innerHTML || element.innerHTML.trim() === '') {
                    element.innerHTML = '<em>无内容</em>';
                }
            }
            
            window.dailySumState.contentFound = hasContent;
            return hasContent;
        }
        
        // 格式化内容
        function formatContent(text) {
            if (!text || text.trim() === '') return '<em>无内容</em>';
            
            // 移除多余的【标题】标记
            const cleanText = text
                .replace(/【[^】]+】/g, '')
                .replace(/^\s*[:-]\s*/gm, '')
                .trim();
                
            if (!cleanText) return '<em>无内容</em>';
            
            // 处理列表项
            let formattedText = cleanText
                // 处理以-、*或•开头的列表项
                .replace(/^[\s]*[-*•][\s]+(.+?)$/gm, '<li>$1</li>')
                // 处理以数字开头的列表项
                .replace(/^[\s]*(\d+)[\.)、][\s]+(.+?)$/gm, '<li>$2</li>')
                // 处理以-或其他字符开头但可能没有空格的情况
                .replace(/^[\s]*[-](.+?)$/gm, '<li>$1</li>');
            
            // 构建HTML
            let result = '';
            let inList = false;
            
            // 分行处理
            const lines = formattedText.split('\n');
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (!line) {
                    // 空行，结束列表
                    if (inList) {
                        result += '</ul>';
                        inList = false;
                    }
                    continue;
                }
                
                if (line.startsWith('<li>')) {
                    // 列表项
                    if (!inList) {
                        result += '<ul>';
                        inList = true;
                    }
                    result += line;
                } else {
                    // 普通段落
                    if (inList) {
                        result += '</ul>';
                        inList = false;
                    }
                    
                    // 包装段落
                    result += '<p>' + line + '</p>';
                }
            }
            
            // 关闭未闭合的列表
            if (inList) {
                result += '</ul>';
            }
            
            // 如果结果为空，返回原始文本
            if (result.trim() === '') {
                result = '<p>' + text.trim() + '</p>';
            }
            
            return result;
        }
        
        // 在页面加载完成后执行初始化
        document.addEventListener('DOMContentLoaded', initializeContent);
        
        // 立即执行一次，以防DOMContentLoaded已经触发
        setTimeout(initializeContent, 100);
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
            
            # 添加控制台消息监听
            page.on("console", lambda msg: log_info(f"浏览器控制台: {msg.text}"))
            
            # 加载HTML文件
            try:
                log_info(f"正在加载HTML文件: {html_path}")
                await page.goto(f"file://{html_path}", timeout=30000)  # 增加超时时间到30秒
            except Exception as e:
                log_error_msg(f"加载HTML文件失败: {str(e)}")
                await browser.close()
                return False
            
            # 等待内容加载
            try:
                log_info("等待页面网络空闲...")
                await page.wait_for_load_state("networkidle", timeout=30000)
                
                # 增加等待时间，确保JavaScript完全执行
                log_info("等待JavaScript执行...")
                await page.wait_for_timeout(5000)  # 增加到5秒钟
                
                # 注入调试代码，帮助检测内容状态
                await page.evaluate("""() => {
                    if (!window.dailySumState) {
                        console.log("警告: dailySumState未定义，可能JavaScript未正确执行");
                        window.dailySumState = { contentFound: false, processingComplete: false };
                    }
                }""")
                
                # 等待JavaScript执行完成的标记
                try:
                    log_info("等待JavaScript处理完成标记...")
                    await page.wait_for_function("""() => {
                        return window.dailySumState && window.dailySumState.processingComplete === true;
                    }""", timeout=10000)  # 10秒超时
                    
                    log_info("JavaScript处理完成")
                except Exception as e:
                    log_warning(f"等待JavaScript执行完成超时: {str(e)}")
                    
                    # 尝试检查内容状态
                    content_status = await page.evaluate("""() => {
                        if (window.dailySumState) {
                            return {
                                contentFound: window.dailySumState.contentFound,
                                processingComplete: window.dailySumState.processingComplete,
                                sectionStatus: window.dailySumState.sectionStatus || {}
                            };
                        }
                        return { error: "dailySumState未定义" };
                    }""")
                    
                    log_info(f"内容状态检查: {content_status}")
            except Exception as e:
                log_warning(f"等待页面加载时出错: {str(e)}，尝试继续...")
            
            # 验证页面内容是否有实际内容
            try:
                log_info("验证页面内容...")
                content_check = await page.evaluate("""() => {
                    // 首先检查全局状态
                    if (window.dailySumState && window.dailySumState.contentFound) {
                        return { status: true, source: "dailySumState" };
                    }
                    
                    // 检查所有内容区块
                    const contentElements = document.querySelectorAll('.bento-item-content');
                    let hasContent = false;
                    let contentSummary = {};
                    
                    for(let el of contentElements) {
                        const id = el.id;
                        const text = el.innerText.trim();
                        const hasValidContent = text.length > 10 && !text.includes('无内容');
                        contentSummary[id] = {
                            length: text.length,
                            valid: hasValidContent,
                            preview: text.substring(0, 20)
                        };
                        
                        if (hasValidContent) {
                            hasContent = true;
                        }
                    }
                    
                    return { 
                        status: hasContent, 
                        source: "DOM检查",
                        contentSummary: contentSummary
                    };
                }""")
                
                log_info(f"内容验证结果: {content_check}")
                
                if not content_check.get('status', False):
                    log_warning("页面内容验证失败，未找到有效的内容区块")
                    # 不要立即返回失败，尝试继续生成图片
                    log_warning("尝试继续生成图片，即使内容区块可能为空")
            except Exception as e:
                log_warning(f"验证页面内容时出错: {str(e)}，尝试继续...")
            
            screenshot_success = False
            
            # 只截取报告容器部分，去掉周围的白边
            try:
                log_info("尝试截取Bento容器部分...")
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
                    log_info("尝试截取整个页面...")
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
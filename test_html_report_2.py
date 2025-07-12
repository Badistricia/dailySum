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

async def install_playwright_deps():
    """安装Playwright依赖"""
    if not PLAYWRIGHT_AVAILABLE:
        log_warning("Playwright未安装，无法安装依赖")
        return False
    
    try:
        from playwright.__main__ import main as playwright_main
        import sys
        
        log_info("检查Playwright依赖...")
        
        # 保存原始参数
        original_argv = sys.argv.copy()
        
        try:
            # 设置参数为install
            sys.argv = ['playwright', 'install', 'chromium']
            
            # 调用playwright的main函数
            await asyncio.to_thread(playwright_main)
            
            log_info("Playwright依赖安装完成")
            return True
        except SystemExit:
            # playwright_main可能会调用sys.exit()，我们捕获这个异常
            log_info("Playwright依赖可能已经安装")
            return True
        except Exception as e:
            log_warning(f"安装Playwright依赖失败: {str(e)}")
            return False
        finally:
            # 恢复原始参数
            sys.argv = original_argv
    except ImportError:
        log_warning("无法导入playwright.__main__，跳过依赖安装")
        return False
    except Exception as e:
        log_warning(f"安装Playwright依赖时出错: {str(e)}")
        return False

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
                
                # 增加等待时间，确保页面完全渲染
                log_info("等待页面渲染...")
                await page.wait_for_timeout(3000)  # 等待3秒钟
            except Exception as e:
                log_warning(f"等待页面加载时出错: {str(e)}，尝试继续...")
            
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

def preprocess_content(content):
    """
    预处理内容，确保能被正确解析
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
    
    # 如果所有方法都失败，返回原始内容
    return content

def check_dependencies():
    """检查依赖"""
    if not PLAYWRIGHT_AVAILABLE:
        log_warning("缺少Playwright库，无法进行HTML转图片，请安装: pip install playwright")
        return False
    return True 
import os
import json
import base64
import shutil
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
import re

# 导入第三方库
try:
    from playwright.async_api import async_playwright
    from nonebot.message import MessageSegment
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

import httpx
from .logger_helper import log_info, log_warning, log_error_msg, log_debug

# 导入配置
from .config import PROMPT_HTML_TEMPLATE, AI_API_KEY, AI_MODEL, AI_TEMPERATURE

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

# 深度学习客户端 - 简化版，专门用于HTML生成
class DeepSeekClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        log_info(f"DeepSeekClient 初始化完成，API Key: {'已设置' if api_key else '未设置'}")
        
    async def generate_html(self, prompt, model=AI_MODEL, temperature=AI_TEMPERATURE, max_retries=3, timeout=180.0):
        log_info(f"开始生成AI HTML摘要，模型: {model}, 温度: {temperature}")
        log_debug(f"提示词前200字符: {prompt[:200]}...")
        
        # 记录请求数据大小
        request_size = len(prompt.encode('utf-8'))
        log_info(f"请求数据大小: {request_size / 1024:.2f} KB")
        
        retry_count = 0
        while retry_count < max_retries:
            try:
                log_debug(f"尝试API请求 (尝试 {retry_count + 1}/{max_retries})...")
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.base_url,
                        headers=self.headers,
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": temperature
                        },
                        timeout=timeout
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    log_info(f"AI生成HTML成功，生成内容长度: {len(content)}")
                    log_debug(f"生成内容前100字符: {content[:100]}...")
                    
                    # 提取HTML代码块
                    html_content = self.extract_html(content)
                    if html_content:
                        log_info("成功提取HTML代码")
                        return html_content
                    else:
                        log_warning("未能从响应中提取HTML代码，使用原始响应")
                        return content
                else:
                    log_error_msg(f"DeepSeek API调用失败: {response.status_code} {response.text}")
                    retry_count += 1
                    await asyncio.sleep(2)  # 等待2秒再重试
            except httpx.TimeoutException:
                log_warning(f"API请求超时，尝试重试 ({retry_count + 1}/{max_retries})")
                retry_count += 1
                await asyncio.sleep(2)  # 等待2秒再重试
            except Exception as e:
                log_error_msg(f"DeepSeek API调用出错: {str(e)}")
                log_error_msg(traceback.format_exc())
                retry_count += 1
                await asyncio.sleep(2)  # 等待2秒再重试
        
        log_error_msg(f"达到最大重试次数 ({max_retries})，AI生成HTML失败")
        return None
    
    def extract_html(self, content):
        """提取HTML代码块，处理可能的markdown格式"""
        # 尝试匹配markdown风格的代码块
        html_match = re.search(r'```html\s*([\s\S]*?)\s*```', content)
        if html_match:
            return html_match.group(1).strip()
            
        # 尝试匹配无语言指定的代码块
        html_match = re.search(r'```\s*(<!DOCTYPE html>[\s\S]*?)\s*```', content)
        if html_match:
            return html_match.group(1).strip()
            
        # 尝试匹配整个HTML文档
        html_match = re.search(r'(<!DOCTYPE html>[\s\S]*)', content)
        if html_match:
            return html_match.group(1).strip()
            
        # 如果没有明确的代码块，但内容看起来像HTML
        if content.strip().startswith('<') and ('</html>' in content or '</body>' in content):
            return content.strip()
            
        return None

# AI客户端实例
ai_client = DeepSeekClient(AI_API_KEY)

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

async def html_to_screenshot(html_content, output_path):
    """
    使用Playwright将HTML内容转换为图片
    :param html_content: HTML内容字符串
    :param output_path: 输出图片路径
    :return: 是否成功
    """
    if not PLAYWRIGHT_AVAILABLE:
        log_warning("缺少Playwright库，无法进行HTML转图片，请安装: pip install playwright")
        return False
    
    # 创建临时HTML文件
    temp_html_path = output_path.replace('.png', '.html')
    with open(temp_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
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
            await page.goto(f"file://{os.path.abspath(temp_html_path)}")
            
            # 等待内容加载
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)  # 额外等待1秒确保JavaScript执行完毕
            
            # 获取主要内容的尺寸
            body_dimensions = await page.evaluate("""
                () => {
                    const body = document.body;
                    const container = document.querySelector('body > div') || body;
                    return {
                        width: container.offsetWidth,
                        height: container.offsetHeight
                    };
                }
            """)
            
            # 设置视口大小以适应内容
            viewport_width = min(body_dimensions['width'] + 40, 1200)  # 添加一些边距，最大宽度1200px
            viewport_height = body_dimensions['height'] + 40  # 添加一些边距
            
            await page.set_viewport_size({
                "width": viewport_width,
                "height": viewport_height
            })
            
            # 截取整个内容
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

async def generate_html_report(group_id, title, date_str, test_mode=False):
    """
    生成HTML日报并转换为图片
    :param group_id: 群号
    :param title: 标题
    :param date_str: 日期字符串
    :param test_mode: 是否为测试模式
    :return: HTML文件路径和图片路径
    """
    try:
        log_info(f"开始生成HTML日报，群号: {group_id}，日期: {date_str}")
        
        # 测试模式下使用预设的聊天记录
        if test_mode:
            chat_log = "这是测试聊天记录。\n用户A: 今天天气真好！\n用户B: 是啊，适合出去玩。\n用户C: 我们去公园吧？\n用户A: 好主意！"
        else:
            # 实际模式下需要从文件加载聊天记录
            log_file = os.path.join(DATA_DIR, f"{group_id}_{date_str}.json")
            if not os.path.exists(log_file):
                log_error_msg(f"找不到聊天记录文件: {log_file}")
                return None, None
                
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
                
                # 构建聊天记录文本
                chat_log = ""
                for msg in messages[:100]:  # 限制消息数量
                    chat_log += f"{msg['time']} {msg['user']}: {msg['content']}\n"
            except Exception as e:
                log_error_msg(f"读取聊天记录失败: {str(e)}")
                return None, None
        
        # 构建提示词
        prompt = PROMPT_HTML_TEMPLATE.format(
            group_name=group_id,
            title=title,
            date=date_str,
            chat_log=chat_log
        )
        
        # 调用AI生成HTML
        html_content = await ai_client.generate_html(prompt)
        
        if not html_content:
            log_error_msg("AI生成HTML失败")
            return None, None
        
        # 保存HTML文件
        temp_html_path = os.path.join(DATA_DIR, f"report3_{date_str}.html")
        with open(temp_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        log_info(f"HTML内容已保存到: {temp_html_path}")
        
        # 将HTML转换为图片
        temp_img_path = os.path.join(DATA_DIR, f"report3_{date_str}.png")
        if await html_to_screenshot(html_content, temp_img_path):
            return temp_html_path, temp_img_path
        else:
            return temp_html_path, None
            
    except Exception as e:
        log_error_msg(f"生成HTML日报失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        return None, None

# 测试HTML日报生成
async def handle_test_report_3(bot, ev):
    """
    处理测试日报3命令 - 使用AI直接生成HTML方式
    :param bot: 机器人实例
    :param ev: 事件对象
    :return: None
    """
    try:
        group_id = str(ev.get('group_id', '未知群'))
        user_id = str(ev.get('user_id', '未知用户'))
        log_info(f"收到测试日报3命令，群号:{group_id}, 用户:{user_id}")
        
        # 检查依赖
        if not PLAYWRIGHT_AVAILABLE:
            await bot.send(ev, "生成图片所需的依赖未安装，请联系管理员安装playwright库")
            return
            
        if not AI_API_KEY:
            await bot.send(ev, "未配置AI API密钥，请联系管理员配置")
            return
            
        # 发送正在处理的提示
        await bot.send(ev, "正在生成AI直接创建的HTML日报图片，请稍候...")
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 生成标题
        title = f"{today} 本群聊天日报"
        
        # 初始化Playwright
        if not await init_playwright():
            await bot.send(ev, "初始化Playwright失败，无法生成图片")
            return
        
        # 生成HTML日报并转换为图片
        html_path, image_path = await generate_html_report(group_id, title, today, test_mode=True)
        
        if image_path and os.path.exists(image_path):
            # 发送图片
            log_info(f"准备发送图片: {image_path}")
            try:
                # 读取图片并转换为base64
                with open(image_path, 'rb') as f:
                    img_bytes = f.read()
                b64_str = base64.b64encode(img_bytes).decode()
                
                await bot.send(ev, MessageSegment.image(f'base64://{b64_str}'))
                log_info("成功发送AI生成的HTML日报图片")
            except Exception as e:
                log_error_msg(f"发送图片失败: {str(e)}")
                
                # 如果发送图片失败，尝试发送HTML文件路径
                if html_path and os.path.exists(html_path):
                    await bot.send(ev, f"图片发送失败，但HTML文件已生成：{os.path.basename(html_path)}")
        elif html_path and os.path.exists(html_path):
            # HTML生成成功但转图片失败
            await bot.send(ev, f"图片生成失败，但HTML页面已生成：{os.path.basename(html_path)}")
        else:
            # HTML也生成失败
            await bot.send(ev, "HTML日报生成失败，请查看日志")
            
    except Exception as e:
        log_error_msg(f"处理测试日报3命令失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        try:
            await bot.send(ev, f"处理测试日报3命令失败: {str(e)}")
        except:
            pass 
import os
import json
import base64
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import traceback

# 使用nonebot原生的MessageSegment而不是从hoshino导入
from nonebot.message import MessageSegment

from .logger_helper import log_info, log_warning, log_error_msg
from .dailysum import HTML_TEMPLATE

# 使用PIL生成图片的字体大小
FONT_SIZE = 16
TITLE_FONT_SIZE = 24
LINE_SPACING = 5
PADDING = 30
BG_COLOR = (255, 255, 255)  # 白色背景
TEXT_COLOR = (33, 33, 33)  # 深灰色文字
TITLE_COLOR = (74, 107, 223)  # 标题蓝色

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 尝试加载字体
def get_font(size):
    """获取字体，优先使用系统中文字体"""
    font_paths = [
        os.path.join(os.path.dirname(__file__), 'msyh.ttc'),  # 优先使用模块目录下的字体
        'C:/Windows/Fonts/msyh.ttc',  # Windows微软雅黑
        'C:/Windows/Fonts/simhei.ttf',  # Windows黑体
        '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',  # Linux
        '/System/Library/Fonts/PingFang.ttc',  # macOS
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',  # 文泉驿微米黑(常见于Linux)
        '/usr/share/fonts/wqy-microhei/wqy-microhei.ttc'  # 另一种常见路径
    ]
    
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                log_info(f"找到字体文件: {font_path}")
                return ImageFont.truetype(font_path, size)
        except Exception as e:
            log_warning(f"加载字体 {font_path} 失败: {str(e)}")
    
    # 如果所有字体都失败，使用默认字体
    try:
        log_info("使用默认字体")
        return ImageFont.truetype(ImageFont.load_default().path, size)
    except:
        log_info("加载默认字体")
        return ImageFont.load_default()

async def text_to_image(title, content, date_str):
    """
    将文本转换为图片
    :param title: 标题
    :param content: 内容
    :param date_str: 日期字符串
    :return: 图片对象
    """
    try:
        log_info("开始将文本转换为图片...")
        
        # 获取字体
        font = get_font(FONT_SIZE)
        title_font = get_font(TITLE_FONT_SIZE)
        
        # 分行处理内容
        lines = content.split('\n')
        
        # 计算每行文字宽度
        max_width = 0
        for line in lines:
            try:
                if hasattr(font, 'getbbox'):
                    bbox = font.getbbox(line)
                    width = bbox[2] - bbox[0]
                elif hasattr(font, 'getmask'):
                    width = font.getmask(line).getbbox()[2]
                else:
                    width = len(line) * FONT_SIZE
                max_width = max(max_width, width)
            except Exception as e:
                log_warning(f"计算文字宽度出错: {str(e)}")
                width = len(line) * FONT_SIZE
                max_width = max(max_width, width)
        
        # 计算标题宽度
        try:
            if hasattr(title_font, 'getbbox'):
                bbox = title_font.getbbox(title)
                title_width = bbox[2] - bbox[0]
            elif hasattr(title_font, 'getmask'):
                title_width = title_font.getmask(title).getbbox()[2]
            else:
                title_width = len(title) * TITLE_FONT_SIZE
        except Exception as e:
            log_warning(f"计算标题宽度出错: {str(e)}")
            title_width = len(title) * TITLE_FONT_SIZE
        
        # 设置图片宽度，包含边距
        width = max(max_width, title_width) + PADDING * 2
        width = min(max(width, 600), 1000)  # 限制宽度范围
        
        # 计算图片高度
        height = PADDING * 3  # 上边距 + 标题高度 + 标题与内容间距
        height += TITLE_FONT_SIZE  # 标题高度
        height += (FONT_SIZE + LINE_SPACING) * len(lines)  # 内容行高度
        height += 30  # 底部日期所需空间
        
        log_info(f"创建图片，宽: {width}，高: {height}")
        
        # 创建图片
        image = Image.new('RGB', (width, height), BG_COLOR)
        draw = ImageDraw.Draw(image)
        
        # 绘制标题
        title_y = PADDING
        draw.text((PADDING, title_y), title, font=title_font, fill=TITLE_COLOR)
        
        # 绘制内容
        y = title_y + TITLE_FONT_SIZE + PADDING
        for line in lines:
            draw.text((PADDING, y), line, font=font, fill=TEXT_COLOR)
            y += FONT_SIZE + LINE_SPACING
        
        # 绘制日期
        draw.text((PADDING, height - 30), f"由AI生成 · {date_str}", font=get_font(12), fill=(136, 136, 136))
        
        # 保存临时文件
        temp_path = os.path.join(DATA_DIR, f"temp_summary_{date_str}.png")
        image.save(temp_path)
        
        log_info(f"成功生成图片: {temp_path}")
        return image, temp_path
    except Exception as e:
        log_error_msg(f"文本转图片失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        return None, None

async def html_to_image(title, content, date_str):
    """
    将HTML转换为图片 - 使用PIL库实现
    :param title: 标题
    :param content: 内容
    :param date_str: 日期字符串
    :return: HTML文件路径和图片路径
    """
    try:
        # 生成HTML内容 - 使用替换而非格式化，避免CSS中的大括号被解释为占位符
        html_content = HTML_TEMPLATE
        html_content = html_content.replace("{title}", title)
        html_content = html_content.replace("{content}", content)
        html_content = html_content.replace("{date}", date_str)
        
        # 生成临时文件路径
        temp_html_path = os.path.join(DATA_DIR, f"test_summary_{date_str}.html")
        
        # 保存HTML到临时文件
        with open(temp_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        log_info(f"HTML内容已保存到临时文件: {temp_html_path}")
        
        # 使用text_to_image生成图片
        image, image_path = await text_to_image(title, content, date_str)
        
        return temp_html_path, image_path
    except Exception as e:
        log_error_msg(f"HTML转图片失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        return None, None

# 测试日报摘要文本
TEST_SUMMARY = """【聊天活跃度】
今日共有3位成员参与聊天，总消息量为7条。
最活跃的时段是上午8点到9点，共有4条消息。

【话题分析】
今日主要讨论了以下话题：
1. 天气和户外活动：讨论了天气好适合去公园，但因工作原因改为周末出行。
2. 午餐选择：讨论了午餐吃什么，有成员提议点外卖。
3. 工作状态：有成员表达了工作结束后的疲惫感。

【情感分析】
整体聊天氛围积极正面，大家互动友好。
早上的交流充满活力，午间讨论热情，下午略显疲惫但仍保持良好状态。

【互动亮点】
最具互动性的话题是关于天气和户外活动的讨论，吸引了所有活跃成员参与。

今日总结：今天是一个平静而普通的工作日，成员们在工作之余保持着轻松愉快的交流氛围。"""

# 处理测试命令
async def handle_test_report(bot, ev):
    """
    处理测试日报命令
    :param bot: 机器人实例
    :param ev: 事件对象
    :return: None
    """
    try:
        group_id = ev.get('group_id', '未知群')
        user_id = ev.get('user_id', '未知用户')
        log_info(f"收到测试日报命令，群号:{group_id}, 用户:{user_id}")
        # 发送正在处理的提示
        await bot.send(ev, "正在生成测试日报图片，请稍候...")
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 使用预设的摘要文本
        title = f"{today} 群聊日报测试"
        content = TEST_SUMMARY
        
        log_info(f"使用预设摘要生成图片，标题: {title}")
        
        # 使用text_to_image直接生成图片，避免HTML格式问题
        log_info("开始生成图片...")
        image, image_path = await text_to_image(title, content, today)
        
        if image_path and os.path.exists(image_path):
            # 发送图片
            log_info(f"准备发送图片: {image_path}")
            success = False
            
            # 尝试方法1：使用file:///路径
            try:
                await bot.send(ev, MessageSegment.image(f'file:///{image_path}'))
                log_info("使用file:///路径发送图片成功")
                success = True
            except Exception as e1:
                log_warning(f"使用file:///路径发送图片失败: {str(e1)}")
                
                # 尝试方法2：使用base64编码
                try:
                    log_info("尝试使用base64编码发送图片...")
                    with open(image_path, 'rb') as f:
                        img_bytes = f.read()
                    b64_str = base64.b64encode(img_bytes).decode()
                    await bot.send(ev, MessageSegment.image(f'base64://{b64_str}'))
                    log_info("使用base64编码发送图片成功")
                    success = True
                except Exception as e2:
                    log_warning(f"使用base64编码发送图片失败: {str(e2)}")
                    
                    # 尝试方法3：直接发送本地路径
                    try:
                        log_info("尝试直接发送本地图片路径...")
                        await bot.send(ev, MessageSegment.image(image_path))
                        log_info("直接发送本地图片路径成功")
                        success = True
                    except Exception as e3:
                        log_error_msg(f"所有图片发送方法都失败: {str(e3)}")
                        
            if not success:
                # 所有方法都失败，发送文本版本
                log_warning("所有图片发送方法都失败，发送文本版本")
                await bot.send(ev, f"【测试日报 - 图片发送失败】\n{title}\n\n{content}")
        else:
            # 如果图片生成失败，发送文本
            log_warning("测试日报图片生成失败，发送文本版本")
            await bot.send(ev, f"【测试日报 - 图片生成失败】\n{title}\n\n{content}")
            
    except Exception as e:
        log_error_msg(f"处理测试日报命令失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        try:
            await bot.send(ev, f"处理测试日报命令失败: {str(e)}")
        except:
            pass 
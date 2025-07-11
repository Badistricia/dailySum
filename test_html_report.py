import os
import json
import base64
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import asyncio
import traceback

from hoshino import Service, MessageSegment
from hoshino.typing import CQEvent

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
        '/System/Library/Fonts/PingFang.ttc'  # macOS
    ]
    
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except Exception as e:
            log_warning(f"加载字体 {font_path} 失败: {str(e)}")
    
    # 如果所有字体都失败，使用默认字体
    try:
        return ImageFont.truetype(ImageFont.load_default().path, size)
    except:
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
        # 获取字体
        font = get_font(FONT_SIZE)
        title_font = get_font(TITLE_FONT_SIZE)
        
        # 分行处理内容
        lines = content.split('\n')
        
        # 计算每行文字宽度
        max_width = 0
        for line in lines:
            width = font.getmask(line).getbbox()[2] if hasattr(font, 'getmask') else len(line) * FONT_SIZE
            max_width = max(max_width, width)
        
        # 计算标题宽度
        title_width = title_font.getmask(title).getbbox()[2] if hasattr(title_font, 'getmask') else len(title) * TITLE_FONT_SIZE
        
        # 设置图片宽度，包含边距
        width = max(max_width, title_width) + PADDING * 2
        width = min(max(width, 600), 1000)  # 限制宽度范围
        
        # 计算图片高度
        height = PADDING * 3  # 上边距 + 标题高度 + 标题与内容间距
        height += TITLE_FONT_SIZE  # 标题高度
        height += (FONT_SIZE + LINE_SPACING) * len(lines)  # 内容行高度
        height += 30  # 底部日期所需空间
        
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
    将HTML转换为图片 - 这个只是保存HTML文件，不实际转换，仅用于调试
    :param title: 标题
    :param content: 内容
    :param date_str: 日期字符串
    :return: HTML文件路径
    """
    try:
        # 生成HTML内容
        html_content = HTML_TEMPLATE.format(
            title=title,
            content=content,
            date=date_str
        )
        
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

# 创建测试用的假数据
async def create_test_data():
    """创建测试用的假数据"""
    test_data = {
        "12345678": [  # 示例群号
            {
                "time": "2023-12-01 08:15:30",
                "qq": "10001",
                "content": "早上好啊，今天天气不错！"
            },
            {
                "time": "2023-12-01 08:16:45",
                "qq": "10002",
                "content": "确实，阳光明媚的！今天有人去公园吗？"
            },
            {
                "time": "2023-12-01 08:20:10",
                "qq": "10003",
                "content": "我想去，但是我还有工作要做..."
            },
            {
                "time": "2023-12-01 09:05:22",
                "qq": "10001",
                "content": "周末再一起去吧，今天确实有点忙。"
            },
            {
                "time": "2023-12-01 12:30:15",
                "qq": "10002",
                "content": "中午吃什么好呢？"
            },
            {
                "time": "2023-12-01 12:32:40",
                "qq": "10003",
                "content": "我准备点外卖，有人一起吗？"
            },
            {
                "time": "2023-12-01 17:45:30",
                "qq": "10001",
                "content": "今天工作终于结束了，好累啊！"
            }
        ]
    }
    
    # 保存测试数据到文件
    test_data_path = os.path.join(DATA_DIR, "test_data.json")
    with open(test_data_path, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    log_info(f"测试数据已保存到: {test_data_path}")
    return test_data

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
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 创建测试数据
        await create_test_data()
        
        # 生成HTML和图片
        title = f"{today} 群聊日报"
        content = TEST_SUMMARY
        
        # 尝试转换为图片
        html_path, image_path = await html_to_image(title, content, today)
        
        if image_path and os.path.exists(image_path):
            # 发送图片
            await bot.send(ev, MessageSegment.image(f'file:///{image_path}'))
            log_info("测试日报图片已发送")
        else:
            # 如果图片生成失败，发送文本
            await bot.send(ev, f"【测试日报 - 图片生成失败】\n{title}\n\n{content}")
            log_warning("测试日报图片生成失败，已发送文本版本")
            
    except Exception as e:
        log_error_msg(f"处理测试日报命令失败: {str(e)}")
        log_error_msg(traceback.format_exc())
        await bot.send(ev, f"处理测试日报命令失败: {str(e)}")

# 测试用的主函数
if __name__ == "__main__":
    # 创建测试数据
    asyncio.run(create_test_data())
    
    # 测试图片生成
    today = datetime.now().strftime('%Y-%m-%d')
    title = f"{today} 群聊日报"
    content = TEST_SUMMARY
    
    # 生成HTML和图片
    html_path, image_path = asyncio.run(html_to_image(title, content, today))
    
    if image_path:
        print(f"测试成功，图片已保存到: {image_path}")
    else:
        print("测试失败，未能生成图片") 
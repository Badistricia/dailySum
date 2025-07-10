import os
import re
import json
import datetime
import asyncio
import traceback
from datetime import datetime, timedelta
import httpx
from PIL import Image
import io
import base64
import shutil

# 猴子补丁，用于修复html2image在Python 3.8下的兼容性问题
import sys
if sys.version_info < (3, 9):
    import typing
    list = typing.List
    dict = typing.Dict

# import html2image # 暂时禁用图片功能
from apscheduler.triggers.cron import CronTrigger
from nonebot import scheduler
from nonebot.message import MessageSegment

from hoshino import Service, priv, logger, get_bot
from .config import *
from .logger_helper import log_debug, log_info, log_warning, log_error_msg, log_critical, logged

# 创建服务实例
sv = Service(
    name='群聊日报',
    use_priv=priv.ADMIN,  # 使用权限：管理员
    manage_priv=priv.ADMIN,  # 管理权限：管理员
    visible=True,  # 可见性：可见
    enable_on_default=False,  # 默认关闭
)

# 确保data目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 确保logs目录存在
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 日志解析正则表达式
# 原始正则表达式
# LOG_PATTERN = r'\[(.*?) nonebot\] INFO: Self: (.*?), Message (.*?) from (.*?)@\[群:(.*?)\]: \'(.*)\''
# 适配run.log的新正则表达式，精确匹配提供的日志格式
LOG_PATTERN = r'\[(.*?) nonebot\] INFO: Self: (.*?), Message (.*?) from (.*?)@\[群:(.*?)\]: \'(.*?)\'$'

# HTML转图片工具初始化 - 暂时注释掉
# try:
#     log_info("初始化 HTML2Image...")
#     chrome_paths = [
#         '/usr/bin/chromium-browser',  # 标准路径
#         '/snap/bin/chromium',         # snap安装路径
#         '/usr/bin/chromium',          # 一些系统上的路径
#         '/usr/bin/google-chrome',     # Google Chrome路径
#         '/usr/bin/google-chrome-stable'
#     ]
#     
#     chrome_path = None
#     for path in chrome_paths:
#         if os.path.exists(path):
#             chrome_path = path
#             log_info(f"找到Chrome/Chromium路径: {chrome_path}")
#             break
#     
#     if chrome_path:
#         hti = html2image.Html2Image(chrome_path=chrome_path)
#         log_info(f"HTML2Image使用浏览器路径 {chrome_path} 初始化成功")
#     else:
#         hti = html2image.Html2Image()
#         log_info("HTML2Image使用默认设置初始化成功")
# except Exception as e:
#     log_critical(f"HTML2Image 初始化失败: {str(e)}")
#     log_critical(traceback.format_exc())
#     hti = None

# 创建HTML文本样式
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日报</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f8f9fa;
            color: #333;
            line-height: 1.6;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #4a6bdf;
            text-align: center;
            border-bottom: 2px solid #eaeaea;
            padding-bottom: 10px;
            margin-top: 0;
        }
        .summary {
            white-space: pre-wrap;
            padding: 10px 0;
        }
        .footer {
            text-align: center;
            font-size: 0.8em;
            margin-top: 20px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="summary">{content}</div>
        <div class="footer">由AI生成 · {date}</div>
    </div>
</body>
</html>
"""

# 深度学习客户端
class DeepSeekClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        log_info(f"DeepSeekClient 初始化完成，API Key: {'已设置' if api_key else '未设置'}")
        
    async def generate(self, prompt, model=AI_MODEL, temperature=AI_TEMPERATURE, max_retries=3, timeout=120.0):
        log_info(f"开始生成AI摘要，模型: {model}, 温度: {temperature}")
        log_debug(f"提示词: {prompt[:200]}...")
        
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
                    log_info(f"AI生成成功，生成内容长度: {len(content)}")
                    log_debug(f"生成内容前100字符: {content[:100]}...")
                    return content
                elif response.status_code == 400:
                    # 如果是请求过大的错误，尝试减少输入长度
                    log_warning(f"请求数据过大 (状态码: {response.status_code})，尝试减少输入大小")
                    
                    # 裁剪提示词到原来的70%
                    prompt_parts = prompt.split("聊天记录：\n")
                    if len(prompt_parts) == 2:
                        instruction, chat_log = prompt_parts
                        # 保留前70%的聊天记录
                        reduced_chat_log = chat_log[:int(len(chat_log) * 0.7)]
                        prompt = f"{instruction}聊天记录：\n{reduced_chat_log}\n\n[注: 由于长度限制，仅显示部分聊天记录]"
                        log_info(f"提示词已减少到原来的70%，新大小: {len(prompt.encode('utf-8')) / 1024:.2f} KB")
                    else:
                        log_error_msg("无法裁剪提示词，格式不符合预期")
                        return None
                else:
                    log_error_msg(f"DeepSeek API调用失败: {response.status_code} {response.text}")
                    # 如果不是400错误，可能是其他API问题，尝试重试
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
        
        log_error_msg(f"达到最大重试次数 ({max_retries})，AI生成失败")
        return None

# AI客户端实例
ai_client = DeepSeekClient(AI_API_KEY)

# 从系统日志获取群聊消息
@logged
async def parse_syslog(log_path, start_time=None, end_time=None, target_group=None):
    """
    解析系统日志，提取群聊消息
    :param log_path: 日志文件路径
    :param start_time: 开始时间，格式为datetime对象
    :param end_time: 结束时间，格式为datetime对象
    :param target_group: 目标群号，为None时解析所有群
    :return: 解析后的群聊消息字典，格式为 {群号: [{时间, QQ号, 消息内容}, ...]}
    """
    if not os.path.exists(log_path):
        log_error_msg(f"日志文件不存在: {log_path}")
        return {}
    
    log_info(f"开始解析日志文件: {log_path}")
    log_info(f"时间范围: {start_time} - {end_time}")
    
    group_messages = {}
    line_count = 0
    matched_count = 0
    
    try:
        # 尝试不同的编码方式
        encodings = ['utf-8', 'gb18030', 'gbk', 'cp936', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                log_info(f"尝试使用 {encoding} 编码读取日志文件")
                with open(log_path, 'r', encoding=encoding, errors='ignore') as f:
                    for line in f:
                        line_count += 1
                        
                        # 每处理10000行记录一次进度
                        if line_count % 10000 == 0:
                            log_debug(f"已处理 {line_count} 行日志，找到 {matched_count} 条群聊消息")
                        
                        # 仅处理可能包含群聊消息的行
                        if 'nonebot' not in line or 'Message' not in line or '@[群:' not in line:
                            continue
                        
                        match = re.search(LOG_PATTERN, line)
                        if not match:
                            continue
                        
                        matched_count += 1
                        
                        # 解析日志
                        try:
                            log_time_str, self_id, msg_id, sender_info, group_id, content = match.groups()
                            
                            # 解析日志时间
                            try:
                                log_time = datetime.strptime(log_time_str, '%Y-%m-%d %H:%M:%S,%f')
                            except ValueError:
                                # 尝试其他可能的时间格式
                                try:
                                    log_time = datetime.strptime(log_time_str, '%Y-%m-%d %H:%M:%S')
                                except ValueError:
                                    log_warning(f"无法解析日志时间: {log_time_str}，跳过该行")
                                    continue
                            
                            # 时间过滤
                            if start_time and log_time < start_time:
                                continue
                            if end_time and log_time > end_time:
                                continue
                            
                            # 群号过滤
                            if target_group and group_id != target_group:
                                continue
                            
                            # 解析发送者QQ号
                            sender_qq = sender_info.split('@')[0]
                            
                            # 简化CQ码内容
                            simplified_content = simplify_cq_code(content)
                            
                            # 将消息添加到对应群
                            if group_id not in group_messages:
                                group_messages[group_id] = []
                            
                            group_messages[group_id].append({
                                'time': log_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'qq': sender_qq,
                                'content': simplified_content
                            })
                        except Exception as e:
                            log_error_msg(f"解析日志行出错: {str(e)}，行内容: {line[:100]}")
                            continue
                            
                # 如果成功读取并找到消息，跳出编码尝试循环
                if matched_count > 0:
                    log_info(f"使用编码 {encoding} 成功解析日志")
                    break
            except UnicodeDecodeError:
                log_warning(f"使用 {encoding} 编码读取日志文件失败，尝试下一种编码")
            except Exception as e:
                log_error_msg(f"读取日志文件出错: {str(e)}")
                log_error_msg(traceback.format_exc())
        
        log_info(f"日志解析完成，共处理 {line_count} 行，找到 {matched_count} 条群聊消息")
        log_info(f"解析出 {len(group_messages)} 个群的消息")
        for group_id, messages in group_messages.items():
            log_info(f"群 {group_id}: {len(messages)} 条消息")
    except Exception as e:
        log_error_msg(f"解析日志文件出错: {str(e)}")
        log_error_msg(traceback.format_exc())
    
    return group_messages

# 保存群聊日志到文件
@logged
async def save_group_logs(group_messages, date_str):
    """
    将群聊消息保存到文件
    :param group_messages: 群聊消息字典
    :param date_str: 日期字符串，格式为'YYYY-MM-DD'
    """
    log_info(f"开始保存群聊日志，日期: {date_str}")
    
    # 确保data目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    
    for group_id, messages in group_messages.items():
        if not messages:
            log_warning(f"群 {group_id} 没有消息，跳过保存")
            continue
        
        # 简化CQ码
        simplified_messages = []
        for msg in messages:
            simplified_msg = msg.copy()  # 创建消息的副本
            simplified_msg['content'] = simplify_cq_code(msg['content'])  # 简化内容
            simplified_messages.append(simplified_msg)
        
        file_path = os.path.join(DATA_DIR, f"{group_id}_{date_str}.json")
        log_info(f"保存群聊日志到文件: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(simplified_messages, f, ensure_ascii=False, indent=2)
            log_info(f"保存群 {group_id} 的日志到 {file_path}，共 {len(simplified_messages)} 条消息")
        except Exception as e:
            log_error_msg(f"保存群聊日志出错: {str(e)}")
            log_error_msg(traceback.format_exc())

# 分割日志文件
@logged
async def split_log_files(day_offset=0, target_group=None):
    """
    分割日志文件，提取指定日期的群聊消息
    :param day_offset: 日期偏移，0表示今天，1表示昨天，以此类推
    :param target_group: 目标群号，为None时解析所有群
    """
    # 计算日期范围
    now = datetime.now()
    target_date = now - timedelta(days=day_offset)
    start_time = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    end_time = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
    date_str = target_date.strftime('%Y-%m-%d')
    
    log_info(f"开始分割日志文件，目标日期: {date_str}")
    log_info(f"日期偏移: {day_offset}，时间范围: {start_time} - {end_time}")
    
    # 选择日志源
    log_source = None
    group_messages = {}
    
    # 当天日志从系统日志获取
    if day_offset == 0:
        if os.path.exists(LOG_PATH):
            log_source = LOG_PATH
            log_info(f"当天日志从系统日志获取: {log_source}")
        else:
            log_error_msg(f"系统日志路径不存在: {LOG_PATH}")
    # 历史日志从备份文件获取
    else:
        # 尝试从备份目录查找日志
        backup_log_path = os.path.join(LOG_DIR, f"run_log_{date_str}.log")
        if os.path.exists(backup_log_path):
            log_source = backup_log_path
            log_info(f"历史日志从备份文件获取: {log_source}")
        else:
            log_warning(f"备份日志文件不存在: {backup_log_path}")
            
            # 如果没有备份日志，先检查是否已存在解析好的群聊记录
            if target_group:
                local_log_path = os.path.join(DATA_DIR, f"{target_group}_{date_str}.json")
                if os.path.exists(local_log_path):
                    log_info(f"在本地找到目标群 {target_group} 的聊天记录文件: {local_log_path}")
                    try:
                        with open(local_log_path, 'r', encoding='utf-8') as f:
                            messages = json.load(f)
                        group_messages = {target_group: messages}
                        log_info(f"成功从本地文件加载群 {target_group} 的聊天记录，共 {len(messages)} 条消息")
                        return group_messages, date_str
                    except Exception as e:
                        log_error_msg(f"加载本地聊天记录文件失败: {str(e)}")
            
            # 最后尝试从系统日志获取历史记录（如果系统日志未被清理）
            if os.path.exists(LOG_PATH):
                log_source = LOG_PATH
                log_info(f"备份日志不存在，尝试从系统日志获取历史记录: {log_source}")
            else:
                log_error_msg(f"系统日志和备份日志都不存在")
    
    # 如果找到了日志源，则解析日志
    if log_source:
        log_info(f"开始从日志源解析群聊消息: {log_source}")
        group_messages = await parse_syslog(log_source, start_time, end_time, target_group)
    
    # 检查是否有消息
    if not group_messages:
        log_warning(f"没有找到任何群的聊天记录，日期: {date_str}")
        return await load_test_data(date_str)
    
    # 保存群聊日志
    await save_group_logs(group_messages, date_str)
    
    return group_messages, date_str

@logged
async def load_test_data(date_str):
    """
    加载测试数据
    :param date_str: 日期字符串
    :return: 测试数据和日期字符串
    """
    log_info("尝试加载测试数据...")
    group_messages = {}
    
    # 尝试从测试数据中加载消息
    test_data_path = os.path.join(DATA_DIR, "test_data.json")
    if os.path.exists(test_data_path):
        log_info(f"从测试数据文件加载: {test_data_path}")
        try:
            with open(test_data_path, 'r', encoding='utf-8') as f:
                group_messages = json.load(f)
            log_info(f"成功从测试数据中加载了 {len(group_messages)} 个群的消息")
            
            # 保存群聊日志
            await save_group_logs(group_messages, date_str)
        except Exception as e:
            log_error_msg(f"加载测试数据出错: {str(e)}")
            log_error_msg(traceback.format_exc())
    else:
        log_warning(f"测试数据文件不存在: {test_data_path}")
    
    return group_messages, date_str

# 处理CQ码图片链接，将其简化为[图片]标识
def simplify_cq_code(content):
    """
    将CQ码简化为简单标识
    :param content: 消息内容
    :return: 简化后的消息内容
    """
    if not isinstance(content, str):
        return content
    
    # 匹配常见的CQ码类型
    content = re.sub(r'\[CQ:image[^\]]+\]', '[图片]', content)
    content = re.sub(r'\[CQ:face[^\]]+\]', '[表情]', content)
    content = re.sub(r'\[CQ:at[^\]]+\]', '[有人@]', content)
    content = re.sub(r'\[CQ:share[^\]]+\]', '[分享]', content)
    content = re.sub(r'\[CQ:record[^\]]+\]', '[语音]', content)
    content = re.sub(r'\[CQ:video[^\]]+\]', '[视频]', content)
    content = re.sub(r'\[CQ:xml[^\]]+\]', '[XML卡片]', content)
    content = re.sub(r'\[CQ:json[^\]]+\]', '[JSON卡片]', content)
    content = re.sub(r'\[CQ:music[^\]]+\]', '[音乐]', content)
    content = re.sub(r'\[CQ:reply[^\]]+\]', '[回复]', content)
    content = re.sub(r'\[CQ:forward[^\]]+\]', '[合并转发]', content)
    content = re.sub(r'\[CQ:redbag[^\]]+\]', '[红包]', content)
    
    # 处理其他未知类型的CQ码
    content = re.sub(r'\[CQ:[^\]]+\]', '[特殊消息]', content)
    
    # 去除过长的URL链接
    content = re.sub(r'https?://\S{30,}', '[链接]', content)
    
    # 去除连续的空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content

# 优化聊天记录格式
def optimize_chat_format(messages):
    """
    优化聊天记录格式，减少冗余信息，压缩数据
    :param messages: 原始聊天记录列表
    :return: 优化后的聊天记录文本
    """
    if not messages:
        return ""
    
    optimized_logs = []
    current_speaker = None
    combined_messages = []
    last_time = None
    
    # 过滤无意义的短消息和表情包
    filtered_messages = []
    for msg in messages:
        content = simplify_cq_code(msg['content'])
        # 过滤仅包含表情、短回复的无意义消息
        if content in ['[表情]', '[图片]', '6', '？', '?', '。', '哦', '嗯', '啊', 'ok', '666', '???']:
            continue
        # 过滤极短消息（少于2个字符）
        if len(content) < 2:
            continue
        filtered_messages.append({
            'time': msg['time'],
            'qq': msg['qq'],
            'content': content
        })
    
    # 如果过滤后消息太少，使用原始消息
    if len(filtered_messages) < len(messages) * 0.3 and len(filtered_messages) < 10:
        filtered_messages = messages
    
    for msg in filtered_messages:
        time_str = msg['time'].split(' ')[1][:5]  # 只取HH:MM部分
        speaker = msg['qq']
        content = simplify_cq_code(msg['content'])
        
        # 如果距离上一条消息时间超过5分钟，不合并
        current_time = datetime.strptime(msg['time'], '%Y-%m-%d %H:%M:%S')
        if last_time and (current_time - last_time).seconds > 300:  # 5分钟 = 300秒
            # 处理之前累积的消息
            if combined_messages:
                combined_content = " | ".join(combined_messages)
                optimized_logs.append(f"[{last_time.strftime('%H:%M')}] {current_speaker}: {combined_content}")
                combined_messages = []
            current_speaker = None  # 重置当前发言人
        
        last_time = current_time
        
        # 如果是同一个发言人的连续消息且内容不太长，合并处理
        if speaker == current_speaker and len(combined_messages) < 3 and sum(len(m) for m in combined_messages) < 100:
            combined_messages.append(content)
        else:
            # 如果有之前累积的消息，先处理
            if combined_messages:
                combined_content = " | ".join(combined_messages)
                optimized_logs.append(f"[{time_str}] {current_speaker}: {combined_content}")
            
            # 重置当前发言人和消息
            current_speaker = speaker
            combined_messages = [content]
    
    # 处理最后一组消息
    if combined_messages:
        time_str = last_time.strftime('%H:%M') if last_time else "00:00"
        combined_content = " | ".join(combined_messages)
        optimized_logs.append(f"[{time_str}] {current_speaker}: {combined_content}")
    
    return "\n".join(optimized_logs)

# 生成群聊摘要
@logged
async def generate_summary(group_id, date_str):
    """
    生成群聊摘要
    :param group_id: 群号
    :param date_str: 日期字符串
    :return: 摘要内容
    """
    log_info(f"开始生成群聊摘要，群: {group_id}, 日期: {date_str}")
    
    file_path = os.path.join(DATA_DIR, f"{group_id}_{date_str}.json")
    
    if not os.path.exists(file_path):
        log_error_msg(f"群聊日志文件不存在: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            messages = json.load(f)
        
        log_info(f"读取群聊日志文件成功，共 {len(messages)} 条消息")
        
        if not messages:
            log_warning(f"群 {group_id} 在 {date_str} 没有聊天记录")
            return None
        
        # 使用优化的聊天记录格式
        chat_log = optimize_chat_format(messages)
        log_info(f"构建聊天记录文本完成，长度: {len(chat_log)}")
        
        # 如果聊天记录过长，进行截断处理
        MAX_CHAT_LOG_LENGTH = 50000  # 最大聊天记录长度限制，防止API调用失败
        
        if len(chat_log) > MAX_CHAT_LOG_LENGTH:
            log_warning(f"聊天记录超出长度限制 ({len(chat_log)} > {MAX_CHAT_LOG_LENGTH})，将进行截断")
            
            # 方式一：保留前后部分
            # prefix = chat_log[:MAX_CHAT_LOG_LENGTH // 4]
            # suffix = chat_log[-MAX_CHAT_LOG_LENGTH // 4:]
            # chat_log = f"{prefix}\n...\n[中间{len(chat_log) - len(prefix) - len(suffix)}字符被省略]\n...\n{suffix}"
            
            # 方式二：直接截断尾部
            chat_log = chat_log[:MAX_CHAT_LOG_LENGTH]
            chat_log += "\n\n[由于长度限制，部分消息被省略]"
            
            log_info(f"截断后的聊天记录长度: {len(chat_log)}")
        
        log_debug(f"聊天记录前200字符: {chat_log[:200]}...")
        
        # 检查API Key
        if not AI_API_KEY:
            log_error_msg("DeepSeek API Key未设置，无法生成摘要")
            return None
        
        # 构建提示词
        prompt = PROMPT_TEMPLATE.format(
            group_name=group_id,  # 这里用群号代替群名，实际应用中可以获取真实群名
            chat_log=chat_log
        )
        log_info("构建提示词完成")
        
        # 调用AI生成摘要
        log_info("开始调用AI生成摘要...")
        summary = await ai_client.generate(prompt)
        
        if not summary:
            log_error_msg(f"AI生成摘要失败")
            return None
        
        log_info(f"AI生成摘要成功，长度: {len(summary)}")
        log_debug(f"摘要前200字符: {summary[:200]}...")
        
        return summary
    except Exception as e:
        log_error_msg(f"生成群聊摘要出错: {str(e)}")
        log_error_msg(traceback.format_exc())
        return None

# 生成图片摘要
@logged
async def generate_image_summary(title, content, date_str):
    """
    将摘要转换为图片
    :param title: 标题
    :param content: 内容
    :param date_str: 日期字符串
    :return: 图片数据（base64编码）
    """
    log_info(f"开始生成图片摘要，日期: {date_str}")
    
    # if not hti:
    #     log_error_msg("HTML2Image未初始化，无法生成图片")
    #     return None
    
    try:
        # 生成HTML内容
        html_content = HTML_TEMPLATE.format(
            title=title,
            content=content,
            date=date_str
        )
        
        # 生成临时文件路径
        temp_html_path = os.path.join(DATA_DIR, f"summary_{date_str}.html")
        temp_png_path = os.path.join(DATA_DIR, f"summary_{date_str}.png")
        
        # 保存HTML到临时文件
        with open(temp_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        log_info(f"HTML内容已保存到临时文件: {temp_html_path}")
        
        # 生成图片
        log_info("开始生成图片...")
        # hti.screenshot(
        #     html_file=temp_html_path,
        #     save_as=temp_png_path,
        #     size=(800, None)  # 宽度固定，高度自适应
        # )
        log_info(f"图片已生成: {temp_png_path}")
        
        # 读取图片并转换为base64
        with open(temp_png_path, 'rb') as f:
            image_data = f.read()
        
        log_info(f"图片大小: {len(image_data) / 1024:.2f} KB")
        
        # 清理临时文件
        try:
            # os.remove(temp_html_path)
            os.remove(temp_png_path)
            log_info("临时文件已清理")
        except Exception as e:
            log_warning(f"清理临时文件失败: {str(e)}")
        
        return image_data
    except Exception as e:
        log_error_msg(f"生成图片摘要出错: {str(e)}")
        log_error_msg(traceback.format_exc())
        return None

# 执行日报生成
@logged
async def execute_daily_summary(bot, target_groups=None, day_offset=0, start_hour=4):
    """
    执行日报生成
    :param bot: 机器人实例
    :param target_groups: 目标群列表，为None时处理所有群
    :param day_offset: 日期偏移，0表示今天，1表示昨天，以此类推
    :param start_hour: 日报统计的起始小时，默认为4点
    """
    # 计算目标日期范围
    now = datetime.now()
    target_date = now - timedelta(days=day_offset)
    
    # 设置时间范围为昨天4点到今天4点
    if day_offset == 0:  # 如果是今天，则范围是昨天4点到今天4点
        start_time = datetime(target_date.year, target_date.month, target_date.day, start_hour, 0, 0) - timedelta(days=1)
        end_time = datetime(target_date.year, target_date.month, target_date.day, start_hour, 0, 0)
    else:  # 如果是查询历史，则范围是目标日期4点到次日4点
        start_time = datetime(target_date.year, target_date.month, target_date.day, start_hour, 0, 0)
        end_time = start_time + timedelta(days=1)
    
    date_str = start_time.strftime('%Y-%m-%d')
    log_info(f"开始执行日报生成，时间范围: {start_time} - {end_time}")
    log_info(f"目标群: {target_groups if target_groups else '所有群'}")
    
    # 分割日志文件
    group_messages, _ = await split_log_files(day_offset)
    
    if not group_messages:
        log_warning(f"没有找到任何群的聊天记录，无法生成日报")
        return
    
    # 处理白名单群
    if not target_groups and DAILY_SUM_GROUPS:
        target_groups = DAILY_SUM_GROUPS
        log_info(f"使用配置的白名单群: {target_groups}")
    
    # 过滤需要处理的群
    groups_to_process = {}
    for group_id, messages in group_messages.items():
        # 如果指定了目标群，且当前群不在目标群中，则跳过
        if target_groups and group_id not in target_groups:
            log_info(f"群 {group_id} 不在目标群列表中，跳过")
            continue
        
        if not messages:
            log_warning(f"群 {group_id} 没有消息，跳过生成日报")
            continue
        
        groups_to_process[group_id] = messages
    
    # 创建信号量控制并发
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    async def process_group(group_id, messages):
        async with semaphore:
            log_info(f"开始处理群 {group_id} 的日报生成")
            
            # 生成摘要
            log_info(f"为群 {group_id} 生成摘要...")
            summary = await generate_summary(group_id, date_str)
            
            if not summary:
                log_warning(f"群 {group_id} 的摘要生成失败，跳过")
                return False
            
            # 发送日报
            try:
                log_info(f"开始向群 {group_id} 发送文本摘要...")
                message_to_send = f"【{date_str} 群聊日报】\n统计范围：{start_time.strftime('%m-%d %H:%M')} - {end_time.strftime('%m-%d %H:%M')}\n\n{summary}"
                await bot.send_group_msg(
                    group_id=int(group_id),
                    message=message_to_send
                )
                log_info(f"成功向群 {group_id} 发送文本日报")
                return True
            except Exception as e:
                log_error_msg(f"向群 {group_id} 发送日报出错: {str(e)}")
                log_error_msg(traceback.format_exc())
                return False
            finally:
                # 添加间隔，避免短时间内发送太多消息
                await asyncio.sleep(TASK_INTERVAL_SECONDS)
    
    # 创建所有群的任务
    tasks = [process_group(group_id, messages) for group_id, messages in groups_to_process.items()]
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 统计结果
    success_count = sum(1 for r in results if r is True)
    fail_count = sum(1 for r in results if r is False)
    error_count = sum(1 for r in results if isinstance(r, Exception))
    
    log_info(f"日报生成任务完成，总计 {len(tasks)} 个群，成功 {success_count} 个，失败 {fail_count} 个，错误 {error_count} 个")

# 获取日报配置状态
@logged
async def get_daily_config_status():
    """
    获取日报配置状态
    :return: 配置状态文本
    """
    status_text = "【群聊日报配置状态】\n"
    status_text += f"定时任务: {'启用' if ENABLE_SCHEDULER else '禁用'}\n"
    status_text += f"发送时间: 每天{SUMMARY_HOUR:02d}:{SUMMARY_MINUTE:02d}\n"
    status_text += f"统计范围: 每天{SUMMARY_START_HOUR:02d}:00到次日{SUMMARY_START_HOUR:02d}:00\n"
    status_text += f"并发任务数: {MAX_CONCURRENT_TASKS}\n"
    status_text += f"任务间隔: {TASK_INTERVAL_SECONDS}秒\n"
    
    if DAILY_SUM_GROUPS:
        status_text += f"启用群数量: {len(DAILY_SUM_GROUPS)}个\n"
        status_text += "启用群列表:\n"
        for i, group_id in enumerate(DAILY_SUM_GROUPS):
            if i < 10:  # 只显示前10个
                status_text += f"- {group_id}\n"
        if len(DAILY_SUM_GROUPS) > 10:
            status_text += f"...等共{len(DAILY_SUM_GROUPS)}个群"
    else:
        status_text += "启用状态: 所有群"
    
    return status_text

# 手动触发总结
@logged
async def manual_summary(bot, ev, day_offset=0, target_group=None):
    """
    手动触发总结
    :param bot: 机器人实例
    :param ev: 事件对象
    :param day_offset: 日期偏移，0表示今天，1表示昨天，以此类推
    :param target_group: 目标群号，为None时使用当前群
    """
    current_group_id = str(ev['group_id'])
    user_id = str(ev['user_id'])
    
    # 如果没有指定目标群，则使用当前群
    if target_group is None:
        target_group = current_group_id
    
    log_info(f"用户 {user_id} 在群 {current_group_id} 手动触发日报生成，目标群: {target_group}，日期偏移: {day_offset}")
    
    # 发送处理中提示
    await bot.send(ev, f"正在生成{'指定群 '+target_group if target_group != current_group_id else '本群'}聊天日报，请稍候...")
    log_info(f"已向群 {current_group_id} 发送处理中提示")
    
    # 计算目标日期
    target_date = datetime.now() - timedelta(days=day_offset)
    date_str = target_date.strftime('%Y-%m-%d')
    
    # 分割日志文件，只处理指定的群
    log_info(f"分割日志文件，目标群: {target_group}")
    group_messages, _ = await split_log_files(day_offset, target_group)
    
    # 检查目标群是否有消息
    if not group_messages or target_group not in group_messages:
        await bot.send(ev, f"未找到{'指定群 '+target_group if target_group != current_group_id else '本群'}的聊天记录")
        log_warning(f"未找到群 {target_group} 的聊天记录")
        return
    
    # 生成摘要
    log_info(f"为群 {target_group} 生成摘要...")
    summary = await generate_summary(target_group, date_str)
    
    if not summary:
        await bot.send(ev, f"生成{'指定群 '+target_group if target_group != current_group_id else '本群'}的日报失败")
        log_warning(f"群 {target_group} 的摘要生成失败")
        return
    
    # 发送到当前群（触发命令的群）
    try:
        log_info(f"开始向群 {current_group_id} 发送文本摘要...")
        message_to_send = f"【{date_str} {'群 '+target_group if target_group != current_group_id else '本群'}聊天日报】\n\n{summary}"
        await bot.send_group_msg(
            group_id=int(current_group_id),
            message=message_to_send
        )
        log_info(f"成功发送群 {target_group} 的文本日报到群 {current_group_id}")
    except Exception as e:
        log_error_msg(f"发送群 {target_group} 日报到群 {current_group_id} 出错: {str(e)}")
        log_error_msg(traceback.format_exc())

# 备份日志文件
@logged
async def backup_logs():
    """
    备份当天的日志文件到本地logs目录
    在每天23:59执行，确保当天的日志被保存
    """
    try:
        # 确保logs目录存在
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # 获取当前日期
        today = datetime.now().strftime('%Y-%m-%d')
        log_info(f"开始备份日志文件，日期: {today}")
        
        # 检查日志路径
        if not os.path.exists(LOG_PATH):
            log_error_msg(f"系统日志路径不存在: {LOG_PATH}")
            return
        
        # 目标备份文件路径
        backup_path = os.path.join(LOG_DIR, f"run_log_{today}.log")
        
        # 复制日志文件
        shutil.copy2(LOG_PATH, backup_path)
        log_info(f"日志文件已备份到: {backup_path}")
        
        # 解析日志并按群保存
        now = datetime.now()
        start_time = datetime(now.year, now.month, now.day, 0, 0, 0)
        end_time = datetime(now.year, now.month, now.day, 23, 59, 59)
        
        log_info(f"开始从备份日志解析群聊消息: {backup_path}")
        group_messages = await parse_syslog(backup_path, start_time, end_time)
        
        # 保存群聊日志
        if group_messages:
            await save_group_logs(group_messages, today)
            log_info(f"成功解析并保存了 {len(group_messages)} 个群的聊天记录")
        else:
            log_warning(f"没有从备份日志中解析到任何群聊消息")
            
    except Exception as e:
        log_error_msg(f"备份日志文件出错: {str(e)}")
        log_error_msg(traceback.format_exc())

# 定时任务状态
scheduler_running = False


@sv.on_prefix(['日报'])
async def view_daily_report(bot, ev):
    """查看指定日期的日报或管理日报功能"""
    global scheduler_running  # 将global声明移到函数开头
    
    if not priv.check_priv(ev, priv.ADMIN):
        await bot.send(ev, '抱歉，只有管理员才能查看日报')
        return
        
    # 获取命令参数
    msg = ev.message.extract_plain_text().strip()
    
    # 解析命令
    if msg.startswith(('启用', '开启')):
        # 启用日报功能
        if scheduler_running:
            await bot.send(ev, '日报定时功能已经在运行中')
            return
            
        try:
            start_scheduler(sv)
            scheduler_running = True
            await bot.send(ev, f'日报定时功能已启用，将在每天{SUMMARY_HOUR:02d}:{SUMMARY_MINUTE:02d}发送日报')
        except Exception as e:
            log_error_msg(f"启用日报定时功能失败: {str(e)}")
            await bot.send(ev, '启用日报定时功能失败，请查看日志')
            
    elif msg.startswith(('禁用', '关闭')):
        # 禁用日报功能
        if not scheduler_running:
            await bot.send(ev, '日报定时功能已经是关闭状态')
            return
            
        try:
            # 移除日报相关的定时任务
            scheduler.remove_job('dailysum_daily')
            scheduler.remove_job('dailysum_log_backup')
            scheduler_running = False
            await bot.send(ev, '日报定时功能已禁用')
        except Exception as e:
            log_error_msg(f"禁用日报定时功能失败: {str(e)}")
            await bot.send(ev, '禁用日报定时功能失败，请查看日志')
    
    elif msg.startswith('状态'):
        # 查看当前配置状态
        try:
            status = await get_daily_config_status()
            await bot.send(ev, status)
        except Exception as e:
            log_error_msg(f"查看日报状态失败: {str(e)}")
            await bot.send(ev, '查看日报状态失败，请查看日志')
    
    elif msg.startswith('添加群'):
        # 添加群到白名单
        try:
            parts = msg.split()
            if len(parts) < 2 or not parts[1].isdigit():
                await bot.send(ev, '参数错误，格式：日报 添加群 123456789')
                return
            
            group_id = parts[1]
            if group_id in DAILY_SUM_GROUPS:
                await bot.send(ev, f'群 {group_id} 已在日报白名单中')
                return
            
            DAILY_SUM_GROUPS.append(group_id)
            # 保存配置
            await save_group_config()
            await bot.send(ev, f'已添加群 {group_id} 到日报白名单')
        except Exception as e:
            log_error_msg(f"添加群到白名单失败: {str(e)}")
            await bot.send(ev, '添加失败，请查看日志')
    
    elif msg.startswith('删除群') or msg.startswith('移除群'):
        # 从白名单移除群
        try:
            parts = msg.split()
            if len(parts) < 2 or not parts[1].isdigit():
                await bot.send(ev, '参数错误，格式：日报 删除群 123456789')
                return
            
            group_id = parts[1]
            if group_id not in DAILY_SUM_GROUPS:
                await bot.send(ev, f'群 {group_id} 不在日报白名单中')
                return
            
            DAILY_SUM_GROUPS.remove(group_id)
            # 保存配置
            await save_group_config()
            await bot.send(ev, f'已从日报白名单移除群 {group_id}')
        except Exception as e:
            log_error_msg(f"从白名单移除群失败: {str(e)}")
            await bot.send(ev, '移除失败，请查看日志')
            
    else:
        # 查看日报
        try:
            if not msg:
                # 没有参数，默认查看昨天的日报
                day_offset = 1
                target_group = None
            else:
                parts = msg.split()
                day_offset = 1  # 默认为昨天
                target_group = None
                
                # 处理时间描述词
                time_words = {
                    '今天': 0,
                    '昨天': 1,
                    '前天': 2
                }
                
                if len(parts) >= 1:
                    # 处理第一个参数
                    if parts[0] in time_words:
                        # 时间描述词
                        day_offset = time_words[parts[0]]
                    elif parts[0].isdigit():
                        if len(parts[0]) > 4:
                            # 长数字，认为是群号
                            target_group = parts[0]
                        else:
                            # 短数字，认为是天数
                            day_offset = int(parts[0])
                
                # 处理第二个参数（如果有）
                if len(parts) >= 2:
                    # 第二个参数应该是群号
                    if parts[1].isdigit():
                        target_group = parts[1]
            
            log_info(f"命令解析结果：日期偏移 = {day_offset}，目标群 = {target_group}")
            await manual_summary(bot, ev, day_offset, target_group)
        except ValueError:
            await bot.send(ev, '参数格式错误。使用方法：\n日报 [天数/时间描述词] [群号] - 查看指定日报\n日报 状态 - 查看当前配置\n日报 添加群 123456789 - 添加群到白名单\n日报 删除群 123456789 - 从白名单删除群\n日报 启用/禁用 - 控制定时功能')
        except Exception as e:
            log_error_msg(f"查看日报失败: {str(e)}")
            await bot.send(ev, '查看日报失败，请查看日志')

# 启动定时任务
def start_scheduler(sv: Service):
    """
    启动定时任务
    :param sv: 服务实例
    """
    if not ENABLE_SCHEDULER:
        log_info("定时任务已禁用，不启动定时器")
        return
    
    log_info("开始启动群聊日报定时任务")
    
    bot = get_bot()
    
    # 每天定时发送日报
    scheduler.add_job(
        execute_daily_summary,
        CronTrigger(hour=SUMMARY_HOUR, minute=SUMMARY_MINUTE),
        args=(bot, None, 0, SUMMARY_START_HOUR),  # bot, target_groups=None, day_offset=0, start_hour=4
        id='dailysum_daily'
    )
    log_info(f"已添加每日 {SUMMARY_HOUR:02d}:{SUMMARY_MINUTE:02d} 的日报定时任务")
    
    # 添加日志备份定时任务，每天23:59执行
    scheduler.add_job(
        backup_logs,
        CronTrigger(hour=23, minute=59),
        id='dailysum_log_backup'
    )
    log_info("已添加23:59的日志备份定时任务")
    
    log_info('群聊日报定时任务启动完成') 

# 保存群配置
@logged
async def save_group_config():
    """保存群配置到文件"""
    try:
        config_file = os.path.join(DATA_DIR, 'group_config.json')
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump({
                'daily_sum_groups': DAILY_SUM_GROUPS
            }, f, ensure_ascii=False, indent=2)
        log_info(f"已保存群配置到 {config_file}")
        return True
    except Exception as e:
        log_error_msg(f"保存群配置失败: {str(e)}")
        return False

# 加载群配置
@logged
async def load_group_config():
    """从文件加载群配置"""
    global DAILY_SUM_GROUPS
    try:
        config_file = os.path.join(DATA_DIR, 'group_config.json')
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                DAILY_SUM_GROUPS = config.get('daily_sum_groups', [])
            log_info(f"已从 {config_file} 加载群配置，白名单群数量: {len(DAILY_SUM_GROUPS)}")
        else:
            log_info("群配置文件不存在，使用默认配置")
        return True
    except Exception as e:
        log_error_msg(f"加载群配置失败: {str(e)}")
        return False 
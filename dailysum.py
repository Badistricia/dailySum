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

# 猴子补丁，用于修复html2image在Python 3.8下的兼容性问题
import sys
if sys.version_info < (3, 9):
    import typing
    list = typing.List
    dict = typing.Dict

# import html2image # 已禁用
from apscheduler.triggers.cron import CronTrigger
from nonebot import scheduler

from hoshino import Service, priv, logger, get_bot
from .config import *
from .logger_helper import log_debug, log_info, log_warning, log_error_msg, log_critical, logged

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

# HTML转图片工具初始化
# try:
#     log_info("初始化 HTML2Image...")
#     hti = html2image.Html2Image()
#     log_info("HTML2Image 初始化成功")
# except Exception as e:
#     log_critical(f"HTML2Image 初始化失败: {str(e)}")
#     log_critical(traceback.format_exc())
#     hti = None

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
        
    async def generate(self, prompt, model=AI_MODEL, temperature=AI_TEMPERATURE):
        log_info(f"开始生成AI摘要，模型: {model}, 温度: {temperature}")
        log_debug(f"提示词: {prompt[:200]}...")
        
        async with httpx.AsyncClient() as client:
            try:
                log_debug("发送API请求...")
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature
                    },
                    timeout=120.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    log_info(f"AI生成成功，生成内容长度: {len(content)}")
                    log_debug(f"生成内容前100字符: {content[:100]}...")
                    return content
                else:
                    log_error_msg(f"DeepSeek API调用失败: {response.status_code} {response.text}")
                    return None
            except Exception as e:
                log_error_msg(f"DeepSeek API调用出错: {str(e)}")
                log_error_msg(traceback.format_exc())
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
                            
                            # 将消息添加到对应群
                            if group_id not in group_messages:
                                group_messages[group_id] = []
                            
                            group_messages[group_id].append({
                                'time': log_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'qq': sender_qq,
                                'content': content
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
        
        file_path = os.path.join(DATA_DIR, f"{group_id}_{date_str}.json")
        log_info(f"保存群聊日志到文件: {file_path}")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            log_info(f"保存群 {group_id} 的日志到 {file_path}，共 {len(messages)} 条消息")
        except Exception as e:
            log_error_msg(f"保存群聊日志出错: {str(e)}")
            log_error_msg(traceback.format_exc())

# 分割日志文件
@logged
async def split_log_files(day_offset=0):
    """
    分割日志文件，提取指定日期的群聊消息
    :param day_offset: 日期偏移，0表示今天，1表示昨天，以此类推
    """
    # 计算日期范围
    now = datetime.now()
    target_date = now - timedelta(days=day_offset)
    start_time = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    end_time = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
    date_str = target_date.strftime('%Y-%m-%d')
    
    log_info(f"开始分割日志文件，目标日期: {date_str}")
    log_info(f"日期偏移: {day_offset}，时间范围: {start_time} - {end_time}")
    
    # 检查日志路径
    if not os.path.exists(LOG_PATH):
        log_error_msg(f"系统日志路径不存在: {LOG_PATH}")
        return await load_test_data(date_str)
    
    # 解析日志
    log_info(f"开始从系统日志解析群聊消息: {LOG_PATH}")
    group_messages = await parse_syslog(LOG_PATH, start_time, end_time)
    
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
        
        # 构建聊天记录文本
        chat_log = "\n".join([f"[{msg['time']}] {msg['qq']}: {msg['content']}" for msg in messages])
        log_info(f"构建聊天记录文本完成，长度: {len(chat_log)}")
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

# 执行日报生成
@logged
async def execute_daily_summary(bot, target_groups=None, day_offset=0):
    """
    执行日报生成
    :param bot: 机器人实例
    :param target_groups: 目标群列表，为None时处理所有群
    :param day_offset: 日期偏移，0表示今天，1表示昨天，以此类推
    """
    # 计算目标日期
    target_date = datetime.now() - timedelta(days=day_offset)
    date_str = target_date.strftime('%Y-%m-%d')
    
    log_info(f"开始执行日报生成，日期: {date_str}")
    log_info(f"目标群: {target_groups if target_groups else '所有群'}")
    
    # 分割日志文件
    group_messages, _ = await split_log_files(day_offset)
    
    if not group_messages:
        log_warning(f"没有找到任何群的聊天记录，无法生成日报")
        return
    
    # 处理每个群
    for group_id, messages in group_messages.items():
        # 如果指定了目标群，且当前群不在目标群中，则跳过
        if target_groups and group_id not in target_groups:
            log_info(f"群 {group_id} 不在目标群列表中，跳过")
            continue
        
        if not messages:
            log_warning(f"群 {group_id} 没有消息，跳过生成日报")
            continue
        
        log_info(f"开始处理群 {group_id} 的日报生成")
        
        # 生成摘要
        log_info(f"为群 {group_id} 生成摘要...")
        summary = await generate_summary(group_id, date_str)
        
        if not summary:
            log_warning(f"群 {group_id} 的摘要生成失败，跳过")
            continue
        
        # 直接发送AI生成的文本摘要
        try:
            log_info(f"开始向群 {group_id} 发送文本摘要...")
            message_to_send = f"【{date_str} 群聊日报】\n\n{summary}"
            await bot.send_group_msg(
                group_id=int(group_id),
                message=message_to_send
            )
            log_info(f"成功发送群 {group_id} 的文本日报")
        except Exception as e:
            log_error_msg(f"发送群 {group_id} 文本日报出错: {str(e)}")
            log_error_msg(traceback.format_exc())

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
    group_messages, _ = await split_log_files(day_offset)
    
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
        log_error_msg(f"发送群 {target_group} 文本日报到群 {current_group_id} 出错: {str(e)}")
        log_error_msg(traceback.format_exc())

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
    scheduler.add_job(execute_daily_summary, CronTrigger(hour=SUMMARY_HOUR_AFTERNOON, minute=0), args=(bot,), id='dailysum_afternoon')
    log_info(f"已添加下午 {SUMMARY_HOUR_AFTERNOON}:00 的定时任务")
    
    scheduler.add_job(execute_daily_summary, CronTrigger(hour=SUMMARY_HOUR_NIGHT, minute=0), args=(bot,), id='dailysum_night')
    log_info(f"已添加晚上 {SUMMARY_HOUR_NIGHT}:00 的定时任务")
    
    log_info('群聊日报定时任务启动完成') 
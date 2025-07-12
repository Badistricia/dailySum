import os

try:
    from hoshino.log import _info_log_file
    # 自动获取HoshinoBot的日志文件路径
    LOG_PATH = os.path.abspath(_info_log_file)
except ImportError:
    # 兜底方案，如果获取失败则需要手动指定
    LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'run.log')  # 指向项目根目录的run.log文件

# 基本配置
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# 定时任务配置
ENABLE_SCHEDULER = True  # 是否启用定时任务
SUMMARY_HOUR = 8  # 每天几点发送日报
SUMMARY_MINUTE = 30  # 每天几分发送日报
SUMMARY_START_HOUR = 4  # 统计时间段的起始小时（例如：4点到次日4点）

# AI配置
AI_API_KEY = "sk-476330950dd24ff6869b6a301930f275"  # DeepSeek API密钥
AI_MODEL = "deepseek-chat"  # AI模型名称
AI_TEMPERATURE = 1.0  # AI生成温度

# 群配置
DAILY_SUM_GROUPS = []  # 日报功能启用的群列表，为空时对所有群启用
# 示例：DAILY_SUM_GROUPS = ['123456789', '987654321'] # 只在这两个群启用日报功能

# 并发控制
MAX_CONCURRENT_TASKS = 3  # 最大并发任务数量
TASK_INTERVAL_SECONDS = 10  # 每个群任务之间的间隔秒数

# 提示词配置
PROMPT_TEMPLATE = """请根据【{group_name}】今天的聊天记录，整理一份QQ群日报，要求：  

0. 不要使用md格式，直接返回纯文本
1. **数据必须严格按照下列格式组织**，每个部分必须带明确标题，使用【】符号：
2. **今日热点话题**（总结5-7个最活跃的讨论点）  
3. **重要消息**  
4. **金句**（摘录精彩内容）  
5. 总结:对今日群聊的简短总结，一两句话即可

【总结】
- 严格遵循上述格式，确保每个部分都有【】标记的标题
- 聊天记录中[图片]表示图片内容，[链接]表示网址

可以参考这种格式:
【今日热点话题】
1. 
2. 
3. 
4.
5.
【重要消息】
1. 
2.
3.


【金句】
1. 
2. 
3.

【今日总结】



聊天记录：
{chat_log}
"""

# HTML直接生成的提示词配置
PROMPT_HTML_TEMPLATE = """请根据【{group_name}】今天的聊天记录，生成一个精美的苹果风格Bento Grid布局的日报HTML页面，要求：

1. 页面需包含以下5个区块：
   - 聊天活跃度：展示今日消息总量、参与人数、最活跃时段等信息
   - 话题分析：列出5-7个主要讨论话题，一句话介绍即可
   - 重要消息：分析整体聊天氛围和群友互动情况
   - 金句：展示精彩对话或有趣互动
   - 总结：对今日群聊的简短总结

2. 布局与设计要求：
   - 必须使用深色主题，类似苹果官网的Bento Grid布局
   - 页面顶部有标题："{title}"
   - 页面底部有落款："由AI生成 · {date}"
   - 使用圆角卡片设计，每个区块有独特图标
   - 布局宽度固定为800px
   - 确保文字清晰易读，深色背景上使用浅色文字
   - 必须使用不超过20行的内联CSS样式，不能使用外部样式表

3. 内容要求：
   - 内容控制在600字以内，简洁明了
   - 结构清晰，每个区块标题醒目
   - 总结部分使用高亮颜色显示

4. 技术要求：
   - 只需提供完整的HTML代码，不需要额外解释
   - 确保HTML代码有良好的缩进和格式
   - 确保代码中不包含任何会阻止直接执行的脚本
   - 代码必须能在现代浏览器中正确显示

请基于以上要求，将聊天记录分析后直接返回完整的HTML代码，无需额外说明。

聊天记录：
{chat_log}
"""
# 最后，用分块布局（类似苹果发布会的Bento Grid风格）生成HTML，方便阅读。

# 图片生成配置
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日报</title>
    <style>
        body {
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background-color: #f5f5f7;
            color: #1d1d1f;
            padding: 20px;
            margin: 0;
            line-height: 1.5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .header {
            background-color: #000;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-weight: 600;
            font-size: 24px;
        }
        .date {
            color: #86868b;
            font-size: 14px;
            margin-top: 5px;
        }
        .bento-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            padding: 20px;
        }
        .bento-item {
            background-color: #f5f5f7;
            border-radius: 8px;
            padding: 15px;
            overflow: hidden;
        }
        .bento-item.large {
            grid-column: span 2;
        }
        .bento-item h2 {
            margin-top: 0;
            font-size: 18px;
            color: #1d1d1f;
            border-bottom: 1px solid #d2d2d7;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }
        .bento-item p {
            margin: 8px 0;
            font-size: 14px;
        }
        .bento-item ul {
            margin: 8px 0;
            padding-left: 20px;
        }
        .bento-item li {
            margin-bottom: 8px;
            font-size: 14px;
        }
        .footer {
            text-align: center;
            padding: 15px;
            color: #86868b;
            font-size: 12px;
            border-top: 1px solid #d2d2d7;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{group_name}日报</h1>
            <div class="date">{date}</div>
        </div>
        <div class="bento-grid">
            {content}
        </div>
        <div class="footer">
            由HoshinoBot生成 · {date}
        </div>
    </div>
</body>
</html>
""" 

# 黑色背景的日报模板
DARK_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        @font-face {
            font-family: 'CustomFont';
            src: url('file://{font_path}') format('truetype');
            font-weight: normal;
            font-style: normal;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'CustomFont', 'Microsoft YaHei', '微软雅黑', 'SimHei', '黑体', sans-serif;
        }
        
        body {
            background-color: #000;
            margin: 0;
            padding: 0;
            color: #fff;
            line-height: 1.6;
        }
        
        .bento-container {
            width: 800px;
            padding: 20px;
            background-color: #000;
            margin: 0;
        }
        
        .bento-title {
            font-size: 28px;
            font-weight: bold;
            color: #fff;
            margin-bottom: 24px;
            text-align: center;
        }
        
        .bento-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            grid-auto-rows: auto;
            gap: 16px;
        }
        
        .bento-item {
            background-color: #1c1c1e;
            border-radius: 20px;
            padding: 20px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            position: relative;
            transition: all 0.3s ease;
        }
        
        .bento-item-large {
            grid-column: span 2;
        }
        
        .bento-item-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 12px;
            color: #0a84ff;
            display: flex;
            align-items: center;
        }
        
        .bento-item-icon {
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
        }
        
        .bento-item-content {
            color: #eee;
            font-size: 15px;
        }
        
        ul {
            padding-left: 20px;
            margin-top: 10px;
        }
        
        li {
            margin-bottom: 8px;
        }
        
        .bento-footer {
            margin-top: 16px;
            text-align: center;
            font-size: 13px;
            color: #888;
        }
        
        .highlight {
            color: #0a84ff;
            font-weight: bold;
        }
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
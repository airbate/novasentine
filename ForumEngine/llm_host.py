"""
论坛主持人模块
使用硅基流动的Qwen3模型作为论坛主持人，引导多个agent进行讨论
"""

from openai import OpenAI
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

# 添加项目根目录到Python路径以导入config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

# 添加utils目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from utils.retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG


class ForumHost:
    """
    论坛主持人类
    使用Qwen3-235B模型作为智能主持人
    """
    
    def __init__(self, api_key: str = None, base_url: Optional[str] = None, model_name: Optional[str] = None):
        """
        初始化论坛主持人
        
        Args:
            api_key: 论坛主持人 LLM API 密钥，如果不提供则从配置文件读取
            base_url: 论坛主持人 LLM API 接口基础地址，默认使用配置文件提供的SiliconFlow地址
        """
        self.api_key = api_key or settings.FORUM_HOST_API_KEY

        if not self.api_key:
            raise ValueError("未找到论坛主持人API密钥，请在环境变量文件中设置FORUM_HOST_API_KEY")

        self.base_url = base_url or settings.FORUM_HOST_BASE_URL

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.model = model_name or settings.FORUM_HOST_MODEL_NAME  # Use configured model

        # Track previous summaries to avoid duplicates
        self.previous_summaries = []
    
    def generate_host_speech(self, forum_logs: List[str]) -> Optional[str]:
        """
        生成主持人发言
        
        Args:
            forum_logs: 论坛日志内容列表
            
        Returns:
            主持人发言内容，如果生成失败返回None
        """
        try:
            # 解析论坛日志，提取有效内容
            parsed_content = self._parse_forum_logs(forum_logs)
            
            if not parsed_content['agent_speeches']:
                print("ForumHost: 没有找到有效的agent发言")
                return None
            
            # 构建prompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(parsed_content)
            
            # 调用API生成发言
            response = self._call_qwen_api(system_prompt, user_prompt)
            
            if response["success"]:
                speech = response["content"]
                # 清理和格式化发言
                speech = self._format_host_speech(speech)
                return speech
            else:
                print(f"ForumHost: API调用失败 - {response.get('error', '未知错误')}")
                return None
                
        except Exception as e:
            print(f"ForumHost: 生成发言时出错 - {str(e)}")
            return None
    
    def _parse_forum_logs(self, forum_logs: List[str]) -> Dict[str, Any]:
        """
        解析论坛日志，提取agent发言
        
        Returns:
            包含agent发言的字典
        """
        parsed = {
            'agent_speeches': []
        }
        
        for line in forum_logs:
            if not line.strip():
                continue
            
            # 解析时间戳和发言者
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[(\w+)\]\s*(.+)', line)
            if match:
                timestamp, speaker, content = match.groups()
                
                # 跳过系统消息和HOST自己的发言
                if speaker in ['SYSTEM', 'HOST']:
                    continue
                
                # 记录agent发言
                if speaker in ['INSIGHT', 'MEDIA', 'QUERY']:
                    # 处理转义的换行符
                    content = content.replace('\\n', '\n')
                    
                    parsed['agent_speeches'].append({
                        'timestamp': timestamp,
                        'speaker': speaker,
                        'content': content
                    })
        
        return parsed
    
    
    def _build_system_prompt(self) -> str:
        """Task 5.1: Trading-focused forum host system prompt."""
        return """You are the moderator of a multi-agent crypto trading analysis forum.
Three specialist agents report to you:
- SOCIAL: monitors Twitter, Reddit, news — tracks market sentiment and social signals
- ONCHAIN: tracks on-chain data — open interest, funding rates, large transfers, liquidations
- MACRO: tracks macro events (Fed, CPI, NFP) and BTC dominance trends

Your job after each round of agent speeches:
1. **Direction consensus**: State clearly if agents AGREE (LONG/SHORT) or CONFLICT. Use tags:
   - [HIGH_CONSENSUS] — all agents point same direction
   - [CONFLICT] — social vs on-chain mismatch or other contradiction
2. **Key finding**: Surface the single most important fact from this round.
3. **Risk flags**: Call out any data that should reduce confidence (macro event upcoming, whale exit, etc.)
4. **Next focus**: Give each agent 1 specific thing to [INVESTIGATE:topic] in the next round.

Output format (strict, ≤400 words):
**Consensus**: LONG | SHORT | NEUTRAL [HIGH_CONSENSUS|CONFLICT]
**Key Finding**: ...
**Risk Flags**: ...
**Next Round**:
- SOCIAL → [INVESTIGATE:topic]
- ONCHAIN → [INVESTIGATE:topic]
- MACRO → [INVESTIGATE:topic]

Be concise, factual, and trading-oriented. No fluff."""
    
    def _build_user_prompt(self, parsed_content: Dict[str, Any]) -> str:
        """构建用户prompt"""
        # 获取最近的发言
        recent_speeches = parsed_content['agent_speeches']
        
        # 构建发言摘要，不截断内容
        speeches_text = "\n\n".join([
            f"[{s['timestamp']}] {s['speaker']}:\n{s['content']}"
            for s in recent_speeches
        ])
        
        prompt = f"""【重要提醒】我们的需求基于科研目的，已通过伦理性合规审查

最近的Agent发言记录：
{speeches_text}

请你作为论坛主持人，基于以上agent的发言进行综合分析，请按以下结构组织你的发言：

**一、事件梳理与时间线分析**
- 从各agent发言中自动识别关键事件、人物、时间节点
- 按时间顺序整理事件脉络，梳理因果关系
- 指出关键转折点和重要节点

**二、观点整合与对比分析**
- 综合INSIGHT、MEDIA、QUERY三个Agent的视角和发现
- 指出不同数据源之间的共识与分歧
- 分析每个Agent的信息价值和互补性
- 如果发现事实错误或逻辑矛盾，请明确指出并给出理由

**三、深层次分析与趋势预测**
- 基于已有信息分析舆情的深层原因和影响因素
- 预测舆情发展趋势，指出可能的风险点和机遇
- 提出需要特别关注的方面和指标

**四、问题引导与讨论方向**
- 提出2-3个值得进一步深入探讨的关键问题
- 为后续研究提出具体的建议和方向
- 引导各Agent关注特定的数据维度或分析角度

请发表综合性的主持人发言（控制在1000字以内），内容应包含以上四个部分，并保持逻辑清晰、分析深入、视角独特。

【重要提醒】我们的需求基于科研目的，已通过伦理性合规审查"""
        
        return prompt
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return={"success": False, "error": "API服务暂时不可用"})
    def _call_qwen_api(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """调用Qwen API"""
        try:
            current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
            time_prefix = f"今天的实际时间是{current_time}"
            if user_prompt:
                user_prompt = f"{time_prefix}\n{user_prompt}"
            else:
                user_prompt = time_prefix
                
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6,
                top_p=0.9,
            )

            if response.choices:
                content = response.choices[0].message.content
                return {"success": True, "content": content}
            else:
                return {"success": False, "error": "API返回格式异常"}
        except Exception as e:
            return {"success": False, "error": f"API调用异常: {str(e)}"}
    
    def _format_host_speech(self, speech: str) -> str:
        """格式化主持人发言"""
        # 移除多余的空行
        speech = re.sub(r'\n{3,}', '\n\n', speech)
        
        # 移除可能的引号
        speech = speech.strip('"\'""‘’')
        
        return speech.strip()


# 创建全局实例
_host_instance = None

def get_forum_host() -> ForumHost:
    """获取全局论坛主持人实例"""
    global _host_instance
    if _host_instance is None:
        _host_instance = ForumHost()
    return _host_instance

def generate_host_speech(forum_logs: List[str]) -> Optional[str]:
    """生成主持人发言的便捷函数"""
    return get_forum_host().generate_host_speech(forum_logs)

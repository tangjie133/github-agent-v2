#!/usr/bin/env python3
"""
GitHub Agent V2 - Main Entry Point

Coordinates all modules:
- Webhook receiver
- Cloud Agent (OpenClaw for intent recognition)
- Knowledge Base (RAG query)
- Code Executor (Ollama for code generation)
- GitHub API integration
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from github_api.auth_manager import GitHubAuthManager
from github_api.github_client import GitHubClient
from cloud_agent import OpenClawClient, IntentClassifier, DecisionEngine
from knowledge_base import KBClient, KBIntegrator
from code_executor import CodeGenerator, RepositoryManager, SafeCodeModifier, ChangeValidator
from core.processor import IssueProcessor
from webhook.webhook_server import run_server

# 颜色定义
COLORS = {
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
    'CYAN': '\033[0;36m',
    'GREEN': '\033[0;32m',
    'YELLOW': '\033[0;33m',
    'RED': '\033[0;31m',
    'BLUE': '\033[0;34m',
    'MAGENTA': '\033[0;35m',
}

# 启动阶段计数器
_startup_step = [0]

def log_step(component: str, message: str, status: str = None):
    """统一的启动日志格式"""
    _startup_step[0] += 1
    step_num = _startup_step[0]
    
    # 组件名称对齐
    component_display = f"{COLORS['CYAN']}[{component}]{COLORS['RESET']}"
    
    # 状态图标
    if status == 'ok':
        status_icon = f"{COLORS['GREEN']}✓{COLORS['RESET']}"
    elif status == 'warn':
        status_icon = f"{COLORS['YELLOW']}⚠{COLORS['RESET']}"
    elif status == 'error':
        status_icon = f"{COLORS['RED']}✗{COLORS['RESET']}"
    else:
        status_icon = "•"
    
    print(f"{COLORS['BOLD']}[{step_num:02d}]{COLORS['RESET']} {component_display} {status_icon} {message}")

def log_detail(message: str, indent: int = 2):
    """缩进详情日志"""
    indent_str = "  " * indent
    print(f"{indent_str}{message}")

def log_banner():
    """显示启动横幅"""
    print()
    print(f"{COLORS['MAGENTA']}{COLORS['BOLD']}╔══════════════════════════════════════════════════════════════╗{COLORS['RESET']}")
    print(f"{COLORS['MAGENTA']}{COLORS['BOLD']}║{COLORS['RESET']}              GitHub Agent V2 - 智能 Issue 处理系统              {COLORS['MAGENTA']}{COLORS['BOLD']}║{COLORS['RESET']}")
    print(f"{COLORS['MAGENTA']}{COLORS['BOLD']}╚══════════════════════════════════════════════════════════════╝{COLORS['RESET']}")
    print()

# 读取日志级别
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

# 定义颜色代码
COLORS_LOG = {
    'DEBUG': '\033[0;35m',     # 紫色
    'INFO': '\033[0;34m',      # 蓝色
    'WARNING': '\033[0;33m',   # 黄色
    'ERROR': '\033[0;31m',     # 红色
    'CRITICAL': '\033[1;31m',  # 粗红
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
}

class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    def format(self, record):
        # 简化模块名
        module_name = record.name.replace('knowledge_base.', 'KB.').replace('code_executor.', 'CE.')
        
        # 根据级别选择颜色
        color = COLORS_LOG.get(record.levelname, COLORS_LOG['RESET'])
        reset = COLORS_LOG['RESET']
        bold = COLORS_LOG['BOLD']
        
        # 格式化时间
        time_str = self.formatTime(record, '%H:%M:%S')
        
        # 格式化消息
        if LOG_LEVEL == 'DEBUG':
            # DEBUG 模式显示详细信息
            return f"{time_str} {color}{bold}[{record.levelname:8}]{reset} {color}[{module_name:15}]{reset} {record.getMessage()}"
        else:
            # INFO 模式简化输出
            level_icon = {'INFO': '•', 'WARNING': '!', 'ERROR': '✗', 'DEBUG': '◆'}.get(record.levelname, '•')
            return f"{color}{level_icon}{reset} {record.getMessage()}"

# 配置日志
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    handlers=[handler]
)
logger = logging.getLogger(__name__)

# 降低第三方库的日志级别
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)


def ensure_kb_service():
    """Ensure KB Service is running, start if not"""
    import requests
    import subprocess
    import time
    
    kb_url = os.environ.get("KB_SERVICE_URL", "http://localhost:8000")
    
    try:
        resp = requests.get(f"{kb_url}/health", timeout=2)
        if resp.status_code == 200:
            return True  # Already running
    except:
        pass
    
    # Try to start KB Service
    log_detail(f"知识库服务未运行，正在自动启动...", indent=3)
    try:
        # Start in background
        subprocess.Popen(
            [sys.executable, "-m", "knowledge_base.kb_service"],
            stdout=open("/tmp/kb_service.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # Wait for it to start
        for i in range(10):
            time.sleep(1)
            try:
                resp = requests.get(f"{kb_url}/health", timeout=2)
                if resp.status_code == 200:
                    log_detail(f"{COLORS['GREEN']}自动启动成功{COLORS['RESET']}", indent=3)
                    return True
            except:
                pass
        
        log_detail(f"{COLORS['YELLOW']}自动启动超时{COLORS['RESET']}", indent=3)
        return False
    except Exception as e:
        log_detail(f"{COLORS['RED']}自动启动失败: {e}{COLORS['RESET']}", indent=3)
        return False


def create_processor() -> IssueProcessor:
    """Create and configure the issue processor with all components"""
    
    log_banner()
    
    # Step 1: GitHub Auth
    log_step("GitHub", "初始化认证管理器...")
    auth_manager = GitHubAuthManager()
    log_step("GitHub", "认证管理器就绪", status='ok')
    
    # Step 2: Cloud Agent (OpenClaw)
    log_step("OpenClaw", "初始化意图识别服务...")
    openclaw_client = OpenClawClient()
    intent_classifier = IntentClassifier(openclaw_client)
    decision_engine = DecisionEngine(openclaw_client)
    intent_classifier.decision_engine = decision_engine
    
    if openclaw_client.health_check():
        log_step("OpenClaw", "服务连接正常", status='ok')
    else:
        log_step("OpenClaw", "服务不可用，将使用本地规则回退", status='warn')
    
    # Step 3: Knowledge Base
    log_step("Knowledge", "初始化知识库服务...")
    ensure_kb_service()
    
    kb_client = KBClient()
    kb_integrator = KBIntegrator(kb_client)
    
    if kb_client.health_check():
        kb_stats = kb_client.get_stats()
        doc_count = kb_stats.get('total_documents', 0) if kb_stats else 0
        log_step("Knowledge", f"服务就绪", status='ok')
        log_detail(f"文档数量: {doc_count}")
    else:
        log_step("Knowledge", "服务不可用，知识增强功能已禁用", status='warn')
    
    # Step 4: Code Executor (Ollama)
    log_step("Ollama", "初始化代码生成服务...")
    code_gen = CodeGenerator()
    repo_mgr = RepositoryManager()
    safe_mod = SafeCodeModifier(code_gen)
    validator = ChangeValidator(code_gen)
    
    if code_gen.health_check():
        log_step("Ollama", f"服务就绪", status='ok')
        log_detail(f"模型: {COLORS['CYAN']}{code_gen.model}{COLORS['RESET']}")
        log_detail(f"地址: {code_gen.host}")
    else:
        log_step("Ollama", "服务不可用，代码生成功能已禁用", status='warn')
    
    # Create integrated code executor
    from code_executor.code_executor import CodeExecutor
    code_executor = CodeExecutor(
        code_generator=code_gen,
        repo_manager=repo_mgr,
        safe_modifier=safe_mod,
        validator=validator
    )
    
    # Step 5: Create processor
    log_step("Core", "初始化 Issue 处理器...")
    processor = IssueProcessor(
        github_client=None,
        cloud_agent=intent_classifier,
        knowledge_base=kb_integrator,
        code_executor=code_executor,
        auth_manager=auth_manager
    )
    log_step("Core", "Issue 处理器就绪", status='ok')
    
    print()
    return processor


def main():
    """Main entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Agent V2")
    parser.add_argument("--host", default="0.0.0.0", help="Webhook server host")
    parser.add_argument("--port", type=int, default=8080, help="Webhook server port")
    parser.add_argument("--test-intent", action="store_true", help="Test intent classification")
    
    args = parser.parse_args()
    
    if args.test_intent:
        # Test intent classification
        logger.info("Testing intent classification...")
        
        from core.models import IssueContext
        
        client = OpenClawClient()
        classifier = IntentClassifier(client)
        
        # Test case 1: Question
        context1 = IssueContext(
            issue_number=1,
            title="Question about implementation",
            body="@agent Why did you use this approach?",
            author="testuser",
            current_instruction="@agent Why did you use this approach?"
        )
        
        result1 = classifier.classify(context1)
        print(f"\nTest 1 (Question):")
        print(f"  Input: {context1.current_instruction}")
        print(f"  Intent: {result1.intent.value}")
        print(f"  Confidence: {result1.confidence}")
        print(f"  Reasoning: {result1.reasoning}")
        
        # Test case 2: Modification request
        context2 = IssueContext(
            issue_number=2,
            title="Bug fix needed",
            body="@agent Please fix the null pointer exception in line 10",
            author="testuser",
            current_instruction="@agent Please fix the null pointer exception in line 10"
        )
        
        result2 = classifier.classify(context2)
        print(f"\nTest 2 (Modification):")
        print(f"  Input: {context2.current_instruction}")
        print(f"  Intent: {result2.intent.value}")
        print(f"  Confidence: {result2.confidence}")
        print(f"  Reasoning: {result2.reasoning}")
        
        return
    
    # Create processor
    processor = create_processor()
    
    # Run webhook server
    log_step("Server", f"启动 Webhook 服务...")
    log_detail(f"监听地址: {COLORS['CYAN']}{args.host}:{args.port}{COLORS['RESET']}")
    log_detail(f"Webhook URL: {COLORS['CYAN']}http://{args.host}:{args.port}/webhook/github{COLORS['RESET']}")
    print()
    run_server(host=args.host, port=args.port, processor=processor)


if __name__ == "__main__":
    main()

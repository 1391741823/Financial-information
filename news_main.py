# -*- coding: utf-8 -*-
"""
===================================
金融新闻摘要系统 - 主调度程序
===================================

职责：
1. 协调各模块完成金融新闻摘要流程
2. 提供命令行入口
3. 支持定时任务模式

使用方式：
    python news_main.py              # 正常运行（生成晚报）
    python news_main.py --debug      # 调试模式
    python news_main.py --topics "AI,半导体"  # 自定义话题
    python news_main.py --schedule   # 定时任务模式
"""

import os

# 代理配置 - 仅在本地环境使用，GitHub Actions 不需要
if os.getenv("GITHUB_ACTIONS") != "true":
    pass

import argparse
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional

from src.config import get_config, Config
from src.news_digest import NewsDigestPipeline
from src.feishu_doc import FeishuDocManager

# 配置日志格式
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging(debug: bool = False, log_dir: str = "./logs") -> None:
    """
    配置日志系统（同时输出到控制台和文件）

    Args:
        debug: 是否启用调试模式
        log_dir: 日志文件目录
    """
    level = logging.DEBUG if debug else logging.INFO

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    today_str = datetime.now().strftime('%Y%m%d')
    log_file = log_path / f"news_digest_{today_str}.log"
    debug_log_file = log_path / f"news_digest_debug_{today_str}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Handler 1: 控制台
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # Handler 2: 常规日志文件
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # Handler 3: 调试日志文件
    debug_handler = RotatingFileHandler(
        debug_log_file, maxBytes=50 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    root_logger.addHandler(debug_handler)

    # 降低第三方库日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

    logging.info(f"日志系统初始化完成，日志目录: {log_path.absolute()}")


logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='金融新闻摘要系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python news_main.py                      # 正常运行
  python news_main.py --debug              # 调试模式
  python news_main.py --topics "AI,半导体,新能源"  # 自定义话题
  python news_main.py --instruction "重点关注美联储动向"  # 额外AI指令
  python news_main.py --no-notify          # 不发送推送通知
  python news_main.py --schedule           # 启用定时任务模式
        '''
    )

    parser.add_argument('--debug', action='store_true', help='启用调试模式')

    parser.add_argument(
        '--topics', type=str,
        help='自定义新闻话题关键词，逗号分隔（覆盖配置文件）'
    )

    parser.add_argument(
        '--instruction', type=str,
        help='额外的 AI 摘要指令（如"重点关注xxx"）'
    )

    parser.add_argument('--no-notify', action='store_true', help='不发送推送通知')

    parser.add_argument(
        '--schedule', action='store_true',
        help='启用定时任务模式，每日定时执行'
    )

    return parser.parse_args()


def run_news_digest(
    config: Config,
    args: argparse.Namespace,
    topics: Optional[List[str]] = None,
    custom_instruction: Optional[str] = None
) -> Optional[str]:
    """
    执行金融新闻摘要流程

    这是定时任务调用的主函数

    Returns:
        Markdown 格式的摘要报告
    """
    try:
        pipeline = NewsDigestPipeline(config=config)

        report = pipeline.run(
            topics=topics,
            custom_instruction=custom_instruction,
            send_notification=not args.no_notify,
        )

        # 可选：生成飞书云文档
        if report:
            try:
                feishu_doc = FeishuDocManager()
                if feishu_doc.is_configured():
                    tz_cn = timezone(timedelta(hours=8))
                    now = datetime.now(tz_cn)
                    digest_type = "早报" if now.hour < 12 else "晚报"
                    doc_title = f"{now.strftime('%Y-%m-%d')} 金融新闻{digest_type}"
                    doc_url = feishu_doc.create_daily_doc(doc_title, report)
                    if doc_url:
                        logger.info(f"飞书云文档创建成功: {doc_url}")
            except Exception as e:
                logger.error(f"飞书文档生成失败: {e}")

        return report

    except Exception as e:
        logger.exception(f"新闻摘要流程执行失败: {e}")
        return None


def main() -> int:
    """
    主入口函数

    Returns:
        退出码（0 表示成功）
    """
    args = parse_arguments()
    config = get_config()
    setup_logging(debug=args.debug, log_dir=config.log_dir)

    # 北京时间
    tz_cn = timezone(timedelta(hours=8))
    now = datetime.now(tz_cn)
    digest_type = "早报" if now.hour < 12 else "晚报"

    logger.info("=" * 60)
    logger.info(f"金融新闻摘要系统 启动 ({digest_type})")
    logger.info(f"运行时间: {now.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    logger.info("=" * 60)

    # 验证配置
    warnings = config.validate()
    for warning in warnings:
        logger.warning(warning)

    # 解析自定义话题
    topics: Optional[List[str]] = None
    if args.topics:
        topics = [t.strip() for t in args.topics.split(',') if t.strip()]
        logger.info(f"使用自定义话题: {topics}")

    custom_instruction = args.instruction
    if custom_instruction:
        logger.info(f"附加 AI 指令: {custom_instruction}")

    try:
        # 模式1: 定时任务模式
        if args.schedule or config.schedule_enabled:
            logger.info("模式: 定时任务")
            logger.info(f"每日执行时间: {config.schedule_time}")

            from src.scheduler import run_with_schedule

            def scheduled_task():
                run_news_digest(config, args, topics, custom_instruction)

            run_with_schedule(
                task=scheduled_task,
                schedule_time=config.schedule_time,
                run_immediately=True
            )
            return 0

        # 模式2: 正常单次运行
        report = run_news_digest(config, args, topics, custom_instruction)
        if report:
            logger.info("\n新闻摘要生成完成")
        else:
            logger.warning("\n新闻摘要生成失败或返回空结果")

        return 0 if report else 1

    except KeyboardInterrupt:
        logger.info("\n用户中断，程序退出")
        return 130

    except Exception as e:
        logger.exception(f"程序执行失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
===================================
金融新闻摘要系统 - 核心管道
===================================

职责：
1. 按话题关键词搜索金融新闻
2. 调用 AI 生成结构化摘要
3. 格式化并推送摘要报告
"""

import logging
import time
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import get_config, Config
from src.search_service import SearchService
from src.analyzer import GeminiAnalyzer
from src.notification import NotificationService
from src.rss_fetcher import fetch_news_from_rss


logger = logging.getLogger(__name__)


class NewsDigestPipeline:
    """
    金融新闻摘要管道

    流程：
    1. fetch_news()      — 按话题搜索金融新闻
    2. summarize_with_ai() — AI 生成结构化摘要
    3. format_digest()   — 格式化为 Markdown 报告
    4. run()             — 协调完整流程（拉新闻 → AI 摘要 → 格式化 → 推送）
    """

    def __init__(self, config: Optional[Config] = None):
        """
        初始化新闻摘要管道

        Args:
            config: 配置对象（可选，默认使用全局配置）
        """
        self.config = config or get_config()

        # 初始化搜索服务（复用现有）
        self.search_service = SearchService(
            bocha_keys=self.config.bocha_api_keys,
            tavily_keys=self.config.tavily_api_keys,
            serpapi_keys=self.config.serpapi_keys,
        )

        # 初始化 AI 分析器（复用现有）
        self.analyzer = GeminiAnalyzer()

        # 初始化通知服务（复用现有）
        self.notifier = NotificationService()

        # ================================================================
        # 标题到链接的映射表（用于在 format_digest 中生成可点击链接）
        # ================================================================
        self.title_link_map = {}

        logger.info(f"新闻摘要管道初始化完成")
        logger.info(f"新闻话题: {', '.join(self.config.news_topics)}")
        logger.info(f"每话题最大文章数: {self.config.news_max_articles}")
        logger.info(f"摘要时段: {self.config.news_digest_schedule}")
        if self.search_service.is_available:
            logger.info("搜索服务已启用")
        else:
            logger.warning("搜索服务未启用（未配置 API Key）")
        if self.analyzer.is_available():
            logger.info("AI 分析器已启用")
        else:
            logger.warning("AI 分析器未启用（未配置 API Key）")

    def fetch_news(self, topics: Optional[List[str]] = None) -> Dict[str, str]:
        """
        从 RSS 源获取金融新闻

        改为使用新浪财经 RSS 而非搜索引擎 API

        Args:
            topics: 话题关键词列表（可选，保留参数但不再用于搜索，仅用于过滤）

        Returns:
            {话题名称: 该话题的原始新闻文本} 字典
        """
        if topics is None:
            topics = self.config.news_topics

        max_articles = self.config.news_max_articles
        topic_news: Dict[str, str] = {}

        logger.info(f"开始从 RSS 拉取金融新闻，共 {len(topics)} 个话题...")

        # 每次拉取新闻前清空映射表，避免上一次的数据残留
        self.title_link_map = {}

        try:
            # 从 RSS 获取新闻
            all_news = fetch_news_from_rss(limit_per_source=max_articles)

            if not all_news:
                logger.warning("RSS 未获取到任何新闻")
                return topic_news

            logger.info(f"RSS 共获取 {len(all_news)} 条新闻，开始按话题过滤...")

            # 按话题关键词过滤新闻（保留原有话题分类逻辑）
            for topic in topics:
                # 话题关键词匹配（包含关键词则归入该话题）
                filtered = []
                for news in all_news:
                    title = news.get("title", "")
                    # 检查标题是否包含话题关键词或其变体
                    keywords = self._get_topic_keywords(topic)
                    if any(kw in title for kw in keywords):
                        filtered.append(news)
                        # 保存标题→链接映射
                        link = news.get('link', '')
                        if title and link:
                            self.title_link_map[title] = link

                if filtered:
                    # 格式化为文本
                    lines = [f"## {topic}"]
                    for i, news in enumerate(filtered[:max_articles], 1):
                        lines.append(f"\n{i}. **{news.get('title', '')}**")
                        if news.get('summary'):
                            lines.append(f"   摘要: {news['summary'][:200]}")
                        if news.get('source'):
                            lines.append(f"   来源: {news['source']}")
                        if news.get('published'):
                            lines.append(f"   时间: {news['published']}")
                    topic_news[topic] = "\n".join(lines)
                    logger.info(f"{topic}: 匹配到 {len(filtered)} 条新闻")
                else:
                    logger.warning(f"{topic}: 未匹配到相关新闻")

            # 如果没有按话题匹配到任何新闻，把全部新闻放在"综合"话题下
            if not topic_news and all_news:
                lines = ["## 综合财经要闻"]
                for i, news in enumerate(all_news[:max_articles * len(topics)], 1):
                    title = news.get('title', '')
                    lines.append(f"\n{i}. **{title}**")
                    if news.get('summary'):
                        lines.append(f"   摘要: {news['summary'][:200]}")
                    if news.get('source'):
                        lines.append(f"   来源: {news['source']}")
                    if news.get('published'):
                        lines.append(f"   时间: {news['published']}")
                    # 保存标题→链接映射
                    link = news.get('link', '')
                    if title and link:
                        self.title_link_map[title] = link
                topic_news["综合"] = "\n".join(lines)
                logger.warning("没有按话题匹配到新闻，已将全部新闻放入'综合'话题")

        except Exception as e:
            logger.error(f"RSS 拉取新闻失败: {e}")

        total_topics = len(topic_news)
        logger.info(f"新闻拉取完成: {total_topics}/{len(topics)} 个话题成功获取新闻")
        return topic_news

    def _get_topic_keywords(self, topic: str) -> List[str]:
        """
        为每个话题生成关键词列表（用于匹配新闻标题）
        """
        keyword_map = {
            "宏观经济": ["宏观", "经济", "GDP", "CPI", "央行", "降息", "降准", "通货膨胀", "就业"],
            "A股市场": ["A股", "上证", "深证", "创业板", "科创板", "北交所", "两市", "成交额", "涨停", "跌停"],
            "行业动态": ["行业", "产业", "新能源", "光伏", "芯片", "半导体", "人工智能", "AI", "消费", "医药"],
            "政策法规": ["政策", "监管", "证监会", "银保监会", "央行", "国务院", "发改委", "财政部", "国资委", "反垄断"],
            "国际市场": ["美股", "港股", "纳斯达克", "道指", "标普", "恒生", "美联储", "欧股", "日经", "国际"],
            "公司新闻": ["财报", "业绩", "营收", "净利润", "增持", "减持", "回购", "分红", "融资", "并购", "上市"],
        }
        return keyword_map.get(topic, [topic])

    def _search_topic_news(self, topic: str, query: str, max_results: int) -> str:
        """
        搜索单个话题的新闻并格式化为文本

        Args:
            topic: 话题名称
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            格式化的新闻文本，失败时返回空字符串
        """
        from src.search_service import SearchResponse

        # 尝试所有可用的搜索引擎
        for provider in self.search_service._providers:
            if not provider.is_available:
                continue

            response = provider.search(query, max_results)
            if response.success and response.results:
                # 格式化为文本
                lines = [f"## {topic} ({provider.name} 搜索)"]
                for i, result in enumerate(response.results, 1):
                    date_str = f" [{result.published_date}]" if result.published_date else ""
                    lines.append(f"\n{i}. **{result.title}**{date_str}")
                    lines.append(f"   来源: {result.source}")
                    lines.append(f"   摘要: {result.snippet[:300]}")
                return "\n".join(lines)

        return ""

    def summarize_with_ai(
        self,
        topic_news: Dict[str, str],
        custom_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调用 AI 对新闻进行摘要

        将所有话题的新闻合并，输入 Gemini 生成结构化摘要

        Args:
            topic_news: {话题: 新闻文本} 字典
            custom_instruction: 额外的自定义指令

        Returns:
            结构化摘要字典（与 GeminiAnalyzer.summarize_news() 返回格式一致）
        """
        if not topic_news:
            logger.warning("没有新闻内容可供摘要")
            return {
                "headline": "今日无新闻数据",
                "market_mood": "未知",
                "categories": [],
                "key_events": [],
                "looking_ahead": "请检查搜索引擎 API Key 配置",
            }

        # 合并所有话题的新闻
        topics_list = list(topic_news.keys())
        topics_str = "、".join(topics_list)

        combined_news_parts = []
        for topic, news_text in topic_news.items():
            combined_news_parts.append(news_text)

        combined_news = "\n\n---\n\n".join(combined_news_parts)

        logger.info(f"开始 AI 摘要，话题: {topics_str}，总新闻长度: {len(combined_news)} 字符")

        # 调用分析器的新闻摘要方法
        result = self.analyzer.summarize_news(
            news_content=combined_news,
            topics=topics_str,
            custom_instruction=custom_instruction,
        )

        return result

    def format_digest(
        self,
        summary: Dict[str, Any],
        digest_type: str = "晚报"
    ) -> str:
        """
        将 AI 摘要格式化为 Markdown 报告

        Args:
            summary: AI 返回的结构化摘要
            digest_type: 摘要类型（"早报" / "晚报"）

        Returns:
            Markdown 格式的摘要报告
        """
        # 北京时间
        tz_cn = timezone(timedelta(hours=8))
        now = datetime.now(tz_cn)
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M')

        mood_emoji = {
            "乐观": "🟢", "中性": "🟡", "谨慎": "🟠", "悲观": "🔴", "未知": "⚪"
        }
        mood = summary.get("market_mood", "未知")
        mood_display = f"{mood_emoji.get(mood, '⚪')} {mood}"

        lines = [
            f"# 📰 金融新闻{digest_type} | {date_str} {time_str}",
            "",
            f"> 🎯 **今日要闻**: {summary.get('headline', '暂无')}",
            f"> 📊 **市场情绪**: {mood_display}",
            "",
            "---",
            "",
        ]

        # 分类摘要
        categories = summary.get("categories", [])
        if categories:
            category_icons = {
                "宏观经济": "🌏", "宏观": "🌏",
                "A股市场": "📊", "A股": "📊", "股市": "📊",
                "行业动态": "🏭", "行业": "🏭",
                "政策法规": "📜", "政策": "📜",
                "国际市场": "🌐", "国际": "🌐",
                "公司新闻": "💼", "公司": "💼",
            }
            for cat in categories:
                title = cat.get("title", "未分类")
                icon = category_icons.get(title, "📌")
                importance = cat.get("importance", "中")
                imp_mark = {"高": " 🔴", "中": " 🟡", "低": " ⚪"}.get(importance, "")

                lines.append(f"## {icon} {title}{imp_mark}")
                lines.append("")

                if cat.get("summary"):
                    lines.append(f"**要点**: {cat['summary']}")
                    lines.append("")

                articles = cat.get("articles", [])
                if articles:
                    for art in articles:
                        impact = art.get("impact", "中性")
                        impact_icon = {"利好": "📈", "利空": "📉", "中性": "➡️"}.get(impact, "➡️")
                        lines.append(
                            f"- {impact_icon} **{art.get('title', '')}**"
                        )
                        if art.get("key_point"):
                            lines.append(f"  {art['key_point']}")

                        # ================================================================
                        # 多重匹配策略：查找链接
                        # ================================================================
                        art_title = art.get('title', '')
                        source_name = art.get('source', '')
                        link = art.get('link', '')

                        # 如果 art 中有 link，直接使用
                        if link and link.startswith('http'):
                            pass  # 已有链接，跳过匹配
                        else:
                            link = None  # 重置，开始匹配

                            # 策略1：精确匹配
                            if art_title in self.title_link_map:
                                link = self.title_link_map[art_title]

                            # 策略2：去掉常见前缀后再匹配
                            if not link:
                                clean_title = art_title
                                # 去掉常见的开头词
                                prefixes = ["证监会同意", "央行", "国务院", "财政部", "工信部", "国家"]
                                for prefix in prefixes:
                                    if art_title.startswith(prefix):
                                        clean_title = art_title[len(prefix):]
                                        break
                                if clean_title in self.title_link_map:
                                    link = self.title_link_map[clean_title]

                            # 策略3：来源名称匹配（如 "36氪" → 找到包含该来源的新闻）
                            if not link and source_name:
                                for title, url in self.title_link_map.items():
                                    if source_name in title:
                                        link = url
                                        break

                            # 策略4：子串匹配（AI标题在原始标题中，或反之）
                            if not link and len(art_title) > 3:
                                for title, url in self.title_link_map.items():
                                    # AI标题是原始标题的子串
                                    if art_title in title:
                                        link = url
                                        break
                                    # 原始标题是AI标题的子串
                                    if len(title) > 5 and title in art_title:
                                        link = url
                                        break

                            # 策略5：关键词匹配（提取核心词汇）
                            if not link:
                                # 提取AI标题中的关键词（去掉常见停用词）
                                stopwords = ["的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "个", "上", "也", "很", "至", "月", "日", "年"]
                                keywords = [w for w in art_title if w not in stopwords]
                                if len(keywords) >= 3:
                                    for title, url in self.title_link_map.items():
                                        # 检查关键词是否都在原始标题中
                                        matched = all(kw in title for kw in keywords)
                                        if matched:
                                            link = url
                                            break

                        # ================================================================
                        # 生成显示
                        # ================================================================
                        if link and link.startswith('http'):
                            # 如果 source_name 是 Markdown 格式，提取纯名称
                            if source_name.startswith('[') and '](' in source_name:
                                match = re.search(r'\[([^\]]+)\]\([^)]+\)', source_name)
                                if match:
                                    source_name = match.group(1)
                            lines.append(f"  *来源: [{source_name}]({link})*")
                        elif source_name and not source_name.startswith('['):
                            lines.append(f"  *来源: {source_name}*")
                        # ================================================================

                    lines.append("")

                lines.append("")

        # 重点事件
        key_events = summary.get("key_events", [])
        if key_events:
            lines.append("## ⚡ 重点关注事件")
            lines.append("")
            for event in key_events:
                lines.append(f"- {event}")
            lines.append("")

        # 前瞻
        looking_ahead = summary.get("looking_ahead", "")
        if looking_ahead:
            lines.append("## 🔮 未来关注")
            lines.append("")
            lines.append(looking_ahead)
            lines.append("")

        # 底部
        lines.extend([
            "---",
            "",
            f"*📅 生成时间: {date_str} {time_str} (北京时间)*",
            "*🤖 AI 生成，仅供参考，不构成投资建议*",
            "*数据来源: NewsAPI*",
        ])

        return "\n".join(lines)

    def run(
        self,
        topics: Optional[List[str]] = None,
        custom_instruction: Optional[str] = None,
        send_notification: bool = True,
    ) -> Optional[str]:
        """
        运行完整的新闻摘要流程

        流程：
        1. 拉取新闻
        2. AI 摘要
        3. 格式化报告
        4. 保存到本地
        5. 推送通知

        Args:
            topics: 自定义话题列表（可选）
            custom_instruction: 额外 AI 指令（可选）
            send_notification: 是否发送推送

        Returns:
            Markdown 格式的摘要报告，失败返回 None
        """
        start_time = time.time()

        # 确定摘要类型（早报/晚报）
        tz_cn = timezone(timedelta(hours=8))
        now = datetime.now(tz_cn)
        digest_type = "早报" if now.hour < 12 else "晚报"

        logger.info(f"===== 开始生成金融新闻{digest_type} =====")
        logger.info(f"时间: {now.strftime('%Y-%m-%d %H:%M')} (北京时间)")

        try:
            # Step 1: 拉取新闻
            logger.info("Step 1/4: 拉取金融新闻...")
            # 在拉取前清空映射表，确保本次任务使用干净的数据
            self.title_link_map = {}
            topic_news = self.fetch_news(topics)

            if not topic_news:
                logger.warning("未拉取到任何新闻，流程终止")
                if send_notification and self.notifier.is_available():
                    self.notifier.send(f"📰 金融新闻{digest_type}生成失败：未拉取到新闻数据，请检查搜索引擎配置。")
                return None

            # Step 2: AI 摘要
            logger.info("Step 2/4: AI 生成摘要...")
            summary = self.summarize_with_ai(topic_news, custom_instruction)

            # Step 3: 格式化
            logger.info("Step 3/4: 格式化报告...")
            report = self.format_digest(summary, digest_type)

            # Step 4: 保存并推送
            logger.info("Step 4/4: 保存并推送...")

            # 保存到本地
            date_str = now.strftime('%Y%m%d')
            filename = f"news_digest_{date_str}_{digest_type}.md"
            filepath = self.notifier.save_report_to_file(report, filename)
            logger.info(f"新闻摘要已保存: {filepath}")

            # 推送通知
            if send_notification:
                if self.notifier.is_available():
                    success = self.notifier.send(report)
                    if success:
                        logger.info(f"新闻{digest_type}推送成功")
                    else:
                        logger.warning(f"新闻{digest_type}推送失败")
                else:
                    logger.info("通知渠道未配置，跳过推送")

            elapsed = time.time() - start_time
            logger.info(f"===== 新闻{digest_type}生成完成，耗时 {elapsed:.2f} 秒 =====")
            logger.info(f"报告长度: {len(report)} 字符")

            return report

        except Exception as e:
            logger.exception(f"新闻摘要流程失败: {e}")
            if send_notification and self.notifier.is_available():
                self.notifier.send(f"⚠️ 金融新闻{digest_type}生成异常: {str(e)[:200]}")
            return None


# === 便捷函数 ===
def get_news_pipeline() -> NewsDigestPipeline:
    """获取新闻摘要管道实例"""
    return NewsDigestPipeline()


if __name__ == "__main__":
    # 测试新闻摘要管道
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
    )

    pipeline = NewsDigestPipeline()
    if pipeline.search_service.is_available and pipeline.analyzer.is_available():
        print("=== 测试金融新闻摘要 ===")
        report = pipeline.run()
        if report:
            print("\n" + "=" * 40)
            print(report[:2000])
    else:
        print("请先配置 GEMINI_API_KEY 和至少一个搜索引擎 API Key")

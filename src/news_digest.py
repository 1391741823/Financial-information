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
    1. fetch_news()      — 按话题搜索金融新闻（RSS + Tavily 补充）
    2. summarize_with_ai() — AI 生成结构化摘要
    3. format_digest()   — 格式化为 Markdown 报告
    4. run()             — 协调完整流程
    """

    # 每个话题的搜索关键词（用于 Tavily 主动搜索）
    TOPIC_SEARCH_QUERIES = {
        "宏观经济": "中国 宏观经济 最新 GDP CPI PMI 央行 货币政策 2026年7月",
        "A股市场": "A股 股市 上证指数 深证成指 成交额 板块 2026年7月",
        "行业动态": "行业 动态 新能源 光伏 芯片 半导体 AI 人工智能 消费 医药 2026年7月",
        "政策法规": "中国 金融 政策 法规 证监会 央行 国务院 发改委 财政部 2026年7月",
        "国际市场": "美股 港股 纳斯达克 道指 标普 恒生 美联储 大宗商品 2026年7月",
        "公司新闻": "公司 财报 业绩 营收 净利润 增持 减持 并购 2026年7月",
    }

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
        获取金融新闻（RSS + Tavily 补充搜索）
        """
        if topics is None:
            topics = self.config.news_topics

        max_articles = self.config.news_max_articles
        topic_news: Dict[str, str] = {}

        logger.info(f"开始从 RSS + Tavily 拉取金融新闻，共 {len(topics)} 个话题...")

        # 每次拉取新闻前清空映射表，避免上一次的数据残留
        self.title_link_map = {}

        try:
            # Step 1: 从 RSS 获取新闻
            all_news = fetch_news_from_rss(limit_per_source=max_articles)

            if not all_news:
                logger.warning("RSS 未获取到任何新闻，将直接使用 Tavily 搜索")
                for topic in topics:
                    search_result = self._search_topic_with_tavily(topic, max_articles)
                    if search_result:
                        topic_news[topic] = search_result
                        logger.info(f"[Tavily] {topic}: 获取到新闻")
                    else:
                        logger.warning(f"[Tavily] {topic}: 搜索未返回结果")
                return topic_news

            logger.info(f"RSS 共获取 {len(all_news)} 条新闻，开始按话题过滤...")

            # Step 2: 按话题关键词过滤 RSS 新闻
            matched_topics = set()
            for topic in topics:
                filtered = []
                keywords = self._get_topic_keywords(topic)

                for news in all_news:
                    title = news.get("title", "")
                    if any(kw in title for kw in keywords):
                        filtered.append(news)
                        # 保存标题→链接映射（升级为字典格式）
                        link = news.get('link', '')
                        if title and link:
                            source = news.get('source', '')
                            self.title_link_map[title] = {'url': link, 'source': source}

                if filtered:
                    lines = [f"## {topic} (RSS)"]
                    for i, news in enumerate(filtered[:max_articles], 1):
                        lines.append(f"\n{i}. **{news.get('title', '')}**")
                        if news.get('summary'):
                            lines.append(f"   摘要: {news['summary'][:200]}")
                        if news.get('source'):
                            lines.append(f"   来源: {news['source']}")
                        if news.get('published'):
                            lines.append(f"   时间: {news['published']}")
                    topic_news[topic] = "\n".join(lines)
                    matched_topics.add(topic)
                    logger.info(f"{topic}: RSS 匹配到 {len(filtered)} 条新闻")
                else:
                    logger.warning(f"{topic}: RSS 未匹配到相关新闻")

            # Step 3: 对 RSS 匹配不到的话题，使用 Tavily 主动搜索
            missing_topics = [t for t in topics if t not in matched_topics]
            if missing_topics and self.search_service.is_available:
                logger.info(f"使用 Tavily 补充搜索缺失话题: {', '.join(missing_topics)}")
                for topic in missing_topics:
                    search_result = self._search_topic_with_tavily(topic, max_articles)
                    if search_result:
                        topic_news[topic] = search_result
                        logger.info(f"[Tavily] {topic}: 补充搜索成功")
                    else:
                        logger.warning(f"[Tavily] {topic}: 搜索未返回结果")

            # Step 4: 如果所有话题都没匹配到，把全部新闻放在"综合"话题下
            if not topic_news and all_news:
                lines = ["## 综合财经要闻 (RSS)"]
                for i, news in enumerate(all_news[:max_articles * len(topics)], 1):
                    title = news.get('title', '')
                    lines.append(f"\n{i}. **{title}**")
                    if news.get('summary'):
                        lines.append(f"   摘要: {news['summary'][:200]}")
                    if news.get('source'):
                        lines.append(f"   来源: {news['source']}")
                    if news.get('published'):
                        lines.append(f"   时间: {news['published']}")
                    link = news.get('link', '')
                    if title and link:
                        source = news.get('source', '')
                        self.title_link_map[title] = {'url': link, 'source': source}
                topic_news["综合"] = "\n".join(lines)
                logger.warning("没有按话题匹配到新闻，已将全部新闻放入'综合'话题")

        except Exception as e:
            logger.error(f"新闻拉取失败: {e}")

        total_topics = len(topic_news)
        logger.info(f"新闻拉取完成: {total_topics}/{len(topics)} 个话题成功获取新闻")
        return topic_news
       
    def _search_topic_with_tavily(self, topic: str, max_articles: int) -> str:
        """
        使用 Tavily 搜索单个话题的新闻

        Args:
            topic: 话题名称
            max_articles: 最大文章数

        Returns:
            格式化的新闻文本，失败返回空字符串
        """
        # 获取该话题的搜索关键词
        query = self.TOPIC_SEARCH_QUERIES.get(topic, f"{topic} 金融 新闻 2026年7月")

        logger.info(f"[Tavily] 搜索 '{topic}': {query}")

        try:
            # 遍历所有可用的搜索引擎（优先 Tavily）
            for provider in self.search_service._providers:
                if not provider.is_available:
                    continue

                response = provider.search(query, max_results=max_articles)

                if response.success and response.results:
                    # 格式化为文本
                    lines = [f"## {topic} ({provider.name} 搜索)"]
                    for i, result in enumerate(response.results[:max_articles], 1):
                        title = result.title or "无标题"
                        snippet = result.snippet or ""
                        # 截取摘要前300字符
                        if len(snippet) > 300:
                            snippet = snippet[:300] + "..."
                        date_str = f" [{result.published_date}]" if result.published_date else ""

                        lines.append(f"\n{i}. **{title}**{date_str}")
                        lines.append(f"   来源: {result.source}")
                        lines.append(f"   摘要: {snippet}")

                        # ================================================================
                        # 保存标题→链接映射（用于生成可点击链接）
                        # ================================================================
                        if title and result.url:
                            source = result.source or ''
                            entry = {'url': result.url, 'source': source}
                            if title not in self.title_link_map:
                                self.title_link_map[title] = entry
                            clean_title = re.sub(r'^\[.*?\]\s*', '', title)
                            if clean_title != title and clean_title not in self.title_link_map:
                                self.title_link_map[clean_title] = entry    

                    logger.info(f"[Tavily] {topic}: 获取 {len(response.results)} 条结果")
                    return "\n".join(lines)
                else:
                    logger.warning(f"[Tavily] {topic}: 搜索失败 - {response.error_message}")

            # 所有 provider 都失败
            logger.warning(f"[Tavily] {topic}: 所有搜索引擎均不可用或搜索失败")
            return ""

        except Exception as e:
            logger.error(f"[Tavily] {topic} 搜索异常: {e}")
            return ""

    def _get_topic_keywords(self, topic: str) -> List[str]:
        """
        为每个话题生成关键词列表（用于匹配 RSS 新闻标题）
        """
        keyword_map = {
            "宏观经济": ["宏观", "经济", "GDP", "CPI", "央行", "降息", "降准", "通货膨胀", "就业", "PMI"],
            "A股市场": ["A股", "上证", "深证", "创业板", "科创板", "北交所", "两市", "成交额", "涨停", "跌停"],
            "行业动态": ["行业", "产业", "新能源", "光伏", "芯片", "半导体", "人工智能", "AI", "消费", "医药"],
            "政策法规": ["政策", "监管", "证监会", "银保监会", "央行", "国务院", "发改委", "财政部", "国资委", "反垄断", "法规"],
            "国际市场": ["美股", "港股", "纳斯达克", "道指", "标普", "恒生", "美联储", "欧股", "日经", "国际"],
            "公司新闻": ["财报", "业绩", "营收", "净利润", "增持", "减持", "回购", "分红", "融资", "并购", "上市"],
        }
        return keyword_map.get(topic, [topic])

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
                        matched_source = ''  # 匹配到的原始来源名
    
                        # 如果 art 中有 link，直接使用
                        if link and link.startswith('http'):
                            pass
                        else:
                            link = None
                            matched_entry = None
    
                            # 策略1：精确匹配
                            if art_title in self.title_link_map:
                                matched_entry = self.title_link_map[art_title]
    
                            # 策略2：去掉常见前缀后再匹配
                            if not matched_entry:
                                clean_title = art_title
                                prefixes = ["证监会同意", "央行", "国务院", "财政部", "工信部", "国家"]
                                for prefix in prefixes:
                                    if art_title.startswith(prefix):
                                        clean_title = art_title[len(prefix):]
                                        break
                                if clean_title in self.title_link_map:
                                    matched_entry = self.title_link_map[clean_title]
    
                            # 策略3：来源名称匹配
                            if not matched_entry and source_name:
                                for title, entry in self.title_link_map.items():
                                    if isinstance(entry, dict):
                                        if source_name in entry.get('source', ''):
                                            matched_entry = entry
                                            break
                                    else:
                                        if source_name in title:
                                            matched_entry = {'url': entry, 'source': source_name}
                                            break
    
                            # 策略4：子串匹配
                            if not matched_entry and len(art_title) > 3:
                                for title, entry in self.title_link_map.items():
                                    if art_title in title:
                                        matched_entry = entry if isinstance(entry, dict) else {'url': entry, 'source': source_name}
                                        break
                                    if len(title) > 5 and title in art_title:
                                        matched_entry = entry if isinstance(entry, dict) else {'url': entry, 'source': source_name}
                                        break
    
                            # 策略5：关键词匹配
                            if not matched_entry:
                                stopwords = ["的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "个", "上", "也", "很", "至", "月", "日", "年"]
                                keywords = [w for w in art_title if w not in stopwords]
                                if len(keywords) >= 3:
                                    for title, entry in self.title_link_map.items():
                                        if all(kw in title for kw in keywords):
                                            matched_entry = entry if isinstance(entry, dict) else {'url': entry, 'source': source_name}
                                            break
    
                            # 提取匹配结果
                            if matched_entry:
                                if isinstance(matched_entry, dict):
                                    link = matched_entry.get('url', '')
                                    matched_source = matched_entry.get('source', '')
                                else:
                                    link = matched_entry
                                    matched_source = source_name
    
                        # ================================================================
                        # 生成显示
                        # ================================================================
                        display_source = matched_source if matched_source else source_name
    
                        if display_source and display_source.startswith('[') and '](' in display_source:
                            match = re.search(r'\[([^\]]+)\]\([^)]+\)', display_source)
                            if match:
                                display_source = match.group(1)
    
                        if link and link.startswith('http'):
                            lines.append(f"  *来源: [{display_source}]({link})*")
                        elif display_source and not display_source.startswith('['):
                            lines.append(f"  *来源: {display_source}*")
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
            "*数据来源: NewsAPI + Tavily*",
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

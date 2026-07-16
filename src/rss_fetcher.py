# src/rss_fetcher.py
import feedparser
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

# 配置多个备用 RSS 源（新浪 + 和讯 + 东方财富）
RSS_FEEDS = [
    # 新浪财经
    "http://rss.sina.com.cn/roll/finance/hot_roll.xml",
    "http://rss.sina.com.cn/news/allnews/finance.xml",
    "http://rss.sina.com.cn/finance/jsy.xml",
    "http://rss.sina.com.cn/roll/stock/hot_roll.xml",
    "http://rss.sina.com.cn/finance/fund.xml",
    "http://rss.sina.com.cn/finance/usstock.xml",
    # 和讯财经（备用）
    "http://news.hexun.com/news_rss.xml",
    # 东方财富（备用）
    "http://news.eastmoney.com/rss/",
]

def clean_html(raw: str) -> str:
    """移除 HTML 标签，保留纯文本"""
    if not raw:
        return ""
    clean = re.sub(r'<[^>]+>', '', raw)
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return clean.strip()

def fetch_news_from_rss(limit_per_source: int = 5) -> List[Dict[str, str]]:
    """
    从多个 RSS 源获取新闻，每个源最多取 limit_per_source 条。
    返回新闻列表，每条包含 title, summary, link, published, source。
    """
    all_news = []
    seen_titles = set()

    # 设置 User-Agent，模拟浏览器
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for feed_url in RSS_FEEDS:
        try:
            logger.info(f"正在解析 RSS: {feed_url}")
            # 传入请求头
            feed = feedparser.parse(feed_url, request_headers=headers)
            
            # 检查解析状态
            if feed.bozo:
                logger.warning(f"RSS 解析警告: {feed.bozo_exception}")
            
            entries = feed.entries
            logger.info(f"  条目数: {len(entries)}")
            
            if not entries:
                continue

            # 提取条目
            for entry in entries[:limit_per_source]:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                # 摘要（可能包含 HTML）
                summary_raw = entry.get("summary", "") or entry.get("description", "") or ""
                summary = clean_html(summary_raw)
                if len(summary) > 300:
                    summary = summary[:300] + "..."

                news_item = {
                    "title": title,
                    "summary": summary,
                    "link": entry.get("link", ""),
                    "published": entry.get("published", "") or entry.get("pubDate", ""),
                    "source": feed_url,
                }
                all_news.append(news_item)

            logger.info(f"  从 {feed_url} 获取 {len(entries[:limit_per_source])} 条新闻")

        except Exception as e:
            logger.error(f"解析 RSS 源 {feed_url} 失败: {e}")
            continue

    logger.info(f"总共从 RSS 获取 {len(all_news)} 条新闻（去重后）")
    return all_news

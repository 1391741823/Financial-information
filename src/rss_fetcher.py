# src/rss_fetcher.py
import feedparser
import logging
import re
from typing import List, Dict

# 配置新浪财经的 RSS 源（你可以根据需要增删）
RSS_FEEDS = [
    "http://rss.sina.com.cn/roll/finance/hot_roll.xml",      # 财经要闻汇总
    "http://rss.sina.com.cn/news/allnews/finance.xml",       # 焦点新闻
    "http://rss.sina.com.cn/finance/jsy.xml",                # 股市及时雨
    "http://rss.sina.com.cn/roll/stock/hot_roll.xml",        # 股票要闻
    "http://rss.sina.com.cn/finance/fund.xml",               # 基金要闻
    "http://rss.sina.com.cn/finance/usstock.xml",            # 美股快报
]

def clean_html(raw: str) -> str:
    """移除 HTML 标签，保留纯文本"""
    if not raw:
        return ""
    # 移除 <...> 标签
    clean = re.sub(r'<[^>]+>', '', raw)
    # 替换常见 HTML 实体
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return clean.strip()

def fetch_news_from_rss(limit_per_source: int = 5) -> List[Dict[str, str]]:
    """
    从所有 RSS 源获取新闻，每个源最多取 limit_per_source 条。
    返回新闻列表，每条包含 title, summary, link, published。
    """
    all_news = []
    seen_titles = set()  # 用于去重

    for feed_url in RSS_FEEDS:
        try:
            logging.info(f"正在解析 RSS: {feed_url}")
            feed = feedparser.parse(feed_url)
            if feed.bozo:  # 检查是否有解析错误
                logging.warning(f"RSS 源可能有问题: {feed.bozo_exception}")
            
            for entry in feed.entries[:limit_per_source]:
                title = entry.get("title", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                
                # 提取摘要（可能是 HTML）
                summary_raw = entry.get("summary", "") or entry.get("description", "") or ""
                summary = clean_html(summary_raw)
                # 如果摘要过长，截断到 300 字符，避免 AI 输入太长
                if len(summary) > 300:
                    summary = summary[:300] + "..."
                
                news_item = {
                    "title": title,
                    "summary": summary,
                    "link": entry.get("link", ""),
                    "published": entry.get("published", "") or entry.get("pubDate", ""),
                    "source": feed_url
                }
                all_news.append(news_item)
                
        except Exception as e:
            logging.error(f"解析 RSS 源 {feed_url} 失败: {e}")
            continue

    logging.info(f"总共从 RSS 获取 {len(all_news)} 条新闻")
    return all_news

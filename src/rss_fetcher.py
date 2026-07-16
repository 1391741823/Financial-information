# src/rss_fetcher.py
"""
金融新闻获取模块 - 使用 NewsAPI
需配置环境变量 NEWSAPI_KEY
"""

import logging
import os
from typing import List, Dict
import requests

logger = logging.getLogger(__name__)

# 从环境变量读取 API Key
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
# 可选：自定义搜索关键词（可通过环境变量覆盖）
SEARCH_QUERY = os.getenv("NEWSAPI_QUERY", "中国 财经 金融 股市 央行")


def fetch_from_newsapi(limit: int = 20) -> List[Dict[str, str]]:
    if not NEWSAPI_KEY:
        logger.error("NEWSAPI_KEY 未配置")
        return []

    try:
        import requests
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": SEARCH_QUERY,
            "language": "zh",
            "sortBy": "publishedAt",
            "pageSize": min(limit, 100),
            "apiKey": NEWSAPI_KEY,
        }
        logger.info(f"正在请求 NewsAPI，关键词: {SEARCH_QUERY}")
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            logger.error(f"NewsAPI 返回错误: {data.get('message', '未知错误')}")
            return []

        articles = data.get("articles", [])
        if not articles:
            logger.warning("NewsAPI 返回的新闻列表为空")
            return []

        news_list = []
        for article in articles:
            title = article.get("title")
            if not title:
                continue
            # 提取来源和链接
            source_name = article.get("source", {}).get("name", "NewsAPI")
            source_url = article.get("url", "")
            # 如果链接存在，把来源和链接拼接成 Markdown 格式
            if source_url:
                source_display = f"[{source_name}]({source_url})"
            else:
                source_display = source_name
            
            news_list.append({
                "title": title,
                "summary": article.get("description", "")[:300] if article.get("description") else "",
                "published": article.get("publishedAt", ""),
                "source": source_display,  # 直接存为带链接的格式
                "link": source_url,
            })

        logger.info(f"成功从 NewsAPI 获取 {len(news_list)} 条新闻")
        return news_list

    except Exception as e:
        logger.error(f"请求 NewsAPI 失败: {e}")
        return []

def fetch_news_from_rss(limit_per_source: int = 5) -> List[Dict[str, str]]:
    """
    主入口函数（保持与原有管道兼容）

    Args:
        limit_per_source: 每个"源"的获取条数（实际总条数会乘以使用的源数量，此处只有一个源）

    Returns:
        新闻列表
    """
    # 总条数设为 limit_per_source * 3 以获得足够数据
    total_limit = limit_per_source * 3
    news = fetch_news_from_newsapi(limit=total_limit)
    if not news:
        logger.warning("未获取到任何新闻，请检查 NEWSAPI_KEY 或网络连接")
    return news

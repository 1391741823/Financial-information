# src/rss_fetcher.py
import logging
import os
from typing import List, Dict
import requests

logger = logging.getLogger(__name__)

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

def fetch_news_from_newsapi(limit: int = 20) -> List[Dict[str, str]]:
    """
    使用 NewsAPI 获取国内财经新闻
    """
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY 未配置")
        return []

    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "中国 财经 金融",  # 搜索关键词
            "language": "zh",
            "sortBy": "publishedAt",
            "pageSize": limit,
            "apiKey": NEWSAPI_KEY
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("status") != "ok":
            logger.error(f"NewsAPI 返回错误: {data.get('message')}")
            return []
        
        articles = data.get("articles", [])
        news_list = []
        for article in articles:
            news_list.append({
                "title": article.get("title", ""),
                "summary": article.get("description", "")[:300] if article.get("description") else "",
                "published": article.get("publishedAt", ""),
                "source": article.get("source", {}).get("name", "NewsAPI"),
                "link": article.get("url", "")
            })
        
        logger.info(f"从 NewsAPI 获取 {len(news_list)} 条新闻")
        return news_list
        
    except Exception as e:
        logger.error(f"NewsAPI 获取新闻失败: {e}")
        return []

def fetch_news_from_rss(limit_per_source: int = 5) -> List[Dict[str, str]]:
    """
    主入口：使用 NewsAPI
    """
    news = fetch_news_from_newsapi(limit=limit_per_source * 3)
    if news:
        return news
    
    logger.warning("所有数据源均未获取到新闻")
    return []

# src/rss_fetcher.py
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def fetch_news_from_cls(limit: int = 20) -> List[Dict[str, str]]:
    """
    使用 a-stock-data 获取财联社快讯
    """
    try:
        from a_stock_data import cls_news
        
        # 获取财联社快讯
        result = cls_news(limit=limit)
        
        if not result:
            logger.warning("财联社快讯返回空数据")
            return []
        
        news_list = []
        for item in result:
            news_list.append({
                "title": item.get("title", "") or item.get("content", "")[:50],
                "summary": item.get("content", "")[:300] if item.get("content") else "",
                "published": item.get("time", ""),
                "source": "财联社",
                "link": item.get("url", "")
            })
        
        logger.info(f"从财联社获取 {len(news_list)} 条新闻")
        return news_list
        
    except ImportError:
        logger.error("请安装 a-stock-data: pip install a-stock-data")
        return []
    except Exception as e:
        logger.error(f"财联社快讯获取失败: {e}")
        return []

def fetch_news_from_rss(limit_per_source: int = 5) -> List[Dict[str, str]]:
    """
    主入口：优先使用财联社快讯
    """
    news = fetch_news_from_cls(limit=limit_per_source * 3)
    if news:
        return news
    
    logger.warning("所有数据源均未获取到新闻")
    return []

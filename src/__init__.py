def __init__(self, config: Optional[Config] = None):
    self.config = config or get_config()
    self.search_service = SearchService(...)
    self.analyzer = GeminiAnalyzer()
    self.notifier = NotificationService()

    # ===== 新增 =====
    self.title_link_map = {}
    # ===== 结束 =====

    logger.info(...)
    # ... 后续日志

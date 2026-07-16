# 📰 金融新闻摘要系统

[![GitHub stars](https://img.shields.io/github/stars/1391741823/Financial-information?style=social)](https://github.com/1391741823/Financial-information/stargazers)
[![CI](https://github.com/1391741823/Financial-information/actions/workflows/news.yml/badge.svg)](https://github.com/1391741823/Financial-information/actions/workflows/news.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)

> 🤖 基于 NewsAPI + AI 大模型的国内金融新闻智能摘要系统，**每小时自动抓取**最新财经资讯，**AI 生成结构化摘要**，并通过飞书/企业微信/Telegram 等多渠道推送，让您**一分钟速览市场动态**。

简体中文

## ✨ 功能特性

### 🎯 核心功能
- **智能新闻抓取** – 通过 NewsAPI 实时获取国内金融新闻（支持自定义搜索关键词）
- **AI 结构化摘要** – 调用 OpenAI 兼容 API（支持 DeepSeek、通义千问等）或 Google Gemini 生成分类摘要
- **自动话题分类** – 将新闻自动归入「宏观经济」「A股市场」「行业动态」「国际市场」「政策法规」等类别
- **重点事件提炼** – AI 自动提取当日最重要的 5-8 条关键事件
- **市场情绪判断** – 基于新闻内容给出「乐观/中性/谨慎/悲观」综合判断
- **可点击链接** – 每条新闻来源均带原文链接，一键跳转详情
- **多渠道推送** – 支持飞书、企业微信、Telegram、邮件、PushPlus、钉钉等
- **零成本部署** – GitHub Actions 免费运行，无需服务器

### 📊 数据来源
- **主要数据源**: NewsAPI（国际通用，GitHub Actions 环境下稳定可用）
- **备用数据源**: 支持 Tushare、财联社快讯（`a-stock-data`）等扩展
- **AI 模型**: 
  - 主力：OpenAI 兼容 API（DeepSeek、通义千问、Moonshot 等，成本低廉）
  - 备选：Google Gemini（免费额度）

### 🛡️ 输出格式
- **📰 金融新闻早/晚报** – 每日自动生成
- **分类汇总** – 每个话题下包含「要点」和具体新闻列表
- **利好/利空标注** – 每条新闻带 📈/📉/➡️ 影响标记
- **来源超链接** – 点击来源名称直接跳转原文
- **关注前瞻** – AI 提示未来可能影响市场的关键事件

## 🚀 快速开始

### 方式一：GitHub Actions（推荐，零成本）

**无需服务器，每小时自动运行！**

#### 1. Fork 本仓库（顺便点个 ⭐ 呀）

点击右上角 `Fork` 按钮，将项目复制到你的 GitHub 账号。

#### 2. 配置 Secrets

进入你 Fork 的仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

**必填配置**

| Secret 名称 | 说明 | 获取方式 |
|------------|------|---------|
| `NEWSAPI_KEY` | NewsAPI 密钥 | [newsapi.org](https://newsapi.org/register) 免费注册获取（每日 100 次请求） |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key | 推荐 [DeepSeek](https://platform.deepseek.com/) 或通义千问等，获取 API Key |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook | 飞书群 → 设置 → 群机器人 → 添加自定义机器人 |

**可选配置（增强功能）**

| Secret 名称 | 说明 | 默认值 |
|------------|------|--------|
| `NEWSAPI_QUERY` | 自定义搜索关键词 | `中国 财经 金融 股市 央行` |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 | 根据服务商填写（如 DeepSeek 为 `https://api.deepseek.com/v1`） |
| `OPENAI_MODEL` | 使用的模型名称 | `deepseek-chat` |
| `TUSHARE_TOKEN` | Tushare Token（备选数据源） | 可选 |
| 其他推送渠道 | 企业微信、Telegram、邮件、PushPlus 等 | 可选，参考下方说明 |

**推送渠道配置（可选，可同时配置多个）**

| Secret 名称 | 说明 |
|------------|------|
| `WECHAT_WEBHOOK_URL` | 企业微信 Webhook |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（@BotFather 获取） |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID |
| `PUSHPLUS_TOKEN` | PushPlus Token（国内推送服务） |
| `EMAIL_SENDER` | 发件人邮箱（如 QQ 邮箱） |
| `EMAIL_PASSWORD` | 邮箱授权码 |
| `EMAIL_RECEIVERS` | 收件人邮箱（多个用逗号分隔） |

> 💡 **至少配置一个通知渠道**，推荐飞书（配置简单，消息体验好）。

#### 3. 启用 Actions

进入 `Actions` 标签 → 点击 `I understand my workflows, go ahead and enable them`

#### 4. 手动测试

`Actions` → `每小时金融新闻摘要` → `Run workflow` → 选择分支 `main` → `Run workflow`

#### 5. 完成！

默认 **每个工作日 7:00-23:00（北京时间）每小时运行一次**，自动推送新闻摘要到你的飞书群。

### 方式二：本地运行 / Docker 部署

#### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/1391741823/Financial-information.git
cd Financial-information

# 2. 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
# 创建 .env 文件，填写以下内容：
# NEWSAPI_KEY=你的Key
# OPENAI_API_KEY=你的Key
# FEISHU_WEBHOOK_URL=你的飞书Webhook
# 其他可选配置...

# 5. 运行
python news_main.py

## 📱 飞书消息示例

```
📰 金融新闻晚报 | 2026-07-16 20:25

🎯 今日要闻: SK海力士美股上市大涨，长鑫科技IPO在即
📊 市场情绪: 🟡 中性

────────

📊 A股市场 🔴

**要点**: 证监会同意宇树科技科创板IPO注册，A股新版交易规则今日施行。

• 📈 **证监会同意宇树科技科创板IPO注册**
  宇树科技科创板IPO获证监会注册同意，上市进程加速。
  *来源: [36氪](https://36kr.com/p/xxx)*

• 📈 **奥飞娱乐上半年净利润同比预增305.30%—413.38%**
  奥飞娱乐预计上半年净利润1.5亿至1.9亿元，同比大幅增长。
  *来源: [36氪](https://36kr.com/p/yyy)*

🏭 行业动态 🔴

**要点**: 共享单车集体调价，起步价上调至1.88-1.99元/60分钟。

• ➡️ **共享单车集体调价：起步价上调至1.88-1.99元/60分钟**
  美团、青桔、哈啰单车在北京等城市上调起步价，行业迎来近年较大范围调价。
  *来源: [金融时报](https://ft.com/...)*

⚡ 重点关注事件

• SK海力士美股上市首日大涨近13%，创外资企业史上最大规模ADR。
• 长鑫科技IPO进入倒计时，承销团阵容公布。
• 共享单车行业集体调价，起步价上调至1.88-1.99元/60分钟。

🔮 未来关注

关注长鑫科技IPO发行进展及定价情况；SK海力士美股后续表现；三星与英伟达会晤结果。

────────
📅 生成时间: 2026-07-16 20:25 (北京时间)
🤖 AI 生成，仅供参考，不构成投资建议
数据来源: NewsAPI
```

## 📁 项目结构
Financial-information/
├── news_main.py # 主程序入口
├── src/
│ ├── init.py
│ ├── config.py # 配置管理
│ ├── analyzer.py # AI 分析器（OpenAI/Gemini）
│ ├── news_digest.py # 新闻摘要管道（核心逻辑）
│ ├── rss_fetcher.py # 新闻获取模块（NewsAPI + 备用源）
│ ├── notification.py # 多渠道推送
│ └── search_service.py # 搜索服务（兼容旧逻辑）
├── logs/ # 日志目录
├── reports/ # 生成的报告文件
├── .github/workflows/
│ └── news.yml # GitHub Actions 定时任务配置
├── requirements.txt # Python 依赖
├── .env.example # 环境变量示例
└── README.md # 项目说明


## 🗺️ Roadmap

- [x] NewsAPI 新闻抓取
- [x] AI 结构化摘要生成
- [x] 飞书消息推送（带可点击链接）
- [x] GitHub Actions 每小时定时运行
- [x] 多话题自动分类
- [ ] 支持更多新闻源（财联社、华尔街见闻等）
- [ ] 历史新闻存储与趋势分析
- [ ] 用户自定义话题关键词
- [ ] WebUI 配置管理界面

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

如果你有好的数据源建议或功能想法，请随时提出。

## 📄 License

[MIT License](LICENSE) © 2026 1391741823

## ⚠️ 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。新闻摘要由 AI 自动生成，可能存在不准确或不完整之处，请以官方信息为准。作者不对使用本项目产生的任何损失负责。

---

**如果觉得有用，请给个 ⭐ Star 支持一下！**


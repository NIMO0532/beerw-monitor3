import requests
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime

# 从 GitHub Actions 环境变量读取 Webhook
WEBHOOK_URL = os.getenv("WECOM_WEBHOOK")
TARGET_URL = "https://www.beerw.com"
# 你要监控的关键词（可修改）
KEYWORDS = ["青岛啤酒", "华润啤酒", "青啤", "雀巢", "健康饮用水", "战略合作"]

# 记录已经推送过的新闻链接，避免重复提醒
pushed_links = set()

def send_to_wecom_markdown(content):
    """发送 Markdown 格式消息到企业微信（支持超链接）"""
    if not WEBHOOK_URL:
        print("未配置 Webhook，跳过发送")
        return
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    try:
        resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
        if resp.status_code == 200:
            print("Markdown 消息发送成功")
        else:
            print(f"发送失败：{resp.text}")
    except Exception as e:
        print(f"发送异常：{str(e)}")

def extract_news_list():
    """从 beerw.com 首页提取新闻列表（标题、链接、时间）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.beerw.com"
    }
    news_list = []
    try:
        resp = requests.get(TARGET_URL, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 适配 beerw.com 结构：抓取所有带 /news/ 的链接
        for a_tag in soup.find_all("a", href=re.compile(r"/news/\d+\.html")):
            title = a_tag.get_text(strip=True)
            link = a_tag.get("href")
            if not title or len(title) < 5 or not link:
                continue

            # 补全为完整链接
            if not link.startswith("http"):
                link = f"https://www.beerw.com{link}"

            # 尝试提取发布时间（从父级或相邻元素找）
            publish_time = ""
            parent = a_tag.parent
            if parent:
                # 找包含日期格式的文本，如 2026-02-26
                time_match = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                if time_match:
                    publish_time = time_match.group(1)

            news_list.append({
                "title": title,
                "link": link,
                "time": publish_time or "未知时间"
            })
        return news_list
    except Exception as e:
        print(f"抓取新闻列表异常：{str(e)}")
        return []

def check_news_keywords(news):
    """检查单篇新闻是否包含关键词"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(news["link"], headers=headers, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        content_text = soup.get_text()

        matched = [kw for kw in KEYWORDS if kw in news["title"] or kw in content_text]
        return matched
    except Exception as e:
        print(f"检查新闻 {news['link']} 异常：{str(e)}")
        return []

def run_monitor():
    global pushed_links
    print(f"[{datetime.now()}] 开始监控 beerw.com...")
    news_list = extract_news_list()
    if not news_list:
        print("未抓取到任何新闻")
        return

    for news in news_list:
        if news["link"] in pushed_links:
            continue

        matched_kws = check_news_keywords(news)
        if matched_kws:
            # 构造 Markdown 消息：带超链接标题 + 时间 + 关键词
            md_content = (
                f"🍺 **Beerw 监控提醒**\n\n"
                f"**[{news['title']}]({news['link']})**\n\n"
                f"发布时间：{news['time']}\n\n"
                f"命中关键词：{', '.join(matched_kws)}\n\n"
                f"@all"
            )
            print(f"发现新闻：{news['title']}，推送中...")
            send_to_wecom_markdown(md_content)
            pushed_links.add(news["link"])

    # 限制已推送记录数量，防止内存过大
    if len(pushed_links) > 500:
        pushed_links = set(list(pushed_links)[-200:])
    print("本轮监控结束")

if __name__ == "__main__":
    run_monitor()

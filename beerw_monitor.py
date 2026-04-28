import requests
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 配置区 ---
WEBHOOK_URL = os.getenv("WECOM_WEBHOOK")

# 同时监控两个栏目
TARGET_URLS = [
    "https://www.beerw.com/class.asp?id=11",   # 原行业资讯
    "https://www.beerw.com/class.asp?id=19"    # 新增：青岛啤酒专栏
]

KEYWORDS = ["青岛啤酒", "华润啤酒", "青啤", "百威啤酒", "大麦", "酒花", "酵母", "燕京啤酒", "啤酒"]

# 监控模式：daily 近24小时 | weekly 近7天
MONITOR_MODE = "daily"

# 去重文件（重启不重复推送）
PUSHED_FILE = "pushed_links.txt"
# --- 配置区结束 ---

# 加载已推送记录
pushed_links = set()
if os.path.exists(PUSHED_FILE):
    with open(PUSHED_FILE, "r", encoding="utf-8") as f:
        pushed_links = set(f.read().splitlines())

def save_pushed_links():
    with open(PUSHED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(pushed_links))

def send_to_wecom_markdown(content):
    if not WEBHOOK_URL:
        print("❌ 未配置 WECOM_WEBHOOK 环境变量")
        return
    data = {
        "msgtype": "markdown",
        "markdown": {"content": content}
    }
    try:
        resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print("✅ 消息推送成功")
        else:
            print(f"❌ 推送失败：{result.get('errmsg', '未知错误')}")
    except Exception as e:
        print(f"❌ 推送异常：{str(e)}")

def parse_news_time(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def is_valid_time_range(date_str):
    if not date_str:
        return True
    news_time = parse_news_time(date_str)
    if not news_time:
        return True
    now = datetime.now()
    if MONITOR_MODE == "daily":
        return now - news_time <= timedelta(days=1)
    elif MONITOR_MODE == "weekly":
        return now - news_time <= timedelta(days=7)
    return False

def extract_news_from_url(url):
    """从单个URL抓取新闻"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.beerw.com"
    }
    news_list = []
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.encoding = "gbk"
        soup = BeautifulSoup(resp.text, "html.parser")
        news_box = soup.find("div", class_="list")
        if not news_box:
            return []
        items = news_box.find_all("li")
        for li in items:
            a_tag = li.find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if not title or len(title) < 4 or not href:
                continue
            # 补全链接
            if href.startswith("/"):
                link = f"https://www.beerw.com{href}"
            else:
                link = f"https://www.beerw.com/{href}"
            # 提取日期
            time_match = re.search(r"(\d{4}-\d{2}-\d{2})", li.get_text())
            time_text = time_match.group(1) if time_match else ""
            news_list.append({
                "title": title,
                "link": link,
                "time": time_text
            })
        return news_list
    except Exception as e:
        print(f"❌ 抓取 {url} 异常：{str(e)}")
        return []

def extract_all_news():
    """抓取所有栏目新闻并合并去重"""
    all_news = []
    for url in TARGET_URLS:
        news = extract_news_from_url(url)
        all_news.extend(news)
    # 全局去重
    seen_links = set()
    unique_news = []
    for n in all_news:
        if n["link"] not in seen_links:
            seen_links.add(n["link"])
            unique_news.append(n)
    print(f"✅ 共抓取 {len(unique_news)} 条有效新闻（行业资讯+青岛啤酒专栏）")
    return unique_news

def check_news_keywords(news):
    return [kw for kw in KEYWORDS if kw in news["title"]]

def run_monitor():
    global pushed_links
    mode_text = "近24小时" if MONITOR_MODE == "daily" else "近7天"
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始监控 行业资讯+青岛啤酒专栏 | {mode_text}")

    news_list = extract_all_news()
    pending = []

    for news in news_list:
        if news["link"] in pushed_links:
            continue
        if not is_valid_time_range(news["time"]):
            continue
        match_kws = check_news_keywords(news)
        if match_kws:
            pending.append({
                "title": news["title"],
                "link": news["link"],
                "time": news["time"] or "未知",
                "kws": ",".join(match_kws)
            })
            pushed_links.add(news["link"])

    if pending:
        md = f"### 🍺 啤酒行业+青岛啤酒 新资讯\n"
        md += f"> 监控栏目：id=11(行业) + id=19(青啤)\n"
        md += f"> 筛选：{mode_text} | 关键词\n\n"
        for idx, item in enumerate(pending, 1):
            md += f"**{idx}. [{item['title']}]({item['link']})**\n"
            md += f"    - 发布时间：{item['time']}\n"
            md += f"    - 命中关键词：{item['kws']}\n\n"
        send_to_wecom_markdown(md)
    else:
        print(f"✅ 未发现符合条件的新消息")
    save_pushed_links()
    print("本轮监控结束")

if __name__ == "__main__":
    run_monitor()

import requests
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- 配置区 ---
# 从环境变量读取 Webhook（GitHub/服务器标准用法）
WEBHOOK_URL = os.getenv("WECOM_WEBHOOK")

# 目标行业资讯栏目（支持多个）
TARGET_URLS = [
    "https://www.beerw.com/class.asp?id=11",
    "https://www.beerw.com/class.asp?id=19"
]

# 监控关键词
KEYWORDS = ["青岛啤酒", "华润啤酒", "青啤", "百威啤酒", "大麦", "酒花", "酵母", "燕京啤酒", "啤酒"]

# 监控模式
# "daily": 近24小时内发布
# "weekly": 近7天内发布
MONITOR_MODE = "weekly"

# 已推送链接（去重）
pushed_links = set()
# --- 配置区结束 ---

def send_to_wecom_markdown(content):
    """发送 Markdown 消息到企业微信"""
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
        if result["errcode"] == 0:
            print("✅ 消息推送成功")
        else:
            print(f"❌ 推送失败：{result['errmsg']}")
    except Exception as e:
        print(f"❌ 推送异常：{str(e)}")

def parse_news_time(date_str):
    """统一解析各种格式的日期字符串为 datetime 对象"""
    if not date_str:
        return None

    # 尝试匹配包含时间的格式
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    # 尝试匹配只有日期的格式
    for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    return None

def is_valid_time_range(date_str):
    """根据 MONITOR_MODE 判断新闻发布时间是否在有效范围内"""
    news_time = parse_news_time(date_str)
    if not news_time:
        return False

    now = datetime.now()

    if MONITOR_MODE == "daily":
        time_diff = now - news_time
        return time_diff <= timedelta(days=1)

    elif MONITOR_MODE == "weekly":
        time_diff = now - news_time
        return time_diff <= timedelta(days=7)

    return False

def extract_industry_news():
    """抓取多个栏目行业资讯新闻"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.beerw.com",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    all_news = []

    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))

        # 抓取所有栏目
        for target_url in TARGET_URLS:
            print(f"\n🔗 正在抓取栏目：{target_url}")
            resp = session.get(target_url, headers=headers, timeout=20)
            resp.encoding = "gb2312"
            html_text = resp.text

            soup = BeautifulSoup(html_text, "html.parser")
            list_items = soup.find_all("li")
            print(f"🔍 本栏目找到 {len(list_items)} 个列表项")

            for li in list_items:
                a_tag = li.find("a")
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                link = a_tag.get("href", "")
                if not title or len(title) < 5 or not link:
                    continue

                # 补全链接
                if link.startswith("/"):
                    link = f"https://www.beerw.com{link}"
                elif not link.startswith("http"):
                    link = f"https://www.beerw.com/{link}"

                # 提取时间
                publish_time = ""
                li_text = li.get_text()
                time_match = re.search(r"(\d{4}[-/年]\d{2}[-/月]\d{2}日? \d{2}:\d{2}:\d{2}|\d{4}[-/年]\d{2}[-/月]\d{2}日?)", li_text)
                if time_match:
                    raw_time = time_match.group(1)
                    publish_time = raw_time.replace("年", "-").replace("月", "-").replace("日", "")

                all_news.append({"title": title, "link": link, "time": publish_time})

        # 全局去重
        unique_news = []
        seen_links = set()
        for news in all_news:
            if news['link'] not in seen_links:
                seen_links.add(news['link'])
                unique_news.append(news)

        print(f"\n✅ 所有栏目最终抓取到 {len(unique_news)} 条有效新闻")
        return unique_news
    except Exception as e:
        print(f"❌ 抓取失败：{str(e)}")
        return []

def check_news_keywords(news):
    """检查标题是否包含关键词"""
    return [kw for kw in KEYWORDS if kw in news["title"]]

def run_monitor():
    global pushed_links
    mode_text = "近24小时" if MONITOR_MODE == "daily" else "近7天"
    print(f"[{datetime.now()}] 开始监控 beerw 多栏目行业资讯（筛选条件：{mode_text}）...")

    news_list = extract_industry_news()
    pending_news = []

    for news in news_list:
        if news["link"] in pushed_links:
            continue

        if not news["time"] or not is_valid_time_range(news["time"]):
            continue

        matched_kws = check_news_keywords(news)
        if matched_kws:
            pending_news.append({
                "title": news['title'],
                "link": news['link'],
                "time": news["time"],
                "keywords": ', '.join(matched_kws)
            })
            pushed_links.add(news["link"])

    if pending_news:
        md_content = f"### 🍺 Beerw 多栏目资讯汇总\n"
        md_content += f"> **监控时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        md_content += f"> **筛选条件**：{mode_text}发布，包含关键词\n\n"

        for idx, item in enumerate(pending_news, 1):
            md_content += f"**{idx}. [{item['title']}]({item['link']})**\n"
            md_content += f"    - 发布时间：{item['time']}\n"
            md_content += f"    - 命中关键词：{item['keywords']}\n\n"

        print(f"📤 共整理到 {len(pending_news)} 条新闻，准备合并发送...")
        send_to_wecom_markdown(md_content)
    else:
        print(f"本轮监控未发现符合条件的 {mode_text} 内的新消息")

    print("本轮监控结束")

if __name__ == "__main__":
    run_monitor()

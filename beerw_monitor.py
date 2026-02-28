import requests
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime, date

# 从 GitHub 环境变量读取企业微信Webhook
WEBHOOK_URL = os.getenv("WECOM_WEBHOOK")
# 指定监控的行业资讯栏目（你提供的地址）
TARGET_URL = "https://www.beerw.com/class.asp?id=11"
# 监控关键词（可按需增减）
KEYWORDS = ["青岛啤酒", "华润啤酒", "青啤", "雀巢", "健康饮用水", "战略合作"]
# 记录已推送的新闻链接（避免重复）
pushed_links = set()

def send_to_wecom_markdown(content):
    """发送带超链接的Markdown消息到企业微信"""
    if not WEBHOOK_URL:
        print("未配置企业微信Webhook，跳过发送")
        return
    
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    try:
        resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
        if resp.status_code == 200 and resp.json()["errcode"] == 0:
            print("Markdown消息推送成功")
        else:
            print(f"推送失败：{resp.text}")
    except Exception as e:
        print(f"推送异常：{str(e)}")

def is_today(date_str):
    """判断新闻发布时间是否为今天"""
    try:
        # 匹配 2026-02-28 格式的日期
        news_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = date.today()
        return news_date == today
    except:
        # 匹配 2026/02/28 格式的日期
        try:
            news_date = datetime.strptime(date_str, "%Y/%m/%d").date()
            return news_date == date.today()
        except:
            # 无法识别日期，默认不推送（避免旧闻）
            return False

def extract_industry_news():
    """抓取指定行业资讯栏目的新闻（标题/链接/发布时间）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.beerw.com"
    }
    news_list = []
    
    try:
        resp = requests.get(TARGET_URL, headers=headers, timeout=15)
        resp.encoding = "utf-8"  # 强制UTF-8编码，避免乱码
        soup = BeautifulSoup(resp.text, "html.parser")

        # 适配行业资讯页面结构：抓取新闻列表项
        news_items = soup.find_all("a", href=re.compile(r"/news/\d+\.html"))
        for item in news_items:
            # 提取新闻链接和标题
            a_tag = item.find("a", href=re.compile(r"/news/\d+\.html"))
            if not a_tag:
                continue
            
            title = a_tag.get_text(strip=True)
            link = a_tag.get("href")
            if not title or len(title) < 5 or not link:
                continue
            
            # 补全完整链接
            if not link.startswith("http"):
                link = f"https://www.beerw.com{link}"
            
            # 提取发布时间（适配多种时间格式）
            publish_time = ""
            item_text = item.get_text()
            time_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", item_text)
            if time_match:
                publish_time = time_match.group(1)

            news_list.append({
                "title": title,
                "link": link,
                "time": publish_time
            })
        
        return news_list
    except Exception as e:
        print(f"抓取行业资讯失败：{str(e)}")
        return []

def check_news_keywords(news):
    """检查新闻标题/内容是否包含关键词"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        # 先检查标题（标题命中直接返回，不用爬正文，节省时间）
        title_matched = [kw for kw in KEYWORDS if kw in news["title"]]
        if title_matched:
            return title_matched
        
        # 标题未命中，再爬正文检查
        resp = requests.get(news["link"], headers=headers, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        content_text = soup.get_text()
        
        content_matched = [kw for kw in KEYWORDS if kw in content_text]
        return content_matched
    except Exception as e:
        print(f"检查新闻 {news['link']} 失败：{str(e)}")
        return []

def run_monitor():
    global pushed_links
    today = date.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now()}] 开始监控 beerw 行业资讯（仅推送今日新闻）...")
    
    # 1. 抓取指定栏目新闻
    news_list = extract_industry_news()
    if not news_list:
        print("未抓取到任何行业资讯")
        return
    
    # 2. 遍历新闻，筛选今日+未推送+含关键词的新闻
    for news in news_list:
        # 跳过已推送的新闻
        if news["link"] in pushed_links:
            continue
        
        # 只处理今天发布的新闻
       # if not news["time"] or not is_today(news["time"]):
        #    continue
       # 临时测试：不过滤日期
        if not news["time"] or not is_today(news["time"]):
            continue 
        # 检查关键词
        matched_kws = check_news_keywords(news)
        if matched_kws:
            # 构造带超链接的Markdown消息
            md_content = (
    f"🍺 **Beerw 行业资讯提醒**\n"
    f"[{news['title']}]({news['link']})\n"
    f"发布时间：{news['time']}\n"
    f"命中关键词：{', '.join(matched_kws)}\n"
    f"@all"
)
            print(f"推送今日新闻：{news['title']}")
            send_to_wecom_markdown(md_content)
            pushed_links.add(news["link"])
    
    # 清理过旧的推送记录（只保留最近200条）
    if len(pushed_links) > 200:
        pushed_links = set(list(pushed_links)[-200:])
    
    print(f"[{datetime.now()}] 本轮监控结束，已推送记录数：{len(pushed_links)}")

if __name__ == "__main__":
    run_monitor()

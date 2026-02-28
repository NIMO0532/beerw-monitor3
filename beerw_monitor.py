import requests
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta

# 从环境变量读取 Webhook
WEBHOOK_URL = os.getenv("WECOM_WEBHOOK")
# 目标行业资讯栏目
TARGET_URL = "https://www.beerw.com/class.asp?id=11"
# 监控关键词（可按需修改）
KEYWORDS = ["青岛啤酒", "华润啤酒", "青啤", "百威啤酒", "大麦", "酒花","酵母","燕京啤酒"]
# 已推送链接（去重）
pushed_links = set()

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

def is_within_7_days(date_str):
    """判断新闻是否为近7天发布（核心修改点）"""
    if not date_str:
        return False
    # 兼容多种日期格式
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]:
        try:
            news_date = datetime.strptime(date_str, fmt).date()
            # 计算当前日期 - 新闻日期 ≤ 7天
            days_diff = (date.today() - news_date).days
            return days_diff >= 0 and days_diff <= 7
        except:
            continue
    return False

def extract_industry_news():
    """抓取行业资讯新闻"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.beerw.com",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    news_list = []
    
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        resp = session.get(TARGET_URL, headers=headers, timeout=20)
        resp.encoding = "gb2312"
        html_text = resp.text
        
        soup = BeautifulSoup(html_text, "html.parser")
        list_items = soup.find_all("li")
        print(f"🔍 找到 {len(list_items)} 个列表项")
        
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
            
            # 提取并格式化时间
            publish_time = ""
            li_text = li.get_text()
            time_match = re.search(r"(\d{4}[-/年]\d{2}[-/月]\d{2}日?)", li_text)
            if time_match:
                publish_time = time_match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            
            news_list.append({"title": title, "link": link, "time": publish_time})
        
        # 去重
        news_list = [dict(t) for t in {tuple(d.items()) for d in news_list}]
        print(f"✅ 最终抓取到 {len(news_list)} 条有效新闻")
        return news_list
    except Exception as e:
        print(f"❌ 抓取失败：{str(e)}")
        return []

def check_news_keywords(news):
    """检查标题是否包含关键词"""
    return [kw for kw in KEYWORDS if kw in news["title"]]

def run_monitor():
    global pushed_links
    print(f"[{datetime.now()}] 开始监控 beerw 行业资讯（近7天）...")
    news_list = extract_industry_news()
    
    # 正式推送：仅处理【近7天发布 + 含关键词 + 未推送】的新闻
    for news in news_list:
        if news["link"] in pushed_links:
            continue
        if not news["time"] or not is_within_7_days(news["time"]):
            continue
        matched_kws = check_news_keywords(news)
        if matched_kws:
            md_content = (
                f"🍺 **Beerw 行业资讯提醒**\n"
                f"[{news['title']}]({news['link']})\n"
                f"发布时间：{news['time']}\n"
                f"命中关键词：{', '.join(matched_kws)}"
            )
            print(f"📤 推送新闻：{news['title']}（关键词：{matched_kws}）")
            send_to_wecom_markdown(md_content)
            pushed_links.add(news["link"])
    
    print("本轮监控结束")

if __name__ == "__main__":
    run_monitor()

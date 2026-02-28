import requests
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime, date

# 从环境变量读取 Webhook
WEBHOOK_URL = os.getenv("WECOM_WEBHOOK")
# 目标行业资讯栏目
TARGET_URL = "https://www.beerw.com/class.asp?id=11"
# 监控关键词
KEYWORDS = ["青岛啤酒", "华润啤酒", "百威啤酒"]
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

def is_today(date_str):
    """判断是否为今日新闻"""
    if not date_str:
        return False
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]:
        try:
            news_date = datetime.strptime(date_str, fmt).date()
            return news_date == date.today()
        except:
            continue
    return False

def extract_industry_news():
    """抓取新闻：适配所有链接格式，不限制/news/"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.beerw.com",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    news_list = []
    
    try:
        # 超时重试
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        resp = session.get(TARGET_URL, headers=headers, timeout=20)
        resp.encoding = "gb2312"  # 固定网站编码
        html_text = resp.text
        
        # 解析页面：抓取所有列表项中的标题链接（适配行业资讯页结构）
        soup = BeautifulSoup(html_text, "html.parser")
        
        # 核心：抓取页面中所有<li>标签里的<a>链接（行业资讯页的新闻都在列表里）
        list_items = soup.find_all("li")
        print(f"🔍 找到 {len(list_items)} 个列表项")
        
        for li in list_items:
            a_tag = li.find("a")
            if not a_tag:
                continue
            
            # 提取标题和链接
            title = a_tag.get_text(strip=True)
            link = a_tag.get("href", "")
            if not title or len(title) < 5 or not link:
                continue
            
            # 补全链接（处理相对路径）
            if link.startswith("/"):
                link = f"https://www.beerw.com{link}"
            elif not link.startswith("http"):
                link = f"https://www.beerw.com/{link}"
            
            # 提取发布时间（从<li>文本中找日期）
            publish_time = ""
            li_text = li.get_text()
            time_match = re.search(r"(\d{4}[-/年]\d{2}[-/月]\d{2}日?)", li_text)
            if time_match:
                publish_time = time_match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            
            news_list.append({
                "title": title,
                "link": link,
                "time": publish_time
            })
        
        # 去重（避免重复链接）
        news_list = [dict(t) for t in {tuple(d.items()) for d in news_list}]
        print(f"✅ 最终抓取到 {len(news_list)} 条有效新闻")
        return news_list
    
    except Exception as e:
        print(f"❌ 抓取失败：{str(e)}")
        return []

def check_news_keywords(news):
    """检查标题是否包含关键词"""
    matched = [kw for kw in KEYWORDS if kw in news["title"]]
    if matched:
        print(f"🔍 新闻 {news['title']} 命中关键词：{matched}")
    return matched

def run_monitor():
    global pushed_links
    print(f"[{datetime.now()}] 开始监控 beerw 行业资讯...")
    news_list = extract_industry_news()
    
    # 1. 测试推送：强制推送第一条新闻（不管日期/关键词）
    if news_list:
        test_news = news_list[0]
        md_content = (
            f"🍺 **Beerw 监控提醒（测试）**\n"
            f"[{test_news['title']}]({test_news['link']})\n"
            f"发布时间：{test_news['time'] or '未知'}\n"
            f"测试说明：强制推送第一条新闻验证抓取功能"
        )
        print(f"📤 推送测试新闻：{test_news['title']}")
        send_to_wecom_markdown(md_content)
        pushed_links.add(test_news["link"])
    else:
        print("❌ 未抓取到任何新闻，发送测试消息...")
        send_to_wecom_markdown("🍺 **Beerw 监控测试**\n通道正常，但未抓取到新闻列表")
    
    # 2. 正式推送：今日+含关键词的新闻（测试完成后可取消注释）
     for news in news_list:
         if news["link"] in pushed_links:
             continue
         if not news["time"] or not is_today(news["time"]):
             continue
         matched_kws = check_news_keywords(news)
         if matched_kws:
             md_content = (
                 f"🍺 **Beerw 行业资讯提醒**\n"
                 f"[{news['title']}]({news['link']})\n"
                 f"发布时间：{news['time']}\n"
                 f"命中关键词：{', '.join(matched_kws)}"
             )
             send_to_wecom_markdown(md_content)
             pushed_links.add(news["link"])
    
    print("本轮监控结束")

if __name__ == "__main__":
    run_monitor()

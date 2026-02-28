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
KEYWORDS = ["青岛啤酒", "华润啤酒", "百威啤酒", "雀巢",]
# 已推送链接（去重）
pushed_links = set()

def send_to_wecom_markdown(content):
    """发送 Markdown 消息到企业微信（简化格式，避免兼容问题）"""
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
    """判断是否为今日新闻（兼容多种格式）"""
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
    """抓取新闻（增加反反爬+调试日志）"""
    # 增强请求头，模拟真实浏览器
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.beerw.com",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    news_list = []
    
    try:
        # 增加超时重试
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        resp = session.get(TARGET_URL, headers=headers, timeout=20)
        
        # 调试：输出页面状态和编码
        print(f"🔍 页面响应状态码：{resp.status_code}")
        print(f"🔍 网站自动识别编码：{resp.apparent_encoding}")
        
        # 强制尝试多种编码解析
        encodings = ["gb2312", "gbk", "utf-8", "iso-8859-1"]
        html_text = ""
        for enc in encodings:
            try:
                resp.encoding = enc
                html_text = resp.text
                if html_text:
                    print(f"✅ 使用编码 {enc} 解析成功")
                    break
            except:
                continue
        
        if not html_text:
            print("❌ 所有编码解析均失败")
            return []
        
        # 调试：输出前500字符，确认是否抓到页面内容
        print(f"🔍 页面前500字符：{html_text[:500]}")
        
        # 解析页面（放宽匹配条件）
        soup = BeautifulSoup(html_text, "html.parser")
        # 匹配所有包含 news 的链接（不管格式）
        all_links = soup.find_all("a")
        news_links = []
        for a in all_links:
            href = a.get("href", "")
            if "/news/" in href and ".html" in href:
                news_links.append(a)
        
        print(f"🔍 找到 {len(news_links)} 条新闻链接")
        
        # 提取新闻信息
        for a_tag in news_links:
            title = a_tag.get_text(strip=True)
            link = a_tag.get("href")
            if not title or len(title) < 2:
                continue
            # 补全链接
            if not link.startswith("http"):
                link = f"https://www.beerw.com{link}"
            # 提取时间（从相邻文本找）
            publish_time = ""
            time_match = re.search(r"(\d{4}[-/年]\d{2}[-/月]\d{2}日?)", a_tag.parent.get_text())
            if time_match:
                publish_time = time_match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            
            news_list.append({"title": title, "link": link, "time": publish_time})
        
        print(f"✅ 最终抓取到 {len(news_list)} 条有效新闻")
        return news_list
    
    except Exception as e:
        print(f"❌ 抓取失败：{str(e)}")
        return []

def check_news_keywords(news):
    """检查关键词（仅检查标题，避免二次访问被屏蔽）"""
    matched = [kw for kw in KEYWORDS if kw in news["title"]]
    if matched:
        print(f"🔍 新闻 {news['title']} 命中关键词：{matched}")
    return matched

def run_monitor():
    global pushed_links
    print(f"[{datetime.now()}] 开始监控 beerw 行业资讯...")
    news_list = extract_industry_news()
    
    # 临时测试：强制推送第一条新闻（不管日期/关键词）
    if news_list:
        test_news = news_list[0]
        md_content = (
            f"🍺 **Beerw 测试提醒**\n"
            f"[{test_news['title']}]({test_news['link']})\n"
            f"发布时间：{test_news['time']}\n"
            f"测试推送：强制发送第一条新闻验证通道"
        )
        print(f"📤 强制推送测试新闻：{test_news['title']}")
        send_to_wecom_markdown(md_content)
        pushed_links.add(test_news["link"])
    else:
        print("❌ 未抓取到任何新闻，发送测试消息...")
        # 即使没抓到新闻，也发一条测试消息验证推送通道
        send_to_wecom_markdown("🍺 **Beerw 监控测试**\n通道正常，但未抓取到新闻（可能被网站屏蔽）")
    
    print("本轮监控结束")

if __name__ == "__main__":
    run_monitor()

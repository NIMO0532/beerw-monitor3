import requests
import os
from bs4 import BeautifulSoup

# 从GitHub环境变量读取企业微信Webhook
WEBHOOK_URL = os.getenv("WECOM_WEBHOOK")
TARGET_URL = "https://www.beerw.com"
KEYWORDS = ["青岛啤酒", "雀巢", "百威啤酒", "华润啤酒"]

def send_to_wecom(content):
    """发送消息到企业微信"""
    if not WEBHOOK_URL:
        print("未配置Webhook，跳过发送")
        return
    data = {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": ["@all"]
        }
    }
    try:
        resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
        if resp.status_code == 200:
            print("消息发送成功")
        else:
            print(f"发送失败：{resp.text}")
    except Exception as e:
        print(f"发送异常：{str(e)}")

def check_website():
    """检查beerw.com关键词"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(TARGET_URL, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        main_content = soup.get_text()

        matched = [kw for kw in KEYWORDS if kw in main_content]
        if matched:
            msg = (
                f"🍺 Beerw监控提醒\n"
                f"网址：{TARGET_URL}\n"
                f"命中关键词：{', '.join(matched)}\n"
                f"请及时查看！"
            )
            print(msg)
            send_to_wecom(msg)
        else:
            print("未发现关键词")
    except Exception as e:
        print(f"检查异常：{str(e)}")

if __name__ == "__main__":
    print("开始执行监控...")
    check_website()
    print("监控执行完成")

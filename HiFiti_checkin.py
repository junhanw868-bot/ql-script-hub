# -*- coding: utf-8 -*-
"""
 cron: 30 6 * * *
 new Env('HiFiHi签到')
 适配 hifihi.com 的自动签到
"""

import os
import re
import time
import random
import requests

# ---------------- 统一通知模块加载 ----------------
hadsend = False
send = None

try:
    from notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️ 未加载通知模块，跳过通知功能")

# ---------------- 随机延迟配置 ----------------
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"


def format_time_remaining(seconds):
    if seconds <= 0:
        return "立即执行"
    hours, minutes = divmod(seconds, 3600)
    minutes, secs = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    elif minutes > 0:
        return f"{minutes}分{secs}秒"
    else:
        return f"{secs}秒"


def wait_with_countdown(delay_seconds, task_name):
    if delay_seconds <= 0:
        return
    print(f"{task_name} 需要等待 {format_time_remaining(delay_seconds)}")
    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            print(f"{task_name} 倒计时: {format_time_remaining(remaining)}")
        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time


def notify_user(title, content):
    if hadsend:
        try:
            send(title, content)
            print(f"✅ 通知发送完成: {title}")
        except Exception as e:
            print(f"❌ 通知发送失败: {e}")
    else:
        print(f"📢 {title}\n📄 {content}")


class HifihiCheckIn:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16; RMX3800 Build/UKQ1.231108.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.200 Mobile Safari/537.36",
            "Accept": "text/plain, */*; q=0.01",
            "Accept-Language": "zh-CN,zh-HK;q=0.9,zh;q=0.8,en-US;q=0.7,en;q=0.6",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://hifihi.com",
            "Referer": "https://hifihi.com/my.htm",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        self.results = []

        # 从环境变量读取 Cookie，支持多账号（换行分隔）
        cookie_env = os.getenv("HIFIHI_COOKIE", "")
        self.cookies = [c.strip() for c in cookie_env.replace('\r\n', '\n').split('\n') if c.strip()]

        self.success_count = 0
        self.fail_count = 0

    def parse_user_id(self, cookie):
        """从Cookie中提取用户ID（取 bbs_sid 前8位）"""
        match = re.search(r" bbs_sid=([^;]+)", cookie)
        if match:
            return match.group(1)[:8]
        match = re.search(r"^bbs_sid=([^;]+)", cookie)
        if match:
            return match.group(1)[:8]
        return "unknown"

    def sign_hifihi(self, cookie_str):
        """HiFiHi 签到 - POST 空 body，靠 Cookie 验证"""
        # 清空旧 cookie
        self.session.cookies.clear()
        
        # 解析并设置 Cookie
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                self.session.cookies.set(key.strip(), value.strip(), domain='hifihi.com')

        try:
            response = self.session.post(
                "https://hifihi.com/sg_sign.htm",
                data="",  # 空 body
                timeout=15
            )
            
            response_text = response.text
            
            # 根据返回内容判断结果（你需要根据实际返回调整关键词）
            if "签到成功" in response_text:
                return True, "签到成功"
            elif "已签到" in response_text or "今日已签" in response_text:
                return False, "今日已签到"
            elif "失败" in response_text:
                return False, "签到失败"
            else:
                # 如果返回是 JSON，尝试解析
                try:
                    import json
                    data = json.loads(response_text)
                    if data.get("code") == 0 or data.get("status") == 1:
                        return True, "签到成功"
                    else:
                        return False, f"签到返回: {data}"
                except:
                    # 返回内容较短时直接打印
                    return False, f"返回: {response_text[:100]}"
                
        except Exception as e:
            return False, f"签到异常: {str(e)}"

    def run(self):
        print("=" * 50)
        print("开始 HiFiHi 签到任务")
        print("=" * 50)

        if not self.cookies:
            print("❌ 未配置 HIFIHI_COOKIE，跳过")
            return 1

        # 随机延迟
        if random_signin and len(self.cookies) > 0:
            delay_seconds = random.randint(0, min(max_random_delay, 3600))
            if delay_seconds > 0:
                print(f"🎲 随机模式: 延迟 {format_time_remaining(delay_seconds)} 后开始")
                wait_with_countdown(delay_seconds, "HiFiHi签到")

        print(f"📝 共发现 {len(self.cookies)} 个 HiFiHi 账号")

        for i, cookie in enumerate(self.cookies):
            user_id = self.parse_user_id(cookie)
            print(f" 账号 {i+1}/{len(self.cookies)} ({user_id}): ", end="")
            success, msg = self.sign_hifihi(cookie)
            print(msg)
            self.results.append(f"HiFiHi 账号{i+1}({user_id}): {msg}")
            if success:
                self.success_count += 1
            else:
                self.fail_count += 1
            
            if i < len(self.cookies) - 1:
                time.sleep(random.uniform(1, 3))

        # 汇总
        print("\n" + "=" * 50)
        print("签到结果汇总:")
        for result in self.results:
            print(f" - {result}")

        if self.results:
            summary_msg = f"成功: {self.success_count} / 失败: {self.fail_count}\n\n" + "\n".join([f"• {r}" for r in self.results])
            notify_user("HiFiHi 签到汇总", summary_msg)

        print("=" * 50)
        return 0 if self.fail_count == 0 else 1


if __name__ == "__main__":
    checkin = HifihiCheckIn()
    exit_code = checkin.run()
    exit(exit_code)

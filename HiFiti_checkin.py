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
# 尝试导入外部通知模块 (如 QL 的 notify.py)，如果找不到则禁用通知功能
hadsend = False
send = None

try:
    from notify import send
    hadsend = True
    print("✅ 已加载notify.py通知模块")
except ImportError:
    print("⚠️ 未加载通知模块，跳过通知功能")

# ---------------- 随机延迟配置 ----------------
# 从环境变量读取最大随机延迟时间，默认为 3600 秒 (1小时)
max_random_delay = int(os.getenv("MAX_RANDOM_DELAY", "3600"))
# 从环境变量读取是否开启随机延迟，默认为 True
random_signin = os.getenv("RANDOM_SIGNIN", "true").lower() == "true"

def format_time_remaining(seconds):
    """
    将秒数格式化为更易读的时间字符串 (xx小时xx分xx秒)
    """
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
    """
    带倒计时显示的等待函数，每10秒刷新一次显示，最后10秒每秒刷新。
    """
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
    """
    封装通知发送逻辑，兼容有无 notify 模块的情况。
    """
    if hadsend:
        try:
            send(title, content)
            print(f"✅ 通知发送完成: {title}")
        except Exception as e:
            print(f"❌ 通知发送失败: {e}")
    else:
        print(f"📢 {title}\n📄 {content}")

class HifihiCheckIn:
    """
    HiFiHi 签到核心逻辑类
    """
    def __init__(self):
        self.session = requests.Session()
        # 设置请求头，模拟手机浏览器访问
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
        self.results = [] # 存储每个账号的签到结果
        self.success_count = 0
        self.fail_count = 0

        # 从环境变量 HIFIHI_COOKIE 中读取 Cookie 字符串
        # 支持多账号，使用换行符分隔
        cookie_env = os.getenv("HIFIHI_COOKIE", "")
        self.cookies = [c.strip() for c in cookie_env.replace('\r\n', '\n').split('\n') if c.strip()]

    def parse_user_id(self, cookie):
        """
        从 Cookie 字符串中提取用户标识 (bbs_sid 的前8位)
        """
        match = re.search(r" bbs_sid=([^;]+)", cookie)
        if match:
            return match.group(1)[:8]
        match = re.search(r"^bbs_sid=([^;]+)", cookie)
        if match:
            return match.group(1)[:8]
        return "unknown"

    def sign_hifihi(self, cookie_str):
        """
        执行签到请求的核心函数。
        Args:
            cookie_str (str): 单个账号的 Cookie 字符串
        Returns:
            tuple: (是否成功, 结果消息)
        """
        # 清空旧的 cookie 避免冲突
        self.session.cookies.clear()
        
        # 解析并设置新的 Cookie
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                self.session.cookies.set(key.strip(), value.strip(), domain='hifihi.com')

        try:
            # 发送 POST 请求到签到接口
            # 根据网页分析，签到接口为 /sg_sign.htm，且不需要发送数据体 (data="")
            response = self.session.post(
                "https://hifihi.com/sg_sign.htm",
                data="", 
                timeout=15
            )
            
            response_text = response.text
            
            # 根据返回内容判断签到状态
            if "签到成功" in response_text:
                return True, "签到成功"
            elif "已签到" in response_text or "今日已签" in response_text:
                return False, "今日已签到"
            elif "失败" in response_text:
                return False, "签到失败"
            else:
                # 如果返回的是 JSON 格式，尝试解析
                try:
                    import json
                    data = json.loads(response_text)
                    if data.get("code") == 0 or data.get("status") == 1:
                        return True, "签到成功"
                    else:
                        return False, f"签到返回: {data}"
                except:
                    # 如果无法解析 JSON，直接返回前100个字符用于调试
                    return False, f"返回: {response_text[:100]}"
                
        except Exception as e:
            return False, f"签到异常: {str(e)}"

    def run(self):
        """
        运行签到任务的主函数。
        """
        print("=" * 50)
        print("开始 HiFiHi 签到任务")
        print("=" * 50)

        if not self.cookies:
            print("❌ 未配置 HIFIHI_COOKIE，跳过")
            return 1

        # 处理随机延迟
        if random_signin and len(self.cookies) > 0:
            delay_seconds = random.randint(0, min(max_random_delay, 3600))
            if delay_seconds > 0:
                print(f"🎲 随机模式: 延迟 {format_time_remaining(delay_seconds)} 后开始")
                wait_with_countdown(delay_seconds, "HiFiHi签到")

        print(f"📝 共发现 {len(self.cookies)} 个 HiFiHi 账号")

        # 遍历所有账号进行签到
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
            
            # 账号间随机休眠 1-3 秒，模拟人类操作
            if i < len(self.cookies) - 1:
                time.sleep(random.uniform(1, 3))

        # 输出汇总结果
        print("\n" + "=" * 50)
        print("签到结果汇总:")
        for result in self.results:
            print(f" - {result}")

        # 发送通知
        if self.results:
            summary_msg = f"成功: {self.success_count} / 失败: {self.fail_count}\n\n" + "\n".join([f"• {r}" for r in self.results])
            notify_user("HiFiHi 签到汇总", summary_msg)

        print("=" * 50)
        return 0 if self.fail_count == 0 else 1


if __name__ == "__main__":
    checkin = HifihiCheckIn()
    exit_code = checkin.run()
    exit(exit_code)

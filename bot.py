import time
import json
import telegram
import asyncio
import requests
import smtplib
import subprocess
import re
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime
from utils import Color
from db import getArticlesForBot, updateArticlesStatus

__all__ = ["feishuBot", "wecomBot", "dingtalkBot", "telegramBot", "mailBot"]
today = datetime.now().strftime("%Y-%m-%d")


class feishuBot:
    """飞书群机器人
    https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN
    """
    def __init__(self, key, proxy_url='') -> None:
        self.key = key
        self.proxy = {'http': proxy_url, 'https': proxy_url} if proxy_url else {'http': None, 'https': None}

    @staticmethod
    def parse_results(results: list):
        text_list = []
        for result in results:
            (feed, value), = result.items()
            text = f'[ {feed} ]\n\n'
            for title, link in value.items():
                text += f'{title}\n{link}\n\n'
            text_list.append(text.strip())
        return text_list

    def send(self, text_list: list):
        for text in text_list:
            print(f'{len(text)} {text[:50]}...{text[-50:]}')

            data = {"msg_type": "text", "content": {"text": text}}
            headers = {'Content-Type': 'application/json'}
            url = f'https://open.feishu.cn/open-apis/bot/v2/hook/{self.key}'
            r = requests.post(url=url, headers=headers, data=json.dumps(data), proxies=self.proxy)

            if r.status_code == 200:
                Color.print_success('[+] feishuBot 发送成功')
            else:
                Color.print_failed('[-] feishuBot 发送失败')
                print(r.text)

    def send_markdown(self, text):
        # TODO 富文本
        data = {"msg_type": "text", "content": {"text": text}}
        self.send(data)


class wecomBot:
    """企业微信群机器人
    https://developer.work.weixin.qq.com/document/path/91770
    """
    def __init__(self, key, proxy_url='') -> None:
        self.key = key
        self.proxy = {'http': proxy_url, 'https': proxy_url} if proxy_url else {'http': None, 'https': None}

    @staticmethod
    def parse_results(results: list):
        text_list = []
        for result in results:
            (feed, value), = result.items()
            text = f'## {feed}\n'
            for title, link in value.items():
                text += f'- [{title}]({link})\n'
            text_list.append(text.strip())
        return text_list

    def send(self, text_list: list):
        for text in text_list:
            print(f'{len(text)} {text[:50]}...{text[-50:]}')

            data = {"msgtype": "markdown", "markdown": {"content": text}}
            headers = {'Content-Type': 'application/json'}
            url = f'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.key}'
            r = requests.post(url=url, headers=headers, data=json.dumps(data), proxies=self.proxy)

            if r.status_code == 200:
                Color.print_success('[+] wecomBot 发送成功')
            else:
                Color.print_failed('[-] wecomBot 发送失败')
                print(r.text)


class dingtalkBot:
    """钉钉群机器人
    https://open.dingtalk.com/document/robots/custom-robot-access
    """
    def __init__(self, key, proxy_url='') -> None:
        self.key = key
        self.proxy = {'http': proxy_url, 'https': proxy_url} if proxy_url else {'http': None, 'https': None}

    @staticmethod
    def parse_results(results: list):
        text_list = []
        for result in results:
            (feed, value), = result.items()
            text = ''.join(f'- [{title}]({link})\n' for title, link in value.items())
            text_list.append([feed, text.strip()])
        return text_list

    def send(self, text_list: list):
        for (feed, text) in text_list:
            print(f'{len(text)} {text[:50]}...{text[-50:]}')

            data = {"msgtype": "markdown", "markdown": {"title": feed, "text": text}}
            headers = {'Content-Type': 'application/json'}
            url = f'https://oapi.dingtalk.com/robot/send?access_token={self.key}'
            r = requests.post(url=url, headers=headers, data=json.dumps(data), proxies=self.proxy)

            if r.status_code == 200:
                Color.print_success('[+] dingtalkBot 发送成功')
            else:
                Color.print_failed('[-] dingtalkBot 发送失败')
                print(r.text)

class mailBot:
    """邮件机器人
    """
    def __init__(self, sender, passwd, receiver: str, fromwho='', server='') -> None:
        self.sender = sender
        self.receiver = receiver
        self.fromwho = fromwho or sender
        server = server or self.get_server(sender)

        self.smtp = smtplib.SMTP_SSL(server)
        self.smtp.login(sender, passwd)

    def get_server(self, sender: str):
        key = sender.rstrip('.com').split('@')[-1]
        server = {
            'qq': 'smtp.qq.com',
            'foxmail': 'smtp.qq.com',
            '163': 'smtp.163.com',
            'sina': 'smtp.sina.com',
            'gmail': 'smtp.gmail.com',
            'outlook': 'smtp.live.com',
        }
        return server.get(key, f'smtp.{key}.com')

    @staticmethod
    def parse_results(results: list):
        text = f'<html><head><h1>每日安全资讯（{today}）</h1></head><body>'
        for result in results:
            (feed, value), = result.items()
            text += f'<h3>{feed}</h3><ul>'
            for title, link in value.items():
                text += f'<li><a href="{link}">{title}</a></li>'
            text += '</ul>'
        text += '<br><br><b>如不需要，可直接回复本邮件退订。</b></body></html>'
        return text

    def send(self, text: str):
        print(f'{len(text)} {text[:50]}...{text[-50:]}')

        msg = MIMEText(text, 'html')
        msg['Subject'] = Header(f'每日安全资讯（{today}）')
        msg['From'] = self.fromwho
        msg['To'] = self.receiver

        try:
            self.smtp.sendmail(self.sender, self.receiver.split(','), msg.as_string())
            Color.print_success('[+] mailBot 发送成功')
        except Exception as e:
            Color.print_failed('[+] mailBot 发送失败')
            print(e)


class telegramBot:
    """Telegram机器人
    https://core.telegram.org/bots/api
    """
    def __init__(self, key, chat_id: list, proxy_url='') -> None:
        self.chat_id = chat_id
        self.bot = telegram.Bot(token=key)

    def test_connect(self):
        try:
            self.bot.get_me()
            return True
        except Exception as e:
            Color.print_failed('[-] telegramBot 连接失败')
            return False

    async def sendMsg(self, chat_id, text):
        async with self.bot:
            print(await self.bot.send_message(chat_id=chat_id, text = text, parse_mode='HTML'))

    @staticmethod
    def parse_results(results: list):
        results = getArticlesForBot()
        ids = []
        text = ''
        for (id, feed_name, feed_url, title, url) in results:
            newfeedname = re.sub(r'[()\[\]|<> \s]+', ' ', feed_name)
            newtitle = re.sub(r'[()\[\]|<> \s]+', ' ', title)
            ids.append(id)
            text += f'<a href="{url}">[{newfeedname}] {newtitle}</a>\n\n'
        text += '频道: <a href="https://t.me/icocoon">@icocoon</a>'

        return ids, text

    def send(self, text: str):
        for id in self.chat_id:
            for i in range(10):
                try:
                    ids, text = self.parse_results([])
                    if len(ids) > 0:
                        asyncio.run(self.sendMsg(id, text))
                        Color.print_success(f'[+] telegramBot 发送成功 {id}')
                        updateArticlesStatus(ids)
                    else:
                        break;
                except Exception as e:
                    Color.print_failed(f'[-] telegramBot 发送失败 {id}')
                    print(e)

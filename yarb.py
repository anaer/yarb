#!/usr/bin/python3

import os
import json
import time
import schedule
import argparse
import datetime
import feedparser
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from bot import *
from utils import Color, Pattern
from db import getRss, updateRssInvalid, addArticles, getArticles, getArticlesForReadme

import requests
requests.packages.urllib3.disable_warnings()

today = datetime.datetime.now().strftime("%Y-%m-%d")
filterWords = []

# 替换圆括号和中括号为空格
def replace_brackets_with_space(string):
    replaced_string = re.sub(r'[()\[\]| \s]+', ' ', string)
    return replaced_string

# 处理长字符串
def truncate_string(string, length = 18):
    if len(string) <= length:
        return string
    else:
        return string[:length] + '...'

def update_today():
    """更新today"""
    root_path = Path(__file__).absolute().parent
    today_path = root_path.joinpath('README.md')
    archive_path = root_path.joinpath(f'archive/{today.split("-")[0]}/{today}.md')

    archive_path.parent.mkdir(parents=True, exist_ok=True)

    data = getArticlesForReadme()
    with open(today_path, 'w+', encoding='utf-8-sig') as f1:
        content = f'# 每日资讯（{today}）\n\n'
        content += f'|时间|来源|标题|\n'
        content += f'|---|---|---|\n'
        for (feed, link, title, url, published_at) in data:
            newfeed = truncate_string(replace_brackets_with_space(feed))
            newtitle = replace_brackets_with_space(title)
            content += f'|{published_at}|[{newfeed}]({link})|[{newtitle}]({url})|\n'
        f1.write(content)

    data = getArticles()
    with open(archive_path, 'w+', encoding='utf-8-sig') as f2:
        content = f'# 每日资讯（{today}）\n\n'
        preFeed = ''
        for (feed, link, title, url) in data:
            if(preFeed != feed):
                preFeed = feed
                content += f'- [{feed}]({link})\n'
            newtitle = replace_brackets_with_space(title)
            content += f'  - [{newtitle}]({url})\n'
        f2.write(content)

def update_rss(rss: dict, proxy_url=''):
    """更新订阅源文件"""
    proxy = {'http': proxy_url, 'https': proxy_url} if proxy_url else {'http': None, 'https': None}

    (key, value), = rss.items()
    rss_path = root_path.joinpath(f'rss/{value["filename"]}')

    result = None
    if url := value.get('url'):
        r = requests.get(value['url'], proxies=proxy)
        if r.status_code == 200:
            with open(rss_path, 'w+') as f:
                f.write(r.text)
            print(f'[+] 更新完成：{key}')
            result = {key: rss_path}
        elif rss_path.exists():
            print(f'[-] 更新失败，使用旧文件：{key}')
            result = {key: rss_path}
        else:
            print(f'[-] 更新失败，跳过：{key}')
    else:
        print(f'[+] 本地文件：{key}')

    return result


def parseThread(url: str, proxy_url=''):
    """获取文章线程"""
    proxy = {'http': proxy_url, 'https': proxy_url} if proxy_url else {'http': None, 'https': None}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    ret = True

    title = ''
    link = ''
    result = []
    try:
        r = requests.get(url, timeout=10, headers=headers, verify=False, proxies=proxy)
        r = feedparser.parse(r.content)
        title = r.feed.title
        link = r.feed.link
        for entry in r.entries:
            d = entry.get('published_parsed')
            if not d:
                d = entry.updated_parsed
            # 转换日期格式
            pubday = datetime.datetime(d[0], d[1], d[2], d[3], d[4], d[5])

            beginTime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = datetime.datetime.today() + datetime.timedelta(1)

            if pubday > beginTime and pubday < tomorrow:
                result.append(entry)
                continue
            # 因rss一般是按时间新->旧排序, 当遇到一条发布时间不满足的情况, 基本可以确定后续都不满足, 直接跳出循环
            break
        Color.print_success(f'[+] {title}\t{url}\t{len(result)}/{len(r.entries)}')
    except Exception as e:
        ret = False
        Color.print_failed(f'[-] failed: {url}')
        print(e)
    return ret, title, url, result


def init_bot(conf: dict, proxy_url=''):
    """初始化机器人"""
    bots = []
    for name, v in conf.items():
        if v['enabled']:
            key = os.getenv(v['secrets']) or v['key']

            if name == 'mail':
                receiver = os.getenv(v['secrets_receiver']) or v['receiver']
                bot = globals()[f'{name}Bot'](v['address'], key, receiver, v['from'], v['server'])
                bots.append(bot)
            elif name == 'telegram':
                bot = globals()[f'{name}Bot'](key, v['chat_id'], proxy_url)
                if bot.test_connect():
                    bots.append(bot)
            else:
                bot = globals()[f'{name}Bot'](key, proxy_url)
                bots.append(bot)
    return bots

def job(args):
    """定时任务"""
    global root_path
    root_path = Path(__file__).absolute().parent
    if args.config:
        config_path = Path(args.config).expanduser().absolute()
    else:
        config_path = root_path.joinpath('config.json')
    with open(config_path, encoding='utf-8-sig') as f:
        conf = json.load(f)

    proxy_rss = conf['proxy']['url'] if conf['proxy']['rss'] else ''
    feeds = getRss()
    Color.print_focus(f'[+] {len(feeds)} feeds')
    # 修改全局变量 需要先使用global声明下
    global filterWords
    filterWords = conf['filterWords'] if conf['filterWords'] else []

    results = []
    if args.test:
        # 测试数据
        results.extend({f'test{i}': {Pattern.create(i*500): 'test'}} for i in range(1, 20))
    else:
        # 获取文章
        numb = 0
        tasks = []
        with ThreadPoolExecutor(100) as executor:
            tasks.extend(executor.submit(parseThread, url, proxy_rss) for url in feeds)
            for task in as_completed(tasks):
                ret, title, link, result = task.result()
                if ret:
                    if result:
                        numb += len(result)
                        results.append(task.result())
                else:
                    updateRssInvalid(link)
        Color.print_focus(f'[+] {len(results)} feeds, {numb} articles')

    print("过滤词:",filterWords)

    addArticles(results)
    # 更新today
    update_today()

    # 推送文章
    proxy_bot = conf['proxy']['url'] if conf['proxy']['bot'] else ''
    bots = init_bot(conf['bot'], proxy_bot)
    for bot in bots:
        bot.send(bot.parse_results(results))

def argument():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', help='Update RSS config file', action='store_true', required=False)
    parser.add_argument('--cron', help='Execute scheduled tasks every day (eg:"11:00")', type=str, required=False)
    parser.add_argument('--config', help='Use specified config file', type=str, required=False)
    parser.add_argument('--test', help='Test bot', action='store_true', required=False)
    return parser.parse_args()


if __name__ == '__main__':
    args = argument()
    if args.cron:
        schedule.every().day.at(args.cron).do(job, args)
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        job(args)

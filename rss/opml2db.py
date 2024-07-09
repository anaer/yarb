#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sqlite3
import datetime
import os
from xml.dom.minidom import parse
import xml.dom.minidom


def insert(cursor, category, title, type, xml_url, html_url, entry_content, scan_delay):
    try:
        cursor.execute('''
        insert or ignore into t_rss(category, title, type, status, xml_url, html_url, entry_content, scan_delay, created_at)
        values(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            category,
            title,
            type,
            1,
            xml_url,
            html_url,
            entry_content,
            scan_delay,
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ])
    except Exception as e:
        print("插入错误", e)
        pass
    return

def opml2db(path):
    conn = sqlite3.connect('rss.db3')
    cur = conn.cursor()
    # 使用minidom解析器打开 XML 文档
    DOMTree = xml.dom.minidom.parse(path)
    collection = DOMTree.documentElement
    if collection.hasAttribute("version"):
        print("Root element : %s" % collection.getAttribute("version"))

    body =  collection.getElementsByTagName('body')[0];

    outlines = body.getElementsByTagName('outline');

    for outline in outlines:
        # 如果包含outline, 表示该项为目录
        if outline.getElementsByTagName('outline'):
            category = outline.getAttribute('title');
            for subOutline in outline.getElementsByTagName('outline'):
                title = subOutline.getAttribute("title");
                type = subOutline.getAttribute("type");
                xmlUrl = subOutline.getAttribute("xmlUrl");
                htmlUrl = subOutline.getAttribute("htmlUrl");
                entryContent = subOutline.getAttribute("entryContent");
                scanDelay = subOutline.getAttribute("scanDelay");
                print(category, title, type, scanDelay)
                insert(cur, category, title, type, xmlUrl, htmlUrl, entryContent, scanDelay)
            conn.commit()
        else:
            title = outline.getAttribute("title");
            type = outline.getAttribute("type");
            xmlUrl = outline.getAttribute("xmlUrl");
            htmlUrl = outline.getAttribute("htmlUrl");
            entryContent = outline.getAttribute("entryContent");
            scanDelay = outline.getAttribute("scanDelay");
            print(title, type, scanDelay)
            insert(cur, '', title, type, xmlUrl, htmlUrl, entryContent, scanDelay)
            conn.commit()

    cur.close()
    conn.close()

names = os.listdir(".")

for name in names:
    if name.endswith('.opml'):
        opml2db(name)
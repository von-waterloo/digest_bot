import sqlite3
print('PFGG')
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from threading import Thread
from bs4 import BeautifulSoup
import requests
import os
import time
from openai import OpenAI
from db import get_connection
load_dotenv()
proxyapi = os.getenv("PROXY_API")
internalapi = os.getenv("INTERNAL_API")
puzzle_key = os.getenv("PUZZLE_KEY")
api_point = "http://127.0.0.1:5000/fusion"
bot_token = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=proxyapi)
app = Flask(__name__)
def init_db():
    connection = sqlite3.connect("news.db", check_same_thread=False)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS newslist (
        posttext TEXT NOT NULL,
        channel TEXT NOT NULL,
        userid TEXT NOT NULL,
        imageurl TEXT,
        sended BOOL NOT NULL,
        postid TEXT NOT NULL
    );""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        channel TEXT NOT NULL,
        userid TEXT NOT NULL
    );""")
    connection.commit()
    connection.close()

init_db()

def send_telegram_message(user, message):
    telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    max_message_length = 4096
    messages = [message[i:i + max_message_length] for i in range(0, len(message), max_message_length)]
    for msg_part in messages:
        params = {
            "chat_id": user,
            "text": msg_part,
            "disable_web_page_preview": True,
            "parse_mode": "MarkdownV2"
        }
        response = requests.get(telegram_api_url, params=params)
        if response.status_code == 400:
            params = {
            "chat_id": user,
            "text": msg_part,
            "disable_web_page_preview": True,
            }
            response = requests.get(telegram_api_url, params=params)
        return

def send_menu(user):
    params = {
            "token": puzzle_key,
            "method": "sendCommand",
            "command_name": "/settings_updated",
            "tg_chat_id": user,
        }
    ans = requests.get(url="https://api.puzzlebot.top/", params=params).json()["data"]
    return True
def send_end_menu(user):
    params = {
            "token": puzzle_key,
            "method": "sendCommand",
            "command_name": "/endnews",
            "tg_chat_id": user,
        }
    ans = requests.get(url="https://api.puzzlebot.top/", params=params).json()["data"]
    return True

def get_post_len(user):
    params = {
            "token": puzzle_key,
            "method": "getVariableValue",
            "variable": "CUSTOM_post_len",
            "user_id": user,
        }
    ans = requests.get(url="https://api.puzzlebot.top/", params=params).json()["data"]
    return ans
def set_post_len():pass #в пазлботе
def check_post(userid, channel_name, newstext, cursor):
    cursor.execute("SELECT posttext, sended FROM newslist WHERE channel = ? AND userid = ?", (channel_name, userid))
    data = cursor.fetchall()
    for row in data:
        if newstext in row[0]:
            if row[1] == 1:
                return True
            else:
                return True
    return False

def get_channels(user, cursor):
    cursor.execute("SELECT channel FROM channels WHERE userid = ?", (user,))
    channels = cursor.fetchall()
    return [channel[0] for channel in channels]

def add_channels(channel_list, cursor, connection):
    for channel in channel_list:
        cursor.execute("SELECT channel FROM channels")
        saved_channels = cursor.fetchall()
        if (channel,) not in saved_channels:
            cursor.execute("INSERT INTO channels (channel) VALUES (?)", (channel,))
    connection.commit()

def get_bot_users():
    pagecount = 1
    ans = None
    outL = list()
    while ans != []:
        params = {
            "token": puzzle_key,
            "method": "getUsersInChat",
            "chat_id": "7931303236",
            "page": pagecount,
        }
        ans = requests.get(url="https://api.puzzlebot.top/", params=params)
        ans=ans.json()["data"]
        for a in ans:
            outL.append(a["user_id"])
        pagecount += 1
    return outL

def bump_news_count(userid):
    params = {
            "token": puzzle_key,
            "method": "variableChange",
            "variable": "CUSTOM_news_count",
            "user_id": userid,
            "expression": """{{CUSTOM_news_count}}+1""",
        }
    ans = requests.get(url="https://api.puzzlebot.top/", params=params).json()
def send_news(user, cursor, connection):
    channels = get_channels(user, cursor)
    actual_news = list()
    postlen = get_post_len(user)
    for channel in channels:
        cursor.execute("SELECT posttext,postid FROM newslist WHERE sended = 0 AND channel = ? AND userid = ?", (channel, user))
        record = cursor.fetchall()
        if record == []:
            continue
        for post in record:
            posttext = post[0]
            postid = post[1]
            cursor.execute("UPDATE newslist SET sended = 1 WHERE posttext = ? AND channel = ? AND userid = ? AND postid = ?", (posttext, channel, user, postid))
            connection.commit()
            response = requests.get(api_point, headers={"apikey": internalapi}, params={"newstext": posttext,"postlen":postlen})
            fusion = response.json().get("fusion", posttext)
            actual_news.append([fusion,channel,postid])
    for news in actual_news:
        message_text = news[0]
        channel = news[1]
        postid = news[2]
        if message_text:
            message_text += f"\n\nИсточник @{channel}\nt.me/{channel}/{postid}"
            send_telegram_message(user,message_text)
        else:
            send_telegram_message(user,"Новостная лента еще не сформирована!")
            send_menu(user)
            return True
    send_end_menu(user)
    return True

def get_news_count(userid,cursor):
    channel_list = get_channels(userid, cursor)
    news_count = 0
    for channel in channel_list:
        cursor.execute("SELECT * FROM newslist WHERE sended = 0 AND channel = ? AND userid = ?", (channel, userid))
        a = cursor.fetchall()
        news_count += len(a)
    return news_count
def get_need_news_count(user):
    params = {
            "token": puzzle_key,
            "method": "getVariableValue",
            "variable": "CUSTOM_need_news_count",
            "user_id" : user,
        }
    ans = requests.get(url="https://api.puzzlebot.top/", params=params).json()["data"]
    return ans
def news_checker():
    print('Запускаюсь')
    while True:
        connection, cursor = get_connection()
        userlist = get_bot_users()
        print("Запустил проверку!")
        for user in userlist:
            channel_list = get_channels(user, cursor)
            for channel in channel_list:
                raw = requests.get(url=f"https://t.me/s/{channel}")
                if raw.status_code != 200:
                    continue
                parser = BeautifulSoup(raw.text, "html.parser")
                for i in range(-1, -20, -1):
                    try:
                        message = parser.find_all("div", class_="tgme_widget_message text_not_supported_wrap js-widget_message")[i]
                        postid = message.get("data-post").split("/")[-1]
                        newstext = message.find_all("div", class_="tgme_widget_message_text js-message_text")[-1].get_text(strip=True)
                        break
                    except IndexError:
                        continue
                if newstext is None:
                    continue
                newstext = newstext.replace('"', "'")
                if not check_post(user, channel, newstext, cursor):
                    cursor.execute("INSERT INTO newslist (posttext, channel, userid, sended,postid) VALUES (?, ?, ?, ?, ?)", (newstext, channel, user, 0, postid))
                    connection.commit()
                    bump_news_count(user)
            news_count = int(get_news_count(user,cursor))
            need_news_count = int(get_need_news_count(user))
            if news_count >= need_news_count:
                send_news(user, cursor, connection)
        print("Закончил проверку, засыпаю!")
        time.sleep(60*3.5) #проверка раз в 3.5минуты

news_checker()

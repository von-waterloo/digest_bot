from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from openai import OpenAI
from db import init_db, get_connection  # Импортируем функции для работы с БД
load_dotenv()
app = Flask(__name__)


# Инициализация базы данных
init_db()
proxyapi = os.getenv("PROXY_API")

internalapi = os.getenv("INTERNAL_API")

puzzle_key = os.getenv("PUZZLE_KEY")
api_point = "http://127.0.0.1:5000/fusion"
bot_token = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=proxyapi,
                base_url = "https://api.proxyapi.ru/openai/v1")
def get_news_count(userid,cursor):
    channel_list = get_channels(userid, cursor)
    news_count = 0
    for channel in channel_list:
        cursor.execute("SELECT * FROM newslist WHERE sended = 0 AND channel = ? AND userid = ?", (channel, userid))
        a = cursor.fetchall()
        news_count += len(a)
    return news_count
def get_channels(user, cursor):
    cursor.execute("SELECT channel FROM channels WHERE userid = ?", (user,))
    channels = cursor.fetchall()
    return [channel[0] for channel in channels]
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
def get_post_len(user):
    params = {
            "token": puzzle_key,
            "method": "getVariableValue",
            "variable": "CUSTOM_post_len",
            "user_id": user,
        }
    ans = requests.get(url="https://api.puzzlebot.top/", params=params).json()["data"]
    return ans
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
    # send_end_menu(user)
    return True
@app.route("/addchannel", methods=["POST"])
def addchannel():
    connection, cursor = get_connection()
    headers = request.headers
    groupname = None
    if headers.get("apikey") != internalapi:
        return jsonify({"Error": "Auth error"}), 404
    try:
        user = BeautifulSoup(headers.get("userid"), "html.parser").find("a").get_text()
        try:
            groupname = BeautifulSoup(headers.get("groupname"), "html.parser").find("pre").get_text()
        except:pass
        if groupname == None:
            groupname = headers.get("groupname")
        groupname = groupname.split("@")[-1]
        groupname = groupname.split("t.me/")[-1]
    except:
            return jsonify({"Error": "Not enough args"}), 404
    is_private = False
    raw = requests.get(url=f"https://t.me/s/{groupname}")
    newstext = None
    if raw.status_code == 200:
        parser = BeautifulSoup(raw.text, "html.parser")
        for i in range(-1, -20, -1):
            try:
                message = parser.find_all("div", class_="tgme_widget_message_bubble")[i]
                newstext = message.find_all("div", class_="tgme_widget_message_text js-message_text")[-1].get_text(strip=True)
                break
            except IndexError:
                continue
        if newstext is None:
            is_private = True
    if is_private == False:
        cursor.execute("SELECT channel FROM channels WHERE channel = ? AND userid = ?", (groupname, user))
        if cursor.fetchall() == []:
            cursor.execute("INSERT INTO channels (channel, userid) VALUES (?, ?)", (groupname, user))
            connection.commit()
        else:
            send_telegram_message(user,"Канал уже добавлен!")
            send_menu(user)
            return jsonify({"ok": "ok"}), 200
    else:
        send_telegram_message(user,"Канал приватный/не существует!")
        send_menu(user)
        return jsonify({"ok": "ok"}), 200
    send_telegram_message(user,f"Канал {groupname} добавлен!")
    send_menu(user)
    return jsonify({"ok": "ok"}), 200
@app.route("/getchannels", methods=["POST"])
def getchannels():
    connection, cursor = get_connection()
    headers = request.headers
    if headers.get("apikey") != internalapi:
        return jsonify({"Error": "Auth error"}), 404
    try:
        user = BeautifulSoup(headers.get("userid"), "html.parser").find("a").get_text()
    except:
        return jsonify({"Error": "Not enough args"}), 404
    channel_list = get_channels(user,cursor)
    msg = "Ваш список каналов:\n"
    if channel_list != []:
        for a in channel_list:
            msg += f"```@{a}```\n"
    else:
        msg = "У вас нет добавленных каналов"
    send_telegram_message(user,msg)
    return jsonify({"ok": "ok"}), 200
@app.route("/delchannel", methods=["POST"])
def delchannel():
    connection, cursor = get_connection()
    headers = request.headers
    groupname = None
    if headers.get("apikey") != internalapi:
        return jsonify({"Error": "Auth error"}), 404
    try:
        user = BeautifulSoup(headers.get("userid"), "html.parser").find("a").get_text()
        try:
            groupname = BeautifulSoup(headers.get("groupname"), "html.parser").find("pre").get_text()
        except:pass
        if groupname == None:
            groupname = headers.get("groupname")
        groupname = groupname.split("@")[-1]
        groupname = groupname.split("t.me/")[-1]
    except:
        return jsonify({"Error": "Not enough args"}), 404
    cursor.execute("SELECT channel FROM channels WHERE channel = ? AND userid = ?", (groupname, user))
    if cursor.fetchall() != []:
        cursor.execute("DELETE FROM channels WHERE channel = ? AND userid = ?", (groupname, user))
        cursor.execute("DELETE FROM newslist WHERE channel = ? AND userid = ?", (groupname, user))
        connection.commit()
        send_telegram_message(user,f"Канал {groupname} удален")
        send_menu(user)
    else:
        send_telegram_message(user,f"У вас нет добавленных каналов/канал не добавлен!")
        send_menu(user)
    return jsonify({"ok": "ok"}), 200
@app.route("/sendnews", methods=["POST"])
def sendnews():
    connection, cursor = get_connection()
    headers = request.headers
    if headers.get("apikey") != internalapi:
        return jsonify({"Error": "Auth error"}), 404
    callbyuser = headers.get("callbyuser") == "1"
    if headers.get("userid"):
        userid = BeautifulSoup(headers.get("userid"), "html.parser").find("a").get_text()
        if get_news_count(userid,cursor) >= 3:
            send_news(userid, cursor, connection)
        else:
            if callbyuser:
                send_telegram_message(userid,"Новостная лента еще не сформирована!")
                send_menu(userid)
    return jsonify({"ok": "ok"}), 200

@app.route("/fusion", methods=["GET"])
def fusion():
    try:
        headers = request.headers
        args = request.args
        
        if headers["apikey"] != internalapi:
            return jsonify({"Error": "Auth error"}), 404
        try:
            args["newstext"]
            args["postlen"]
        except:
            return jsonify({"Error": "Not enough args"}), 404
        news_text = args["newstext"]
        postlen = args["postlen"]
        if postlen == "1":
            chat_completion = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": "Ты — помощник по сокращению текста. Твоя задача — сокращать текст поста, но оставлять основной смысл. Сокращай до одного предложения."},
                    {"role": "user", "content": f"Прочитай текст и сократи его сохранив ключевые факты и контекст: {news_text}"}
                    ]
            )
            response_dict = chat_completion.to_dict() if hasattr(chat_completion, "to_dict") else dict(chat_completion)
            summary = response_dict["choices"][0]["message"]["content"]
        elif postlen == "2":
            chat_completion = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": "Ты — помощник по сокращению текста. Твоя задача — передавать содержание более полно, но в компактном формате. Изложи содержание с акцентом на ключевые моменты и факты, избегая лишних деталей."},
                    {"role": "user", "content": f"Прочитай текст и изложи его компактно, но с сохранением всех важных деталей и фактов: {news_text}"}
                    ]
            )
            response_dict = chat_completion.to_dict() if hasattr(chat_completion, "to_dict") else dict(chat_completion)
            summary = response_dict["choices"][0]["message"]["content"]
        elif postlen == "3":
            summary = news_text
        return jsonify({"fusion": summary}), 200
    except:pass
    return jsonify({"Error": "Undef error"}), 404
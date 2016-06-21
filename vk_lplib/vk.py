# coding: utf8
__author__ = 'stroum'

#
# Copyright (c) 2016 Alexander Rizaev
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import datetime
import time
import json
import traceback
from enum import IntEnum
import logging

import requests
import gevent

user_name_cache = {}
chat_name_cache = {}


def get_time(ts=0):
    if ts == 0:
        ts = time.time()
    return datetime.datetime.fromtimestamp(
        int(ts)
    ).strftime('%d/%m/%y %H:%M:%S')


class VK:
    handlers = {}
    CHAT_IDS = 2000000000

    def __init__(self, bot_id, token, wait=25):
        self.bot_id = bot_id
        self.token = token
        self.wait = wait

    def add_handler(self, on, func):
        self.handlers[on] = func
        return

    def query(self, method, params):
        params["access_token"] = self.token
        params["v"] = "5.37"
        r = requests.post("https://api.vk.com/method/{}".format(method, self.token), data=params)
        j = json.loads(r.text)
        logging.debug("{}({})".format(method, params))
        logging.debug(j)
        return j

    def send_message(self, who=0, message="", reply=0, attachment=""):
        data = {
            "message": message
        }

        if reply != 0:
            data["forward_messages"] = reply

        if len(attachment) > 0:
            data["attachment"] = attachment

        if who > self.CHAT_IDS:
            data["chat_id"] = who - self.CHAT_IDS
        else:
            data["user_id"] = who

        x = self.query("messages.send", data)
        time.sleep(1)
        return x

    def delete_message(self, msg_id):
        return self.query("messages.delete", params={
            "message_ids": [msg_id],
        })

    def get_longpoll_server(self):
        j = self.query("messages.getLongPollServer", {
            "use_ssl": 1
        })
        o = j["response"]
        return VK_LongPoll(o["ts"], o["server"], o["key"])

    def mark_as_read(self, peer_id):
        return self.query("messages.markAsRead", {"peer_id": peer_id})

    def get_sender_name(self, id):
        _type = "user"
        if int(id) > self.CHAT_IDS:
            id -= self.CHAT_IDS
            _type = "chat"
        if _type == "user":
            if id in user_name_cache:
                return user_name_cache[id]
            j = self.query("users.get", {
                "user_ids": id,
            })["response"]
            user_name_cache[id] = "{} {}".format(j[0]["first_name"], j[0]["last_name"])
            return user_name_cache[id]
        else:
            if id in chat_name_cache:
                return chat_name_cache[id]
            j = self.query("messages.getChat", {
                "chat_id": id,
            })["response"]
            chat_name_cache[id] = j["title"]
            return chat_name_cache[id]

    def listen_longpoll(self):
        def listen():
            server = self.get_longpoll_server()
            while True:
                r = requests.post("https://{}?act=a_check&key={}&ts={}&wait={}&mode=2".format(
                    server.server, server.key, server.ts, self.wait
                ))
                try:
                    j = json.loads(r.text)
                    logging.debug(j)

                    if "ts" not in j:
                        server = self.get_longpoll_server()
                        continue

                    server.ts = j["ts"]
                    if len(j["updates"]) == 0:
                        continue

                    def task(i):
                        updates = j["updates"][i]
                        type = updates[0]

                        logging.debug("executing task {}, type {}".format(i, type))

                        """0,$message_id,0 -- удаление сообщения с указанным local_id
                        1,$message_id,$flags -- замена флагов сообщения (FLAGS:=$flags)
                        2,$message_id,$mask[,$user_id] -- установка флагов сообщения (FLAGS|=$mask)
                        3,$message_id,$mask[,$user_id] -- сброс флагов сообщения (FLAGS&=~$mask)
                        4,$message_id,$flags,$from_id,$timestamp,$subject,$text,$attachments -- добавление нового сообщения
                        8,-$user_id,0 -- друг $user_id стал онлайн
                        9,-$user_id,$flags -- друг $user_id стал оффлайн ($flags равен 0, если пользователь покинул сайт (например, нажал выход) и 1, если оффлайн по таймауту (например, статус away))

                        51,$chat_id,$self -- один из параметров (состав, тема) беседы $chat_id были изменены. $self - были ли изменения вызываны самим пользователем
                        61,$user_id,$flags -- пользователь $user_id начал набирать текст в диалоге. событие должно приходить раз в ~5 секунд при постоянном наборе текста. $flags = 1
                        62,$user_id,$chat_id -- пользователь $user_id начал набирать текст в беседе $chat_id.
                        70,$user_id,$call_id -- пользователь $user_id совершил звонок имеющий идентификатор $call_id, дополнительную информацию о звонке можно получить используя метод voip.getCallInfo.
                        80,$count,0 — новый счетчик непрочитанных в левом меню стал равен $count.
                        114,{ $peerId, $sound, $disabled_until } — изменились настройки оповещений, где peerId — $peer_id чата/собеседника, sound — 1 || 0, включены/выключены звуковые оповещения, disabled_until — выключение оповещений на необходимый срок (-1: навсегда, 0: включены, other: timestamp, когда нужно включить).

                        """
                        if "on_typing" in self.handlers:
                            if type == 61:
                                # user_id, flags
                                self.handlers["on_typing"](user_id=updates[1], flags=updates[2])
                            if type == 62:
                                # user_id, chat_id
                                self.handlers["on_typing"](user_id=updates[1], chat_id=updates[2])

                        if "on_message" in self.handlers:
                            if type == 4:
                                msg_id = updates[1]
                                flags = updates[2]
                                from_id = updates[3]
                                timestamp = updates[4]
                                # subject = updates[5]
                                text = updates[6]

                                try:
                                    from_uid = updates[7]["from"]
                                except Exception as e:
                                    from_uid = from_id
                                self.handlers["on_message"](msg_id, flags, from_id, timestamp, text, from_uid)

                    # WTF???
                    threads = [gevent.spawn(task, i) for i in range(len(j["updates"]))]
                    gevent.joinall(threads)
                except Exception as e:
                    print(traceback.format_exc())

        listen()


class VK_LongPoll:
    def __init__(self, ts, server, key):
        self.ts = ts
        self.server = server
        self.key = key


class Flags(IntEnum):
    """
    +1		UNREAD	сообщение непрочитано
    +2		OUTBOX	исходящее сообщение
    +4		REPLIED	на сообщение был создан ответ
    +8		IMPORTANT	помеченное сообщение
    +16		CHAT	сообщение отправлено через чат
    +32		FRIENDS	сообщение отправлено другом
    +64		SPAM	сообщение в папке "Спам"
    +128	DELЕTЕD	сообщение удалено (в корзине)
    +256	FIXED	сообщение проверено пользователем на спам
    +512	MEDIA	сообщение содержит медиаконтент
    +1024	ATTACH	к сообщению прикреплен файл
    +2048	EMAIL	сообщение получено или отправлено по электропочте
    +4096	NOCHAT	сообщение не должно выводиться в чате
    +8192	MULTICHAT	сообщение отправленное в мультичат (несколько собеседников, peer_id > 2e9)
    """

    UNREAD = 1
    OUTBOX = 2
    REPLIED = 4
    IMPORTANT = 8
    CHAT = 16
    FRIENDS = 32
    SPAM = 64
    DELETED = 128
    FIXED = 256
    MEDIA = 512
    ATTACH = 1024
    EMAIL = 2048
    NOCHAT = 4096
    MULTICHAT = 8192

    @classmethod
    def get(cls, number):
        flags = []
        flags_a = flags.append
        for mask in cls:
            if number & mask == mask:
                flags_a(mask)
        return flags

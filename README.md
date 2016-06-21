# vk_lplib
Библиотека для работы с VK Long Poll

## Как использовать:
```python
from vk_lplib.vk import VK, Flags

def on_message(msg_id, flags, from_id, ts, text, from_uid):
    # пример использования флагов
    if Flags.MULTICHAT and Flags.FRIENDS in Flags.get(flags):
        pass
    pass


v = VK(1, "TOKEN") # Где 1 - id пользователя
v.add_handler('on_message', on_message)
v.listen_longpoll()
```

## Список методов:
```
query(method, params)
send_message(who=0, message="", reply=0, attachment="") # who = кому, reply = ответ на msg_id
delete_message(msg_id) # удалить сообщение с msg_id
mark_as_read(peer_id) # отметить как прочитанное
get_sender_name(id) # возвращает ИМЯ ФАМИЛИЯ или название чата откуда пришло сообщение
```

## Установка:
```sh
pip install git+https://github.com/stroum/vk_lplib.git
```

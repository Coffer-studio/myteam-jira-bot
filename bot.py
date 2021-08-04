import json
from bot.bot import Bot
from bot.handler import MessageHandler, BotButtonCommandHandler
from jira import JIRA
import requests
import io
import sqlite3

con = sqlite3.connect('cofferbot.db')


TOKEN = "" #your token here

bot = Bot(token=TOKEN)
cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, email text, jid text, state int)")

jira_options = {'server': ''}
login = ''
token = ''
jira = JIRA(options=jira_options, basic_auth=(login, token))

peoples = {"v@coffer.studio" : "(5fd3612591bb2e0108dabe17)", #Вадим
"kk@coffer.studio" : "(60913b82f0db130069b9b9f0)", #Костя
"k@coffer.studio" : "(5fa926d10b4e3a006bf99508)", #Коля
"d@coffer.studio" : "(5fb67a7531795a006f3cc4d8)", #Даня
"kt@coffer.studio" : "(60e44c3fc0db53006aabbb0d)", #Костя Тараскин
"a.voronin@coffer.studio" : "(5fafe64db5dd5a007124dc2c)", #Леша
"e@coffer.studio" : "(5fdb8231d364960139079541)", #Женя
"dk@coffer.studio" : "(5fa86ed144658b0071756481)", #Дарья
"s@coffer.studio" : "(5fa86ed144658b0071756481)", #Сергей
}

jqlFilters = ['AND status in ("In Progress", "To Do", "на оценку") AND priority = Highest order by created DESC', 
'AND status in ("In Progress", "To Do", "на оценку") AND priority = High order by created DESC',
'AND status in ("In Progress") order by created DESC',
'AND status in ("To Do") order by created DESC',
'AND status in ("на оценку") order by created DESC',
]

isProblem = False
isEstimate = False

def split(word): 
    return [char for char in word]  

def currentIssue(people = 0):
    found = False
    for i in range(len(jqlFilters)):
        if found==False:
            issues_list = findIssue(people, i)
            if type(issues_list) is str:
                return issues_list
            else:
                if issues_list["total"]>0:
                    found = True
                    return issues_list["issues"][0]
        else:
            i = len(jqlFilters)
    return "Новые задачи не найдены"

def findIssue(email = 0, priority = 0):
    if email==0:
        return "email не определен"
    else:
        id = 0
        for jemail, jid in peoples.items():
            if jemail == email:
                id = jid
        if id==0:
            return "id не определен"
        else:
            jql = 'assignee in '+id+jqlFilters[priority]
            issues_list = jira.search_issues(jql, maxResults=1,fields="attachment, summary, description", expand=True, json_result=True)
            return issues_list

def getIssue(bot, event):
    issue=currentIssue(event.from_chat)
    print(issue)
    if type(issue) is str:
        bot.send_text(chat_id=event.from_chat, text=issue)
        bot.send_text(chat_id="s@coffer.studio", text="У "+event.from_chat+" "+issue)
    else:
        print(1)
        if "key" in issue:
            data="Текущая задача: <b>"+issue["key"]+"</b><ol>"
            print(data)
            if "fields" in issue:
                if "summary" in issue["fields"]:
                    data+="<li>Название задачи: "+issue["fields"]["summary"]+"</li>"
                if "description" in issue["fields"] and issue["fields"]["description"] is not None:
                    data+="<li>Описание задачи: "+issue["fields"]["description"].replace('/n', '').replace('[', '').replace(']', '')+"</li>"
                if "attachment" in issue["fields"]:
                    if len(issue["fields"]["attachment"])>0:
                        data+="<li>Есть вложения, будут отправлены отдельно</li>"
            data+="</ol>"
        else:
            data="Новые задачи не найдены"
        print(data)
        bot.send_text(chat_id=event.from_chat,
        text=data,
        parse_mode="HTML",
        inline_keyboard_markup="{}".format(json.dumps([[
                        {"text": "Открыть", "url": "https://cofferstudio.atlassian.net/browse/"+issue["key"]},
                        {"text": "Оценить", "callbackData": "call_back_id_1", "style": "base"},
                        {"text": "Есть проблема", "callbackData": "call_back_id_2", "style": "attention"},
                        {"text": "Завершить", "callbackData": "call_back_id_3", "style": "primary"}
                    ]]))
        )
    if "fields" in issue:
        if "attachment" in issue["fields"]:
            for i in range(len(issue["fields"]["attachment"])):
                r = requests.get(issue["fields"]["attachment"][i]["content"], auth=(login, token), stream=True)
                bot.send_file(chat_id=event.from_chat, file=r.content)

def problemWorker(bot, event):
    issue=currentIssue(event.from_chat)
    data="Ошибка"
    if type(issue) is str:
        data=issue
    else:
        if "key" in issue:
            data="У "+event.from_chat+" проблема с задачей "+issue["key"]+". Сообщение: "+event.text
    bot.send_text(event.from_chat, text="Сообщение отправлено")
    bot.send_text("s@coffer.studio", text=data)


def setEstimate(bot, event):
    setState(bot, event, 3)
    try:
        estimate = int(event.text)
    except:
        print('некорректная оценка')
    if type(estimate) is not int:
        bot.send_text(event.from_chat, text="Некорретное значение оценки. Нужно целое число")
    else:
        issue=currentIssue(event.from_chat)
        if type(issue) is str:
            data=issue
        else:
            if "key" in issue:
                jira.issue(issue["key"]).update({"customfield_10016":estimate})
                data="Оценка установлена"
        bot.send_text(event.from_chat, text=data)

def taskDone(bot, event):
    url = split(event.data["message"]["parts"][0]["payload"][0][0]["url"])
    tempSlash = []
    for i in range(len(url)):
        if str(url[i])=="/":
            tempSlash.append(i)
    if len(tempSlash)>0:
        tempSlash=max(tempSlash)+1
        while tempSlash>0:
            url.pop(0)
            tempSlash = tempSlash-1
        key = ''.join(url)
        try:
            jira.transition_issue(key, "ТЕСТ")
            getIssue(bot, event)
        except Exception as e:
            print(e)
            bot.send_text(chat_id=event.from_chat,text="Ошибка при изменении статуса")
    else:
        bot.send_text(chat_id=event.from_chat,text="Ошибка при закрытии задачи")

def buttons_answer_cb(bot, event):
    if event.data['callbackData'] == "call_back_id_1":
        bot.answer_callback_query(
            query_id=event.data['queryId'],
            text="Укажите оценку в сторипоинтах в сообщении",
            show_alert=False
        )
        issue=currentIssue(event.from_chat)
        if type(issue) is str:
            data=issue
        else:
            if "key" in issue:
                data = "Укажите оценку для задачи "+issue["key"]+" в сообщении. Нужна целая величина, например '5'"
        bot.send_text(chat_id=event.from_chat,text=data)
        setState(bot, event, 3)

    elif event.data['callbackData'] == "call_back_id_2":
        bot.answer_callback_query(
            query_id=event.data['queryId'],
            text="Опишите проблему в сообщении",
            show_alert=False
        )
        issue=currentIssue(event.from_chat)
        if type(issue) is str:
            data=issue
        else:
            if "key" in issue:
                data = "Опишите проблему по задаче "+issue["key"]+" в сообщении"
        bot.send_text(chat_id=event.from_chat,text=data)
        setState(bot, event, 2)

    elif event.data['callbackData'] == "call_back_id_3":
        taskDone(bot, event)
        bot.answer_callback_query(
            query_id=event.data['queryId'],
            text="Задача завершена.",
            show_alert=True
        )
        getIssue(bot, event)

def getUser(bot, event):
    email = event.from_chat
    con = sqlite3.connect('cofferbot.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE email = '"+email+"'")
    user = cur.fetchall()
    if isinstance(user, list) and len(user)>0:
        user = user[0]
    userId = 0
    if not user:
        id = 0
        for jemail, jid in peoples.items():
            if jemail == email:
                id = jid
        if id==0:
            bot.send_text(chat_id=event.from_chat,text="id не определен")
        cur.execute("INSERT INTO users VALUES (?, ?, ?, ?)",(None, email, id,1))
        con.commit()
        message_cb(bot, event)
    else:
        userId = user[2]
    return user

def setState(bot, event, state=1):
    user = getUser(bot, event)
    con = sqlite3.connect('cofferbot.db')
    cur = con.cursor()
    if not user:
        bot.send_text(chat_id=event.from_chat,text="Ошибка при изменении статуса")
    else:
        cur.execute("UPDATE users SET state = ? WHERE email = ?",(state, user[1]))
        con.commit()
    
def message_cb(bot, event):
    user = getUser(bot, event)
    if user[3] == 2:
        problemWorker(bot, event)
        setState(bot, event, 1)
    elif user[3] == 3:
        setEstimate(bot, event)
        setState(bot, event, 1)
    else:
       getIssue(bot, event)
    

bot.dispatcher.add_handler(MessageHandler(callback=message_cb))
bot.dispatcher.add_handler(BotButtonCommandHandler(callback=buttons_answer_cb))
bot.start_polling()
bot.idle()  
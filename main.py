import os
import json
import re

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, CallbackContext, CommandHandler
import numpy
import cv2

def get_login_key(html):
    fullpage = BeautifulSoup(html, "html.parser")
    h = fullpage.find("head")
    capture = h.find("script", text=re.compile("antibot")).string.strip()
    start = capture.find("\"key\":") + 7 # "key":"
    end   = capture.find("\"", start)
    return capture[start:end]

def find_videos(html):
    fullpage = BeautifulSoup(html, "html.parser")
    videoPreviews = fullpage.find_all("div", class_ = "node node-video node-teaser node-teaser clearfix")

    videos = set()
    for videoPreview in videoPreviews:
        
        a_tags = videoPreview.find_all("a")

        for tag in a_tags:
            if "/videos/" in tag.get("href"):
                id = tag.get("href").split("/")[-1].split("?")[0]
                title = tag.string
            elif "/users/" in tag.get("href"):
                user = tag.get("href").split("/")[-1].split("?")[0]
                user_display = tag.string

        videos.add((id, title, user, user_display))

    return videos

def load_sent_list():
    if (os.path.exists("sent_list.json") == False):
        with open("sent_list.json", "w+") as f: # Create if not exist
            json.dump([], f)

    with open("sent_list.json", "r") as f:
        return json.load(f)

def save_sent_list(sent_list):
    with open("sent_list.json", "w") as f:
            json.dump(sent_list, f)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36',
    }

loginUrl ='https://ecchi.iwara.tv/user/login'
loginPageHtml = requests.get(loginUrl, headers=headers).text
subUrl = 'https://ecchi.iwara.tv/subscriptions'
videoUrl = 'https://ecchi.iwara.tv/videos'
userUrl =  'https://ecchi.iwara.tv/users'
videoAPIUrl = 'https://ecchi.iwara.tv/api/video'

config = json.load(open("config.json"))

data = {
    'name':config["user_info"]["user_name"],
    'pass':config["user_info"]["password"],
    'form_build_id':'form-dummy',
    'form_id':'user_login',
    'antibot_key': get_login_key(loginPageHtml),
    'op': "ログイン",
}

#Setup telegram bot
print("Connecting to telegram bot...")
updater = Updater(config["telegram_info"]["token"], base_url = config["telegram_info"]["APIServer"])
botInfo = updater.bot.getMe()
print("Connected to telegram bot: " + botInfo.first_name)

#Load sent list
print("Loading sent list...")
sent_list = load_sent_list()

#Main Session
session = requests.Session()

#Login
print("Login...")
session.post(loginUrl, data=data, headers=headers)

#Processing Videos
subPageHtml = session.get(subUrl, headers = headers).text

videos = find_videos(subPageHtml)

for video in videos:
    
    id = video[0]
    title = video[1]
    user = video[2]
    user_display = video[3]

    print("Found video ID {}: {} by {}".format(id, title, user_display))

    if id in sent_list:
        print("Video ID {} Already sent, skipped. ".format(id))
        continue

    resourceInfos = json.loads(session.get(videoAPIUrl + "/" + id, headers = headers).text)

    for resourceInfo in resourceInfos:

        if resourceInfo["resolution"] == "Source":

            link = "https:" + resourceInfo["uri"]
            file_type = resourceInfo["mime"][6:] # Exclude "video/"

            videoFileName = id + '.' + file_type
            
            if (os.path.exists(videoFileName)):
                print("Video ID {} Already downloaded, skipped downloading. ".format(id))
                break

            print("Downloading video {} (ID: {}) ...".format(title, id))
            with open(videoFileName, "wb") as f:
                for chunk in requests.get(link, headers = headers).iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        f.flush()
            break

    # Sending video to telegram
    print("Sending video ID {} to telegram...".format(id))

    cap = cv2.VideoCapture(videoFileName)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)

    updater.bot.send_video(chat_id=config["telegram_info"]["chat_id"], 
                        video = open(videoFileName, 'rb'), 
                        supports_streaming = True, 
                        timeout = 300, 
                        height = height, 
                        width = width,
                        caption = """<a herf="{}/{}/">{}</a> by: <a herf="{}/{}/">{}</a>""".format(videoUrl, id, title, userUrl, user, user_display),
                        parse_mode = "HTML")
    
    #Save sent list
    print("Saving sent list...")
    sent_list.append(id)
    save_sent_list(sent_list)



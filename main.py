import os
import sys
import json
import re

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, CallbackContext, CommandHandler
import numpy
import cv2

class IwaraTgBot:
    def __init__(self):
        self.headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36',
        }

        self.loginUrl ='https://ecchi.iwara.tv/user/login'
        self.subUrl = 'https://ecchi.iwara.tv/subscriptions'
        self.videoUrl = 'https://ecchi.iwara.tv/videos'
        self.userUrl =  'https://ecchi.iwara.tv/users'
        self.videoAPIUrl = 'https://ecchi.iwara.tv/api/video'

        #Load Config
        self.config = json.load(open("config.json"))

        #Setup telegram bot
        print("Connecting to telegram bot...")
        self.updater = Updater(self.config["telegram_info"]["token"], base_url = self.config["telegram_info"]["APIServer"])
        botInfo = self.updater.bot.getMe()
        print("Connected to telegram bot: " + botInfo.first_name)

        #Main Session
        self.session = requests.Session()

    def login(self):

        def get_login_key(html):
            fullpage = BeautifulSoup(html, "html.parser")
            h = fullpage.find("head")
            capture = h.find("script", text=re.compile("antibot")).string.strip()
            start = capture.find("\"key\":") + 7 # "key":"
            end   = capture.find("\"", start)
            return capture[start:end]


        loginPageHtml = requests.get(self.loginUrl, headers=self.headers).text
        
        data = {
            'name':self.config["user_info"]["user_name"],
            'pass':self.config["user_info"]["password"],
            'form_build_id':'form-dummy',
            'form_id':'user_login',
            'antibot_key': get_login_key(loginPageHtml),
            'op': "ログイン",
        }

        #Login
        print("Login...")
        self.session.post(self.loginUrl, data=data, headers=self.headers)

    def find_videos(self, html):
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

    def download_video(self, id):
        resourceInfos = json.loads(self.session.get(self.videoAPIUrl + "/" + id, headers = self.headers).text)

        for resourceInfo in resourceInfos:

            if resourceInfo["resolution"] == "Source":

                link = "https:" + resourceInfo["uri"]
                file_type = resourceInfo["mime"][6:] # Exclude "video/"

                videoFileName = id + '.' + file_type
                
                if (os.path.exists(videoFileName)):
                    print("Video ID {} Already downloaded, skipped downloading. ".format(id))
                    break

                print("Downloading video ID: {} ...".format(id))
                with open(videoFileName, "wb") as f:
                    for chunk in requests.get(link, headers = self.headers).iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            f.flush()
                break
        
        return videoFileName

    def send_video(self, path, id, title, user, user_display):
        # Sending video to telegram
        print("Sending video {} to telegram...".format(path))

        cap = cv2.VideoCapture(path)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        duration = int(int(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000) # mSec to Sec

        self.updater.bot.send_video(chat_id=self.config["telegram_info"]["chat_id"], 
                            video = open(path, 'rb'), 
                            supports_streaming = True, 
                            timeout = 300, 
                            height = height, 
                            width = width,
                            duration = duration,
                            caption = """<a href="{}/{}/">{}</a> by: <a href="{}/{}/">{}</a>""".format(self.videoUrl, id, title, self.userUrl, user, user_display),
                            parse_mode = "HTML")

    def download_sub(self):

        def load_sent_list():
            if (os.path.exists("sent_list.json") == False):
                with open("sent_list.json", "w+") as f: # Create if not exist
                    json.dump([], f)

            with open("sent_list.json", "r") as f:
                return json.load(f)

        def save_sent_list(sent_list):
            with open("sent_list.json", "w") as f:
                    json.dump(sent_list, f)

        #Load sent list
        print("Loading sent list...")
        self.sent_list = load_sent_list()

        self.login()

        #Finding Videos
        subPageHtml = self.session.get(self.subUrl, headers = self.headers).text
        videos = self.find_videos(subPageHtml)

        for video in videos:
            
            id = video[0]
            title = video[1]
            user = video[2]
            user_display = video[3]

            print("Found video ID {}: {} by {}".format(id, title, user_display))

            if id in self.sent_list:
                print("Video ID {} Already sent, skipped. ".format(id))
                continue

            videoFileName = self.download_video(id)
            self.send_video(videoFileName, id, title, user, user_display)
            
            #Save sent list
            print("Saving sent list...")
            self.sent_list.append(id)
            save_sent_list(self.sent_list)

            #Delete the video form server
            os.remove(videoFileName)

if __name__ == '__main__':
    args = sys.argv

    def usage():
        print("""
Usage: python {} <option>
option can be:
\t dlsub: download the latest page of your subscription list
        """.format(args[0]))
        exit(1)

    if (len(args) != 2): usage()

    bot = IwaraTgBot()

    if (args[1] == "dlsub"): bot.download_sub()
    else: usage()

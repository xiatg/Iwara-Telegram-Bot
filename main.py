from distutils.command.upload import upload
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
        self.newUrl = 'https://ecchi.iwara.tv/videos-3'

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
        """ Login to iwara.tv """

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
        print("Logging in...")
        self.session.post(self.loginUrl, data=data, headers=self.headers)

    def get_video_info(self, id):
        """
        Get video info by id.
        The info is returned as a list.
        """
        videoHTML = self.session.get(self.videoUrl + '/' + id, headers = self.headers).text
        videoPage = BeautifulSoup(videoHTML, "html.parser")

        uploadInfo = videoPage.find("div", class_ = "submitted")
        title = uploadInfo.find("h1", class_ = "title").string
        userA = uploadInfo.find("a", class_ = "username")
        user_display = userA.string
        user = userA.get("href").split("/")[-1].split("?")[0]

        description = videoPage.find("div", class_ = "field-item even").text

        a_tags = videoPage.find_all("a")

        v_tags = []
        for tag in a_tags:
            if tag.get("href") != None:
                if "categories" in tag.get("href"):
                    v_tag = tag.string.replace(' ', '_')
                    v_tags.append(v_tag)

        thumbUrl = "http:" + videoPage.find(id = "video-player").get("poster")
        thumbFileName = id + ".jpg"

        if (os.path.exists(thumbFileName)):
            print("Thumbnail ID {} Already downloaded, skipped downloading. ".format(id))
        else:
            print("Downloading thumbnail for video ID: {} ...".format(id))
            with open(thumbFileName, "wb") as f:
                        for chunk in requests.get(thumbUrl, headers = self.headers).iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                                f.flush()

        return [title, user, user_display, description, v_tags, thumbFileName]

    def find_videos(self, html):
        fullpage = BeautifulSoup(html, "html.parser")
        videoPreviews = fullpage.find_all("div", class_ = "node node-video node-teaser node-teaser clearfix")

        ids = set()
        for videoPreview in videoPreviews:
            
            a_tags = videoPreview.find_all("a")

            for tag in a_tags:
                if "/videos/" in tag.get("href"):
                    id = tag.get("href").split("/")[-1].split("?")[0]
                    ids.add(id)

        return ids

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

    def send_video(self, path, id = "", title = "", user = "", user_display = "", description = "", v_tags = [], thumbPath = ""):
        # Sending video to telegram
        print("Sending video {} to telegram...".format(path))

        cap = cv2.VideoCapture(path)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps

        caption = """
<a href="{}/{}/">{}</a>
by: <a href="{}/{}/">{}</a>
""".format(self.videoUrl, id, title, self.userUrl, user, user_display)
        for v_tag in v_tags:
            caption += " #" + v_tag

        print(caption)

        msg = None

        if (os.path.exists(thumbPath) == False):
            msg = self.updater.bot.send_video(chat_id=self.config["telegram_info"]["chat_id"], 
                                video = open(path, 'rb'), 
                                supports_streaming = True, 
                                timeout = 300, 
                                height = height, 
                                width = width,
                                duration = duration,
                                caption = caption,
                                parse_mode = "HTML")
        else:
            msg = self.updater.bot.send_video(chat_id=self.config["telegram_info"]["chat_id"], 
                                video = open(path, 'rb'), 
                                supports_streaming = True, 
                                timeout = 300, 
                                height = height, 
                                width = width,
                                duration = duration,
                                caption = caption,
                                thumb = open(thumbPath, 'rb'), # Thumbnail
                                parse_mode = "HTML")
            os.remove(thumbPath)

        #Delete the video form server
        os.remove(path)

        return msg.message_id

    def download_new(self):

        self.login()

        #Get page
        print("Getting page...")
        html = self.session.get(self.newUrl, headers = self.headers).text

        #Find videos
        ids = self.find_videos(html)

        #Download videos
        for id in ids:
            video_info = self.get_video_info(id)
            videoFileName = self.download_video(id)

            title = video_info[0]
            user = video_info[1]
            user_display = video_info[2]
            description = video_info[3]
            v_tags = video_info[4]
            thumbFileName = video_info[5]

            self.send_video(videoFileName, id, title, user, user_display, description, v_tags, thumbFileName)

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
        ids = self.find_videos(subPageHtml)

        for id in ids:
            
            print("Found video ID {}".format(id))

            if (id in self.sent_list):
                print("Video ID {} Already sent, skipped. ".format(id))
                continue

            video_info = self.get_video_info(id)
            videoFileName = self.download_video(id)

            title = video_info[0]
            user = video_info[1]
            user_display = video_info[2]
            description = video_info[3]
            v_tags = video_info[4]
            thumbFileName = video_info[5]

            self.send_video(videoFileName, id, title, user, user_display, description, v_tags, thumbFileName)
            
            #Save sent list
            print("Saving sent list...")
            self.sent_list.append(id)
            save_sent_list(self.sent_list)

if __name__ == '__main__':
    args = sys.argv

    def usage():
        print("""
Usage: python {} <option>
option can be:
\t dlsub: download the latest page of your subscription list
\t dlnew: download the latest page of the new videos
        """.format(args[0]))
        exit(1)

    if (len(args) != 2): usage()

    bot = IwaraTgBot()

    if (args[1] == "dlsub"): bot.download_sub()
    elif (args[1] == "dlnew"): bot.download_new()
    else: usage()

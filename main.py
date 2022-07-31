import os
import sys
import json
import re
import time
from datetime import datetime
import sqlite3

import requests
from bs4 import BeautifulSoup
from telegram.ext import Updater
import cv2

class IwaraTgBot:
    def __init__(self, ecchi = False):
        self.headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36',
        }

        if (ecchi):
            self.loginUrl ='https://ecchi.iwara.tv/user/login'
            self.subUrl = 'https://ecchi.iwara.tv/subscriptions'
            self.videoUrl = 'https://ecchi.iwara.tv/videos'
            self.userUrl =  'https://ecchi.iwara.tv/users'
            self.videoAPIUrl = 'https://ecchi.iwara.tv/api/video'
            self.newUrl = 'https://ecchi.iwara.tv/videos-3'
        else:
            self.loginUrl ='https://iwara.tv/user/login'
            self.subUrl = 'https://iwara.tv/subscriptions'
            self.videoUrl = 'https://iwara.tv/videos'
            self.userUrl =  'https://iwara.tv/users'
            self.videoAPIUrl = 'https://iwara.tv/api/video'
            self.newUrl = 'https://iwara.tv/videos-3'

        #Load Config
        self.config = json.load(open("config.json"))

        #Init DB
        self.DBpath = "IwaraTgDB.db"

        #Setup telegram bot
        print("Connecting to telegram bot...")
        self.updater = Updater(self.config["telegram_info"]["token"], base_url = self.config["telegram_info"]["APIServer"])
        self.bot = self.updater.bot
        botInfo = self.bot.getMe()
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

    def connect_DB(self):
        conn = sqlite3.connect(self.DBpath)
        c = conn.cursor()
        return c, conn
    
    def close_DB(self, conn):
        conn.commit()
        conn.close()

    def init_DB(self, tableName):
        c, conn = self.connect_DB()

        c.execute("""CREATE TABLE IF NOT EXISTS """ + tableName + """ (
            id TEXT PRIMARY KEY,
            title TEXT,
            user TEXT,
            user_display TEXT,
            date TEXT,
            chat_id INTEGER,
            views INTEGER,
            likes INTEGER
        )""")

        self.close_DB(conn)

    def save_video_info(self, tableName, id, title = None, user = None, user_display = None, chat_id = None, views = None, likes = None):
        """
        Save video info to database.
        """
        c, conn = self.connect_DB()

        c.execute("""INSERT INTO """ + tableName + """ (id, title, user, user_display, date, chat_id, views, likes) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (id, title, user, user_display, datetime.now().strftime("%Y%m%d"), chat_id, views, likes,))
        
        self.close_DB(conn)

    def is_video_exist(self, tableName, id):
        c, conn = self.connect_DB()

        c.execute("SELECT * FROM " + tableName + " WHERE id = ?", (id,))
        if c.fetchone() is None:
            result = False
        else:
            result =  True

        self.close_DB(conn)

        return result

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

        v_tags = [user_display.replace(' ', '_').replace('\u3000', '_')]
        for tag in a_tags:
            if tag.get("href") != None:
                if "categories" in tag.get("href"):
                    v_tag = tag.string.replace(' ', '_')
                    v_tags.append(v_tag)

        try:
            thumbUrl = "http:" + videoPage.find(id = "video-player").get("poster")
        except:
            print("The video is hosted by YouTube. No thumbnail is available on iwara.tv.")
        
        thumbFileName = id + ".jpg"

        if (os.path.exists(thumbFileName)):
            print("Thumbnail ID {} Already downloaded, skipped downloading. ".format(id))
        else:
            try:
                print("Downloading thumbnail for video ID: {} from {}...".format(id, thumbUrl))
                with open(thumbFileName, "wb") as f:
                            for chunk in requests.get(thumbUrl, headers = self.headers).iter_content(chunk_size=1024):
                                if chunk:
                                    f.write(chunk)
                                    f.flush()
            except:
                print("Failed to download thumbnail. Skipping...")
                if (os.path.exists(thumbFileName)):
                    os.remove(thumbFileName)

        return [title, user, user_display, description, v_tags, thumbFileName]

    def get_video_stat(self, id):
        """
        Get video stat by id.
        The stat is returned as a list.
        """
        videoHTML = self.session.get(self.videoUrl + '/' + id, headers = self.headers).text
        videoPage = BeautifulSoup(videoHTML, "html.parser")

        stats = videoPage.find("div", class_ = "node-views").text.replace("\n", "").replace("\t", "").replace(",", "").split(" ")
        likes = int(stats[1])
        views = int(stats[2])

        return [likes, views]

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
        try:
            return videoFileName
        except: # Download Failed
            return None

    def get_youtube_id(self, id):
        videoHTML = self.session.get(self.videoUrl + '/' + id, headers = self.headers).text
        videoPage = BeautifulSoup(videoHTML, "html.parser")
        video_frame = videoPage.find("iframe")
        video_source = video_frame.get("src")
        start = video_source.find("embed/") + 6
        end = video_source.find("?")
        video_id = video_source[start:end]
        return video_id
        
    def send_yt_link(self, yt_id, id = "", title = "", user = "", user_display = "", description = "", v_tags = []):
        
        yt_link = "https://www.youtube.com/watch?v=" + yt_id

        caption = yt_link + """
<a href="{}/{}/">{}</a>
by: <a href="{}/{}/">{}</a>
""".format(self.videoUrl, id, title, self.userUrl, user, user_display)
        for v_tag in v_tags:
            caption += " #" + v_tag

        print(caption)

        msg = None

        msg = self.bot.send_message(chat_id = self.config["telegram_info"]["chat_id"], text = caption, parse_mode = "HTML")

        return msg.message_id

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
            msg = self.bot.send_video(chat_id=self.config["telegram_info"]["chat_id"], 
                                video = open(path, 'rb'), 
                                supports_streaming = True, 
                                timeout = 300, 
                                height = height, 
                                width = width,
                                duration = duration,
                                caption = caption,
                                parse_mode = "HTML")
        else:
            msg = self.bot.send_video(chat_id=self.config["telegram_info"]["chat_id"], 
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

    def send_description(self, user, user_display, description):
        msg_t = self.bot.send_message(chat_id=self.config["telegram_info"]["chat_id_discuss"], text = "Getting message ID...")
        self.bot.delete_message(chat_id=self.config["telegram_info"]["chat_id_discuss"], message_id= msg_t.message_id)

        print(msg_t.message_id)

        msg_description = """
<a href="{}/{}/">{}</a> said:
""".format(self.userUrl, user, user_display) + description

        self.bot.send_message(chat_id=self.config["telegram_info"]["chat_id_discuss"], text = msg_description, parse_mode = "HTML", reply_to_message_id=msg_t.message_id - 1)

    def download_new(self):

        tableName = "videosNew"

        self.init_DB(tableName)
        
        self.login()

        #Get page
        print("Getting page...")
        html = self.session.get(self.newUrl, headers = self.headers).text

        #Find videos
        ids = self.find_videos(html)

        #Download videos
        for id in ids:

            print("Found video ID {}".format(id))

            if (self.is_video_exist(tableName, id)):
                print("Video ID {} Already sent, skipped. ".format(id))
                continue

            video_info = self.get_video_info(id)

            yt_id = None

            try: # if the video is hosted on YouTube
                yt_id = self.get_youtube_id(id)
            except:
                videoFileName = self.download_video(id)

                if (videoFileName == None):
                    print("Video ID {} Download failed, skipped. ".format(id))
                    continue

            title = video_info[0]
            user = video_info[1]
            user_display = video_info[2]
            description = video_info[3]
            v_tags = video_info[4]
            thumbFileName = video_info[5]

            if (yt_id == None):
                msg_id = self.send_video(videoFileName, id, title, user, user_display, description, v_tags, thumbFileName)
            else:
                msg_id = self.send_yt_link(yt_id, id, title, user, user_display, description, v_tags)

            self.save_video_info(tableName, id, title, user, user_display, msg_id)

            time.sleep(5) # Wait for telegram to forward the video to the group
            self.send_description(user = user, user_display = user_display, description = description)

    def download_sub(self):

        tableName = "videosSub"

        self.init_DB(tableName)

        self.login()

        #Finding Videos
        subPageHtml = self.session.get(self.subUrl, headers = self.headers).text
        ids = self.find_videos(subPageHtml)

        for id in ids:
            
            print("Found video ID {}".format(id))

            if (self.is_video_exist(tableName, id)):
                print("Video ID {} Already sent, skipped. ".format(id))
                continue

            video_info = self.get_video_info(id)
            
            yt_id = None

            try: # if the video is hosted on YouTube
                yt_id = self.get_youtube_id(id)
            except:
                videoFileName = self.download_video(id)

                if (videoFileName == None):
                    print("Video ID {} Download failed, skipped. ".format(id))
                    continue

            title = video_info[0]
            user = video_info[1]
            user_display = video_info[2]
            description = video_info[3]
            v_tags = video_info[4]
            thumbFileName = video_info[5]

            if (yt_id == None):
                msg_id = self.send_video(videoFileName, id, title, user, user_display, description, v_tags, thumbFileName)
            else:
                msg_id = self.send_yt_link(yt_id, id, title, user, user_display, description, v_tags)
            
            self.save_video_info(tableName, id, title, user, user_display, None)

if __name__ == '__main__':
    args = sys.argv

    def usage():
        print("""
Usage: python {} <option>
option can be:
\t -n/normal: normal mode
\t -e/ecchi: ecchi mode (NSFW)
\t \t -n/-e dlsub: download the latest page of your subscription list
\t \t -n/-e dlnew: download the latest page of the new videos
        """.format(args[0]))
        exit(1)

    if (len(args) < 2 or len(args) > 3): usage()

    if (args[1] == "-n" or args[1] == "normal"): bot = IwaraTgBot()
    elif (args[1] == "-e" or args[1] == "ecchi"): bot = IwaraTgBot(ecchi = True)
    else: usage()

    if (args[2] == "dlsub"): bot.download_sub()
    elif (args[2] == "dlnew"): bot.download_new()
    else: usage()

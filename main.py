import os
import sys
import json
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import sqlite3

from telegram.ext import Updater
import cv2

from typing import Optional, List

from api_client import ApiClient

class IwaraTgBot:
    def __init__(self, ecchi = False):
        self.rating = "ecchi" if ecchi else "general"

        #Load Config
        self.config = json.load(open("config.json"))
        self.videoUrl = "https://iwara.tv/video"
        self.userUrl = "https://iwara.tv/profile"

        #Setup Iwara API Client
        self.client = ApiClient(self.config["user_info"]["user_name"], self.config["user_info"]["password"])

        #Init DB
        self.DBpath = "IwaraTgDB.db"

        #Setup telegram bot
        print("Connecting to telegram bot...")
        self.updater = Updater(self.config["telegram_info"]["token"], base_url = self.config["telegram_info"]["APIServer"])
        self.bot = self.updater.bot
        botInfo = self.bot.getMe()
        print("Connected to telegram bot: " + botInfo.first_name)

    def login(self) -> bool:
        """ Login to iwara.tv """

        #Login
        print("Logging in...")
        r = self.client.login()

        if r.status_code == 200:
            print("Login success")
            return True
        else:
            print("Login failed")
            return False

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
        (id, title, user, user_display, int(datetime.now().strftime("%Y%m%d")), chat_id, views, likes,))
        
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
        """# Extract video info from video object
        """

        try:
            video = self.client.get_video(id).json()
        except Exception as e:
            raise e

        title = video["title"]
        user = video["user"]['username']
        user_display = video["user"]['name']
        description = video['body']
        tags = [user_display]
        for tag in video["tags"]:
            tags.append(tag["id"])

        thumbFileName = video["id"] + ".jpg"

        return [title, user, user_display, description, tags, thumbFileName]

    def get_video_stat(self, video):
        """# Extract video stats from video object
        """

        likes = int(video['numLikes'])
        views = int(video['numViews'])

        return [likes, views]

    def find_videos(self, subscribed = False) -> List:
        print("Finding videos... (rating: {}, subscribed: {})".format(self.rating, subscribed))

        if (subscribed and self.client.token == None):
            raise Exception("Not logged in!")
            
        videos = []

        for page in range(10):
            try:
                videos += (self.client.get_videos(sort = 'date', rating = self.rating, page = page, subscribed = subscribed).json()['results'])
            except Exception as e:
                print("Error: {}".format(e))

        return videos

    def download_video(self, id) -> Optional[str]:
        try:
            print("Downloading video {}...".format(id))
            return self.client.download_video(id)
        except Exception as e: # Download Failed
            print("Download Failed: {}".format(e))
            return None

    def download_video_thumbnail(self, id) -> Optional[str]:
        try:
            return self.client.download_video_thumbnail(id)
        except: # Download Failed
            return None

    def get_youtube_link(self, video) -> Optional[str]:
        try:
            return video["embedUrl"]
        except:
            return None
        
    def send_yt_link(self, yt_link, id = "", title = "", user = "", user_display = "", description = "", v_tags = []):
        
        # yt_link = "https://www.youtube.com/watch?v=" + yt_id

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

        try:
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
            
            #Delete the video form server
            os.remove(thumbPath)
            os.remove(path)

            return msg.message_id
        
        except Exception as e:
            #Delete the video form server
            os.remove(thumbPath)
            os.remove(path)
            raise e

    def send_description(self, user, user_display, description):
        msg_t = self.bot.send_message(chat_id=self.config["telegram_info"]["chat_id_discuss"], text = "Getting message ID...")
        self.bot.delete_message(chat_id=self.config["telegram_info"]["chat_id_discuss"], message_id= msg_t.message_id)

        #Debug
        print(msg_t.message_id)

        print(description)

        msg_description = """
<a href="{}/{}/">{}</a> said:
""".format(self.userUrl, user, user_display) + ("" if (description == None) else description)

        #Debug
        print(msg_description)

        self.bot.send_message(chat_id=self.config["telegram_info"]["chat_id_discuss"], text = msg_description, parse_mode = "HTML", reply_to_message_id=msg_t.message_id - 1)

    def update_stat_after(self, date, tableName):
        c, conn = self.connect_DB()

        c.execute("""SELECT id FROM """ + tableName + " WHERE date >= ?", (date,))
        entries = c.fetchall()

        for (id,) in entries:
            try:
                #Debug
                print("Updating video ID {}".format(id))

                video = self.client.get_video(id).json()

                #Debug
                print(video)

                (likes, views) = self.get_video_stat(video)

                #Debug
                print(id)
                print(likes, views)

                c.execute("""UPDATE """ + tableName + " SET likes = ?, views = ? WHERE id = ?", (likes, views, id))
            except Exception as e:
                print("Error: {}".format(e))
                pass

        self.close_DB(conn)

    def download(self, subscribed = False):

        tableName = "videosNew" if subscribed == False else "videosSub"

        self.init_DB(tableName)
        
        if (not self.login()):
            print("Login Failed")
            return

        videos = self.find_videos(subscribed = subscribed)

        #Download videos
        for video in videos:

            id = video['id']

            print("Found video ID {}".format(id))

            if (self.is_video_exist(tableName, id)):
                print("Video ID {} Already sent, skipped. ".format(id))
                continue

            try:
                video_info = self.get_video_info(id)
            except Exception as e:
                print("Error in getting video info: {}".format(e))
                continue

            print("[DEBUG] Video ID {} Info: ".format(id))
            print(video_info)

            yt_link = self.get_youtube_link(video)

            title = video_info[0]
            user = video_info[1]
            user_display = video_info[2]
            description = video_info[3]
            v_tags = video_info[4]

            if (yt_link == None):
                videoFileName = self.download_video(id)

                if (videoFileName == None):
                    print("Video ID {} Download failed, skipped. ".format(id))
                    continue

                thumbFileName = self.download_video_thumbnail(id)

                if (thumbFileName == None):
                    print("Video ID {} Thumbnail Download failed, skipped. ".format(id))
                    continue

                try:
                    msg_id = self.send_video(videoFileName, id, title, user, user_display, description, v_tags, thumbFileName)
                except Exception as e:
                    print("Error in sending video: {}".format(e))
                    continue
            else:

                msg_id = self.send_yt_link(yt_link, id, title, user, user_display, description, v_tags)

            self.save_video_info(tableName, id, title, user, user_display, msg_id)

            time.sleep(5) # Wait for telegram to forward the video to the group

            if "chat_id_discuss" in self.config["telegram_info"]:
                self.send_description(user = user, user_display = user_display, description = description)

    def send_ranking(self, title, entries):

        ranking_description = f"""#{title}
"""

        for i in range(1, len(entries)+1):
            (title, user_display, chat_id, likes, views, heats,) = entries[i-1]
            ranking_description += f"""
Top {i} ❤️{likes} 🔥{views}
<a href="https://t.me/iwara2/{chat_id}">{title}</a> by {user_display}"""

        self.bot.send_message(chat_id=self.config["telegram_info"]["ranking_id"], text = ranking_description, parse_mode = "HTML")

    def ranking(self, type = "DAILY"):

        tableName = "videosNew"

        today = datetime.today()
        yesterday = today - relativedelta(days = 1)
        oneweekago = today - relativedelta(days = 7)
        onemonthago = today - relativedelta(months = 1)
        oneyearago = today - relativedelta(years = 1)

        date = None
        title = None
        if (type == "DAILY"):
            date = yesterday
            title = f"""Daily Ranking 每日排行榜
""" + today.strftime("%Y-%m-%d")
        elif (type == "WEEKLY"):
            date = oneweekago
            title = """Weekly Ranking 每周排行榜
""" + oneweekago.strftime("%Y-%m-%d") + " ~ " + today.strftime("%Y-%m-%d")
        elif (type == "MONTHLY"):
            date = onemonthago
            title = """Monthly Ranking 月度排行榜
""" + onemonthago.strftime("%Y-%m")
        elif (type == "YEARLY"):
            date = oneyearago
            title = """Annual Ranking 年度排行榜
""" + oneyearago.strftime("%Y")
            

        if (date != None):

            self.login()

            print("Fetching video stats...")

            self.update_stat_after(date.strftime("%Y%m%d"), tableName)
            
            c, conn = self.connect_DB()

            c.execute("""SELECT title, user_display, chat_id, likes, views, likes * 20 + views as heats FROM """ + tableName + " WHERE date >= ? ORDER BY heats DESC", (date.strftime("%Y%m%d"),))
            entries = c.fetchmany(10)

            # c.execute("""SELECT title, user_display, chat_id, views FROM """ + tableName + " WHERE date >= ? ORDER BY views DESC", (date.strftime("%Y%m%d"),))
            # entries_views = c.fetchmany(5)

            self.close_DB(conn)

            self.send_ranking(title, entries)


if __name__ == '__main__':
    args = sys.argv

    def usage():
        print("""
Usage: python {} <mode> <option>
mode can be:
\t -n/normal: normal mode
\t -e/ecchi: ecchi mode (NSFW)
option can be:
\t dlsub: download the latest page of your subscription list
\t dlnew: download the latest page of the new videos
\t rank -d/-w/-m/-y: send daily/weekly/monthly/annually ranking of your database

        """.format(args[0]))
        exit(1)

    if (len(args) < 2 or len(args) > 4): usage()

    if (args[1] == "-n" or args[1] == "normal"): bot = IwaraTgBot()
    elif (args[1] == "-e" or args[1] == "ecchi"): bot = IwaraTgBot(ecchi = True)
    else: usage()

    if (args[2] == "dlsub"): bot.download(subscribed=True)
    elif (args[2] == "dlnew"): bot.download()
    elif (args[2] == "rank"):
        if (args[3] == "-d"): bot.ranking("DAILY")
        elif (args[3] == "-w"): bot.ranking("WEEKLY")
        elif (args[3] == "-m"): bot.ranking("MONTHLY")
        elif (args[3] == "-y"): bot.ranking("YEARLY")
        else: usage()
    else: usage()

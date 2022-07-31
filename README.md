# Iwara-Telegram-Bot

Iwara-Telegram-Bot: your ultimate [Python-Telegram-Bot](https://github.com/python-telegram-bot/python-telegram-bot) that connects [iwara.tv](https://iwara.tv/) and [Telegram](https://telegram.org/).

## Demo

## Features
```
Usage: python {} <mode> <request>
mode can be:
-n/normal: normal mode
-e/ecchi: ecchi mode (NSFW)
request can be:
dlsub: download the latest page of your subscription list
dlnew: download the latest page of the new videos
```

<!-- ✅ - Published  
🚧 - In Progress  
💡 - Planned   -->

1. ✅ `dlsub` - Download Subscribed
   - Send all videos in the first page of [From people you follow](https://iwara.tv/subscriptions) to a Telegram **chat**.
   - Maintain a `IwaraTgDB.db` to track all videos that have already been sent to the chat.
2. ✅ `dlnew` - Download New
   - Send all videos in the first page of [Recent videos](https://www.iwara.tv/videos) to a Telegram **channel**.
   - Maintain a `IwaraTgDB.db` to track all videos that have already been sent to the channel.
   - Add the video description to the comment section of the post.

## Deployment

### Prerequisite

- A [Telegram Bot](https://core.telegram.org/bots/) (Token)
- A [Local Bot API Server](https://core.telegram.org/bots/api#using-a-local-bot-api-server) (Server url)
  <!-- - Iwara videos with resolution of `Source` are usually larger than 50 MB. -->

#### To use `dlsub` for your bot

- The chat ID of the conversation between you and your bot

#### To use `dlnew` for your Telegram channel

- The chat ID of your Telegram channel
- The chat ID of the linked discussion group of your Telegram channel

### macOS, Ubuntu

1. Clone the repository
```
git clone https://github.com/watanabexia/Iwara-Telegram-Bot
```
2. Install the dependencies
```
pip install -r requirements.txt
```
3. Create a file named `config.json` inside the repository folder `Iwara-Telegram-Bot`, with the following content:
```json
{
    "user_info" : {
        "user_name" : <Your Iwara user name>,
        "password" : <Your Iwara Password>
    },
    "telegram_info" : {
        "token" : <Your Bot API Token>,
        "chat_id" : <The chat ID of your bot or channel>,
        "chat_id_discuss": <The chat ID of the linked discussion group>,
        "APIServer" : <Your Bot API Server url>
    }
}
```
4. Bon Appétit
```
Usage: python {} <mode> <request>
mode can be:
-n/normal: normal mode
-e/ecchi: ecchi mode (NSFW)
request can be:
dlsub: download the latest page of your subscription list
dlnew: download the latest page of the new videos
```
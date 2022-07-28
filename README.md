# Iwara-Telegram-Bot

A Python Telegram Bot that can download videos from [ecchi.iwara.tv](https://ecchi.iwara.tv/) and send to a certain chat.

## Features

```
Usage: python main.py <option>
option can be:
    dlsub: download the latest page of your subscription list
```

<!-- ✅ - Published  
🚧 - In Progress  
💡 - Planned   -->

1. ✅ `dlsub` - Subscription Tracker
   - Download all videos in the first page of your subscription.
   - Maintain a `sent_list.json` to track all videos that have been already sent to the chat.

## Deployment

### Prerequisite

- A [Telegram Bot](https://core.telegram.org/bots/) (Token)
- A Telegram Chat ID
- A [Local Bot API Server](https://core.telegram.org/bots/api#using-a-local-bot-api-server) (Server url)
  <!-- - Iwara videos with resolution of `Source` are usually larger than 50 MB. -->

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
        "chat_id" : <Your Chat ID>,
        "APIServer" : <Your Bot API Server url>
    }
}
```
4. Bon Appétit
```
python main.py <option>
```




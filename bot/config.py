import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

ALERT_JSON_PATH = "data/alerts.json"
USERS_JSON_PATH = "data/users.json"


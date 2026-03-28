from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))
DEFAULT_BALANCE = float(os.getenv("DEFAULT_BALANCE"))
DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT"))
JBLANKED_API_KEY = os.getenv("JBLANKED_API_KEY", "")

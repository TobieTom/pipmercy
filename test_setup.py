from database import init_db, get_db
import config

init_db()
print("Database initialized successfully")

conn = get_db()
rows = conn.execute("SELECT * FROM settings").fetchall()
for row in rows:
    print(dict(row))
conn.close()

print("Config loaded:")
print(f"  TELEGRAM_TOKEN: {config.TELEGRAM_TOKEN[:6]}...")
print(f"  GROQ_API_KEY:   {config.GROQ_API_KEY[:6]}...")
print(f"  TWELVE_DATA_KEY:{config.TWELVE_DATA_KEY[:6]}...")
print(f"  CHAT_ID:        {config.CHAT_ID}")
print(f"  DEFAULT_BALANCE:{config.DEFAULT_BALANCE}")
print(f"  DEFAULT_RISK_PERCENT: {config.DEFAULT_RISK_PERCENT}")

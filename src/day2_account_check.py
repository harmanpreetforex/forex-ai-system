import os
from dotenv import load_dotenv
from oandapyV20 import API
import oandapyV20.endpoints.accounts as accounts

# Load credentials from .env
load_dotenv()

API_TOKEN = os.getenv("OANDA_API_TOKEN")
ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")
ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "practice")

# Connect to OANDA
client = API(access_token=API_TOKEN, environment=ENVIRONMENT)

# Request account summary
r = accounts.AccountSummary(ACCOUNT_ID)
client.request(r)

summary = r.response["account"]

print("✅ Connected to OANDA successfully!")
print(f"   Account ID  : {summary['id']}")
print(f"   Currency    : {summary['currency']}")
print(f"   Balance     : {float(summary['balance']):,.2f} {summary['currency']}")
print(f"   Open Trades : {summary['openTradeCount']}")
print(f"   Unrealized P/L: {summary['unrealizedPL']}")
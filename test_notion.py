import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()
client = Client(auth=os.getenv("NOTION_TOKEN"))
db_id = os.getenv("NOTION_DATABASE_ID")

try:
    print("Querying...")
    res = client.request(path=f"databases/{db_id}/query", method="POST", body={"filter": {"property": "URL", "url": {"equals": "https://www.youtube.com/watch?v=vCD-A8FNUPA"}}})
    print("Success!", res)
except Exception as e:
    print("Error:", e)

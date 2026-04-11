from appwrite.client import Client
from appwrite.services.storage import Storage
import os
from dotenv import load_dotenv

load_dotenv()

client = Client()
client.set_endpoint('https://sgp.cloud.appwrite.io/v1')
client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
client.set_key(os.getenv("APPWRITE_API_KEY"))


storage = Storage(client)
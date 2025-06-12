from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os 

load_dotenv()

connectionstring = os.getenv("URl")

MONGO_URL = connectionstring
client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000, tls=True)

db = client["healthcare_platform_db"]

def init_db():
    pass

def get_db():
    return db

import pymongo
import os
import logging

logger = logging.getLogger(__name__)

mongo_db = None
client = None

try:
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
    # Ping server to verify connection
    client.server_info()
    mongo_db = client["cardsync"]
    logger.info("MongoDB initialized successfully and connected to database 'cardsync'")
except Exception as e:
    logger.error(f"MongoDB initialization error: {e}")
    mongo_db = None
    client = None

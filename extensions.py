# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis

# 1. تهيئة قاعدة البيانات والـ Migrations
db = SQLAlchemy()
migrate = Migrate()

# 2. تهيئة الـ Limiter (حارس الـ Brute force)
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day"])

# 3. تهيئة كائن الـ Redis (مع إضافة حماية تجعله يتصل محلياً بشكل افتراضي)
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
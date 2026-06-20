import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """
    الإعدادات الأساسية المشتركة بين كل البيئات
    """

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///app.db"
    )

    # Uploads
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER",
        "uploads"
    )

    # الحد الأقصى لحجم الملفات المرفوعة 5MB
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024


    # JWT
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=15
    )

    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=7
    )


    # JWT Cookie Settings
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SAMESITE = "Lax"


    # Redis
    REDIS_HOST = os.environ.get(
        "REDIS_HOST",
        "localhost"
    )

    REDIS_PORT = int(
        os.environ.get(
            "REDIS_PORT",
            6379
        )
    )

    REDIS_DB = int(
        os.environ.get(
            "REDIS_DB",
            0
        )
    )


    # API
    APP_VERSION = "1.0.0"



class DevelopmentConfig(BaseConfig):
    """
    بيئة التطوير المحلية
    """

    DEBUG = True

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-only-secure-key-change-me"
    )

    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY",
        "dev-only-jwt-secret-key-change-me"
    )


    ALLOWED_ORIGINS = os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5173"
    )


    JWT_COOKIE_SECURE = False



class ProductionConfig(BaseConfig):
    """
    بيئة الإنتاج
    """

    DEBUG = False


    SECRET_KEY = os.environ.get(
        "SECRET_KEY"
    )


    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY"
    )


    ALLOWED_ORIGINS = os.environ.get(
        "ALLOWED_ORIGINS"
    )


    # HTTPS فقط في الإنتاج
    JWT_COOKIE_SECURE = True



    @classmethod
    def validate(cls):
        """
        منع تشغيل السيرفر في الإنتاج
        بدون إعدادات أمان حقيقية
        """

        if not cls.SECRET_KEY:
            raise RuntimeError(
                "Missing SECRET_KEY in production"
            )


        if not cls.JWT_SECRET_KEY:
            raise RuntimeError(
                "Missing JWT_SECRET_KEY in production"
            )


        if not cls.ALLOWED_ORIGINS:
            raise RuntimeError(
                "Missing ALLOWED_ORIGINS in production"
            )



# اختيار البيئة

config_layouts = {

    "development": DevelopmentConfig,

    "production": ProductionConfig

}



current_env = os.environ.get(
    "FLASK_ENV",
    "development"
).lower()



Config = config_layouts.get(
    current_env,
    DevelopmentConfig
)



# تشغيل فحص الإنتاج تلقائياً

if hasattr(Config, "validate"):

    Config.validate()
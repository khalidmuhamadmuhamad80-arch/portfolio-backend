import os
import uuid
import logging

from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, send_from_directory, g
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import (
    db,
    migrate,
    limiter,
    redis_client
)

from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.contact import contact_bp
from routes.dashboard import dashboard_bp


def configure_logging(app):
    if app.debug:
        return

    os.makedirs("logs", exist_ok=True)

    file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10
    )

    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s "
            "[%(pathname)s:%(lineno)d]"
        )
    )

    file_handler.setLevel(logging.INFO)

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

    app.logger.info("Application startup")


def register_error_handlers(app):

    @app.errorhandler(Exception)
    def handle_exception(error):

        if isinstance(error, HTTPException):
            return jsonify({
                "success": False,
                "message": error.description
            }), error.code

        app.logger.error(
            f"Unhandled Exception: {str(error)}",
            exc_info=True
        )

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500


def register_jwt_handlers(jwt):

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            "success": False,
            "message": "Token expired"
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            "success": False,
            "message": "Invalid token"
        }), 401

    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        return jsonify({
            "success": False,
            "message": "Authorization token required"
        }), 401


def startup_checks(app):

    with app.app_context():

        try:
            db.session.execute(db.text("SELECT 1"))
            app.logger.info("Database connection OK")

        except Exception as e:
            app.logger.critical(
                f"Database startup check failed: {str(e)}"
            )
            raise

        try:
            redis_client.ping()
            app.logger.info("Redis connection OK")

        except Exception as e:
            app.logger.warning(
                f"Redis unavailable: {str(e)}"
            )


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1
    )

    allowed_origins = app.config.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5173"
    )

    CORS(
        app,
        resources={
            r"/*": {
                "origins": allowed_origins
            }
        },
        allow_headers=[
            "Content-Type",
            "Authorization"
        ],
        methods=[
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS"
        ],
        supports_credentials=True
    )

    jwt = JWTManager(app)

    register_jwt_handlers(jwt)

    limiter.init_app(app)

    db.init_app(app)

    migrate.init_app(app, db)

    configure_logging(app)

    register_error_handlers(app)

    startup_checks(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(dashboard_bp)

    @app.before_request
    def assign_request_id():
        g.request_id = str(uuid.uuid4())

    @app.route("/uploads/<path:filename>")
    def uploads(filename):

        upload_folder = app.config.get(
            "UPLOAD_FOLDER",
            "uploads"
        )

        return send_from_directory(
            upload_folder,
            filename
        )

    @app.route("/")
    def home():

        return jsonify({
            "success": True,
            "message": "API running"
        })

    @app.route("/health")
    def health():

        try:

            db.session.execute(
                db.text("SELECT 1")
            )

            redis_ok = False

            try:
                redis_client.ping()
                redis_ok = True
            except Exception:
                pass

            return jsonify({
                "success": True,
                "status": "healthy",
                "database": True,
                "redis": redis_ok
            })

        except Exception:

            return jsonify({
                "success": False,
                "status": "unhealthy"
            }), 500

    @app.route("/version")
    def version():

        return jsonify({
            "version": app.config.get("APP_VERSION","1.0.0"),

        })

    return app


app = create_app()

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
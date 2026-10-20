from flask import Flask



def create_app():
    app = Flask(__name__)

    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    from app.api import api_bp

    app.register_blueprint(api_bp)

    return app

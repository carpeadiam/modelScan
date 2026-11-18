import os

from flask import Flask

from pg.config import get_settings
from pg.storage import get_storage


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY", os.urandom(16).hex()),
                      JSON_SORT_KEYS=False, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    app.config["PG_SETTINGS"] = get_settings()
    app.config["PG_STORAGE"] = None
    if test_config:
        app.config.update(test_config)

    def storage():
        if app.config["PG_STORAGE"] is None:
            app.config["PG_STORAGE"] = get_storage(app.config["PG_SETTINGS"])
        return app.config["PG_STORAGE"]

    app.storage = storage  # type: ignore[attr-defined]
    from .routes import bp
    app.register_blueprint(bp)

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        return resp

    return app

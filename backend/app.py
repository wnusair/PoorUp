"""
PoorUp — Flask application entry point.
Run with: python app.py  OR  gunicorn -k eventlet -w 1 app:app
"""
import eventlet
eventlet.monkey_patch()

import os

from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_ENV", "development") == "development"
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=debug_enabled,
        use_reloader=False,  # reloader causes issues with eventlet monkey-patch
    )

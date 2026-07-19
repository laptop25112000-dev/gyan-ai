import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from gyaaan_core import chat_response, history_response, index_response
from flask import Flask


app = Flask(__name__, template_folder="../templates", static_folder="../static")


@app.route("/")
def index():
    return index_response()


@app.route("/api/history", methods=["GET", "DELETE"])
def handle_history():
    return history_response()


@app.route("/api/chat", methods=["POST"])
def api_chat():
    return chat_response()


if __name__ == "__main__":
    print("GYAAN UI ready locally at http://127.0.0.1:5000")
    app.run(debug=True, port=5000, use_reloader=False)

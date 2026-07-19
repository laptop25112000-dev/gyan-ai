from gyaaan_core import chat_response, history_response, index_response
from flask import Flask


app = Flask(__name__)


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
    print("GYAAN UI ready at http://127.0.0.1:5000")
    app.run(debug=True, port=5000, use_reloader=False)

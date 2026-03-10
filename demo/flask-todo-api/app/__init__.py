"""Flask Todo API — demo target for test-guardian evaluation."""

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# In-memory store
_todos: list[dict] = []
_next_id = 1
_api_keys = {"test-key-123": "admin", "read-only-key": "reader"}


def _require_auth() -> tuple[dict, int] | None:
    """Check for valid API key in Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"error": "Missing authorization header"}), 401
    token = auth.removeprefix("Bearer ")
    if token not in _api_keys:
        return jsonify({"error": "Invalid API key"}), 403
    return None


@app.route("/api/todos", methods=["GET"])
def list_todos():
    """List all todos. Supports ?status=done|pending filter."""
    status_filter = request.args.get("status")
    todos = _todos
    if status_filter:
        todos = [t for t in todos if t["status"] == status_filter]
    return jsonify({"todos": todos, "count": len(todos)})


@app.route("/api/todos", methods=["POST"])
def create_todo():
    """Create a new todo. Requires auth."""
    global _next_id
    auth_err = _require_auth()
    if auth_err:
        return auth_err

    data = request.get_json()
    if not data or "title" not in data:
        return jsonify({"error": "title is required"}), 400

    todo = {
        "id": _next_id,
        "title": data["title"],
        "description": data.get("description", ""),
        "status": "pending",
    }
    _next_id += 1
    _todos.append(todo)
    return jsonify(todo), 201


@app.route("/api/todos/<int:todo_id>", methods=["GET"])
def get_todo(todo_id: int):
    """Get a single todo by ID."""
    todo = next((t for t in _todos if t["id"] == todo_id), None)
    if not todo:
        return jsonify({"error": "Todo not found"}), 404
    return jsonify(todo)


@app.route("/api/todos/<int:todo_id>", methods=["PUT"])
def update_todo(todo_id: int):
    """Update a todo. Requires auth."""
    auth_err = _require_auth()
    if auth_err:
        return auth_err

    todo = next((t for t in _todos if t["id"] == todo_id), None)
    if not todo:
        return jsonify({"error": "Todo not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    if "title" in data:
        todo["title"] = data["title"]
    if "description" in data:
        todo["description"] = data["description"]
    if "status" in data:
        if data["status"] not in ("pending", "done"):
            return jsonify({"error": "status must be 'pending' or 'done'"}), 400
        todo["status"] = data["status"]

    return jsonify(todo)


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
def delete_todo(todo_id: int):
    """Delete a todo. Requires auth."""
    global _todos
    auth_err = _require_auth()
    if auth_err:
        return auth_err

    original_len = len(_todos)
    _todos = [t for t in _todos if t["id"] != todo_id]
    if len(_todos) == original_len:
        return jsonify({"error": "Todo not found"}), 404
    return jsonify({"message": "Deleted"}), 200


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "flask-todo-api"})


if __name__ == "__main__":
    app.run(debug=True, port=5001)

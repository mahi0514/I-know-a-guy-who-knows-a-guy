"""
ConnectApp — Cloud Backend with PostgreSQL
"""

from flask import Flask, request, jsonify, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from collections import deque

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

def get_db():
    # 1. Fetch the Render database URL we just configured
    db_url = os.environ.get("DATABASE_URL")
    
    # 2. Fix the prefix because SQLAlchemy/psycopg2 requires 'postgresql://' instead of 'postgres://'
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    # 3. Connect to PostgreSQL cloud instance
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    
    # 4. Initialize tables if they don't exist in PostgreSQL
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                bio TEXT
            );
            CREATE TABLE IF NOT EXISTS connections (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                connected_user_id INTEGER NOT NULL,
                UNIQUE(user_id, connected_user_id)
            );
        """)
        conn.commit()
    return conn

# ---------- Frontend ----------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

# ---------- API ----------

@app.route("/api/users", methods=["GET"])
def list_users():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, email, bio FROM users ORDER BY name")
        rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200

@app.route("/api/users", methods=["POST"])
def create_user():
    data = request.get_json(force=True)
    name, email, bio = data.get("name"), data.get("email"), data.get("bio", "")
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, email, bio) VALUES (%s, %s, %s) RETURNING id",
                (name, email, bio),
            )
            user_id = cur.fetchone()["id"]
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": "email already exists"}), 409
    finally:
        conn.close()

    return jsonify({"id": user_id, "name": name, "email": email, "bio": bio}), 201

@app.route("/api/connections", methods=["POST"])
def add_connection():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    connected_user_id = data.get("connected_user_id")
    mutual = data.get("mutual", True)

    if not user_id or not connected_user_id:
        return jsonify({"error": "user_id and connected_user_id are required"}), 400
    if user_id == connected_user_id:
        return jsonify({"error": "a user cannot connect to themselves"}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO connections (user_id, connected_user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, connected_user_id),
            )
            if mutual:
                cur.execute(
                    "INSERT INTO connections (user_id, connected_user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (connected_user_id, user_id),
                )
            conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "connected", "mutual": mutual}), 201

def build_adjacency():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT user_id, connected_user_id FROM connections")
        rows = cur.fetchall()
    conn.close()
    graph = {}
    for row in rows:
        graph.setdefault(row["user_id"], []).append(row["connected_user_id"])
    return graph

@app.route("/api/graph", methods=["GET"])
def get_graph():
    user_id = request.args.get("user_id", type=int)
    depth = request.args.get("depth", default=1, type=int)

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    adjacency = build_adjacency()
    visited = {user_id}
    edge_pairs = set()
    frontier = [user_id]

    for _ in range(max(depth, 1)):
        next_frontier = []
        for node in frontier:
            for neighbor in adjacency.get(node, []):
                edge_pairs.add(tuple(sorted((node, neighbor))))
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
        frontier = next_frontier

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name FROM users WHERE id IN %s", (tuple(visited),)
        )
        rows = cur.fetchall()
    conn.close()

    nodes = [{"id": r["id"], "label": r["name"]} for r in rows]
    edges = [{"from": a, "to": b} for a, b in edge_pairs]

    return jsonify({"nodes": nodes, "edges": edges}), 200

def find_shortest_path(start_id, target_id):
    if start_id == target_id:
        return [start_id]

    graph = build_adjacency()
    visited = {start_id}
    queue = deque([(start_id, [start_id])])

    while queue:
        current, path = queue.popleft()
        for neighbor in graph.get(current, []):
            if neighbor == target_id:
                return path + [neighbor]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None

@app.route("/api/path", methods=["GET"])
def get_path():
    from_id = request.args.get("from", type=int)
    to_id = request.args.get("to", type=int)

    if not from_id or not to_id:
        return jsonify({"error": "from and to query params are required"}), 400

    path_ids = find_shortest_path(from_id, to_id)
    if path_ids is None:
        return jsonify({"connected": False, "path": []}), 200

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name FROM users WHERE id IN %s", (tuple(path_ids),)
        )
        rows = cur.fetchall()
    conn.close()

    id_to_name = {row["id"]: row["name"] for row in rows}
    named_path = [{"id": pid, "name": id_to_name.get(pid, "Unknown")} for pid in path_ids]

    return jsonify({
        "connected": True,
        "degrees": len(path_ids) - 1,
        "path": named_path,
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)

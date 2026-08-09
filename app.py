import json
import os
import queue
import threading
import uuid

from flask import Flask, jsonify, render_template, request, Response

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
CONDITIONS_FILE = os.path.join(DATA_DIR, "conditions.json")
ICONS_DIR = os.path.join(BASE_DIR, "static", "icons")
ICON_EXTS = {".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"}

SEED_VERSION = 3

_lock = threading.Lock()
_sse_clients = []

DEFAULT_CHARACTER = {
    "name": "Unnamed",
    "hp": 7,
    "marked_hp": [],
    "stress": 6,
    "marked_stress": [],
    "armor": 0,
    "marked_armor": [],
    "hope": 6,
    "marked_hope": [],
    "scars": 0,
    "conditions": [],
}


def _condition(cond_id, name, description, icon, light, dark):
    return {
        "id": cond_id,
        "name": name,
        "description": description,
        "default": True,
        "icon": icon,
        "color_light": light,
        "color_dark": dark,
    }


_STANDARD_CONDITIONS = [
    (
        "hidden", "Hidden",
        "While you're out of sight from all enemies and they don't otherwise know your location, "
        "you gain the Hidden condition. Any rolls against a Hidden creature have Disadvantage. "
        "After an adversary moves to where they would see you, you move into their line of sight, "
        "or you make an attack, you are no longer Hidden.",
        "hidden", "#6f7f8f", "#3d4750",
    ),
    (
        "restrained", "Restrained",
        "Restrained characters can't move, but can still take actions from their current position.",
        "restrained", "#8e6f1f", "#5c470e",
    ),
    (
        "vulnerable", "Vulnerable",
        "When a creature is Vulnerable, all rolls targeting them have Advantage.",
        "vulnerable", "#b03a2e", "#7a1f16",
    ),
]

_UNIQUE_CONDITIONS = [
    (
        "poisoned", "Poisoned",
        "While Poisoned, the target must roll a d6 before they make an action roll. "
        "On a result of 4 or lower, they must mark a Stress.",
        "poisoned", "#2b5e2e", "#143a17",
    ),
    (
        "cursed", "Cursed",
        "While the target is Cursed, you can mark a Stress when that target rolls with Hope "
        "to make the roll be with Fear instead.",
        "dread", "#3a3a6f", "#1c1c45",
    ),
    (
        "ignited", "Ignited",
        "While Ignited, the target takes 1d4 magic damage when they make an action roll.",
        "flame", "#d96b1f", "#8f3d0e",
    ),
    (
        "exiled", "Exiled",
        "While Exiled, the target and their allies have Disadvantage during social situations "
        "within the Noble's domain.",
        "exiled", "#5f7a8f", "#3a4e5c",
    ),
    (
        "protected", "Protected",
        "While Protected, the target has resistance to all damage.",
        "protected", "#2d6a8f", "#174e6f",
    ),
    (
        "entranced", "Entranced",
        "While Entranced, the target can't act and is Vulnerable.",
        "fairy-wand", "#c9a227", "#8a6513",
    ),
    (
        "enveloped", "Enveloped",
        "While Enveloped, the target must mark an additional Stress every time they make an action roll. "
        "When the Ooze takes Severe damage, all Enveloped targets are freed and the condition is cleared.",
        "enveloped", "#4e8f5e", "#2d5e3a",
    ),
    (
        "dazed", "Dazed",
        "While Dazed, they can't use their Regeneration action but are immune to magic damage.",
        "spiral", "#9a3d8f", "#4a1240",
    ),
    (
        "rooted", "Rooted",
        "While Rooted, the Treant has resistance to physical damage.",
        "rooted", "#5e8f2e", "#3a5e17",
    ),
    (
        "marked", "Marked",
        "While the target is Marked, their Evasion is halved.",
        "marked", "#8f2e2e", "#5e1717",
    ),
    (
        "chilled", "Chilled",
        "While the target is Chilled, they have disadvantage on attack rolls.",
        "snowflake", "#3a9fd9", "#1f6f9c",
    ),
    (
        "trapped", "Trapped",
        "While Trapped, the target is Restrained and Vulnerable until they break free, "
        "ending both conditions, with a successful Instinct Roll.",
        "cobweb_1", "#6f5e8f", "#453a5e",
    ),
    (
        "guilty", "Guilty",
        "When the Seraph succeeds on a standard attack against a Guilty target, they deal "
        "Severe damage instead of their standard damage.",
        "scales", "#8f8f8f", "#5e5e5e",
    ),
]


def build_default_conditions():
    conditions = []
    for cid, name, desc, icon, light, dark in _STANDARD_CONDITIONS:
        conditions.append(_condition(cid, name, desc, icon, light, dark))
    for cid, name, desc, icon, light, dark in _UNIQUE_CONDITIONS:
        conditions.append(_condition(cid, name, desc, icon, light, dark))
        conditions.append(_condition(
            f"{cid}-temporary", f"{name} (Temporary)", desc, icon, light, dark
        ))
    conditions.append(_condition(
        "advantage", "Advantage",
        "Advantage represents an opportunity that you seize to increase your chances of success. "
        "When you roll with advantage, you roll a d6 advantage die with your dice pool and add "
        "its result to your total.",
        "advantage", "#2d8f4e", "#175e2f",
    ))
    conditions.append(_condition(
        "disadvantage", "Disadvantage",
        "Disadvantage represents an additional difficulty, hardship, or challenge you face when "
        "attempting an action. When you roll with disadvantage, you roll a d6 disadvantage die "
        "with your dice pool and subtract its result from your total.",
        "disadvantage", "#8f3a2e", "#5e1f16",
    ))
    return conditions


def load_json(filepath, default):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_characters():
    return load_json(CHARACTERS_FILE, {"characters": []})


def _write_characters(store):
    save_json(CHARACTERS_FILE, store)


def _read_conditions():
    return load_json(CONDITIONS_FILE, {"conditions": []})


def _write_conditions(store):
    save_json(CONDITIONS_FILE, store)


def get_characters():
    with _lock:
        return _read_characters()


def get_normalized_characters():
    store = get_characters()
    return [
        normalize_character(ch, ch.get("id"))
        for ch in store["characters"]
        if ch.get("id")
    ]


def get_conditions():
    with _lock:
        store = load_json(CONDITIONS_FILE, None)
    if store is None or not isinstance(store.get("conditions"), list):
        store = {"version": SEED_VERSION, "conditions": build_default_conditions()}
        save_conditions(store)
        return store
    return migrate_conditions(store)


def migrate_conditions(store):
    """Refresh built-in (default) conditions from the current seed whenever the
    seed version bumps. Custom conditions are left untouched. Runs lazily on load."""
    version = store.get("version", 0)
    if version >= SEED_VERSION:
        return store

    seed = build_default_conditions()
    seed_by_id = {c["id"]: c for c in seed}
    existing_by_id = {c["id"]: c for c in store["conditions"]}

    migrated = []
    used = set()
    for sc in seed:
        cid = sc["id"]
        used.add(cid)
        if cid in existing_by_id and existing_by_id[cid].get("default"):
            merged = dict(existing_by_id[cid])
            merged["name"] = sc["name"]
            merged["description"] = sc["description"]
            merged["icon"] = sc["icon"]
            merged["color_light"] = sc["color_light"]
            merged["color_dark"] = sc["color_dark"]
            merged["default"] = True
            migrated.append(merged)
        else:
            migrated.append(dict(sc))
    for cond in store["conditions"]:
        if cond["id"] not in used:
            migrated.append(cond)

    store = {"version": SEED_VERSION, "conditions": migrated}
    save_conditions(store)
    return store


def save_conditions(store):
    with _lock:
        _write_conditions(store)


def icon_file_exists(icon):
    if not icon:
        return False
    return os.path.exists(os.path.join(ICONS_DIR, os.path.basename(icon)))


def list_icons():
    if not os.path.isdir(ICONS_DIR):
        return []
    names = []
    for fn in os.listdir(ICONS_DIR):
        if os.path.splitext(fn)[1].lower() in ICON_EXTS:
            names.append(fn)
    return sorted(names)


def sanitize_icon(value):
    if not value:
        return None
    name = os.path.basename(str(value)).strip()
    if not name or ".." in name or "\\" in name or "/" in name:
        return None
    return name


def sanitize_color(value):
    if not value:
        return None
    s = str(value).strip().lower()
    if len(s) in (4, 7) and s.startswith("#"):
        if all(c in "0123456789abcdef" for c in s[1:]):
            return s
    return None


def resolve_icon(cond):
    """Resolve a stored icon value to an actual filename present in the icons folder."""
    icon = cond.get("icon")
    if not icon:
        return None
    name = os.path.basename(str(icon))
    if "." in name:
        return name if icon_file_exists(name) else None
    for ext in (".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"):
        if icon_file_exists(name + ext):
            return name + ext
    return None


def serialize_conditions(store=None):
    if store is None:
        store = get_conditions()
    out = []
    for c in store.get("conditions", []):
        cond = dict(c)
        icon = resolve_icon(cond)
        cond["icon"] = icon
        cond["icon_available"] = icon is not None
        out.append(cond)
    return {"conditions": out}


def normalize_character(raw, char_id):
    data = dict(DEFAULT_CHARACTER)
    if isinstance(raw, dict):
        data.update(raw)
    data["id"] = char_id
    data["name"] = str(data.get("name", "Unnamed")).strip() or "Unnamed"

    for key in ("hp", "stress", "armor", "hope", "scars"):
        try:
            data[key] = max(0, int(data.get(key, DEFAULT_CHARACTER[key])))
        except (TypeError, ValueError):
            data[key] = DEFAULT_CHARACTER[key]

    marked_keys = {
        "marked_hp": "hp",
        "marked_stress": "stress",
        "marked_armor": "armor",
        "marked_hope": "hope",
    }
    for key, count_key in marked_keys.items():
        max_value = data[count_key]
        if key == "marked_hope":
            max_value = max(0, max_value - data["scars"])
        arr = data.get(key)
        if not isinstance(arr, list):
            arr = []
        norm = []
        for i in range(max_value):
            norm.append(bool(arr[i]) if i < len(arr) else False)
        data[key] = norm

    conditions = data.get("conditions")
    if not isinstance(conditions, list):
        conditions = []
    data["conditions"] = [str(c) for c in conditions]
    return data


def broadcast(client_id=None):
    msg = {"client_id": client_id}
    for q in list(_sse_clients):
        try:
            q.put_nowait(msg)
        except queue.Full:
            pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    return render_template(
        "status.html",
        characters=get_normalized_characters(),
        conditions=serialize_conditions()["conditions"],
    )


@app.route("/characters")
def characters_page():
    return render_template(
        "character.html",
        characters=get_normalized_characters(),
        conditions=serialize_conditions()["conditions"],
    )


@app.route("/gm")
def gm_page():
    return render_template(
        "gm.html",
        characters=get_normalized_characters(),
        conditions=serialize_conditions()["conditions"],
    )


@app.route("/codex")
def codex_page():
    return render_template(
        "codex.html",
        conditions=serialize_conditions()["conditions"],
        icons=list_icons(),
    )


@app.get("/api/characters")
def api_characters():
    return jsonify({"characters": get_normalized_characters()})


@app.post("/api/characters")
def api_create_character():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip() or "Unnamed"
    char_id = str(uuid.uuid4())
    character = dict(DEFAULT_CHARACTER)
    character["id"] = char_id
    character["name"] = name
    character = normalize_character(character, char_id)
    with _lock:
        store = _read_characters()
        store["characters"].append(character)
        _write_characters(store)
    broadcast(payload.get("client_id"))
    return jsonify({"status": "ok", "id": char_id})


@app.post("/api/characters/<char_id>")
def api_update_character(char_id):
    payload = request.get_json(silent=True) or {}
    character = normalize_character(payload, char_id)
    with _lock:
        store = _read_characters()
        for i, ch in enumerate(store["characters"]):
            if ch["id"] == char_id:
                store["characters"][i] = character
                _write_characters(store)
                broadcast(payload.get("client_id"))
                return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Character not found"}), 404


@app.delete("/api/characters/<char_id>")
def api_delete_character(char_id):
    payload = request.get_json(silent=True) or {}
    with _lock:
        store = _read_characters()
        store["characters"] = [c for c in store["characters"] if c["id"] != char_id]
        _write_characters(store)
    broadcast(payload.get("client_id"))
    return jsonify({"status": "ok"})


@app.get("/api/conditions")
def api_conditions():
    return jsonify(serialize_conditions())


@app.get("/api/icons")
def api_icons():
    return jsonify({"icons": list_icons()})


@app.post("/api/conditions")
def api_create_condition():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"status": "error", "message": "Name is required"}), 400
    with _lock:
        store = _read_conditions()
        existing = {c.get("name", "").lower() for c in store["conditions"]}
        if name.lower() in existing:
            return jsonify(
                {"status": "error", "message": "A condition with that name already exists"}
            ), 409
        condition = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": str(payload.get("description", "")),
            "default": False,
            "icon": sanitize_icon(payload.get("icon")),
            "color_light": sanitize_color(payload.get("color_light")),
            "color_dark": sanitize_color(payload.get("color_dark")),
        }
        store["conditions"].append(condition)
        _write_conditions(store)
    broadcast(payload.get("client_id"))
    return jsonify({"status": "ok", "id": condition["id"]})


@app.post("/api/conditions/<cond_id>")
def api_update_condition(cond_id):
    payload = request.get_json(silent=True) or {}
    with _lock:
        store = _read_conditions()
        for i, cond in enumerate(store["conditions"]):
            if cond["id"] == cond_id:
                if cond.get("default"):
                    return jsonify(
                        {"status": "error", "message": "Default conditions cannot be edited"}
                    ), 403
                name = str(payload.get("name", cond["name"])).strip() or cond["name"]
                for j, other in enumerate(store["conditions"]):
                    if j != i and other["name"].lower() == name.lower():
                        return jsonify(
                            {"status": "error", "message": "A condition with that name already exists"}
                        ), 409
                cond["name"] = name
                cond["description"] = str(payload.get("description", cond["description"]))
                cond["icon"] = sanitize_icon(payload.get("icon", cond.get("icon")))
                cond["color_light"] = sanitize_color(payload.get("color_light", cond.get("color_light")))
                cond["color_dark"] = sanitize_color(payload.get("color_dark", cond.get("color_dark")))
                store["conditions"][i] = cond
                _write_conditions(store)
                broadcast(payload.get("client_id"))
                return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Condition not found"}), 404


@app.delete("/api/conditions/<cond_id>")
def api_delete_condition(cond_id):
    payload = request.get_json(silent=True) or {}
    with _lock:
        store = _read_conditions()
        for cond in store["conditions"]:
            if cond["id"] == cond_id:
                if cond.get("default"):
                    return jsonify(
                        {"status": "error", "message": "Default conditions cannot be deleted"}
                    ), 403
                store["conditions"] = [c for c in store["conditions"] if c["id"] != cond_id]
                _write_conditions(store)
                broadcast(payload.get("client_id"))
                return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Condition not found"}), 404


@app.get("/api/stream")
def api_stream():
    def generate():
        q = queue.Queue(maxsize=50)
        _sse_clients.append(q)
        try:
            yield "retry: 2000\n\n"
            while True:
                try:
                    msg = q.get(timeout=20)
                    yield f"event: update\ndata: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in _sse_clients:
                _sse_clients.remove(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    with _lock:
        if not os.path.exists(CONDITIONS_FILE):
            _write_conditions({"conditions": build_default_conditions()})
        if not os.path.exists(CHARACTERS_FILE):
            _write_characters({"characters": []})
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)

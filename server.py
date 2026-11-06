"""고충토로추진위원회 모바일 주문접수 - Flask + SQLite (공통 장바구니)."""
import json, os, sqlite3, time
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, abort

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "orders.db")
app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="/static")


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINSERT, day TEXT, brand TEXT, name TEXT,
        slot TEXT, items TEXT, total INTEGER, created REAL)""".replace("AUTOINSERT", "AUTOINCREMENT"))
    return c


def slots():
    out, m = [], 15 * 60
    while m <= 16 * 60 + 30:
        out.append(f"{m // 60:02d}:{m % 60:02d}")
        m += 10
    return out


def load_menus():
    with open(os.path.join(BASE, "menus.json"), encoding="utf-8") as f:
        return json.load(f)


def today():
    return datetime.now().strftime("%Y-%m-%d")


@app.get("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.get("/api/menus")
def api_menus():
    return jsonify(menus=load_menus(), slots=slots())


@app.get("/api/orders")
def api_orders():
    with db() as c:
        rows = c.execute("SELECT * FROM orders WHERE day=? ORDER BY slot, id", (today(),)).fetchall()
    return jsonify([{**dict(r), "items": json.loads(r["items"])} for r in rows])


@app.post("/api/orders")
def api_add():
    d = request.get_json(force=True, silent=True) or {}
    menus = load_menus()
    brand = d.get("brand")
    name = (d.get("name") or "").strip()[:20]
    slot = d.get("slot")
    if brand not in menus or not name or slot not in slots() or not d.get("items"):
        abort(400, "입력값을 확인해 주세요")
    # 가격은 서버 메뉴표로 다시 계산 (클라이언트 값 신뢰 안 함)
    catalog = {m["id"]: m for m in menus[brand]["items"]}
    items, total = [], 0
    for it in d["items"][:30]:
        m = catalog.get(it.get("id"))
        size = it.get("size")
        qty = max(1, min(int(it.get("qty", 1)), 20))
        if not m or size not in m["prices"]:
            abort(400, "메뉴 오류")
        price = m["prices"][size]
        items.append({"name": m["name"], "size": size, "qty": qty, "price": price})
        total += price * qty
    with db() as c:
        c.execute("INSERT INTO orders(day,brand,name,slot,items,total,created) VALUES(?,?,?,?,?,?,?)",
                  (today(), brand, name, slot, json.dumps(items, ensure_ascii=False), total, time.time()))
    return jsonify(ok=True, total=total)


@app.delete("/api/orders/<int:oid>")
def api_del(oid):
    with db() as c:
        c.execute("DELETE FROM orders WHERE id=?", (oid,))
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)

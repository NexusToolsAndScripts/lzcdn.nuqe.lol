import threading
import time
import requests
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

BAZAAR_URL = "https://api.hypixel.net/skyblock/bazaar"
FETCH_INTERVAL = 300  # 5 minutes

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["120 per minute"]
)

bazaar_cache = {
    "products": {},
    "last_updated": 0
}


def fetch_bazaar_loop():
    """Fetch bazaar once every 5 minutes globally"""
    global bazaar_cache

    while True:
        try:
            r = requests.get(BAZAAR_URL, timeout=15)
            r.raise_for_status()
            data = r.json()

            if data.get("success"):
                bazaar_cache["products"] = data["products"]
                bazaar_cache["last_updated"] = data["lastUpdated"]
                print("[Bazaar] Cache updated")

        except Exception as e:
            print("[Bazaar] Fetch failed:", e)

        time.sleep(FETCH_INTERVAL)


def clean_product(product_id, product):
    qs = product["quick_status"]

    return {
        "item_id": product_id,
        "buy_price": round(qs["buyPrice"], 3),
        "sell_price": round(qs["sellPrice"], 3),
        "buy_volume": qs["buyVolume"],
        "sell_volume": qs["sellVolume"],
        "buy_orders": qs["buyOrders"],
        "sell_orders": qs["sellOrders"],
        "weekly_buy": qs["buyMovingWeek"],
        "weekly_sell": qs["sellMovingWeek"]
    }


@app.route("/search")
@limiter.limit("10 per second")
def search():
    query = request.args.get("q", "").upper()
    if not query:
        return jsonify({"error": "Missing query"}), 400

    results = []
    for pid, product in bazaar_cache["products"].items():
        if query in pid:
            results.append(clean_product(pid, product))

    return jsonify({
        "query": query,
        "count": len(results),
        "last_updated": bazaar_cache["last_updated"],
        "results": results
    })


@app.route("/item/<item_id>")
@limiter.limit("10 per second")
def item(item_id):
    item_id = item_id.upper()

    product = bazaar_cache["products"].get(item_id)
    if not product:
        return jsonify({"error": "Item not found"}), 404

    return jsonify({
        "last_updated": bazaar_cache["last_updated"],
        "data": clean_product(item_id, product)
    })


@app.route("/health")
def health():
    return jsonify({
        "cached_items": len(bazaar_cache["products"]),
        "last_updated": bazaar_cache["last_updated"]
    })


if __name__ == "__main__":
    threading.Thread(target=fetch_bazaar_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)

import os
import time
import uuid

import requests
import urllib3
from bakong_khqr import KHQR
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")

BAKONG_TOKEN = os.getenv("BAKONG_TOKEN", "").strip()
IS_RELAY = BAKONG_TOKEN.startswith("rbk")
BAKONG_API = "https://api.khqr.dev/v1" if IS_RELAY else "https://api-bakong.nbc.gov.kh/v1"
SSL_VERIFY = os.getenv("BAKONG_SSL_VERIFY", "false").lower() in ("1", "true", "yes")

if not SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SDK is only used offline: building the EMVCo QR string and the QR image.
# All HTTP calls go through `bakong_post` (requests) so SSL verify can be turned off.
khqr = KHQR()


def bakong_post(endpoint, payload):
    if not BAKONG_TOKEN:
        raise ValueError("BAKONG_TOKEN is not set in .env")
    resp = requests.post(
        BAKONG_API + endpoint,
        json=payload,
        headers={"Authorization": f"Bearer {BAKONG_TOKEN}"},
        timeout=15,
        verify=SSL_VERIFY,
    )
    try:
        data = resp.json()
    except ValueError:
        raise ValueError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
        raise ValueError(data.get("responseMessage") or f"HTTP {resp.status_code}")
    return data


def check_bakong_payment(md5):
    """Returns PAID, SCANNED, EXPIRED or UNPAID."""
    res = bakong_post("/check_transaction_by_md5", {"md5": md5})
    data = res.get("data") if isinstance(res.get("data"), dict) else {}

    if IS_RELAY:
        status = str(data.get("status", "")).upper()
        tracking = str(data.get("trackingStatus", "")).upper()
        if "SCANNED" in (status, tracking):
            return "SCANNED"
        if "EXPIRED" in (status, tracking):
            return "EXPIRED"
        if status == "PAID" or tracking == "SUCCESS":
            return "PAID"

    return "PAID" if res.get("responseCode") == 0 else "UNPAID"

PRODUCTS = [
    {"id": 1, "name": "Iced Coffee", "price": 0.01,
     "image": "https://images.unsplash.com/photo-1517701604599-bb29b565090c?w=600",
     "description": "Cold brewed Cambodian coffee with condensed milk."},
    {"id": 2, "name": "T-Shirt", "price": 0.02,
     "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600",
     "description": "Soft cotton t-shirt, available in all sizes."},
    {"id": 3, "name": "Notebook", "price": 0.03,
     "image": "https://images.unsplash.com/photo-1531346878377-a5be20888e57?w=600",
     "description": "A5 dotted notebook, 120 pages."},
]

# In-memory store of payments: {md5: {...}}. Use a database in production.
PAYMENTS = {}


def get_product(product_id):
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        abort(404)
    return product


def create_khqr(amount, bill_number):
    """Returns (qr_string, md5, bill_number)."""
    if IS_RELAY:
        # KHQR.dev token: merchant info & currency come from the store settings
        res = bakong_post("/generate_qr", {"amount": float(amount)})
        if res.get("responseCode") != 0:
            raise ValueError(res.get("responseMessage") or "Failed to generate KHQR")
        data = res["data"]
        return data["qr"], data["md5"], data.get("tran_id") or bill_number

    # NBC token / offline: full EMVCo fields are required
    qr = khqr.create_qr(
        account_id=os.getenv("BAKONG_ACCOUNT_ID"),
        merchant_name=os.getenv("MERCHANT_NAME", "My Store"),
        merchant_city=os.getenv("MERCHANT_CITY", "Phnom Penh"),
        amount=amount,
        currency=os.getenv("CURRENCY", "USD"),
        store_label=os.getenv("STORE_LABEL", "MyShop"),
        phone_number=os.getenv("MERCHANT_PHONE", ""),
        bill_number=bill_number,
        terminal_label=os.getenv("TERMINAL_LABEL", "WEB-01"),
        static=False,
    )
    return str(qr), khqr.generate_md5(str(qr)), bill_number


@app.route("/")
def home():
    return render_template("home.html", products=PRODUCTS)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    return render_template("product.html", product=get_product(product_id))


@app.route("/product/<int:product_id>/pay", methods=["POST"])
def pay(product_id):
    product = get_product(product_id)
    bill_number = "INV" + uuid.uuid4().hex[:10].upper()
    try:
        qr, md5, bill_number = create_khqr(product["price"], bill_number)
    except (ValueError, requests.RequestException) as e:
        return f"Could not create KHQR: {e}", 502

    PAYMENTS[md5] = {
        "md5": md5,
        "qr": qr,
        "product_id": product["id"],
        "amount": product["price"],
        "bill_number": bill_number,
        "status": "UNPAID",
        "created_at": time.time(),
    }
    return redirect(url_for("payment", md5=md5))


@app.route("/payment/<md5>")
def payment(md5):
    tx = PAYMENTS.get(md5) or abort(404)
    qr_image = khqr.qr_image(tx["qr"], format="base64_uri")
    return render_template("payment.html", tx=tx, qr_image=qr_image,
                           product=get_product(tx["product_id"]))


@app.route("/api/check-payment/<md5>")
def check_payment(md5):
    tx = PAYMENTS.get(md5)
    if not tx:
        return jsonify({"error": "Transaction not found"}), 404

    if tx["status"] != "PAID":
        if not BAKONG_TOKEN:
            return jsonify({"status": "UNPAID", "message": "No BAKONG_TOKEN set, cannot verify"})
        try:
            tx["status"] = check_bakong_payment(md5)
        except (ValueError, requests.RequestException) as e:
            return jsonify({"status": tx["status"], "error": str(e)}), 502

    return jsonify({"status": tx["status"]})


@app.route("/success/<md5>")
def success(md5):
    tx = PAYMENTS.get(md5) or abort(404)
    if tx["status"] != "PAID":
        return redirect(url_for("payment", md5=md5))
    return render_template("success.html", tx=tx, product=get_product(tx["product_id"]))


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=5000)

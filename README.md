# flask-khqr

A simple Flask shop that sells products and takes payment with **KHQR** (Bakong, Cambodia).

- Home page with a product list
- Product detail page with a **Pay with KHQR** button
- Payment page that shows the KHQR code and checks the payment automatically
- Success page once the payment is confirmed

## Requirements

- Python **3.10+** (`bakong-khqr` does not work on Python 3.9)
- A Bakong token: either a **KHQR.dev** token (`rbk_...`) or an **NBC developer** token

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env
```

## Configuration (`.env`)

| Variable | Description |
| --- | --- |
| `SECRET_KEY` | Flask secret key. Use a random string. |
| `FLASK_DEBUG` | `1` to turn on debug mode. |
| `BAKONG_TOKEN` | Your KHQR.dev (`rbk_...`) or NBC developer token. |
| `BAKONG_SSL_VERIFY` | `false` skips SSL certificate checks on Bakong API calls. Use `true` in production. |
| `BAKONG_ACCOUNT_ID` | Bakong account that receives the money, e.g. `name@bank`. *NBC token only.* |
| `MERCHANT_NAME` | Merchant name shown in the banking app. *NBC token only.* |
| `MERCHANT_CITY` | Merchant city, e.g. `Phnom Penh`. *NBC token only.* |
| `MERCHANT_PHONE` | Merchant phone number. *NBC token only.* |
| `STORE_LABEL` | Store label. *NBC token only.* |
| `TERMINAL_LABEL` | Terminal label. *NBC token only.* |
| `CURRENCY` | `USD` or `KHR`. *NBC token only.* |

**Which token should I use?**

- **KHQR.dev token (`rbk_...`)**: only the amount is sent. Merchant info and currency come from your KHQR.dev store settings.
- **NBC developer token**: the QR is built locally from the merchant fields above, and payments are checked with the official NBC API. The NBC API only accepts requests from Cambodian IP addresses.

## Run

```bash
python app.py
```

Then open http://127.0.0.1:5000.

## Payment flow

1. The customer opens a product and clicks **Pay with KHQR**.
2. The server creates a KHQR code and saves the transaction, keyed by the QR's MD5 hash.
3. The payment page shows the QR. The customer scans it with any KHQR banking app (ABA, ACLEDA, Bakong, ...).
4. The page checks the status **every 5 seconds for up to 10 minutes**. There is also an **I have paid** button to check right away.
5. When the status is `PAID`, the customer is sent to the success page.

Payment statuses: `UNPAID`, `SCANNED` (KHQR.dev only), `PAID`, `EXPIRED`.

## Routes

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Product list |
| GET | `/product/<id>` | Product detail |
| POST | `/product/<id>/pay` | Create a KHQR and go to the payment page |
| GET | `/payment/<md5>` | QR code page with automatic checking |
| GET | `/api/check-payment/<md5>` | JSON response: `{"status": "PAID" \| "UNPAID" \| "SCANNED" \| "EXPIRED"}` |
| GET | `/success/<md5>` | Payment success page |

## Project structure

```
app.py              # Flask routes, products, Bakong API calls (requests)
templates/          # base, home, product, payment, success pages
.env.example        # sample config (copy to .env)
requirements.txt
```

## Notes

- Products and payments are kept **in memory**, so they are lost when the server restarts. Use a database for real orders.
- Sample prices are $0.01–$0.03 so you can test with real money cheaply. Edit `PRODUCTS` in `app.py` to change them.
- All Bakong API calls use `requests`, so SSL verification can be turned off with `BAKONG_SSL_VERIFY=false`. The `bakong-khqr` SDK is only used to build the QR string offline and to draw the QR image.
- Never commit `.env`. It is already in `.gitignore`.

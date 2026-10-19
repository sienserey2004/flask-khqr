import time
from bakong_khqr import KHQR

# Initialize with your KHQR.dev Store Token
khqr = KHQR("rbk_xxxxxxxxxxxxxxxxxxxx")

# 1. Generate Dynamic KHQR (amount only; backend auto-detects currency & merchant info)
res = khqr.create_qr(amount=1.50)
print("KHQR String :", str(res))       # or res.qr
print("Transaction MD5:", res.md5)     # MD5 hash for status verification
print("Bill Number    :", res.tran_id) # Unique bill/transaction reference

# Optional: Generate with Hosted Web Checkout
checkout_res = khqr.create_qr(
    amount=1.50,
    return_url="https://yourstore.com/checkout/return",
    success_url="https://yourstore.com/checkout/success",
    cancel_url="https://yourstore.com/checkout/cancel"
)
print("Web Checkout URL:", checkout_res.checkout_url)

# 2. Smart Polling Loop (Handles PAID, SCANNED, UNPAID, and EXPIRED)
start_time = time.time()
timeout_seconds = 10 * 60  # 10 minutes

while True:
    status, next_delay = khqr.check_payment(res.md5, start_time=start_time)
    print(f"Current Status: {status} | Next check in: {next_delay}s")

    if status == "PAID":
        print("🎉 Payment Successful!")
        payment_info = khqr.get_payment(res.md5)
        print("Transaction Details:", payment_info)
        break

    elif status == "EXPIRED":
        print("❌ Transaction has expired!")
        break

    elif status == "SCANNED":
        print("📱 Customer has scanned the QR. Awaiting PIN/confirmation...")

    # Stop polling if client timeout is reached
    if time.time() - start_time >= timeout_seconds:
        print("🛑 Local polling timeout reached.")
        break

    time.sleep(next_delay)
2. Using Official NBC Token or Offline KHQR Generation
If initialized without a token or with an official NBC Developer Token, the SDK uses the standard EMVCo offline engine:

from bakong_khqr import KHQR

# Without token (Offline EMVCo Generator) or with NBC Token
khqr = KHQR("your_nbc_developer_token_here")

# Full EMVCo parameters are required
qr_string = khqr.create_qr(
    account_id="user_name@bank",
    merchant_name="My Store",
    merchant_city="Phnom Penh",
    amount=10.00,
    currency="USD",
    store_label="Cashier-01",
    phone_number="012345678",
    bill_number="TRX012345",
    terminal_label="POS-01",
    static=False,
    expiration=1
)

md5 = khqr.generate_md5(qr_string)

# Check status via official NBC API (Returns either PAID or UNPAID)
status = khqr.check_payment(md5)
print("Status:", status)
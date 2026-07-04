import os
import stripe
from flask import Blueprint, request, jsonify, session
from routes.auth import require_login
from supabase_client import update_profile, get_profile

billing_bp = Blueprint("billing", __name__)

def get_stripe_key():
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    return stripe.api_key

SITE_URL = os.environ.get("SITE_URL", "https://aiwithai.online")

# ₹ per minute of sandbox runtime for pay-as-you-go credits
RATE_INR_PER_MINUTE = float(os.environ.get("SANDBOX_RATE_INR_PER_MINUTE", "2"))

# Bundle: pay BUNDLE_PRICE_INR once, get BUNDLE_MINUTES minutes (better than standard rate)
BUNDLE_PRICE_INR = float(os.environ.get("BUNDLE_PRICE_INR", "500"))
BUNDLE_MINUTES = float(os.environ.get("BUNDLE_MINUTES", "300"))

# ---------------------------------------------------------------------------
# One-time credit purchase (pay-as-you-go sandbox minutes + unlocks legend labs)
# Respects the amount the user actually clicked.
# ---------------------------------------------------------------------------
@billing_bp.route("/api/billing/create-credit-checkout", methods=["POST"])
@require_login
def create_credit_checkout():
    if not get_stripe_key():
        return jsonify({"ok": False, "error": "Payments not configured"}), 503

    data = request.get_json(force=True, silent=True) or {}
    currency = (data.get("currency") or "inr").lower()

    if currency == "gbp":
        try:
            amount_gbp = float(data.get("amount_gbp", 0))
        except (ValueError, TypeError):
            amount_gbp = 0
        if amount_gbp < 10:
            return jsonify({"ok": False, "error": "Minimum top-up is £10"}), 400

        # £10 = 500 minutes, scales linearly
        minutes = (amount_gbp / 10.0) * 500

        checkout = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {"name": f"AiwithAI Sandbox Credits ({int(minutes)} minutes)"},
                    "unit_amount": int(round(amount_gbp * 100)),  # pence
                },
                "quantity": 1,
            }],
            success_url=f"{SITE_URL}/account?topup=1",
            cancel_url=f"{SITE_URL}/account",
            client_reference_id=session["user_id"],
            customer_email=session.get("user_email"),
            metadata={"user_id": session["user_id"], "type": "credits", "minutes": str(minutes)}
        )
        return jsonify({"ok": True, "url": checkout.url})

    # --- INR (default) ---
    try:
        amount_inr = float(data.get("amount_inr", 0))
    except (ValueError, TypeError):
        amount_inr = 0
    if amount_inr < 10:
        return jsonify({"ok": False, "error": "Minimum top-up is ₹10"}), 400

    minutes = amount_inr / RATE_INR_PER_MINUTE

    checkout = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "inr",
                "product_data": {"name": f"AiwithAI Sandbox Credits ({round(minutes,1)} minutes)"},
                "unit_amount": int(round(amount_inr * 100)),  # paise
            },
            "quantity": 1,
        }],
        success_url=f"{SITE_URL}/account?topup=1",
        cancel_url=f"{SITE_URL}/account",
        client_reference_id=session["user_id"],
        customer_email=session.get("user_email"),
        metadata={"user_id": session["user_id"], "type": "credits", "minutes": str(minutes)}
    )
    return jsonify({"ok": True, "url": checkout.url})

# ---------------------------------------------------------------------------
# Bundle checkout: fixed ₹500 -> 300 minutes (better rate than standard top-up)
# ---------------------------------------------------------------------------
@billing_bp.route("/api/billing/create-bundle-checkout", methods=["POST"])
@require_login
def create_bundle_checkout():
    if not get_stripe_key():
        return jsonify({"ok": False, "error": "Payments not configured"}), 503

    checkout = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "inr",
                "product_data": {"name": f"AiwithAI Project Bundle ({int(BUNDLE_MINUTES)} minutes)"},
                "unit_amount": int(round(BUNDLE_PRICE_INR * 100)),  # paise
            },
            "quantity": 1,
        }],
        success_url=f"{SITE_URL}/account?topup=1",
        cancel_url=f"{SITE_URL}/account",
        client_reference_id=session["user_id"],
        customer_email=session.get("user_email"),
        metadata={"user_id": session["user_id"], "type": "credits", "minutes": str(BUNDLE_MINUTES)}
    )
    return jsonify({"ok": True, "url": checkout.url})

# ---------------------------------------------------------------------------
# Webhook - source of truth for credit updates.
# Always reads minutes from metadata.minutes (set correctly above for both
# INR and GBP at creation time).
# ---------------------------------------------------------------------------
@billing_bp.route("/api/billing/webhook", methods=["POST"])
def stripe_webhook():
    if not get_stripe_key():
        return "Payments not configured", 503

    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        if not webhook_secret:
            return "Webhook secret not configured", 500
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        print(f"WEBHOOK SIGNATURE ERROR: {str(e)}")
        return jsonify({"error": "Invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        obj = event["data"]["object"].to_dict()
        metadata = obj.get("metadata") or {}
        user_id = metadata.get("user_id") or obj.get("client_reference_id")

        if not user_id:
            print("Webhook Error: No user_id found in metadata or client_reference_id")
            return jsonify({"error": "No user_id"}), 400

        try:
            minutes_purchased = float(metadata.get("minutes", 0))
            profile = get_profile(user_id) or {}
            current_credits = float(profile.get("credits_minutes") or 0)
            new_total = current_credits + minutes_purchased

            success = update_profile(user_id, {
                "credits_minutes": new_total,
                "stripe_customer_id": obj.get("customer"),
            })
            if success:
                print(f"CREDITS ADDED: user={user_id} added={minutes_purchased} total={new_total}")
            else:
                print(f"CREDITS FAILED: update_profile returned False for user={user_id}")
                return jsonify({"error": "Database update failed"}), 500
        except Exception as e:
            print(f"CRITICAL DB UPDATE ERROR: {str(e)}")
            return jsonify({"error": "Database error"}), 500

    return jsonify({"received": True}), 200

import os
from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from routes.auth import require_login
from supabase_client import delete_user, get_profile

account_bp = Blueprint("account", __name__)

@account_bp.route("/account")
@require_login
def account_page():
    profile = get_profile(session["user_id"]) or {}
    session["credits_minutes"] = float(profile.get("credits_minutes", 0) or 0)
    return render_template(
        "account.html",
        user_name=session.get("user_name", ""),
        user_email=session.get("user_email", ""),
        plan=profile.get("plan", "free"),
        credits_minutes=round(float(profile.get("credits_minutes", 0) or 0), 1),
        stripe_configured=bool(os.environ.get("STRIPE_SECRET_KEY")),
    )

@account_bp.route("/api/account/delete", methods=["GET", "POST"])
@require_login
def delete_account():
    user_id = session["user_id"]
    try:
        delete_user(user_id)
        session.clear()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

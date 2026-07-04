import os, json
from flask import Blueprint, request, jsonify, session, redirect, url_for
from supabase_client import create_user, verify_user, get_profile

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/register", methods=["GET","POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    name = data.get("name", "").strip()
    if not email or not password or not name:
        return jsonify({"ok": False, "error": "Name, email and password required"}), 400
    user, err = create_user(email, password, name)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    session["user_id"] = user["id"]
    session["user_email"] = email
    session["user_name"] = name
    session["plan"] = "free"
    session["credits_minutes"] = 0
    return jsonify({"ok": True})

@auth_bp.route("/api/login", methods=["GET","POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password required"}), 400
    user, err = verify_user(email, password)
    if err:
        return jsonify({"ok": False, "error": err}), 401
    session["user_id"] = user["id"]
    session["user_email"] = email
    session["user_name"] = user.get("name") or email.split("@")[0]
    profile = get_profile(user["id"])
    session["plan"] = profile.get("plan", "free") if profile else "free"
    session["credits_minutes"] = float(profile.get("credits_minutes", 0)) if profile else 0
    session["stripe_customer_id"] = profile.get("stripe_customer_id") if profile else None
    return jsonify({"ok": True})

@auth_bp.route("/api/logout", methods=["GET","POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@auth_bp.route("/logout")
def logout_get():
    session.clear()
    return redirect(url_for("main.index"))

def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("main.login_page"))
        return f(*args, **kwargs)
    return decorated

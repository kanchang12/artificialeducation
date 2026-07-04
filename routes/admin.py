import os, time, glob, json
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from supabase_client import (
    get_assigned_build_ids, assign_course, unassign_course,
    list_all_assignments, list_all_users, set_setting, get_setting,
)

admin_bp = Blueprint("admin", __name__)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.admin_login"))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if ADMIN_EMAIL and ADMIN_PASSWORD and email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin.admin_dashboard"))
        error = "Invalid credentials"
    return render_template("admin_login.html", error=error)

@admin_bp.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin.admin_login"))

@admin_bp.route("/admin/costs", methods=["POST"])
@require_admin
def admin_save_costs():
    for key in ["koyeb", "hosting", "gemini", "domain", "marketing"]:
        val = request.form.get(key, "0")
        try:
            float(val)
        except ValueError:
            val = "0"
        set_setting(f"cost_{key}", val)
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/admin/backfill", methods=["POST"])
@require_admin
def admin_backfill():
    # SQLite creates profile rows automatically; nothing to backfill.
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/admin/assign", methods=["POST"])
@require_admin
def admin_assign_course():
    user_id = request.form.get("user_id", "").strip()
    build_id = request.form.get("build_id", "").strip()
    if user_id and build_id:
        assign_course(user_id, build_id)
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/unassign", methods=["POST"])
@require_admin
def admin_unassign_course():
    user_id = request.form.get("user_id", "").strip()
    build_id = request.form.get("build_id", "").strip()
    if user_id and build_id:
        unassign_course(user_id, build_id)
    return redirect(url_for("admin.admin_dashboard"))


def _load_build_titles():
    BASE = os.path.dirname(os.path.dirname(__file__))
    out = []
    for f in sorted(glob.glob(os.path.join(BASE, "data/builds/*.json"))):
        with open(f) as fp:
            d = json.load(fp)
            out.append({"id": d.get("id"), "title": d.get("title")})
    return out


@admin_bp.route("/admin")
@require_admin
def admin_dashboard():
    users = []
    total_users = 0
    total_credits_inr = 0.0
    debug_error = None
    try:
        users = list_all_users()
        total_users = len(users)
        rate = float(os.environ.get("SANDBOX_RATE_INR_PER_MINUTE", "2"))
        total_credits_inr = sum(float(u.get("credits_minutes", 0) or 0) for u in users) * rate
    except Exception as e:
        users = []
        debug_error = str(e)

    paying_users = sum(1 for u in users if float(u.get("credits_minutes", 0) or 0) > 0)

    # Stripe charges a percentage fee per transaction - calculate, don't guess
    stripe_fee_percent = float(os.environ.get("STRIPE_FEE_PERCENT", "2.0"))
    stripe_fees = round(total_credits_inr * stripe_fee_percent / 100, 2)

    editable_costs = {
        "koyeb": get_setting("cost_koyeb", "0"),
        "hosting": get_setting("cost_hosting", "0"),
        "gemini": get_setting("cost_gemini", "0"),
        "domain": get_setting("cost_domain", "0"),
        "marketing": get_setting("cost_marketing", "0"),
    }

    costs = {
        "Koyeb hosting": editable_costs["koyeb"],
        "Hosting / DB": editable_costs["hosting"],
        "Gemini API": editable_costs["gemini"],
        "Domain (aiwithai.online)": editable_costs["domain"],
        f"Stripe fees ({stripe_fee_percent}% of credit revenue)": str(stripe_fees),
        "Marketing / Ads": editable_costs["marketing"],
    }
    total_cost = sum(float(v or 0) for v in costs.values())

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        paying_users=paying_users,
        free_users=total_users - paying_users,
        total_credits_inr=round(total_credits_inr, 2),
        costs=costs,
        total_cost=round(total_cost, 2),
        net=round(total_credits_inr - total_cost, 2),
        users=users[:50],
        editable_costs=editable_costs,
        debug_error=debug_error,
        rate=os.environ.get("SANDBOX_RATE_INR_PER_MINUTE", "2"),
        builds=_load_build_titles(),
        assignments=list_all_assignments(),
    )

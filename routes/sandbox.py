import sys, io, traceback, json, ast, contextlib, os, time
from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from data_loader import get_sandbox, load_sandboxes
from routes.auth import require_login
from supabase_client import get_profile, update_profile

sandbox_bp = Blueprint("sandbox", __name__)

FREE_SANDBOXES = {"sb_01_silent_bug", "sb_02_json_fence"}
RATE_INR_PER_MINUTE = float(os.environ.get("SANDBOX_RATE_INR_PER_MINUTE", "2"))

def get_credits():
    return float(session.get("credits_minutes", 0) or 0)

def refresh_credits():
    from supabase_client import get_profile
    profile = get_profile(session["user_id"])
    if profile:
        session["credits_minutes"] = float(profile.get("credits_minutes", 0) or 0)
    return get_credits()

def is_unlocked(sb_id):
    """Free sandboxes: always. Others: need credit balance."""
    if sb_id in FREE_SANDBOXES:
        return True
    return get_credits() > 0

@sandbox_bp.route("/sandbox/<sb_id>")
@require_login
def sandbox_detail(sb_id):
    refresh_credits()
    if not is_unlocked(sb_id):
        return redirect(url_for("main.upgrade_page"))
    sb = get_sandbox(sb_id)
    if not sb:
        return redirect(url_for("main.dashboard"))
    all_sbs = load_sandboxes()
    idx = next((i for i, s in enumerate(all_sbs) if s.get("id") == sb_id), 0)
    prev_sb = all_sbs[idx - 1] if idx > 0 else None
    next_sb = all_sbs[idx + 1] if idx < len(all_sbs) - 1 else None
    is_free = sb_id in FREE_SANDBOXES
    return render_template("sandbox.html", sb=sb, prev_sb=prev_sb, next_sb=next_sb,
                           user_name=session.get("user_name", ""),
                           is_free=is_free,
                           credits_minutes=round(get_credits(), 1),
                           rate=RATE_INR_PER_MINUTE)

@sandbox_bp.route("/api/sandbox/run", methods=["GET","POST"])
@require_login
def sandbox_run():
    data = request.get_json(force=True, silent=True) or {}
    sb_id = data.get("id", "")
    user_code = data.get("code", "")

    if not is_unlocked(sb_id):
        return jsonify({"ok": False, "error": "Out of credits. Top up to keep coding."}), 403

    sb = get_sandbox(sb_id)
    if not sb:
        return jsonify({"ok": False, "error": "Sandbox not found"}), 404

    results = []
    all_passed = True

    for tc in sb.get("test_cases", []):
        setup = tc.get("setup", "")
        call = tc.get("call", "")
        expected = tc.get("expected")
        label = tc.get("label", "Test")

        full_code = user_code + "\n" + setup + "\n_result = " + call

        stdout_capture = io.StringIO()
        local_ns = {}

        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(compile(full_code, "<sandbox>", "exec"), local_ns)
            actual = local_ns.get("_result")
            passed = actual == expected
            if not passed:
                all_passed = False
            results.append({
                "label": label,
                "passed": passed,
                "expected": repr(expected),
                "actual": repr(actual),
                "stdout": stdout_capture.getvalue()
            })
        except Exception as e:
            all_passed = False
            tb = traceback.format_exc().split("\n")
            short_tb = "\n".join([l for l in tb if l.strip()][-3:])
            results.append({
                "label": label,
                "passed": False,
                "expected": repr(expected),
                "actual": f"ERROR: {short_tb}",
                "stdout": stdout_capture.getvalue()
            })

    return jsonify({
        "ok": True,
        "all_passed": all_passed,
        "results": results,
        "score": f"{sum(1 for r in results if r['passed'])}/{len(results)}"
    })

# ---------------------------------------------------------------------------
# Heartbeat: called every ~15s by the client WHILE a paid sandbox is open.
# Deducts elapsed minutes from the user's credit balance. Free sandboxes
# send no heartbeat (no-op here either way).
# ---------------------------------------------------------------------------
@sandbox_bp.route("/api/sandbox/heartbeat", methods=["GET","POST"])
@require_login
def sandbox_heartbeat():
    data = request.get_json(force=True, silent=True) or {}
    sb_id = data.get("id", "")
    seconds = float(data.get("seconds", 0) or 0)
    seconds = max(0, min(seconds, 60))  # clamp per-tick to avoid abuse

    if sb_id in FREE_SANDBOXES:
        return jsonify({"ok": True, "credits_minutes": round(get_credits(), 2), "unlimited": True})

    minutes_used = seconds / 60.0
    current = get_credits()
    new_balance = max(0, current - minutes_used)

    session["credits_minutes"] = new_balance
    update_profile(session["user_id"], {"credits_minutes": new_balance})

    return jsonify({
        "ok": True,
        "credits_minutes": round(new_balance, 2),
        "unlimited": False,
        "out_of_credits": new_balance <= 0
    })

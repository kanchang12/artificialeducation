import os
from flask import Blueprint, render_template, session, redirect, url_for, Response

main_bp = Blueprint("main", __name__)

SITE_URL = os.environ.get("SITE_URL", "https://aiwithai.online")

@main_bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("builds.builds_list"))
    return render_template("landing.html")

@main_bp.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("builds.builds_list"))
    return render_template("auth.html", mode="login")

@main_bp.route("/register")
def register_page():
    if session.get("user_id"):
        return redirect(url_for("builds.builds_list"))
    return render_template("auth.html", mode="register")

@main_bp.route("/upgrade")
def upgrade_page():
    if not session.get("user_id"):
        return redirect(url_for("main.login_page"))
    return render_template("upgrade.html", user_name=session.get("user_name", ""),
                           stripe_configured=bool(os.environ.get("STRIPE_SECRET_KEY")))

@main_bp.route("/try-free", methods=["GET", "POST"])
def try_free_page():
    return redirect(url_for("main.index") + "#try-free")

@main_bp.route("/privacy")
def privacy_page():
    return render_template("privacy.html")

@main_bp.route("/terms")
def terms_page():
    return render_template("terms.html")

# ---------------------------------------------------------------------------
# SEO / AEO
# ---------------------------------------------------------------------------
@main_bp.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /login",
        "Allow: /register",
        "Allow: /try-free",
        "Allow: /privacy",
        "Allow: /terms",
        "Allow: /upgrade",
        "Disallow: /account",
        "Disallow: /builds",
        "Disallow: /admin",
        "Disallow: /api/",
        f"Sitemap: {SITE_URL}/sitemap.xml",
    ]
    return Response("\n".join(lines), mimetype="text/plain")

@main_bp.route("/sitemap.xml")
def sitemap_xml():
    static_paths = ["/login", "/register", "/try-free", "/privacy", "/terms", "/upgrade"]
    urls = "".join(f"<url><loc>{SITE_URL}{p}</loc></url>" for p in static_paths)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, mimetype="application/xml")

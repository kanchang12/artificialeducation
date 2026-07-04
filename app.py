import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from routes.auth import auth_bp
from routes.main import main_bp
from routes.billing import billing_bp
from routes.account import account_bp
from routes.admin import admin_bp
from routes.builds import builds_bp
from routes.labs import labs_bp
from routes.sandbox import sandbox_bp
from routes.blackbox import blackbox_bp
from routes.try_free import try_free_bp
from routes.youtube import youtube_bp

from supabase_client import init_db
init_db()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(account_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(builds_bp)
app.register_blueprint(labs_bp)
app.register_blueprint(sandbox_bp)
app.register_blueprint(blackbox_bp)
app.register_blueprint(try_free_bp)
app.register_blueprint(youtube_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)

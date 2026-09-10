"""
app.py — JanSolve Main Application
Digital Platform to Crowdsource Societal Challenges and Collaborative Problem Solving
SIH26043 | Government of Jharkhand
"""

import os
from flask import Flask, render_template, session
from database import init_db, seed_db, get_db
from auth import auth_bp
from routes.citizen import citizen_bp
from routes.government import government_bp
from routes.expert import expert_bp
from routes.admin import admin_bp

# ════════════════════════════════════════════
#  APP FACTORY
# ════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = 'jansolve-sih2026-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ════════════════════════════════════════════
#  REGISTER BLUEPRINTS
# ════════════════════════════════════════════

app.register_blueprint(auth_bp)
app.register_blueprint(citizen_bp)
app.register_blueprint(government_bp)
app.register_blueprint(expert_bp)
app.register_blueprint(admin_bp)


# ════════════════════════════════════════════
#  TEMPLATE CONTEXT PROCESSOR
# ════════════════════════════════════════════

@app.context_processor
def inject_globals():
    """Inject common variables into all templates."""
    return {
        'current_user': {
            'id': session.get('user_id'),
            'name': session.get('user_name'),
            'email': session.get('email'),
            'role': session.get('role'),
            'organization': session.get('organization'),
        } if 'user_id' in session else None
    }


# ════════════════════════════════════════════
#  MAIN ROUTES (Blueprint: 'main')
# ════════════════════════════════════════════

from flask import Blueprint
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Homepage with hero section, stats, and recent problems."""
    db = get_db()

    # Platform statistics for homepage
    stats = {
        'problems_reported': db.execute("SELECT COUNT(*) FROM problems").fetchone()[0],
        'solutions_submitted': db.execute("SELECT COUNT(*) FROM solutions").fetchone()[0],
        'experts_connected': db.execute("SELECT COUNT(*) FROM experts").fetchone()[0],
        'problems_solved': db.execute(
            "SELECT COUNT(*) FROM problems WHERE status = 'COMPLETED'"
        ).fetchone()[0],
    }

    # Recent problems for homepage preview
    recent_problems = db.execute(
        """SELECT p.*, u.name as reporter_name, c.icon as category_icon
           FROM problems p
           JOIN users u ON p.user_id = u.id
           LEFT JOIN categories c ON p.category = c.name
           ORDER BY p.created_at DESC LIMIT 6"""
    ).fetchall()

    # Categories for display
    categories = db.execute("SELECT * FROM categories").fetchall()

    db.close()

    return render_template('index.html',
                           stats=stats,
                           recent_problems=recent_problems,
                           categories=categories)


app.register_blueprint(main_bp)


# ════════════════════════════════════════════
#  ERROR HANDLERS
# ════════════════════════════════════════════

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', code=404,
                           message='Page not found'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', code=500,
                           message='Internal server error'), 500


# ════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════

if __name__ == '__main__':
    print("[INIT] JanSolve - Initializing...")
    init_db()
    seed_db()
    print("[SERVER] Starting server at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)

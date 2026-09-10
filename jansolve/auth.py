"""
auth.py — JanSolve Authentication Module
Handles login, registration, logout, and access control decorators.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import get_db

auth_bp = Blueprint('auth', __name__)


# ════════════════════════════════════════════
#  ACCESS CONTROL DECORATORS
# ════════════════════════════════════════════

def login_required(f):
    """Decorator: redirect to login if user is not authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Decorator: restrict access to specific user roles.
    
    Usage:
        @role_required('government', 'admin')
        def gov_dashboard():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('role') not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ════════════════════════════════════════════
#  REGISTRATION
# ════════════════════════════════════════════

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'citizen')
        phone = request.form.get('phone', '').strip()
        organization = request.form.get('organization', '').strip()
        skills = request.form.get('skills', '').strip()

        # ── Validation ──
        errors = []
        if not name:
            errors.append('Name is required.')
        if not email:
            errors.append('Email is required.')
        if not password:
            errors.append('Password is required.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if role not in ('citizen', 'student', 'government', 'admin'):
            errors.append('Invalid role selected.')

        # Check if email already exists
        db = get_db()
        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing_user:
            errors.append('An account with this email already exists.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            db.close()
            return render_template('register.html',
                                   name=name, email=email, role=role,
                                   phone=phone, organization=organization,
                                   skills=skills)

        # ── Create user ──
        password_hash = generate_password_hash(password)
        db.execute(
            """INSERT INTO users (name, email, password_hash, role, phone, organization, skills) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, email, password_hash, role, phone or None,
             organization or None, skills or None)
        )

        # If role is student, also create an expert profile
        if role == 'student' and skills:
            user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                """INSERT INTO experts (user_id, name, skills, organization, expertise_area, match_keywords)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, name, skills, organization or None,
                 skills.split(',')[0].strip() if skills else None,
                 skills.lower())
            )

        db.commit()
        db.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


# ════════════════════════════════════════════
#  LOGIN
# ════════════════════════════════════════════

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html', email=email)

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        db.close()

        if user is None or not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', email=email)

        # ── Set session ──
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['email'] = user['email']
        session['role'] = user['role']
        session['organization'] = user['organization']

        flash(f'Welcome back, {user["name"]}!', 'success')

        # ── Redirect based on role ──
        role_dashboards = {
            'citizen': 'citizen.dashboard',
            'student': 'expert.dashboard',
            'government': 'government.dashboard',
            'admin': 'admin.dashboard',
        }
        return redirect(url_for(role_dashboards.get(user['role'], 'main.index')))

    return render_template('login.html')


# ════════════════════════════════════════════
#  LOGOUT
# ════════════════════════════════════════════

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

"""
routes/admin.py — Admin Routes Blueprint
Handles platform administration, user directory management, category taxonomy management,
and system-wide analytics.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from auth import login_required, role_required
from database import get_db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required
@role_required('admin')
def dashboard():
    db = get_db()

    stats = {
        'total_users': db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'total_citizens': db.execute("SELECT COUNT(*) FROM users WHERE role = 'citizen'").fetchone()[0],
        'total_students': db.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0],
        'total_gov': db.execute("SELECT COUNT(*) FROM users WHERE role = 'government'").fetchone()[0],
        'total_problems': db.execute("SELECT COUNT(*) FROM problems").fetchone()[0],
        'total_solutions': db.execute("SELECT COUNT(*) FROM solutions").fetchone()[0],
        'total_experts': db.execute("SELECT COUNT(*) FROM experts").fetchone()[0],
        'total_votes': db.execute("SELECT COUNT(*) FROM votes").fetchone()[0],
    }

    recent_users = db.execute(
        "SELECT * FROM users ORDER BY created_at DESC LIMIT 8"
    ).fetchall()

    categories = db.execute("SELECT * FROM categories").fetchall()
    db.close()

    return render_template('admin_dashboard.html',
                           stats=stats,
                           recent_users=recent_users,
                           categories=categories)


@admin_bp.route('/users')
@login_required
@role_required('admin')
def users_list():
    """Manage all registered users across all 4 roles."""
    db = get_db()
    role_filter = request.args.get('role', '').strip()

    if role_filter:
        users = db.execute("SELECT * FROM users WHERE role = ? ORDER BY created_at DESC", (role_filter,)).fetchall()
    else:
        users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()

    db.close()
    return render_template('admin_users.html', users=users, role_filter=role_filter)


@admin_bp.route('/users/<int:user_id>/change_role', methods=['POST'])
@login_required
@role_required('admin')
def change_user_role(user_id):
    """Change user role."""
    new_role = request.form.get('role')
    if new_role in ('citizen', 'student', 'government', 'admin'):
        db = get_db()
        db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        db.commit()
        db.close()
        flash(f'User role updated to {new_role}.', 'success')
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/categories', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def categories_list():
    """Manage problem categories."""
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        icon = request.form.get('icon', '📋').strip()

        if name:
            try:
                db.execute(
                    "INSERT INTO categories (name, description, icon) VALUES (?, ?, ?)",
                    (name, description, icon)
                )
                db.commit()
                flash(f'Category "{name}" added successfully.', 'success')
            except Exception:
                flash('Category with this name already exists.', 'danger')
        return redirect(url_for('admin.categories_list'))

    categories = db.execute("SELECT * FROM categories").fetchall()
    db.close()
    return render_template('admin_categories.html', categories=categories)

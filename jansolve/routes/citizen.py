"""
routes/citizen.py — Citizen Routes Blueprint
Handles citizen dashboard, problem reporting, duplicate warning, viewing, upvoting, and solution voting.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename
from auth import login_required, role_required
from database import get_db
from ai.categorization import analyze_problem
from ai.duplicate_detection import find_similar_problems

citizen_bp = Blueprint('citizen', __name__, url_prefix='/citizen')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@citizen_bp.route('/dashboard')
@login_required
@role_required('citizen')
def dashboard():
    db = get_db()
    user_id = session['user_id']

    # Get citizen's statistics
    total_reported = db.execute(
        "SELECT COUNT(*) FROM problems WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    verified = db.execute(
        "SELECT COUNT(*) FROM problems WHERE user_id = ? AND status != 'REPORTED' AND status != 'REJECTED'",
        (user_id,)
    ).fetchone()[0]

    solved = db.execute(
        "SELECT COUNT(*) FROM problems WHERE user_id = ? AND status = 'COMPLETED'",
        (user_id,)
    ).fetchone()[0]

    in_progress = db.execute(
        "SELECT COUNT(*) FROM problems WHERE user_id = ? AND status = 'IN_PROGRESS'",
        (user_id,)
    ).fetchone()[0]

    # Get recent problems by this citizen
    my_problems = db.execute(
        """SELECT p.*, c.icon as category_icon 
           FROM problems p 
           LEFT JOIN categories c ON p.category = c.name
           WHERE p.user_id = ? 
           ORDER BY p.created_at DESC LIMIT 10""",
        (user_id,)
    ).fetchall()

    # Get recent problems from all citizens
    recent_problems = db.execute(
        """SELECT p.*, u.name as reporter_name, c.icon as category_icon
           FROM problems p 
           JOIN users u ON p.user_id = u.id
           LEFT JOIN categories c ON p.category = c.name
           ORDER BY p.created_at DESC LIMIT 5"""
    ).fetchall()

    db.close()

    return render_template('citizen_dashboard.html',
                           total_reported=total_reported,
                           verified=verified,
                           solved=solved,
                           in_progress=in_progress,
                           my_problems=my_problems,
                           recent_problems=recent_problems)


@citizen_bp.route('/report', methods=['GET', 'POST'])
@login_required
@role_required('citizen')
def report_problem():
    db = get_db()
    categories = db.execute("SELECT * FROM categories").fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        user_category = request.form.get('category', '').strip()
        force_submit = request.form.get('force_submit', '0') == '1'

        if not title or not description or not location:
            flash('Title, description, and location are required.', 'danger')
            db.close()
            return render_template('report_problem.html', categories=categories,
                                   title=title, description=description, location=location)

        # ── Step 1: AI Categorization & Priority Analysis ──
        ai_res = analyze_problem(title, description)
        predicted_category = ai_res['category']
        predicted_sub_category = ai_res['sub_category']
        predicted_priority = ai_res['priority']
        predicted_confidence = ai_res['confidence']

        # If user picked a category, prioritize user's choice or fallback to AI prediction
        final_category = user_category if user_category else predicted_category

        # ── Step 2: Check for Duplicate / Similar Problems ──
        if not force_submit:
            existing_problems = db.execute(
                "SELECT id, title, description, location, category, support_count, status FROM problems"
            ).fetchall()
            similar_matches = find_similar_problems(title, description, existing_problems, threshold=0.40)

            if similar_matches:
                db.close()
                return render_template('duplicate_warning.html',
                                       new_title=title,
                                       new_description=description,
                                       new_location=location,
                                       new_category=final_category,
                                       ai_res=ai_res,
                                       similar_matches=similar_matches)

        # ── Step 3: Handle Optional Image Upload ──
        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                fname = secure_filename(file.filename)
                import time
                unique_name = f"{int(time.time())}_{fname}"
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
                image_filename = unique_name

        # ── Step 4: Insert into Database ──
        cursor = db.cursor()
        cursor.execute(
            """INSERT INTO problems 
               (user_id, title, description, location, category, sub_category, priority,
                status, image_path, ai_category, ai_sub_category, ai_priority, ai_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'REPORTED', ?, ?, ?, ?, ?)""",
            (session['user_id'], title, description, location, final_category,
             predicted_sub_category, predicted_priority, image_filename,
             predicted_category, predicted_sub_category, predicted_priority, predicted_confidence)
        )
        problem_id = cursor.lastrowid
        db.commit()
        db.close()

        flash(f'Problem reported successfully! AI categorized as {predicted_category} ({int(predicted_confidence*100)}% confidence).', 'success')
        return redirect(url_for('citizen.problem_details', problem_id=problem_id))

    db.close()
    return render_template('report_problem.html', categories=categories)


@citizen_bp.route('/problem/<int:problem_id>')
def problem_details(problem_id):
    """View full problem details, AI analysis, solutions, and community voting."""
    db = get_db()
    user_id = session.get('user_id')

    problem = db.execute(
        """SELECT p.*, u.name as reporter_name, u.organization as reporter_org, c.icon as category_icon,
                  d.name as department_name
           FROM problems p
           JOIN users u ON p.user_id = u.id
           LEFT JOIN categories c ON p.category = c.name
           LEFT JOIN departments d ON p.department_id = d.id
           WHERE p.id = ?""",
        (problem_id,)
    ).fetchone()

    if not problem:
        flash('Problem not found.', 'danger')
        db.close()
        return redirect(url_for('main.index'))

    # Check if current user supported this problem
    has_supported = False
    user_voted_solutions = set()
    if user_id:
        support = db.execute(
            "SELECT 1 FROM problem_supports WHERE user_id = ? AND problem_id = ?",
            (user_id, problem_id)
        ).fetchone()
        has_supported = bool(support)

        # Get list of solution IDs this user voted for
        user_votes = db.execute(
            "SELECT solution_id FROM votes WHERE user_id = ?", (user_id,)
        ).fetchall()
        user_voted_solutions = {v['solution_id'] for v in user_votes}

    # Get solutions for this problem with ranking calculation
    solutions = db.execute(
        """SELECT s.*, u.name as author_name, u.organization as author_org
           FROM solutions s
           JOIN users u ON s.user_id = u.id
           WHERE s.problem_id = ?
           ORDER BY s.selected DESC, s.overall_score DESC, s.vote_count DESC""",
        (problem_id,)
    ).fetchall()

    # Get impact metrics if completed
    impact = db.execute(
        "SELECT * FROM impact_metrics WHERE problem_id = ?", (problem_id,)
    ).fetchone()

    db.close()

    return render_template('problem_details.html',
                           problem=problem,
                           solutions=solutions,
                           impact=impact,
                           has_supported=has_supported,
                           user_voted_solutions=user_voted_solutions)


@citizen_bp.route('/support/<int:problem_id>', methods=['POST'])
@login_required
def support_problem(problem_id):
    """Upvote/support an existing problem to boost its community priority."""
    db = get_db()
    user_id = session['user_id']

    try:
        db.execute(
            "INSERT INTO problem_supports (user_id, problem_id) VALUES (?, ?)",
            (user_id, problem_id)
        )
        db.execute(
            "UPDATE problems SET support_count = support_count + 1 WHERE id = ?",
            (problem_id,)
        )
        db.commit()
        flash('Thank you for supporting this problem! Community interest helps officials prioritize it.', 'success')
    except Exception:
        flash('You have already supported this problem.', 'info')

    db.close()
    return redirect(url_for('citizen.problem_details', problem_id=problem_id))


@citizen_bp.route('/vote/<int:solution_id>', methods=['POST'])
@login_required
def vote_solution(solution_id):
    """Vote on a proposed solution. Calculates 40% public vote + 30% feasibility + 30% impact score."""
    db = get_db()
    user_id = session['user_id']

    solution = db.execute("SELECT * FROM solutions WHERE id = ?", (solution_id,)).fetchone()
    if not solution:
        flash('Solution not found.', 'danger')
        db.close()
        return redirect(url_for('main.index'))

    problem_id = solution['problem_id']

    # Prevent duplicate voting by same user
    existing_vote = db.execute(
        "SELECT 1 FROM votes WHERE user_id = ? AND solution_id = ?",
        (user_id, solution_id)
    ).fetchone()

    if existing_vote:
        flash('You have already voted for this solution.', 'warning')
        db.close()
        return redirect(url_for('citizen.problem_details', problem_id=problem_id))

    # Insert vote
    db.execute("INSERT INTO votes (user_id, solution_id) VALUES (?, ?)", (user_id, solution_id))
    db.execute("UPDATE solutions SET vote_count = vote_count + 1 WHERE id = ?", (solution_id,))

    # Recalculate ranking score for all solutions under this problem
    # Formula: Public vote (40%) + Feasibility (30%) + Expected Impact (30%)
    all_sols = db.execute(
        "SELECT id, vote_count, feasibility_score, impact_score FROM solutions WHERE problem_id = ?",
        (problem_id,)
    ).fetchall()

    max_votes = max([s['vote_count'] for s in all_sols] + [1])
    for s in all_sols:
        norm_votes = (s['vote_count'] / max_votes) * 10.0  # Scale to 0-10
        feasibility = s['feasibility_score'] or 7.0         # Default 7/10
        impact = s['impact_score'] or 7.5                  # Default 7.5/10

        overall = round((norm_votes * 0.40) + (feasibility * 0.30) + (impact * 0.30), 2)
        db.execute(
            "UPDATE solutions SET overall_score = ?, feasibility_score = ?, impact_score = ? WHERE id = ?",
            (overall, feasibility, impact, s['id'])
        )

    db.commit()
    db.close()

    flash('Your vote has been recorded! Solution ranking updated.', 'success')
    return redirect(url_for('citizen.problem_details', problem_id=problem_id))


@citizen_bp.route('/browse')
def browse_problems():
    """Browse, filter, and search societal challenges."""
    db = get_db()
    query = request.args.get('q', '').strip()
    cat_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()

    sql = """
        SELECT p.*, u.name as reporter_name, c.icon as category_icon,
               (SELECT COUNT(*) FROM solutions WHERE problem_id = p.id) as solution_count
        FROM problems p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category = c.name
        WHERE 1=1
    """
    params = []

    if query:
        sql += " AND (p.title LIKE ? OR p.description LIKE ? OR p.location LIKE ?)"
        q_wild = f"%{query}%"
        params.extend([q_wild, q_wild, q_wild])

    if cat_filter:
        sql += " AND p.category = ?"
        params.append(cat_filter)

    if status_filter:
        sql += " AND p.status = ?"
        params.append(status_filter)

    sql += " ORDER BY p.created_at DESC"

    problems = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    db.close()

    return render_template('browse_problems.html',
                           problems=problems,
                           categories=categories,
                           query=query,
                           cat_filter=cat_filter,
                           status_filter=status_filter)

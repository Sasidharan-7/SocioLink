"""
routes/government.py — Government Official Routes Blueprint
Handles government dashboard, problem review & verification, department assignment,
expert recommendations via AI, solution evaluation, and ground impact metrics entry.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from auth import login_required, role_required
from database import get_db
from ai.expert_matching import match_experts_for_problem

government_bp = Blueprint('government', __name__, url_prefix='/gov')


@government_bp.route('/dashboard')
@login_required
@role_required('government')
def dashboard():
    db = get_db()

    stats = {
        'total': db.execute("SELECT COUNT(*) FROM problems").fetchone()[0],
        'reported': db.execute("SELECT COUNT(*) FROM problems WHERE status = 'REPORTED'").fetchone()[0],
        'verified': db.execute("SELECT COUNT(*) FROM problems WHERE status = 'VERIFIED'").fetchone()[0],
        'under_review': db.execute("SELECT COUNT(*) FROM problems WHERE status = 'UNDER_REVIEW'").fetchone()[0],
        'in_progress': db.execute("SELECT COUNT(*) FROM problems WHERE status = 'IN_PROGRESS'").fetchone()[0],
        'completed': db.execute("SELECT COUNT(*) FROM problems WHERE status = 'COMPLETED'").fetchone()[0],
        'high_priority': db.execute("SELECT COUNT(*) FROM problems WHERE priority = 'HIGH'").fetchone()[0],
    }

    category_stats = db.execute(
        """SELECT category, COUNT(*) as count 
           FROM problems GROUP BY category ORDER BY count DESC"""
    ).fetchall()

    recent_problems = db.execute(
        """SELECT p.*, u.name as reporter_name 
           FROM problems p 
           JOIN users u ON p.user_id = u.id
           ORDER BY p.created_at DESC LIMIT 8"""
    ).fetchall()

    pending_verification = db.execute(
        """SELECT p.*, u.name as reporter_name 
           FROM problems p 
           JOIN users u ON p.user_id = u.id
           WHERE p.status = 'REPORTED'
           ORDER BY p.created_at DESC LIMIT 5"""
    ).fetchall()

    db.close()

    return render_template('government_dashboard.html',
                           stats=stats,
                           category_stats=category_stats,
                           recent_problems=recent_problems,
                           pending_verification=pending_verification)


@government_bp.route('/problems')
@login_required
@role_required('government')
def problem_list():
    """All problems with admin filters."""
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    category_filter = request.args.get('category', '').strip()
    priority_filter = request.args.get('priority', '').strip()

    sql = """
        SELECT p.*, u.name as reporter_name, d.name as department_name,
               (SELECT COUNT(*) FROM solutions WHERE problem_id = p.id) as solution_count
        FROM problems p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN departments d ON p.department_id = d.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND p.status = ?"
        params.append(status_filter)
    if category_filter:
        sql += " AND p.category = ?"
        params.append(category_filter)
    if priority_filter:
        sql += " AND p.priority = ?"
        params.append(priority_filter)

    sql += " ORDER BY CASE WHEN p.status = 'REPORTED' THEN 0 ELSE 1 END, p.created_at DESC"

    problems = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    db.close()

    return render_template('government_problems.html',
                           problems=problems,
                           categories=categories,
                           status_filter=status_filter,
                           category_filter=category_filter,
                           priority_filter=priority_filter)


@government_bp.route('/problem/<int:problem_id>', methods=['GET', 'POST'])
@login_required
@role_required('government')
def view_problem(problem_id):
    """View problem in official console, verify/reject, assign department, and run AI expert matching."""
    db = get_db()

    if request.method == 'POST':
        action = request.form.get('action')
        new_status = request.form.get('status')
        department_id = request.form.get('department_id')
        new_priority = request.form.get('priority')

        if action == 'verify':
            db.execute(
                """UPDATE problems SET status = 'VERIFIED', verified_by = ?, verified_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (session['user_id'], problem_id)
            )
            flash('Problem officially VERIFIED! Open for student/expert solution submissions.', 'success')
        elif action == 'reject':
            db.execute("UPDATE problems SET status = 'REJECTED' WHERE id = ?", (problem_id,))
            flash('Problem marked as REJECTED.', 'warning')
        elif action == 'update_meta':
            db.execute(
                "UPDATE problems SET status = ?, department_id = ?, priority = ? WHERE id = ?",
                (new_status, department_id or None, new_priority, problem_id)
            )
            flash('Problem details & department assignment updated.', 'success')

        db.commit()
        return redirect(url_for('government.view_problem', problem_id=problem_id))

    problem = db.execute(
        """SELECT p.*, u.name as reporter_name, u.email as reporter_email, u.phone as reporter_phone,
                  d.name as department_name, v.name as verifier_name
           FROM problems p
           JOIN users u ON p.user_id = u.id
           LEFT JOIN departments d ON p.department_id = d.id
           LEFT JOIN users v ON p.verified_by = v.id
           WHERE p.id = ?""",
        (problem_id,)
    ).fetchone()

    if not problem:
        flash('Problem not found.', 'danger')
        db.close()
        return redirect(url_for('government.dashboard'))

    # Retrieve all solutions for this problem
    solutions = db.execute(
        """SELECT s.*, u.name as author_name, u.organization as author_org, u.email as author_email
           FROM solutions s
           JOIN users u ON s.user_id = u.id
           WHERE s.problem_id = ?
           ORDER BY s.selected DESC, s.overall_score DESC, s.vote_count DESC""",
        (problem_id,)
    ).fetchall()

    # Retrieve all departments for dropdown
    departments = db.execute("SELECT * FROM departments").fetchall()

    # ── AI Module 6: NLP Expert & University Matching ──
    all_experts = db.execute("SELECT * FROM experts").fetchall()
    recommended_experts = match_experts_for_problem(
        problem['title'], problem['description'], problem['category'], all_experts, top_n=4
    )

    # Impact metrics if present
    impact = db.execute("SELECT * FROM impact_metrics WHERE problem_id = ?", (problem_id,)).fetchone()

    db.close()

    return render_template('government_problem_detail.html',
                           problem=problem,
                           solutions=solutions,
                           departments=departments,
                           recommended_experts=recommended_experts,
                           impact=impact)


@government_bp.route('/select_solution/<int:solution_id>', methods=['POST'])
@login_required
@role_required('government')
def select_solution(solution_id):
    """Government selects winning solution and moves problem to SOLUTION_SELECTED / IN_PROGRESS."""
    db = get_db()

    solution = db.execute("SELECT * FROM solutions WHERE id = ?", (solution_id,)).fetchone()
    if not solution:
        flash('Solution not found.', 'danger')
        db.close()
        return redirect(url_for('government.dashboard'))

    problem_id = solution['problem_id']

    # Reset any previous selected solutions for this problem
    db.execute("UPDATE solutions SET selected = 0 WHERE problem_id = ?", (problem_id,))
    # Mark this solution as selected
    db.execute("UPDATE solutions SET selected = 1 WHERE id = ?", (solution_id,))
    # Update problem status to SOLUTION_SELECTED
    db.execute("UPDATE problems SET status = 'SOLUTION_SELECTED' WHERE id = ?", (problem_id,))

    db.commit()
    db.close()

    flash('Winning solution officially selected! Status moved to SOLUTION_SELECTED.', 'success')
    return redirect(url_for('government.view_problem', problem_id=problem_id))


@government_bp.route('/start_implementation/<int:problem_id>', methods=['POST'])
@login_required
@role_required('government')
def start_implementation(problem_id):
    """Move problem status to IN_PROGRESS."""
    db = get_db()
    db.execute("UPDATE problems SET status = 'IN_PROGRESS' WHERE id = ?", (problem_id,))
    db.commit()
    db.close()
    flash('Implementation phase started! Status changed to IN PROGRESS.', 'info')
    return redirect(url_for('government.view_problem', problem_id=problem_id))


@government_bp.route('/impact/<int:problem_id>', methods=['GET', 'POST'])
@login_required
@role_required('government')
def record_impact(problem_id):
    """Record ground impact metrics after implementation is completed."""
    db = get_db()
    problem = db.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()

    if not problem:
        flash('Problem not found.', 'danger')
        db.close()
        return redirect(url_for('government.dashboard'))

    existing_impact = db.execute("SELECT * FROM impact_metrics WHERE problem_id = ?", (problem_id,)).fetchone()

    if request.method == 'POST':
        before_metric = request.form.get('before_metric', '').strip()
        before_value = float(request.form.get('before_value', '0') or '0')
        after_metric = request.form.get('after_metric', '').strip()
        after_value = float(request.form.get('after_value', '0') or '0')
        people_benefited = int(request.form.get('people_benefited', '0') or '0')
        implementation_cost = request.form.get('implementation_cost', '').strip()
        completion_date = request.form.get('completion_date', '').strip()
        description = request.form.get('description', '').strip()

        # Calculate improvement percentage
        # Example: Before 120 complaints/mo, After 35 complaints/mo => 70.8% improvement
        if before_value > 0:
            improvement = round(((before_value - after_value) / before_value) * 100, 1)
        else:
            improvement = 100.0

        if existing_impact:
            db.execute(
                """UPDATE impact_metrics SET 
                   before_metric = ?, before_value = ?, after_metric = ?, after_value = ?,
                   people_benefited = ?, implementation_cost = ?, completion_date = ?,
                   description = ?, improvement_percentage = ?
                   WHERE problem_id = ?""",
                (before_metric, before_value, after_metric, after_value,
                 people_benefited, implementation_cost, completion_date,
                 description, improvement, problem_id)
            )
        else:
            db.execute(
                """INSERT INTO impact_metrics 
                   (problem_id, before_metric, before_value, after_metric, after_value,
                    people_benefited, implementation_cost, completion_date, description, improvement_percentage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (problem_id, before_metric, before_value, after_metric, after_value,
                 people_benefited, implementation_cost, completion_date, description, improvement)
            )

        # Automatically mark problem as COMPLETED!
        db.execute("UPDATE problems SET status = 'COMPLETED' WHERE id = ?", (problem_id,))
        db.commit()
        db.close()

        flash(f'Impact metrics recorded! Ground improvement measured at {improvement}%. Problem COMPLETED.', 'success')
        return redirect(url_for('government.view_problem', problem_id=problem_id))

    db.close()
    return render_template('impact_form.html', problem=problem, impact=existing_impact)


@government_bp.route('/impact-overview')
@login_required
@role_required('government')
def impact_overview():
    """Impact analytics across all implemented civic solutions."""
    db = get_db()
    impact_cases = db.execute(
        """SELECT m.*, p.title as problem_title, p.location, p.category
           FROM impact_metrics m
           JOIN problems p ON m.problem_id = p.id
           ORDER BY m.created_at DESC"""
    ).fetchall()

    total_benefited = sum(c['people_benefited'] for c in impact_cases) if impact_cases else 0
    avg_improvement = round(sum(c['improvement_percentage'] for c in impact_cases) / len(impact_cases), 1) if impact_cases else 0.0

    db.close()
    return render_template('impact.html',
                           impact_cases=impact_cases,
                           total_benefited=total_benefited,
                           avg_improvement=avg_improvement)

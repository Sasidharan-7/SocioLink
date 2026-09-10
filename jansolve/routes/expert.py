"""
routes/expert.py — Student / Expert Routes Blueprint
Handles innovator dashboard, AI-recommended challenge matching,
challenge discovery, profile/skills setup, and solution submission.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from auth import login_required, role_required
from database import get_db
from ai.expert_matching import match_experts_for_problem

expert_bp = Blueprint('expert', __name__, url_prefix='/expert')


@expert_bp.route('/dashboard')
@login_required
@role_required('student')
def dashboard():
    db = get_db()
    user_id = session['user_id']

    # Current user details
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    # User's submitted solutions
    my_solutions = db.execute(
        """SELECT s.*, p.title as problem_title, p.status as problem_status, p.id as problem_id
           FROM solutions s
           JOIN problems p ON s.problem_id = p.id
           WHERE s.user_id = ?
           ORDER BY s.created_at DESC""",
        (user_id,)
    ).fetchall()

    # Open verified challenges
    open_challenges = db.execute(
        """SELECT p.*, u.name as reporter_name, c.icon as category_icon,
                  (SELECT COUNT(*) FROM solutions WHERE problem_id = p.id) as solution_count
           FROM problems p
           JOIN users u ON p.user_id = u.id
           LEFT JOIN categories c ON p.category = c.name
           WHERE p.status IN ('VERIFIED', 'UNDER_REVIEW')
           ORDER BY p.created_at DESC LIMIT 6"""
    ).fetchall()

    # AI Personalized Recommendations: Match challenges to user's skills
    recommended_challenges = []
    user_skills = user['skills'] or ''
    if user_skills and open_challenges:
        # Create dummy expert entry for current user
        user_exp = [{
            'id': user['id'], 'name': user['name'], 'skills': user_skills,
            'expertise_area': user_skills, 'department': user['organization'] or '',
            'organization': user['organization'] or '', 'match_keywords': user_skills
        }]
        for p in open_challenges:
            match_res = match_experts_for_problem(p['title'], p['description'], p['category'], user_exp, top_n=1)
            if match_res:
                score = match_res[0]['match_percent']
                if score >= 50:
                    p_dict = dict(p)
                    p_dict['match_percent'] = score
                    recommended_challenges.append(p_dict)

        recommended_challenges.sort(key=lambda x: x['match_percent'], reverse=True)

    total_solutions = len(my_solutions)
    selected_solutions = sum(1 for s in my_solutions if s['selected'])

    db.close()

    return render_template('expert_dashboard.html',
                           my_solutions=my_solutions,
                           open_challenges=open_challenges,
                           recommended_challenges=recommended_challenges,
                           total_solutions=total_solutions,
                           selected_solutions=selected_solutions,
                           user=user)


@expert_bp.route('/challenges')
@login_required
@role_required('student')
def challenges():
    """Browse all open challenges ready for student innovation."""
    db = get_db()
    query = request.args.get('q', '').strip()
    cat_filter = request.args.get('category', '').strip()

    sql = """
        SELECT p.*, u.name as reporter_name, c.icon as category_icon,
               (SELECT COUNT(*) FROM solutions WHERE problem_id = p.id) as solution_count
        FROM problems p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category = c.name
        WHERE p.status IN ('VERIFIED', 'UNDER_REVIEW')
    """
    params = []
    if query:
        sql += " AND (p.title LIKE ? OR p.description LIKE ? OR p.location LIKE ?)"
        q_wild = f"%{query}%"
        params.extend([q_wild, q_wild, q_wild])
    if cat_filter:
        sql += " AND p.category = ?"
        params.append(cat_filter)

    sql += " ORDER BY p.created_at DESC"

    open_challenges = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT * FROM categories").fetchall()
    db.close()

    return render_template('expert_challenges.html',
                           challenges=open_challenges,
                           categories=categories,
                           query=query,
                           cat_filter=cat_filter)


@expert_bp.route('/submit/<int:problem_id>', methods=['GET', 'POST'])
@login_required
@role_required('student')
def submit_solution(problem_id):
    """Submit solution for an open societal challenge."""
    db = get_db()
    problem = db.execute(
        """SELECT p.*, u.name as reporter_name, c.icon as category_icon 
           FROM problems p 
           JOIN users u ON p.user_id = u.id
           LEFT JOIN categories c ON p.category = c.name
           WHERE p.id = ?""",
        (problem_id,)
    ).fetchone()

    if not problem:
        flash('Problem not found.', 'danger')
        db.close()
        return redirect(url_for('expert.dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        estimated_cost = request.form.get('estimated_cost', '').strip()
        implementation_time = request.form.get('implementation_time', '').strip()
        expected_impact = request.form.get('expected_impact', '').strip()
        required_resources = request.form.get('required_resources', '').strip()

        if not title or not description:
            flash('Title and description are required.', 'danger')
            db.close()
            return render_template('submit_solution.html', problem=problem,
                                   title=title, description=description)

        db.execute(
            """INSERT INTO solutions 
               (problem_id, user_id, title, description, estimated_cost,
                implementation_time, expected_impact, required_resources,
                vote_count, feasibility_score, impact_score, overall_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 7.5, 8.0, 4.65)""",
            (problem_id, session['user_id'], title, description, estimated_cost,
             implementation_time, expected_impact, required_resources)
        )

        # Move problem status to UNDER_REVIEW if still VERIFIED
        if problem['status'] == 'VERIFIED':
            db.execute("UPDATE problems SET status = 'UNDER_REVIEW' WHERE id = ?", (problem_id,))

        db.commit()
        db.close()

        flash('Solution proposed successfully! Citizens can now review and vote on your proposal.', 'success')
        return redirect(url_for('citizen.problem_details', problem_id=problem_id))

    db.close()
    return render_template('submit_solution.html', problem=problem)


@expert_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def profile():
    """Manage skills, university, and expertise areas for AI matching."""
    db = get_db()
    user_id = session['user_id']

    if request.method == 'POST':
        organization = request.form.get('organization', '').strip()
        skills = request.form.get('skills', '').strip()
        bio = request.form.get('bio', '').strip()

        db.execute(
            "UPDATE users SET organization = ?, skills = ?, bio = ? WHERE id = ?",
            (organization, skills, bio, user_id)
        )

        # Also update or insert in experts table
        existing_exp = db.execute("SELECT id FROM experts WHERE user_id = ?", (user_id,)).fetchone()
        user_name = session['user_name']
        if existing_exp:
            db.execute(
                """UPDATE experts SET organization = ?, skills = ?, expertise_area = ?, match_keywords = ?
                   WHERE user_id = ?""",
                (organization, skills, skills.split(',')[0].strip() if skills else None,
                 f"{organization} {skills}".lower(), user_id)
            )
        else:
            db.execute(
                """INSERT INTO experts (user_id, name, skills, organization, expertise_area, match_keywords)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, user_name, skills, organization,
                 skills.split(',')[0].strip() if skills else None,
                 f"{organization} {skills}".lower())
            )

        db.commit()
        flash('Profile and skills updated! AI challenge recommendations refreshed.', 'success')
        return redirect(url_for('expert.dashboard'))

    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    return render_template('expert_profile.html', user=user)

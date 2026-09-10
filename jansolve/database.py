"""
database.py — JanSolve Database Module
Handles SQLite database initialization, schema creation, and seed data.
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')


def get_db():
    """Get a database connection with row factory enabled."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    """Create all tables if they don't exist."""
    db = get_db()
    cursor = db.cursor()

    # ── Users table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('citizen', 'student', 'government', 'admin')),
            phone TEXT,
            organization TEXT,
            skills TEXT,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Categories table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT
        )
    ''')

    # ── Departments table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
        )
    ''')

    # ── Problems table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT,
            category TEXT,
            sub_category TEXT,
            priority TEXT DEFAULT 'MEDIUM',
            status TEXT DEFAULT 'REPORTED' CHECK(status IN (
                'REPORTED', 'VERIFIED', 'UNDER_REVIEW', 
                'SOLUTION_SELECTED', 'IN_PROGRESS', 'COMPLETED', 'REJECTED'
            )),
            image_path TEXT,
            ai_category TEXT,
            ai_sub_category TEXT,
            ai_priority TEXT,
            ai_confidence REAL,
            support_count INTEGER DEFAULT 0,
            department_id INTEGER,
            verified_by INTEGER,
            verified_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (verified_by) REFERENCES users(id)
        )
    ''')

    # ── Solutions table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            estimated_cost TEXT,
            implementation_time TEXT,
            expected_impact TEXT,
            required_resources TEXT,
            vote_count INTEGER DEFAULT 0,
            feasibility_score REAL DEFAULT 0,
            impact_score REAL DEFAULT 0,
            overall_score REAL DEFAULT 0,
            selected INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (problem_id) REFERENCES problems(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── Votes table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            solution_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, solution_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (solution_id) REFERENCES solutions(id)
        )
    ''')

    # ── Problem Support (upvotes) table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_supports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, problem_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        )
    ''')

    # ── Experts table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS experts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            skills TEXT,
            organization TEXT,
            department TEXT,
            expertise_area TEXT,
            match_keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # ── Impact Metrics table ──
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS impact_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL UNIQUE,
            before_metric TEXT,
            before_value REAL,
            after_metric TEXT,
            after_value REAL,
            people_benefited INTEGER,
            implementation_cost TEXT,
            completion_date TEXT,
            description TEXT,
            improvement_percentage REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        )
    ''')

    db.commit()
    db.close()
    print("[OK] Database tables created successfully.")


def seed_db():
    """Insert demo data — only if users table is empty."""
    db = get_db()
    cursor = db.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        db.close()
        print("[INFO] Database already seeded. Skipping.")
        return

    # ── Seed Categories ──
    categories = [
        ('Water & Sanitation', 'Drinking water, sewage, drainage, waste management', '💧'),
        ('Roads & Infrastructure', 'Road conditions, bridges, public buildings', '🛣️'),
        ('Healthcare', 'Hospitals, clinics, medical facilities, public health', '🏥'),
        ('Education', 'Schools, colleges, educational infrastructure', '📚'),
        ('Environment', 'Pollution, deforestation, climate issues', '🌿'),
        ('Electricity', 'Power supply, street lights, electrical infrastructure', '⚡'),
        ('Transportation', 'Public transport, bus services, connectivity', '🚌'),
        ('Agriculture', 'Farming, irrigation, crop diseases, market access', '🌾'),
        ('Public Safety', 'Crime, safety measures, emergency services', '🛡️'),
        ('Other', 'Issues not covered by other categories', '📋'),
    ]
    cursor.executemany(
        "INSERT INTO categories (name, description, icon) VALUES (?, ?, ?)",
        categories
    )

    # ── Seed Departments ──
    departments = [
        ('Department of Water Resources', 'Manages water supply and sanitation'),
        ('Department of Roads & Buildings', 'Manages road and infrastructure'),
        ('Department of Health & Family Welfare', 'Manages healthcare facilities'),
        ('Department of Education', 'Manages educational institutions'),
        ('Department of Environment & Forests', 'Manages environmental issues'),
        ('Jharkhand Bijli Vitran Nigam', 'Manages electricity distribution'),
        ('Department of Transport', 'Manages public transportation'),
        ('Department of Agriculture', 'Manages agricultural development'),
        ('Department of Home Affairs', 'Manages public safety and law enforcement'),
    ]
    cursor.executemany(
        "INSERT INTO departments (name, description) VALUES (?, ?)",
        departments
    )

    # ── Seed Users ──
    users = [
        ('Amit Kumar', 'citizen@demo.com', generate_password_hash('citizen123'),
         'citizen', '9876543210', None, None, 'Citizen of Ranchi'),
        ('Priya Sharma', 'student@demo.com', generate_password_hash('student123'),
         'student', '9876543211', 'BIT Mesra', 'Environmental Engineering, Water Treatment, Data Analysis',
         'B.Tech student interested in civic solutions'),
        ('Rajesh Singh', 'gov@demo.com', generate_password_hash('gov123'),
         'government', '9876543212', 'Government of Jharkhand',
         None, 'District Collector, Ranchi'),
        ('Admin User', 'admin@demo.com', generate_password_hash('admin123'),
         'admin', '9876543213', 'JanSolve Platform',
         None, 'Platform Administrator'),
        ('Sunita Devi', 'citizen2@demo.com', generate_password_hash('citizen123'),
         'citizen', '9876543214', None, None, 'Citizen of Jamshedpur'),
        ('Dr. Arvind Mishra', 'expert@demo.com', generate_password_hash('student123'),
         'student', '9876543215', 'IIT(ISM) Dhanbad',
         'Water Treatment, Environmental Science, Public Health',
         'Professor of Environmental Engineering'),
        ('Neha Gupta', 'student2@demo.com', generate_password_hash('student123'),
         'student', '9876543216', 'NIT Jamshedpur',
         'Civil Engineering, Urban Planning, Infrastructure',
         'M.Tech student in Urban Planning'),
    ]
    cursor.executemany(
        """INSERT INTO users (name, email, password_hash, role, phone, organization, skills, bio) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        users
    )

    # ── Seed Experts ──
    experts = [
        (6, 'Dr. Arvind Mishra', 'Water Treatment, Environmental Science, Public Health',
         'IIT(ISM) Dhanbad', 'Environmental Engineering',
         'Water Purification, Waste Management',
         'water sanitation waste treatment pollution drainage sewage'),
        (7, 'Neha Gupta', 'Civil Engineering, Urban Planning, Infrastructure',
         'NIT Jamshedpur', 'Civil Engineering',
         'Road Construction, Urban Development',
         'roads infrastructure bridges construction urban planning buildings'),
        (None, 'Prof. Sanjay Tiwari', 'Public Health, Epidemiology, Healthcare Systems',
         'RIMS Ranchi', 'Medical Sciences',
         'Healthcare Access, Disease Prevention',
         'healthcare hospital medical health clinic disease prevention'),
        (None, 'Dr. Meena Kumari', 'Agricultural Science, Soil Analysis, Crop Management',
         'Birsa Agricultural University', 'Agriculture',
         'Crop Disease, Irrigation, Organic Farming',
         'agriculture farming irrigation crop soil seeds market'),
        (None, 'Prof. Vikash Ranjan', 'Electrical Engineering, Smart Grid, Solar Energy',
         'BIT Mesra', 'Electrical Engineering',
         'Power Systems, Renewable Energy',
         'electricity power supply grid solar street lights energy'),
        (None, 'Dr. Anita Das', 'Education Technology, Curriculum Design',
         'Ranchi University', 'Education',
         'Digital Education, Teacher Training',
         'education school college students teachers learning digital'),
        (None, 'Dr. Rahul Verma', 'Transportation Engineering, Traffic Management',
         'NIT Jamshedpur', 'Transportation',
         'Public Transit, Traffic Flow',
         'transportation bus road traffic transit public transport connectivity'),
    ]
    cursor.executemany(
        """INSERT INTO experts (user_id, name, skills, organization, department, expertise_area, match_keywords) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        experts
    )

    # ── Seed Problems (Jharkhand-specific) ──
    now = datetime.now()
    problems = [
        (1, 'Contaminated drinking water in Kanke area',
         'The drinking water supply in Kanke, Ranchi has been contaminated for the past two weeks. Residents are falling sick with waterborne diseases. The water has a yellowish color and foul smell. Municipal water treatment plant is not functioning properly.',
         'Kanke, Ranchi', 'Water & Sanitation', 'Water Contamination', 'HIGH',
         'VERIFIED', 'Water & Sanitation', 'Water Contamination', 'HIGH', 0.94,
         12, 1, 3, (now - timedelta(days=15)).isoformat()),

        (5, 'Garbage accumulation near Sakchi market',
         'Garbage has been piling up near Sakchi market in Jamshedpur for over a week. The waste collection trucks have not been operating regularly. The area has become a breeding ground for mosquitoes and flies. Shop owners and residents are facing severe health hazards.',
         'Sakchi, Jamshedpur', 'Water & Sanitation', 'Waste Management', 'HIGH',
         'UNDER_REVIEW', 'Water & Sanitation', 'Waste Management', 'HIGH', 0.91,
         8, 1, 3, (now - timedelta(days=10)).isoformat()),

        (1, 'Damaged road near Birsa Munda Airport',
         'The main road connecting Birsa Munda Airport to Ranchi city has multiple large potholes. Several accidents have occurred in the past month. The road surface has completely deteriorated especially during monsoon season.',
         'Hinoo, Ranchi', 'Roads & Infrastructure', 'Road Damage', 'HIGH',
         'VERIFIED', 'Roads & Infrastructure', 'Road Damage', 'HIGH', 0.96,
         23, 2, 3, (now - timedelta(days=20)).isoformat()),

        (5, 'No street lights on Dimna Road',
         'Street lights on Dimna Road in Jamshedpur have not been working for over a month. The road becomes extremely dark after sunset making it unsafe for pedestrians and commuters. Multiple complaints to the electricity board have gone unanswered.',
         'Dimna Road, Jamshedpur', 'Electricity', 'Street Lights', 'MEDIUM',
         'REPORTED', 'Electricity', 'Street Lights', 'MEDIUM', 0.89,
         5, None, None, (now - timedelta(days=5)).isoformat()),

        (1, 'Lack of healthcare facility in Namkum block',
         'Namkum block in Ranchi has no primary health center within 15 kilometers. Pregnant women and elderly patients have to travel long distances for basic medical treatment. There is an urgent need for at least a primary health sub-center.',
         'Namkum, Ranchi', 'Healthcare', 'Healthcare Access', 'HIGH',
         'VERIFIED', 'Healthcare', 'Healthcare Access', 'HIGH', 0.92,
         18, 3, 3, (now - timedelta(days=25)).isoformat()),

        (5, 'School building roof collapsed in Dhanbad',
         'The roof of a government primary school in Jharia, Dhanbad has partially collapsed. Students are being forced to attend classes in the open. The building has been declared unsafe but no repair work has started.',
         'Jharia, Dhanbad', 'Education', 'School Infrastructure', 'HIGH',
         'UNDER_REVIEW', 'Education', 'School Infrastructure', 'HIGH', 0.95,
         15, 4, 3, (now - timedelta(days=12)).isoformat()),

        (1, 'Industrial pollution in Adityapur',
         'Multiple factories in the Adityapur Industrial Area are releasing untreated effluents into the Subarnarekha river. The water has turned dark and fish are dying. Local residents who depend on the river for daily use are severely affected.',
         'Adityapur, Jamshedpur', 'Environment', 'Water Pollution', 'HIGH',
         'REPORTED', 'Environment', 'Water Pollution', 'HIGH', 0.88,
         10, None, None, (now - timedelta(days=8)).isoformat()),

        (5, 'Irregular bus service to Bokaro Steel City',
         'Public bus service between Ranchi and Bokaro Steel City has become highly irregular. Buses are often cancelled without notice. Commuters and daily wage workers are severely affected.',
         'Bokaro', 'Transportation', 'Public Transport', 'MEDIUM',
         'REPORTED', 'Transportation', 'Public Transport', 'MEDIUM', 0.87,
         6, None, None, (now - timedelta(days=3)).isoformat()),

        (1, 'Crop damage due to lack of irrigation in Gumla',
         'Farmers in Gumla district are facing severe crop losses due to absence of proper irrigation channels. The monsoon has been irregular and there is no alternative water source for farming. Over 200 farming families are affected.',
         'Gumla', 'Agriculture', 'Irrigation', 'HIGH',
         'VERIFIED', 'Agriculture', 'Irrigation', 'HIGH', 0.90,
         14, 8, 3, (now - timedelta(days=18)).isoformat()),

        (5, 'Frequent chain snatching incidents near Ranchi station',
         'There has been a sharp increase in chain snatching and petty crime incidents near Ranchi Railway Station area. Women and elderly are particularly targeted during evening hours. Existing CCTV cameras are not functioning.',
         'Ranchi Station Area', 'Public Safety', 'Crime', 'HIGH',
         'VERIFIED', 'Public Safety', 'Crime', 'HIGH', 0.85,
         20, 9, 3, (now - timedelta(days=22)).isoformat()),
    ]

    for p in problems:
        cursor.execute(
            """INSERT INTO problems 
               (user_id, title, description, location, category, sub_category, priority,
                status, ai_category, ai_sub_category, ai_priority, ai_confidence,
                support_count, department_id, verified_by, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            p
        )

    # ── Seed Solutions for first 2 problems ──
    solutions = [
        (1, 2, 'Solar-Powered Water Purification System',
         'Install a decentralized solar-powered water purification unit at the Kanke water distribution point. The system uses UV filtration and reverse osmosis, powered entirely by solar panels. It can purify 5000 liters/day and requires minimal maintenance.',
         '₹4,50,000', '3 months', 'Clean drinking water for 2000+ households',
         'Solar panels, RO membranes, UV filters, storage tanks',
         15, 8.0, 8.5, 0.0, 0, (now - timedelta(days=10)).isoformat()),

        (1, 6, 'Community Water Testing & Chlorination Program',
         'Implement a community-based water testing and chlorination program. Train local volunteers to test water quality weekly using portable testing kits. Set up automated chlorination units at key distribution points.',
         '₹1,20,000', '1 month', 'Immediate reduction in waterborne diseases',
         'Water testing kits, chlorination tablets, volunteer training materials',
         8, 9.0, 7.0, 0.0, 0, (now - timedelta(days=8)).isoformat()),

        (2, 7, 'Smart Waste Management with IoT Sensors',
         'Deploy IoT-enabled smart bins at key locations in Sakchi market. Bins will have fill-level sensors that alert waste management teams when they reach 80% capacity. Implement a route optimization algorithm for waste collection trucks.',
         '₹6,00,000', '4 months', 'Eliminate garbage overflow, reduce disease spread',
         'IoT sensors, smart bins, mobile app for waste collectors, GPS tracking',
         6, 7.0, 8.0, 0.0, 0, (now - timedelta(days=5)).isoformat()),
    ]
    for s in solutions:
        cursor.execute(
            """INSERT INTO solutions 
               (problem_id, user_id, title, description, estimated_cost,
                implementation_time, expected_impact, required_resources,
                vote_count, feasibility_score, impact_score, overall_score,
                selected, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            s
        )

    # ── Seed some votes ──
    vote_data = [
        (1, 1), (1, 1), (5, 1),  # votes for solution 1
        (1, 2), (5, 2),          # votes for solution 2
    ]
    # Skipping duplicate votes with IGNORE
    for user_id, solution_id in vote_data:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO votes (user_id, solution_id) VALUES (?, ?)",
                (user_id, solution_id)
            )
        except sqlite3.IntegrityError:
            pass

    # ── Seed Impact Metrics (for a completed problem example) ──
    # We don't have a completed problem yet, so skip for now.

    db.commit()
    db.close()
    print("[OK] Database seeded with demo data.")

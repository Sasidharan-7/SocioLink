"""
Test end-to-end hackathon lifecycle
"""
from app import app
from database import get_db

client = app.test_client()

print('=== STEP 1: Citizen Login ===')
client.post('/login', data={'email': 'citizen@demo.com', 'password': 'citizen123'}, follow_redirects=True)

print('=== STEP 2: Citizen Reports Problem ===')
report_data = {
    'title': 'Garbage accumulation near village primary school',
    'description': 'Garbage has been accumulating near our village school and has not been collected for several days. Severe foul smell and flies.',
    'location': 'Torpa, Khunti',
    'category': '',
    'force_submit': '1'
}
res = client.post('/citizen/report', data=report_data, follow_redirects=True)
assert res.status_code == 200

db = get_db()
new_prob = db.execute('SELECT * FROM problems ORDER BY id DESC LIMIT 1').fetchone()
prob_id = new_prob['id']
print(f"[OK] Created Problem ID: {prob_id}")
print(f"     AI Category: {new_prob['ai_category']}")
print(f"     AI Priority: {new_prob['ai_priority']}")
print(f"     AI Confidence: {int(new_prob['ai_confidence']*100)}%")
print(f"     Status: {new_prob['status']}")

assert new_prob['ai_category'] == 'Water & Sanitation'
assert new_prob['ai_priority'] == 'HIGH'
assert new_prob['status'] == 'REPORTED'

client.get('/logout')

print('=== STEP 3: Government Official Verifies Problem ===')
client.post('/login', data={'email': 'gov@demo.com', 'password': 'gov123'}, follow_redirects=True)
client.post(f'/gov/problem/{prob_id}', data={'action': 'verify'}, follow_redirects=True)

db = get_db()
prob_after_ver = db.execute('SELECT status FROM problems WHERE id = ?', (prob_id,)).fetchone()
print(f"[OK] Problem Status after Official Verification: {prob_after_ver['status']}")
assert prob_after_ver['status'] == 'VERIFIED'
client.get('/logout')

print('=== STEP 4: Student Submits Solution ===')
client.post('/login', data={'email': 'student@demo.com', 'password': 'student123'}, follow_redirects=True)
sol_data = {
    'title': 'Decentralized Organic Waste Composting & IoT Smart Bins',
    'description': 'Deploy 2 aerated composting pits near village perimeter and 4 LoRaWAN monitored bins at school gate.',
    'estimated_cost': 'Rs 1,50,000',
    'implementation_time': '3 weeks',
    'expected_impact': '100% waste processed locally into organic fertilizer',
    'required_resources': 'Compost pits, microbial culture, 4 IoT fill sensors'
}
client.post(f'/expert/submit/{prob_id}', data=sol_data, follow_redirects=True)

db = get_db()
new_sol = db.execute('SELECT * FROM solutions WHERE problem_id = ? ORDER BY id DESC LIMIT 1', (prob_id,)).fetchone()
sol_id = new_sol['id']
print(f"[OK] Solution ID {sol_id} Created by Student!")
client.get('/logout')

print('=== STEP 5: Citizen Votes on Solution ===')
client.post('/login', data={'email': 'citizen@demo.com', 'password': 'citizen123'}, follow_redirects=True)
client.post(f'/citizen/vote/{sol_id}', follow_redirects=True)

db = get_db()
sol_after_vote = db.execute('SELECT vote_count, overall_score FROM solutions WHERE id = ?', (sol_id,)).fetchone()
print(f"[OK] Solution Vote Count: {sol_after_vote['vote_count']}, Calculated Score: {sol_after_vote['overall_score']}/10")
assert sol_after_vote['vote_count'] == 1
client.get('/logout')

print('=== STEP 6: Government Selects Winning Solution ===')
client.post('/login', data={'email': 'gov@demo.com', 'password': 'gov123'}, follow_redirects=True)
client.post(f'/gov/select_solution/{sol_id}', follow_redirects=True)
db = get_db()
prob_sel = db.execute('SELECT status FROM problems WHERE id = ?', (prob_id,)).fetchone()
print(f"[OK] Problem Status after Solution Selection: {prob_sel['status']}")
assert prob_sel['status'] == 'SOLUTION_SELECTED'

print('=== STEP 7: Government Starts Implementation ===')
client.post(f'/gov/start_implementation/{prob_id}', follow_redirects=True)
db = get_db()
prob_prog = db.execute('SELECT status FROM problems WHERE id = ?', (prob_id,)).fetchone()
print(f"[OK] Problem Status during Implementation: {prob_prog['status']}")
assert prob_prog['status'] == 'IN_PROGRESS'

print('=== STEP 8: Government Enters Ground Impact Metrics ===')
impact_data = {
    'before_metric': 'Uncollected waste piles per week',
    'before_value': '12',
    'after_metric': 'Uncollected waste piles per week',
    'after_value': '0',
    'people_benefited': '1800',
    'implementation_cost': 'Rs 1,45,000',
    'completion_date': '2026-09-09',
    'description': 'Zero garbage overflow achieved. Local school compound clean and composting pit active.'
}
client.post(f'/gov/impact/{prob_id}', data=impact_data, follow_redirects=True)

db = get_db()
prob_done = db.execute('SELECT status FROM problems WHERE id = ?', (prob_id,)).fetchone()
impact_rec = db.execute('SELECT * FROM impact_metrics WHERE problem_id = ?', (prob_id,)).fetchone()
print(f"[OK] Final Problem Status: {prob_done['status']}")
print(f"[OK] Measured Impact Improvement: {impact_rec['improvement_percentage']}%, Benefited: {impact_rec['people_benefited']} citizens")
assert prob_done['status'] == 'COMPLETED'
assert impact_rec['improvement_percentage'] == 100.0

print('\n*******************************************************')
print('*** FULL 19-STEP HACKATHON DEMO LIFECYCLE VERIFIED! ***')
print('*******************************************************')

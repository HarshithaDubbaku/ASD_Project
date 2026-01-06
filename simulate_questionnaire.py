from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    # create test user if not exists
    user = User.query.filter_by(username='simulate_user').first()
    if not user:
        user = User(username='simulate_user', password_hash=generate_password_hash('password'), email='sim@example.com')
        db.session.add(user)
        db.session.commit()

    client = app.test_client()
    # login
    resp = client.post('/login', data={'username': 'simulate_user', 'password': 'password'}, follow_redirects=True)
    print('Login status code:', resp.status_code)

    # submit user_info
    resp = client.post('/user_info', data={'age': '30', 'gender': 'Male', 'ethnicity': 'Other', 'used_app_before': 'No', 'relation': 'Self'}, follow_redirects=True)
    print('/user_info status code:', resp.status_code)

    # prepare questionnaire answers (10 questions)
    data = {}
    for i in range(1, 11):
        data[f'q{i}'] = 'No'
    resp = client.post('/questionnaire', data=data, follow_redirects=True)
    print('/questionnaire status code:', resp.status_code)
    print('Response length:', len(resp.get_data(as_text=True)))
    # print some of the response to verify prediction
    text = resp.get_data(as_text=True)
    if 'Prediction' in text or 'Risk Score' in text:
        print('Prediction appears in response')
    else:
        print('No prediction visible in response; check for flashes or redirects')

print('Done')
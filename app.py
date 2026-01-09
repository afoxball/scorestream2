import os
import json
from google import genai
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from forms import RegistrationForm, LoginForm, CodingChallengeForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '5791628bb0b13ce0c676dfde280ba245')

# Gemini Configuration
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    client = None
    print("Warning: GOOGLE_API_KEY not set. Gemini features will not work.")

# Database configuration
db_uri = os.environ.get('DATABASE_URL', 'postgresql://username:password@localhost:5432/scorestream_db')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

CHALLENGES = {
    1: {
        'title': 'Sum of a List',
        'description': "Create a list called 'numbers' with at least 3 integers. Iterate over the list and calculate the sum, storing it in 'total_sum'.",
        'rubric': "1. 'numbers' list defined with >= 3 integers.\n2. Loop used for iteration.\n3. 'total_sum' variable contains the correct sum."
    },
    2: {
        'title': 'Find the Maximum',
        'description': "Create a function called 'find_max' that takes a list of numbers as an argument and returns the largest number in that list. Then call your function with the list [10, 5, 20, 3] and store the result in a variable called 'max_val'.",
        'rubric': "1. Function 'find_max' defined.\n2. 'find_max' returns max of input list.\n3. Function called with [10, 5, 20, 3].\n4. 'max_val' stores the result 20."
    },
    3: {
        'title': 'Sum of Even Numbers',
        'description': "Create a function called 'sum_evens' that takes a list of numbers. It should return the sum of only the even numbers in the list. Then call your function with the list [1, 2, 3, 4, 5, 6] and store the result in a variable called 'even_total'.",
        'rubric': "1. Function 'sum_evens' defined.\n2. 'sum_evens' returns sum of even numbers only.\n3. Function called with [1, 2, 3, 4, 5, 6].\n4. 'even_total' stores the result 12."
    },
    4: {
        'title': 'Count Vowels',
        'description': "Create a function called 'count_vowels' that takes a string as an argument and returns the number of vowels (a, e, i, o, u) in that string. Then call your function with the string 'hello world' and store the result in a variable called 'vowel_count'.",
        'rubric': "1. Function 'count_vowels' defined.\n2. 'count_vowels' returns count of vowels (case-insensitive).\n3. Function called with 'hello world'.\n4. 'vowel_count' stores the result 3."
    },
    5: {
        'title': 'Reverse String',
        'description': "Create a function called 'reverse_string' that takes a string as an argument and returns the string reversed. Then call your function with the string 'python' and store the result in a variable called 'reversed_str'.",
        'rubric': "1. Function 'reverse_string' defined.\n2. 'reverse_string' returns reversed string.\n3. Function called with 'python'.\n4. 'reversed_str' stores the result 'nohtyp'."
    }
}

@app.route("/challenge", methods=['GET', 'POST'])
def challenge():
    challenge_id = request.args.get('id', 1, type=int)
    current_challenge = CHALLENGES.get(challenge_id)
    
    if not current_challenge:
        return redirect(url_for('challenge', id=1))

    form = CodingChallengeForm()
    feedback = []
    passed = False
    
    if form.validate_on_submit():
        user_code = form.code_submission.data
        
        if client:
            # Use Gemini for grading
            prompt = f"""
You are a Python coding tutor.
Prompt: {current_challenge['description']}
Rubric:
{current_challenge['rubric']}

Student Code:
{user_code}

Evaluate the student code based on the rubric.
Return a valid JSON object with exactly these two keys:
- "passed": boolean (true if all rubric items are met, false otherwise)
- "feedback": string (constructive feedback explaining what is wrong or congratulating if correct. Keep it under 3 sentences.)
Do not wrap the JSON in Markdown delimiters.
"""
            try:
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                response_text = response.text.strip()
                
                # Clean up if markdown delimiters are present
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                     response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                    
                result = json.loads(response_text)
                passed = result.get('passed', False)
                feedback.append(result.get('feedback', 'No feedback provided.'))
                
            except Exception as e:
                feedback.append(f"AI Grading Error: {str(e)}")
        else:
             feedback.append("AI Grading is not configured. Please set GOOGLE_API_KEY.")
            
    return render_template('challenge.html', 
                           title=current_challenge['title'], 
                           description=current_challenge['description'],
                           form=form, 
                           feedback=feedback, 
                           passed=passed,
                           challenge_id=challenge_id,
                           next_challenge_id=challenge_id + 1 if challenge_id < len(CHALLENGES) else None)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

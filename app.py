import os
import json
import click
from datetime import datetime, timezone
from google import genai
from flask import Flask, render_template, redirect, url_for, flash, request, session
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
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    
    # Relationships for tracking
    submissions = db.relationship('Submission', backref='author', lazy=True)
    sessions = db.relationship('UserSession', backref='user', lazy=True)
    page_visits = db.relationship('PageVisit', backref='visitor', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

    @property
    def is_admin(self):
        return self.role == 'admin' or self.role == 'superuser'
        
    @property
    def is_teacher(self):
        return self.role == 'teacher' or self.role == 'admin' or self.role == 'superuser'

    def get_stats(self):
        total_submissions = Submission.query.filter_by(user_id=self.id).count()
        passed_submissions = Submission.query.filter_by(user_id=self.id, passed=True).count()
        percent_correct = (passed_submissions / total_submissions * 100) if total_submissions > 0 else 0
        
        # Calculate time on site (sum of closed session durations)
        total_duration_seconds = 0
        closed_sessions = UserSession.query.filter(UserSession.user_id==self.id, UserSession.logout_time != None).all()
        for s in closed_sessions:
            if s.logout_time and s.login_time:
                total_duration_seconds += (s.logout_time - s.login_time).total_seconds()
        
        minutes_on_site = round(total_duration_seconds / 60, 2)

        return {
            'total_submissions': total_submissions,
            'passed_submissions': passed_submissions,
            'percent_correct': round(percent_correct, 1),
            'minutes_on_site': minutes_on_site
        }

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    challenge_id = db.Column(db.Integer, nullable=False)
    code = db.Column(db.Text, nullable=False)
    passed = db.Column(db.Boolean, default=False)
    feedback = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class UserSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    logout_time = db.Column(db.DateTime)
    ip_address = db.Column(db.String(45))

class PageVisit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def track_page_visit():
    if current_user.is_authenticated and request.endpoint and 'static' not in request.endpoint:
        visit = PageVisit(user_id=current_user.id, path=request.path)
        db.session.add(visit)
        # Commit might be too heavy for every request, but for this scale it ensures accuracy
        try:
            db.session.commit()
        except:
            db.session.rollback()

@app.route('/')
def home():
    return render_template('index.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='scrypt')
        # Default role is 'student' handled by database default
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
                feedback_text = result.get('feedback', 'No feedback provided.')
                feedback.append(feedback_text)
                
                # Save submission
                if current_user.is_authenticated:
                    submission = Submission(
                        user_id=current_user.id,
                        challenge_id=challenge_id,
                        code=user_code,
                        passed=passed,
                        feedback=str(feedback_text)
                    )
                    db.session.add(submission)
                    db.session.commit()
                
            except Exception as e:
                print(f"Error during AI grading: {e}")
                feedback.append(f"AI Grading Error: {str(e)}")
        else:
             print("Client not configured.")
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
            
            # Track login
            user.last_login = datetime.now(timezone.utc)
            user_session = UserSession(user_id=user.id, ip_address=request.remote_addr)
            db.session.add(user_session)
            db.session.commit()
            
            # Store session ID in Flask session to update on logout
            session['current_db_session_id'] = user_session.id
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    # Track logout time if we have a tracked session
    session_id = session.get('current_db_session_id')
    if session_id:
        user_session = UserSession.query.get(session_id)
        if user_session:
            user_session.logout_time = datetime.now(timezone.utc)
            db.session.commit()
            
    logout_user()
    return redirect(url_for('home'))

# CLI Commands for User Management

@app.cli.command("init-db")
def init_db():
    """Create database tables."""
    db.create_all()
    print("Database tables created successfully.")

@app.cli.command("promote-user")
@click.argument("email")
@click.argument("role")
def promote_user(email, role):
    """Promote a user to a specific role (admin, teacher, student)."""
    valid_roles = ['student', 'teacher', 'admin', 'superuser']
    if role not in valid_roles:
        print(f"Error: Role must be one of {valid_roles}")
        return

    user = User.query.filter_by(email=email).first()
    if user:
        user.role = role
        db.session.commit()
        print(f"Success: User {email} has been promoted to {role}.")
    else:
        print(f"Error: User with email {email} not found.")

@app.cli.command("init-admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
def init_admin(username, email, password):
    """Create a new superuser directly from CLI."""
    user = User.query.filter_by(email=email).first()
    if user:
        print(f"Error: User with email {email} already exists.")
        return
    
    hashed_password = generate_password_hash(password, method='scrypt')
    user = User(username=username, email=email, password=hashed_password, role='superuser')
    db.session.add(user)
    db.session.commit()
    print(f"Success: Superuser {username} ({email}) created.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

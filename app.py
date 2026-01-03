import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from forms import RegistrationForm, LoginForm, CodingChallengeForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '5791628bb0b13ce0c676dfde280ba245')

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

@app.route("/challenge", methods=['GET', 'POST'])
def challenge():
    form = CodingChallengeForm()
    feedback = []
    passed = False
    
    if form.validate_on_submit():
        user_code = form.code_submission.data
        
        # Rubric / Evaluation Logic
        # Prompt: Create a list called 'numbers' with at least 3 integers. 
        # Iterate over the list and calculate the sum, storing it in 'total_sum'.
        
        local_scope = {}
        try:
            # Basic keyword check
            if 'for ' not in user_code and 'while ' not in user_code:
                feedback.append("Coach: It looks like you aren't using a loop. Try using a 'for' loop to go through the list.")
            
            # Execution
            exec(user_code, {}, local_scope)
            
            if 'numbers' not in local_scope:
                feedback.append("Coach: We couldn't find a list named 'numbers'. Please define one, e.g., numbers = [1, 2, 3].")
            elif not isinstance(local_scope['numbers'], list):
                feedback.append("Coach: 'numbers' should be a list.")
            else:
                expected_sum = sum(local_scope['numbers'])
                if 'total_sum' not in local_scope:
                    feedback.append("Coach: Please store the final sum in a variable named 'total_sum'.")
                elif local_scope['total_sum'] != expected_sum:
                    feedback.append(f"Coach: The calculated sum was {local_scope['total_sum']}, but we expected {expected_sum}. Check your addition logic inside the loop.")
                else:
                    passed = True
                    feedback.append("Success! You've correctly iterated over the list and found the sum.")
                    
        except Exception as e:
            feedback.append(f"Coach: Your code caused an error: {e}. Check your syntax.")
            
    return render_template('challenge.html', title='Coding Challenge', form=form, feedback=feedback, passed=passed)


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

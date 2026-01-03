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

CHALLENGES = {
    1: {
        'title': 'Sum of a List',
        'description': "Create a list called 'numbers' with at least 3 integers. Iterate over the list and calculate the sum, storing it in 'total_sum'.",
    },
    2: {
        'title': 'Find the Maximum',
        'description': "Create a function called 'find_max' that takes a list of numbers as an argument and returns the largest number in that list. Then call your function with the list [10, 5, 20, 3] and store the result in a variable called 'max_val'.",
    },
    3: {
        'title': 'Sum of Even Numbers',
        'description': "Create a function called 'sum_evens' that takes a list of numbers. It should return the sum of only the even numbers in the list. Then call your function with the list [1, 2, 3, 4, 5, 6] and store the result in a variable called 'even_total'.",
    },
    4: {
        'title': 'Count Vowels',
        'description': "Create a function called 'count_vowels' that takes a string as an argument and returns the number of vowels (a, e, i, o, u) in that string. Then call your function with the string 'hello world' and store the result in a variable called 'vowel_count'.",
    },
    5: {
        'title': 'Reverse String',
        'description': "Create a function called 'reverse_string' that takes a string as an argument and returns the string reversed. Then call your function with the string 'python' and store the result in a variable called 'reversed_str'.",
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
        local_scope = {}
        
        try:
            # Basic keyword check
            if challenge_id == 1 and ('for ' not in user_code and 'while ' not in user_code):
                feedback.append("Coach: It looks like you aren't using a loop. Try using a 'for' loop to go through the list.")
            
            # Execution
            exec(user_code, {}, local_scope)
            
            if challenge_id == 1:
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
            
            elif challenge_id == 2:
                if 'find_max' not in local_scope or not callable(local_scope['find_max']):
                    feedback.append("Coach: Please define a function named 'find_max'.")
                elif 'max_val' not in local_scope:
                    feedback.append("Coach: Please call your function and store the result in 'max_val'.")
                else:
                    # Verify max_val for the specific list requested
                    if local_scope['max_val'] != 20:
                         feedback.append("Coach: 'max_val' should be 20 for the list [10, 5, 20, 3]. Check your function call or logic.")
                    else:
                        # Test with another case to ensure it's not hardcoded
                        try:
                            test_res = local_scope['find_max']([1, 100, -5])
                            if test_res == 100:
                                passed = True
                                feedback.append("Success! Your function works correctly.")
                            else:
                                feedback.append("Coach: Your function didn't return the correct maximum for a test case [1, 100, -5].")
                        except Exception as e:
                            feedback.append(f"Coach: Error testing your function: {e}")

            elif challenge_id == 3:
                if 'sum_evens' not in local_scope or not callable(local_scope['sum_evens']):
                    feedback.append("Coach: Please define a function named 'sum_evens'.")
                elif 'even_total' not in local_scope:
                    feedback.append("Coach: Please call your function and store the result in 'even_total'.")
                else:
                    if local_scope['even_total'] != 12:
                         feedback.append("Coach: 'even_total' should be 12 for the list [1, 2, 3, 4, 5, 6]. Check your logic.")
                    else:
                        try:
                            test_res = local_scope['sum_evens']([10, 11, 12])
                            if test_res == 22:
                                passed = True
                                feedback.append("Success! Your function correctly sums even numbers.")
                            else:
                                feedback.append("Coach: Your function didn't return the correct sum for [10, 11, 12]. Expected 22.")
                        except Exception as e:
                            feedback.append(f"Coach: Error testing your function: {e}")

            elif challenge_id == 4:
                if 'count_vowels' not in local_scope or not callable(local_scope['count_vowels']):
                    feedback.append("Coach: Please define a function named 'count_vowels'.")
                elif 'vowel_count' not in local_scope:
                    feedback.append("Coach: Please call your function and store the result in 'vowel_count'.")
                else:
                    if local_scope['vowel_count'] != 3:
                         feedback.append("Coach: 'vowel_count' should be 3 for 'hello world'. Check your logic.")
                    else:
                        try:
                            test_res = local_scope['count_vowels']("aeiou")
                            if test_res == 5:
                                passed = True
                                feedback.append("Success! Your function correctly counts vowels.")
                            else:
                                feedback.append("Coach: Your function didn't return the correct count for 'aeiou'. Expected 5.")
                        except Exception as e:
                            feedback.append(f"Coach: Error testing your function: {e}")

            elif challenge_id == 5:
                if 'reverse_string' not in local_scope or not callable(local_scope['reverse_string']):
                    feedback.append("Coach: Please define a function named 'reverse_string'.")
                elif 'reversed_str' not in local_scope:
                    feedback.append("Coach: Please call your function and store the result in 'reversed_str'.")
                else:
                    if local_scope['reversed_str'] != 'nohtyp':
                         feedback.append("Coach: 'reversed_str' should be 'nohtyp' for 'python'. Check your logic.")
                    else:
                        try:
                            test_res = local_scope['reverse_string']("abc")
                            if test_res == "cba":
                                passed = True
                                feedback.append("Success! Your function correctly reverses strings.")
                            else:
                                feedback.append("Coach: Your function didn't return the correct reverse for 'abc'. Expected 'cba'.")
                        except Exception as e:
                            feedback.append(f"Coach: Error testing your function: {e}")

        except Exception as e:
            feedback.append(f"Coach: Your code caused an error: {e}. Check your syntax.")
            
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

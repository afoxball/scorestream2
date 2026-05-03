from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo, NumberRange

class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', 
                             validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', 
                            validators=[DataRequired(), Length(min=2, max=50)])
    age = IntegerField('Age', 
                      validators=[DataRequired(), NumberRange(min=1, max=150, message='Please enter a valid age')])
    username = StringField('Username', 
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', 
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', 
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class CodingChallengeForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    class_period = SelectField('Class Period', choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4')], validators=[DataRequired()])
    code_submission = TextAreaField('Your Code', validators=[DataRequired()])
    submit = SubmitField('Run Code')


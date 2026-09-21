from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Work Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    department_id = SelectField('Department', coerce=int, validators=[DataRequired()])
    role = SelectField('Role', choices=[
        ('employee', 'Employee'),
        ('manager', 'Manager'),
        ('hr', 'HR Specialist'),
        ('it', 'IT Support Engineer'),
        ('finance', 'Finance Officer'),
        ('procurement', 'Procurement Specialist'),
        ('admin', 'System Administrator')
    ], default='employee')
    designation = StringField('Designation / Title', validators=[DataRequired()])
    submit = SubmitField('Create Account')

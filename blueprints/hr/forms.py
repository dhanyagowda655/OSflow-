from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length

class OnboardEmployeeForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Work Email Address', validators=[DataRequired(), Email()])
    department_id = SelectField('Department', coerce=int, validators=[DataRequired()])
    designation = StringField('Job Title / Designation', validators=[DataRequired()], default='Software Engineer')
    manager_id = SelectField('Reporting Manager', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Onboarding Special Instructions (e.g. Hardware/Access requirements)', default='Standard engineering setup: MacBook Pro, GitHub Org access, and orientation session.')
    submit = SubmitField('Initiate AI Onboarding Workflow')

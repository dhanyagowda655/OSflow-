from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, DecimalField, SelectField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class LeaveRequestForm(FlaskForm):
    leave_type = SelectField('Leave Type', choices=[
        ('Annual', 'Annual Leave (Paid)'),
        ('Casual', 'Casual Leave'),
        ('Sick', 'Sick / Medical Leave')
    ], default='Annual')
    days = IntegerField('Duration (Days)', validators=[DataRequired(), NumberRange(min=1, max=30)], default=1)
    reason = TextAreaField('Reason / Description', validators=[DataRequired(), Length(min=5, max=500)])
    submit = SubmitField('Submit Leave Request')

class LaptopRequestForm(FlaskForm):
    model_preference = SelectField('Requested Device', choices=[
        ('MacBook Pro 14" M3 (Engineering Standard)', 'MacBook Pro 14" M3 (Engineering Standard)'),
        ('Dell XPS 15 Enterprise (Business & Design)', 'Dell XPS 15 Enterprise (Business & Design)'),
        ('ThinkPad X1 Carbon (Ultra-portable)', 'ThinkPad X1 Carbon (Ultra-portable)')
    ])
    business_justification = TextAreaField('Business Justification', validators=[DataRequired(), Length(min=10, max=500)])
    priority = SelectField('Urgency', choices=[
        ('medium', 'Normal (Standard Delivery)'),
        ('high', 'High (Urgent Replacement)'),
        ('urgent', 'Critical Project Need')
    ], default='medium')
    submit = SubmitField('Submit Laptop Request')

class ITTicketForm(FlaskForm):
    subject = StringField('Issue Summary', validators=[DataRequired(), Length(min=5, max=150)])
    description = TextAreaField('Detailed Description (Error messages, steps to reproduce)', validators=[DataRequired(), Length(min=10, max=1000)])
    priority = SelectField('Priority', choices=[
        ('low', 'Low - General Question'),
        ('medium', 'Medium - Impaired Workflow'),
        ('high', 'High - Work Blocked'),
        ('urgent', 'Urgent - System Outage')
    ], default='medium')
    submit = SubmitField('Submit IT Ticket')

class ExpenseClaimForm(FlaskForm):
    category = SelectField('Expense Category', choices=[
        ('Travel', 'Travel & Flights'),
        ('Meals', 'Meals & Entertainment'),
        ('Hardware', 'Equipment & Peripherals'),
        ('Software', 'Software Subscription'),
        ('Misc', 'Miscellaneous')
    ], default='Travel')
    amount = DecimalField('Amount ($ USD)', validators=[DataRequired(), NumberRange(min=1.0, max=50000.0)])
    vendor = StringField('Vendor / Merchant Name', validators=[DataRequired()])
    description = TextAreaField('Business Purpose', validators=[DataRequired()])
    receipt = FileField('Receipt File (PNG, JPG, PDF, or TXT)', validators=[
        FileAllowed(['png', 'jpg', 'jpeg', 'pdf', 'txt'], 'Images or PDFs only!')
    ])
    submit = SubmitField('Submit Expense Claim')

class CustomNLRequestForm(FlaskForm):
    prompt = TextAreaField('Describe what you need in plain English', validators=[
        DataRequired(),
        Length(min=5, max=1000, message='Please provide at least a brief sentence describing your need.')
    ])
    submit = SubmitField('AI Generate & Execute Workflow')

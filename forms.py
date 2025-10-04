from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length

class RegisterForm(FlaskForm):
    username = StringField('Usuari', validators=[DataRequired(), Length(3, 80)])
    password = PasswordField('Contrasenya', validators=[DataRequired(), Length(6)])
    submit = SubmitField('Registrar')

class PremiumActivateForm(FlaskForm):
    key = StringField('Clau Premium', validators=[DataRequired(), Length(min=10, max=64)])
    submit = SubmitField('Activar')

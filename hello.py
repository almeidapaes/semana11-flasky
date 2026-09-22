import os
import requests

from dotenv import load_dotenv
from flask import Flask, render_template, session, redirect, url_for, flash
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv(
    os.path.join(basedir, '.env')
)

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'hard to guess string'
)

app.config['SQLALCHEMY_DATABASE_URI'] = \
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

bootstrap = Bootstrap(app)
moment = Moment(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

FLASKY_ADMIN = os.getenv('FLASKY_ADMIN')
API_URL = os.getenv('API_URL')
API_KEY = os.getenv('API_KEY')
API_FROM = os.getenv('API_FROM')
FLASKY_NAME = os.getenv('FLASKY_NAME')
FLASKY_PRONTUARIO = os.getenv('FLASKY_PRONTUARIO')


class Role(db.Model):

    __tablename__ = 'roles'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )

    users = db.relationship(
        'User',
        backref='role',
        lazy='dynamic'
    )

    def __repr__(self):
        return '<Role %r>' % self.name


class User(db.Model):

    __tablename__ = 'users'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(64),
        unique=True,
        index=True,
        nullable=False
    )

    role_id = db.Column(
        db.Integer,
        db.ForeignKey('roles.id')
    )

    def __repr__(self):
        return '<User %r>' % self.username


class NameForm(FlaskForm):

    name = StringField(
        'What is your name?',
        validators=[DataRequired()]
    )

    role = SelectField(
        'Role?:',
        choices=[
            ('Administrator', 'Administrator'),
            ('Moderator', 'Moderator'),
            ('User', 'User')
        ],
        validators=[DataRequired()]
    )

    submit = SubmitField('Submit')


def create_default_roles():

    role_names = [
        'Administrator',
        'Moderator',
        'User'
    ]

    roles = {}

    for role_name in role_names:

        role = Role.query.filter_by(
            name=role_name
        ).first()

        if role is None:

            role = Role(
                name=role_name
            )

            db.session.add(role)

        roles[role_name] = role

    db.session.commit()

    return roles


def send_registration_email(user):

    if not API_URL:
        raise RuntimeError(
            'API_URL não configurada.'
        )

    if not API_KEY:
        raise RuntimeError(
            'API_KEY não configurada.'
        )

    if not API_FROM:
        raise RuntimeError(
            'API_FROM não configurado.'
        )

    if not FLASKY_ADMIN:
        raise RuntimeError(
            'FLASKY_ADMIN não configurado.'
        )

    recipients = [
        'flaskaulasweb@zohomail.com',
        FLASKY_ADMIN
    ]

    body = f"""
Novo usuário cadastrado.

Prontuário: {FLASKY_PRONTUARIO}
Nome do aluno: {FLASKY_NAME}
Usuário cadastrado: {user.username}
Função: {user.role.name}
"""

    response = requests.post(
        API_URL,
        auth=(
            'api',
            API_KEY
        ),
        data={
            'from': API_FROM,
            'to': recipients,
            'subject': 'Novo usuário cadastrado',
            'text': body
        },
        timeout=15
    )

    response.raise_for_status()

    return response.json()


@app.shell_context_processor
def make_shell_context():

    return dict(
        db=db,
        User=User,
        Role=Role
    )


@app.errorhandler(404)
def page_not_found(e):

    return render_template(
        '404.html'
    ), 404


@app.errorhandler(500)
def internal_server_error(e):

    return render_template(
        '500.html'
    ), 500


@app.route('/', methods=['GET', 'POST'])
def index():

    form = NameForm()

    roles_dictionary = create_default_roles()

    if form.validate_on_submit():

        username = form.name.data.strip()

        user = User.query.filter_by(
            username=username
        ).first()

        if user is None:

            selected_role = roles_dictionary[
                form.role.data
            ]

            user = User(
                username=username,
                role=selected_role
            )

            db.session.add(user)
            db.session.commit()

            session['known'] = False

            try:

                send_registration_email(user)

                flash(
                    'Usuário cadastrado e e-mail enviado.'
                )

            except Exception as error:

                print(
                    'Erro ao enviar e-mail:',
                    error
                )

                flash(
                    'Usuário cadastrado, mas ocorreu '
                    'um erro no envio do e-mail.'
                )

        else:

            session['known'] = True

        session['name'] = username

        return redirect(
            url_for('index')
        )

    users = User.query.order_by(
        User.id
    ).all()

    roles = Role.query.order_by(
        Role.id
    ).all()

    users_count = User.query.count()

    roles_count = Role.query.count()

    grouped_roles = []

    for role in roles:

        role_users = role.users.order_by(
            User.id
        ).all()

        grouped_roles.append({
            'role': role,
            'users': role_users
        })

    return render_template(
        'index.html',
        form=form,
        name=session.get('name'),
        known=session.get('known', False),
        users=users,
        roles=roles,
        users_count=users_count,
        roles_count=roles_count,
        grouped_roles=grouped_roles
    )


if __name__ == '__main__':
    app.run(debug=True)
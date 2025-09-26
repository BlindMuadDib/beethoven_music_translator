import os
import secrets
from logging import getLogger
from flask import Flask, render_template_string, request, flash, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, UserMixin, RoleMixin, login_required, roles_required
from flask_security.signals import user_registered
from flask_security.forms import RegisterFormV2
from wtforms import StringField
from authlib.integrations.flask_client import OAuth

# Basic logging
log = getLogger(__name__)

# --- Database Setup ---
db = SQLAlchemy()

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    fs_uniquifier = db.Column(db.String(255), unique=True, nullable=False)
    tf_primary_method = db.Column(db.String(64), nullable=True)
    tf_totp_secret = db.Column(db.String(255), nullable=True)
    roles = db.relationship('Role', secondary='roles_users',
                            backref=db.backref('users', lazy='dynamic'))

roles_users = db.Table('roles_users',
                       db.Column('user_id',
                                 db.Integer(),
                                 db.ForeignKey('user.id')),
                       db.Column('role_id',
                                 db.Integer(),
                                 db.ForeignKey('role.id')))

class AccessRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    access_code = db.Column(db.String(64), unique=True, nullable=True)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', backref=db.backref('access_request',
                                                      uselist=False))

# --- Custom Forms ---
class ExtendedRegisterForm(RegisterFormV2):
    access_code = StringField('Access Code')

    def validate(self, **kwargs):
        if not super().validate(**kwargs):
            return False

        # Manually check if the access code was provided and flash an error if not
        if not self.access_code.data:
            flash("Access Code is required", "error")
            return False

        req = AccessRequest.query.filter_by(
            email=self.email.data, access_code=self.access_code.data,
            approved=True
        ).first()
        if not req:
            # Use flash to display the error
            flash("Invalid access code or email.", "error")
            return False

        if req.user_id is not None:
            # Also flash this error
            flash("Access code has already been used.", "error")
            return False

        return True

# --- Application Factory ---
user_datastore = SQLAlchemyUserDatastore(db, User, Role)

def send_access_code_email(email, code):
    """Placehodler for sending an email. In a real app, use Flask-Mail."""
    log.info(f"EMAIL --- To: {email}, Code: {code} --- EMAIL")

def create_app(testing=False):
    app = Flask(__name__)

    # Set the testing flag from the argument
    is_testing = testing or os.environ.get("FLASK_ENV") == "testing"

    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "super-secret-key-for-dev")
    app.config['SECURITY_PASSWORD_SALT'] = os.environ.get("SECURITY_PASSWORD_SALT", "super-secret-salt-for-dev")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if is_testing:
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Tests cannot be properly isolated if SECURITY_TWO_FACTOR_REQUIRED is
        # True
        app.config['SECURITY_TWO_FACTOR_REQUIRED'] = False
        # Use a file-based DB for testing to support multiple workers in the container
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
    else:
        app.config['SECURITY_TWO_FACTOR_REQUIRED'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

    # --- Flask-Security Configuration ---
    # Unify login error messages to prevent user enumeration and match test
    app.config["SECURITY_MSG_USER_DOES_NOT_EXIST"] = ("Invalid email or password", "error")
    app.config["SECUIRYT_MSG_INVALID_PASSWORD"] = ("Invalid email or password", "error")

    app.config['SECURITY_TOTP_SECRETS'] = {"1": "JBSWY3DPEHPK3PXP"} # Add a dummy secret for testing
    app.config['SECURITY_TOTP_ISSUER'] = "MusicTranslator" # This is the name users will see in their authenticator app

    app.config['SECURITY_REGISTERABLE'] = True
    app.config['SECURITY_SEND_REGISTER_EMAIL'] = False
    app.config['SECURITY_CHANGEABLE'] = True
    app.config['SECURITY_RECOVERABLE'] = True
    app.config['SECURITY_TWO_FACTOR'] = True
    app.config['SECURITY_RENDER_EXTRA_FORM_FIELDS'] = True # Render custom form fields
    app.config['SECURITY_TWO_FACTOR_ENABLED_METHODS'] = ["authenticator"]
    app.config['SECURITY_OAUTH_ENABLE'] = True
    app.config['SECURITY_OAUTH_CONFIG'] = {
        'google': {
            'display_name': 'Google',
            'consumer_key': os.environ.get('GOOGLE_CLIENT_ID', 'dummy_id'),
            'consumer_secret': os.environ.get('GOOGLE_CLIENT_SECRET', 'dummy_secret'),
        }
    }

    db.init_app(app)
    security = Security(app, user_datastore,
                        register_form=ExtendedRegisterForm)

    def setup_database(app_instance):
        with app_instance.app_context():
            db.create_all()
            user_datastore.find_or_create_role(name='admin',
                                               description='Full access')
            user_datastore.find_or_create_role(name='account_holder',
                                               description='Account holder access')
            if not user_datastore.find_user(email='admin@musictranslator.org'):
                # Use an environment variable for the admin password!
                admin_pw = os.environ.get("ADMIN_INITIAL_PASSWORD", "super-insecure-default-password")
                user_datastore.create_user(
                    email='admin@musictranslator.org',
                    password=admin_pw,
                    roles=['admin']
                )
            db.session.commit()

    # Only set up the database automatically if NOT testing.
    # The test suite will manage its own database
    if not is_testing:
        with app.app_context():
            setup_database(app)

    # --- Views ---
    @app.route('/')
    def index():
        return render_template_string("""
            <h1>Welcome!</h1>
            {% if current_user.is_authenticated %}
                <p>Hello, {{ current_user.email }}!</p>
                <p><a href="{{ url_for('security.logout') }}">Logout</a></p>
            {% else %}
                <p>
                    <a href="{{ url_for('security.login') }}">Login</a> |
                    <a href="{{ url_for('request_access') }}">Request Access</a> |
                    <a href="{{ url_for('security.register') }}">Register</a>
                </p>
            {% endif %}
        """)

    @app.route('/request-access', methods=['GET', 'POST'])
    def request_access():
        if request.method == 'POST':
            email = request.form.get('email')
            if not email:
                flash("Email is required.", "error")
            elif AccessRequest.query.filter_by(email=email).first():
                flash("A request for this email already exists.", "info")
            else:
                new_req = AccessRequest(email=email)
                db.session.add(new_req)
                db.session.commit()
                flash("Request submitted! An admin will review it shortly",
                      "success")
            return redirect(url_for('request_access'))

        return render_template_string("""
            <h2>Request Access Code</h2>
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                <ul>
                {% for category, message in messages %}
                  <li class="{{ category }}">{{ message }}</li>
                {% endfor %}
                </ul>
              {% endif %}
            {% endwith %}
            <form method="POST">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required>
                <button type="submit">Submit</button>
            </form>
        """)

    # --- Admin Panel ---
    @app.route('/admin/')
    @roles_required('admin')
    def admin_index():
        return "<h1>Admin Panel</h1><p><a href='/admin/requests'>View Access Requests</a></p>"

    @app.route('/admin/requests')
    @roles_required('admin')
    def admin_requests():
        requests = AccessRequest.query.order_by(AccessRequest.approved.asc()).all()
        return render_template_string("""
            <h2>Access Requests</h2>
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}{% for c, m in messages %}<p>{{m}}</p>{% endfor %}{% endif %}
            {% endwith %}
            <table border="1">
                <tr><th>ID</th><th>Email</th><th>Status</th><th>Action</th></tr>
                {% for req in requests %}
                <tr>
                    <td>{{ req.id }}</td>
                    <td>{{ req.email }}</td>
                    <td{{ 'Approved' if req.approved else 'Pending' }}</td>
                    <td>
                        {% if not req.approved %}
                        <form method="POST" action="/admin/approve/{{ req.id }}">
                            <button type="submit">Approve</button>
                        </form>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
        """, requests=requests)

    @app.route('/admin/approve/<int:req_id>', methods=['POST'])
    @roles_required('admin')
    def admin_approve(req_id):
        req = db.get_or_404(AccessRequest, req_id)
        if not req.approved:
            req.approved = True
            req.access_code = secrets.token_hex(16)
            db.session.commit()
            send_access_code_email(req.email, req.access_code)
            flash(f"Request approved for {req.email}", "success")
        else:
            flash("Request was already approved.", "info")
        return redirect(url_for('admin_requests'))

    # --- Link User to AccessRequest after registration ---
    @user_registered.connect_via(app)
    def on_user_registered(app_instance, user, **extra):
        """
        When a user registers, associate their user ID with their access request
        """
        req = AccessRequest.query.filter_by(email=user.email).first()
        if req:
            req.user_id = user.id
            db.session.commit()

    # --- TESTING-ONLY ENDPOINTS ---
    if is_testing:
        @app.route('/_reset_db', methods=['POST'])
        def reset_db():
            print("--- RESETTING DATABASE ---")
            setup_database(app)
            return "Database reset!", 200

        @app.route('/_get_access_code/<email>', methods=['GET'])
        def get_access_code(email):
            # Only return the access code if the request is approved AND has
            # a code.
            req = AccessRequest.query.filter_by(email=email,
                                                approved=True).first()
            if req and req.access_code:
                return jsonify({"access_code": req.access_code})
            return jsonify({"error": "Not found"}), 404

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

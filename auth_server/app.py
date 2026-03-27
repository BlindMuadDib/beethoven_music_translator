import os
import secrets
import logging
from logging import getLogger
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, SQLAlchemyUserDatastore, UserMixin, RoleMixin, login_required, roles_required, current_user
from flask_security.signals import user_registered
from flask_security.forms import RegisterFormV2
from flask_mail import Mail, Message
from authlib.integrations.flask_client import OAuth

# Basic logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
log = getLogger(__name__)

# --- Database Setup ---
db = SQLAlchemy()
mail = Mail()

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
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
    approved = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', backref=db.backref('access_request',
                                                      uselist=False))

# --- Custom Forms ---
class ExtendedRegisterForm(RegisterFormV2):
    def validate(self, **kwargs):
        if not super().validate(**kwargs):
            return False

        # Check for an approved AccessRequest
        req = AccessRequest.query.filter_by(email=self.email.data).first()

        if not req:
            # Use flash to display the error
            flash("You must request access before registering.", "error")
            return False

        if not req.approved:
            flash("Your access request has not been approved yet.", "error")
            return False

        if req.user_id is not None:
            # Also flash this error
            flash("This email has already been registered.", "error")
            return False

        return True

# --- Datastore and Helpers ---
user_datastore = SQLAlchemyUserDatastore(db, User, Role)

def send_approval_email(email):
    """Sends an email notifying the user they are approved."""
    try:
        msg = Message("Your Access Request is Approved!",
                      sender=os.environ.get('MAIL_USERNAME', 'donotreply@musictranslator.org'),
                      recipients=[email])

        # Get the registration URL
        # Use _external=True to get the full URL
        register_url = url_for('security.register', _external=True)

        msg.body = f"You have been approved to create an account for the Music Translator for and by Deaf.\n\n" \
                   f"Please visit the link below to register:\n{register_url}"

        mail.send(msg)
        log.info(f"Approval email sent to : {email}")
    except Exception as e:
        log.error(f"Failed to send approval email to {email}: {e}")

def setup_database(app_instance):
    with app_instance.app_context():
        db.create_all()
        user_datastore.find_or_create_role(name='admin',
                                           description='Full access')
        user_datastore.find_or_create_role(name='account_holder',
                                           description='Account holder access')
        if not user_datastore.find_user(email='admin@musictranslator.org'):
            # Use an environment variable for the admin password!
            admin_pw = os.environ.get("ADMIN_INITIAL_PASSWORD",
                                      "super-insecure-default-password")
            user_datastore.create_user(
                email='admin@musictranslator.org',
                password=admin_pw,
                roles=['admin']
            )
        db.session.commit()

# --- Application Factory ---
def create_app(testing=False):
    app = Flask(__name__)

    # Set the testing flag from the argument
    is_testing = testing or os.environ.get("FLASK_ENV") == "testing"

    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "super-secret-key-for-dev")
    app.config['SECURITY_PASSWORD_SALT'] = os.environ.get("SECURITY_PASSWORD_SALT", "super-secret-salt-for-dev")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Disable email deliverability checks (DNS lookups)
    # This prevents 'Invalid email address' errors during tests for @test.com
    # domains, and prevents network timeouts in production from blocking
    # registration
    app.config['SECURITY_EMAIL_VALIDATOR_ARGS'] = {'check_deliverability': False}

    if is_testing:
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Tests cannot be properly isolated if SECURITY_TWO_FACTOR_REQUIRED is
        # True
        app.config['SECURITY_TWO_FACTOR_REQUIRED'] = False
        # Use a file-based DB for testing to support multiple workers in the container
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        # Disable email sending and confirmation for tests
        app.config['SECURITY_SEND_REGISTER_EMAIL'] = False
        app.config['SECURITY_CONFIRMABLE'] = False
    else:
        app.config['SECURITY_TWO_FACTOR_REQUIRED'] = True
        # Enable email sending and confirmation for production
        app.config['SECURITY_SEND_REGISTER_EMAIL'] = True
        app.config['SECURITY_CONFIRMABLE'] = True

        # Build the PostgresSQL connection string from environment variables
        db_user = os.environ.get('POSTGRES_USER')
        db_pass = os.environ.get('POSTGRES_PASSWORD')
        db_host = os.environ.get('POSTGRES_HOST')
        db_name = os.environ.get('POSTGRES_DB')

        if not all([db_user, db_pass, db_host, db_name]):
            # Log a fatal error if the database isn't configured
            log.critical("FATAL: Database environment variables not set!")
            # This will cause the app to crash on startup, which is
            # a good thing (fail fast)
            raise ValueError("Missing POSTGRES environment variables")

        app.config['SQLALCHEMY_DATABASE_URI'] = \
            f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"

        # This configuration prevents 'server closed the connection unexpectedly' errors
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            "pool_pre_ping": True,  # Checks if connection is alive before using it
            "pool_recycle": 1800,   # Recycle connections after 30 minutes
            "pool_size": 10,        # Keep up to 10 connections open
            "max_overflow": 20,     # Allow 20 temporary extra connections during spikes
        }

    # --- Flask-Security Configuration ---
    # Unify login error messages to prevent user enumeration and match test
    app.config["SECURITY_MSG_USER_DOES_NOT_EXIST"] = ("Invalid email or password", "error")
    app.config["SECURITY_MSG_INVALID_PASSWORD"] = ("Invalid email or password", "error")

    app.config['SECURITY_TOTP_SECRETS'] = {"1": "JBSWY3DPEHPK3PXP"} # Add a dummy secret for testing
    app.config['SECURITY_TOTP_ISSUER'] = "MusicTranslator" # This is the name users will see in their authenticator app

    app.config['SECURITY_POST_LOGIN_VIEW'] = '/auth'
    app.config['SECURITY_POST_REGISTER_VIEW'] = '/auth'
    app.config['SECURITY_REGISTERABLE'] = True
    app.config['SECURITY_SEND_REGISTER_EMAIL'] = False
    app.config['SECURITY_URL_PREFIX'] = '/auth'
    app.config['SECURITY_CHANGEABLE'] = True
    app.config['SECURITY_RECOVERABLE'] = True
    app.config['SECURITY_TWO_FACTOR'] = True
    app.config['SECURITY_TWO_FACTOR_ENABLED_METHODS'] = ["authenticator"]
    app.config['SECURITY_OAUTH_ENABLE'] = True
    app.config['SECURITY_OAUTH_CONFIG'] = {
        'google': {
            'display_name': 'Google',
            'consumer_key': os.environ.get('GOOGLE_CLIENT_ID', 'dummy_id'),
            'consumer_secret': os.environ.get('GOOGLE_CLIENT_SECRET', 'dummy_secret'),
        }
    }

    # --- Flask-Mail Configuration (for Zoho) ---
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.zoho.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't']
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'donotreply@musictranslator.org')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['SECURITY_EMAIL_SENDER'] = os.environ.get('MAIL_USERNAME', 'donotreply@musictranslator.org')

    # Make the app aware of the /auth prefix from the Ingress
    # It will use the X-Forwarded-Prefix header set by the Ingress controller
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1,
                            x_host=1, x_prefix=1)

    db.init_app(app)
    mail.init_app(app)
    security = Security(app, user_datastore,
                        register_form=ExtendedRegisterForm)

    # Explicitly initialize OAuth if Flask-Security didn't do it
    if not hasattr(security, 'oauth'):
        security.oauth = OAuth(app)

        # Create a simple class to hold provider info for the template
        class OAuthProvider:
            def __init__(self, name, conf):
                self.name = name
                self.display_name = conf.get('display_name', name)

        # Register providers and populate the list for the template
        providers_list = []
        oauth_config = app.config.get('SECURITY_OAUTH_CONFIG', {})

        for name, conf in oauth_config.items():
            # 1. Register with Authlib so login works
            security.oauth.register(name, **conf)
            # 2. Add to list so the template loop works
            providers_list.append(OAuthProvider(name, conf))

        # Attach the list to the oauth object
        security.oauth.providers = providers_list

    # Only set up the database automatically if NOT testing.
    # The test suite will manage its own database
    if not is_testing:
        with app.app_context():
            setup_database(app)

    # --- Views ---
    @app.route('/auth')
    def index():
        return render_template('index.html')

    @app.route('/auth/request-access', methods=['GET', 'POST'])
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

        return render_template('request_access.html')

    @app.route('/auth/user/profile', methods=['GET'])
    @login_required
    def user_profile():
        """Provides user info if logged in."""
        return jsonify({
            "email": current_user.email,
            # Add any other user details the frontend should have here
        })

    # --- Admin Panel ---
    @app.route('/auth/admin/')
    @roles_required('admin')
    def admin_index():
        return redirect(url_for('admin_requests'))

    @app.route('/auth/admin/requests')
    @roles_required('admin')
    def admin_requests():
        requests = AccessRequest.query.order_by(AccessRequest.approved.asc()).all()
        return render_template('admin_requests.html', requests=requests)

    @app.route('/auth/admin/approve/<int:req_id>', methods=['POST'])
    @roles_required('admin')
    def admin_approve(req_id):
        req = db.get_or_404(AccessRequest, req_id)
        if not req.approved:
            req.approved = True
            db.session.commit()
            send_approval_email(req.email)
            flash(f"Request approved for {req.email}. Notification sent", "success")
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

    # --- Internal Endpoints ---
    @app.route('/internal/validate-session')
    def internal_validate_session():
        """
        An internal endpoint for other services to validate a session cookie.
        Relies on the session cookie being forwarded in the request.
        """
        # Flask-Security's `current_user` is loaded based on the session
        # cookie. If the user is authenticated, the cookie was valid.
        if current_user.is_authenticated:
            log.info("Internal session validation success for user: %s",
                     current_user.email)
            return jsonify({"valid": True})

        log.info("Internal session validation failed: No authenticated user")
        return jsonify({"valid": False})

    @app.route('/internal/healthz')
    def health_check():
        """
        Kubernetes Liveness Probe.
        Checks if the application is running and can reach the database.
        """
        try:
            # Run a lightweight query to ensure DB connectivity
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "healthy"}), 200
        except Exception as e:
            # Log the specific error so its visible in kubectl logs
            log.error("Health check failed: %s", e)
            # Return 500, which tells K8s to restart the pod
            return jsonify({"status": "unhealthy", "reason": str(e)}), 500

    # --- TESTING-ONLY ENDPOINTS ---
    if is_testing:
        @app.route('/_reset_db', methods=['POST'])
        def reset_db():
            print("--- RESETTING DATABASE ---")
            setup_database(app)
            return "Database reset!", 200

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

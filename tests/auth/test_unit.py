"""
This unit test suite is for an authenticator server for the Music Translator for and by Deaf.
The server will align with a Flask microframework and OWASP standards for
a Gunicorn Kubernetes server

Basic requirements for beta authenticator server:
    Create RBAC
    Admins must 2FA with Google Authenticator App
    Allow users to request access with an email address
    An admin must approve requests before an access code is sent to the email
    Only admin can access user data
    Implement OAuth

Use Flask-Security "pip install -U Flask-Security" for:
    authentication, password management, 'social'/OAuth, user registration,
    2FA, account activation, username management, change email
    RBAC?

Use SQLAlchemy for the user database.
"""

import unittest
from unittest.mock import patch
from flask import Flask
import auth_server
from auth_server.app import create_app, db, user_datastore, AccessRequest, setup_database

class TestAuthAccessServer(unittest.TestCase):

    def setUp(self):
        """Set up a new app instance for each test."""
        self.app = create_app(testing=True)
        # Override the 2FA requirement for unit tests so they don't break.
        # The unit tests are not designed to test the 2FA login flow.
        # self.app.config['SECURITY_TWO_FACTOR_REQUIRED'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.addCleanup(self.app_context.pop)

        db.create_all()
        setup_database(self.app)

        self.client = self.app.test_client()

        # Roles are created by setup_database, they just need to be found
        self.admin_role = user_datastore.find_role('admin')
        self.user_role = user_datastore.find_role('account_holder')

        # Create test-specific users
        # Note: setup_database already created 'admin@musictranslator.org'
        self.admin_user = user_datastore.create_user(email='admin@test.com',
                                                     password='password',
                                                     roles=[self.admin_role],
                                                     active=True)
        self.test_user = user_datastore.create_user(email='user@test.com',
                                                    password='password',
                                                    roles=[self.user_role],
                                                    active=True)
        db.session.commit()

    def tearDown(self):
        """Clean up the database after each test."""
        db.session.remove()
        db.drop_all()

    def login(self, email, password):
        """Helped function to log in a user."""
        return self.client.post('/auth/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def logout(self):
        """Helper function to log out."""
        return self.client.get('/auth/logout', follow_redirects=True)

    def test_rbac(self):
        """
        Test Role Based Access Control for the admin panel.
        """
        self.login('admin@test.com', 'password')
        response = self.client.get('/auth/admin', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Access Requests', response.data)
        self.logout()

        self.login('user@test.com', 'password')
        response = self.client.get('/auth/admin', follow_redirects=True)
        self.assertEqual(response.status_code, 403) # Forbidden
        self.logout()

    def test_admin_must_2fa(self):
        """
        Test that admins must Two Factor Authenticate with Google Authenticator
        App
        """
        self.assertTrue(self.app.config['SECURITY_TWO_FACTOR'])
        # In a real scenario, after login, an admin without 2FA setup would be
        # redirected to a setup page. We confirm the setting is active.
        admin = user_datastore.find_user(email='admin@test.com')
        self.assertTrue(admin.tf_primary_method is None) # Initially no 2FA is setup

    @patch('auth_server.app.send_approval_email')
    def test_access_request_and_approval(self, mock_send_email):
        """
        Test access request and admin approval workflow.
        """
        # User requests access
        response = self.client.post(
            '/auth/request-access',
            data={'email': 'new_user@test.com'},
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Request submitted!', response.data)
        request = AccessRequest.query.filter_by(email='new_user@test.com').first()
        self.assertIsNotNone(request)
        self.assertFalse(request.approved)

        # Admin approves request
        self.login('admin@test.com', 'password')
        response = self.client.post(
            f'/auth/admin/approve/{request.id}',
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Request approved', response.data)

        db.session.refresh(request)
        self.assertTrue(request.approved)

        # Verify email was sent
        mock_send_email.assert_called_once_with('new_user@test.com')
        self.logout()

    def test_access_request_security(self):
        """
        Tests that only the admin can view the list of access requests
        """
        self.client.post(
            '/auth/request-access',
            data={'email': 'another@test.com'},
            follow_redirects=True
        )

        # Admin can view
        self.login('admin@test.com', 'password')
        response = self.client.get('/auth/admin/requests')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'another@test.com', response.data)
        self.logout()

        # Regular user cannot view
        self.login('user@test.com', 'password')
        response = self.client.get('/auth/admin/requests')
        self.assertEqual(response.status_code, 403)

    def test_access_approval_security(self):
        """
        Tests that only an admin can approve an access request.
        """
        response = self.client.post('/auth/request-access',
                                    data={'email': 'third@test.com'})
        request = AccessRequest.query.filter_by(email='third@test.com').first()

        # Regular user cannot approve
        self.login('user@test.com', 'password')
        response = self.client.post(
            f'/auth/admin/approve/{request.id}',
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 403)
        db.session.refresh(request)
        self.assertFalse(request.approved) # Still not approved

    def test_only_one_request_per_email(self):
        """
        Test that only one active request can be made per email address
        """
        # First request should succeed
        response1 = self.client.post(
            '/auth/request-access',
            data={'email': 'single_request@test.com'},
            follow_redirects=True
        )
        self.assertEqual(response1.status_code, 200)
        self.assertIn(b'Request submitted!', response1.data)

        # A second request with the same email should not create a new entry
        # and should inform the user
        response2 = self.client.post(
            '/auth/request-access',
            data={'email': 'single_request@test.com'},
            follow_redirects=True
        )
        self.assertEqual(response2.status_code, 200)
        self.assertIn(b'A request for this email already exists.',
                      response2.data)

        # Verify there is only one request in the database for this email
        requests = AccessRequest.query.filter_by(
            email='single_request@test.com'
        ).all()
        self.assertEqual(len(requests), 1)

    def test_create_account_with_approval(self):
        """
        Tests that users who have been approved can create an account.
        """
        req = AccessRequest(
            email='approved@test.com',
            approved=True
        )
        db.session.add(req)
        db.session.commit()

        # Use a strong password to pass default complexity checks
        response = self.client.post('/auth/register', data={
            'email': 'approved@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200) # Should land on post-register/login page
        new_user = user_datastore.find_user(email='approved@test.com')
        self.assertIsNotNone(new_user)
        self.assertTrue(new_user.is_active)

    def test_registration_validation(self):
        """
        Test that registration fails without a valid, approved AccessRequest
        """
        # 1. No AccessRequest at all
        response = self.client.post('/auth/register', data={
            'email': 'no_request@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        }, follow_redirects=True)

        self.assertIn(b'You must request access before registering', response.data)
        self.assertIsNone(user_datastore.find_user(email='no_request@test.com'))

        # 2. AccessRequest exists but is not approved
        req = AccessRequest(email='unapproved@test.com', approved=False)
        db.session.add(req)
        db.session.commit()

        response = self.client.post('/auth/register', data={
            'email': 'unapproved@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        }, follow_redirects=True)
        self.assertIn(b'Your access request has not been approved yet', response.data)
        self.assertIsNone(user_datastore.find_user(email='unapproved@test.com'))

    def test_database_stores_information(self):
        """
        Test that the database correctly stores user and access request info.
        """
        req = AccessRequest(email='dbtest@test.com', approved=True)
        db.session.add(req)
        db.session.commit()

        self.client.post('/auth/register', data={
            'email': 'dbtest@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        })

        user = user_datastore.find_user(email='dbtest@test.com')
        self.assertIsNotNone(user)
        self.assertNotEqual(user.password, 'StrongPass123!') # Check that password is hashed
        self.assertEqual(user.email, 'dbtest@test.com')

        db.session.refresh(req)
        self.assertEqual(req.user_id, user.id)

    def test_oauth_config(self):
        """
        Test that OAuth is configured in the application
        """
        self.assertIn('google', self.app.config['SECURITY_OAUTH_CONFIG'])
        # A simple check to ensure the login page contains the link to Google OAuth
        response = self.client.get('/auth/login')
        self.assertIn(b'Sign in with Google', response.data)

    def test_healthz_endpoint(self):
        """
        Test the Liveness Probe endpoint to ensure Kubernetes can monitor
        the pod.
        """
        response = self.client.get('/internal/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'healthy'})

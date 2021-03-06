# encoding=utf-8
import logging

from sqlalchemy.exc import IntegrityError
import tornado.gen
from tornado.web import HTTPError
import tornado.web

from terroroftinytown.tracker.base import BaseHandler
from terroroftinytown.tracker.form import (LoginForm, AddUserForm, ConfirmForm,
    ChangePasswordForm)
from terroroftinytown.tracker.model import User, Session
import terroroftinytown.tracker.util


ACCOUNT_COOKIE_NAME = 'tottu'
ACCOUNT_TOKEN_COOKIE_NAME = 'tottt'
logger = logging.getLogger(__name__)


class LoginHandler(BaseHandler):
    def get(self):
        form = LoginForm()
        self.render('admin/account/login.html', form=form)

    @tornado.gen.coroutine
    def post(self):
        form = LoginForm(self.request.arguments)

        if form.validate() \
        and self._login(form.username.data, form.password.data):
            logger.info(self.user_audit_text('User %s logged in.'),
                        form.username.data)
            self.redirect(
                self.get_argument('next', self.reverse_url('admin.overview'))
            )
            return

        yield terroroftinytown.tracker.util.sleep(1)
        self.render('admin/account/login.html', form=form, message='Log in failed.')

    def _login(self, username, password):
        if User.no_users_exist():
            User.save_new_user(username, password)

        if User.check_account(username, password):
            self.set_secure_cookie(
                ACCOUNT_COOKIE_NAME, username, expires_days=30
            )
            self.set_secure_cookie(
                ACCOUNT_TOKEN_COOKIE_NAME, User.get_user_token(username),
                expires_days=30
            )
            return True


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie(ACCOUNT_COOKIE_NAME)
        self.clear_cookie(ACCOUNT_TOKEN_COOKIE_NAME)
        self.redirect('/')


class AllUsersHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        add_user_form = AddUserForm()

        self.render(
            'admin/account/all.html',
            usernames=User.all_usernames(),
            add_user_form=add_user_form
        )

    @tornado.web.authenticated
    def post(self):
        action = self.get_argument('action')
        message = None

        if action != 'add_user':
            raise HTTPError(400, 'Unknown action')

        add_user_form = AddUserForm(self.request.arguments)

        if add_user_form.validate():
            username = add_user_form.username.data
            password = add_user_form.password.data

            try:
                User.save_new_user(username, password)
            except IntegrityError:
                message = 'User already exists.'
            else:
                logger.info(self.user_audit_text('Added new user %s'),
                            username)
                self.redirect(self.reverse_url('user.overview', username))
                return

        self.render(
            'admin/account/all.html',
            add_user_form=add_user_form,
            usernames=User.all_usernames(),
            message=message
        )


class UserHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, username):
        delete_form = ConfirmForm()
        password_form = ChangePasswordForm()

        self.render(
            'admin/account/user.html',
            username=username, delete_form=delete_form,
            password_form=password_form
        )

    @tornado.web.authenticated
    def post(self, username):
        action = self.get_argument('action')
        delete_form = ConfirmForm(self.request.arguments)
        password_form = ChangePasswordForm(self.request.arguments)

        if action == 'delete':
            message = self._delete(username, delete_form)
        elif action == 'password':
            message = self._password(username, password_form)
        else:
            raise HTTPError(400, 'Unknown action')

        self.render(
            'admin/account/user.html',
            username=username, delete_form=delete_form,
            password_form=password_form, message=message
        )

    def _delete(self, username, form):
        if form.validate():
            logger.info(self.user_audit_text('Deleted user %s'), username)
            User.delete_user(username)
            self.redirect(self.reverse_url('users.overview'))
        else:
            return 'Error'

    def _password(self, username, form):
        if form.validate():
            if form.username.data != username:
                return 'Wrong username'

            logger.info(self.user_audit_text('Updated user %s password'),
                        username)
            User.update_password(username, form.password.data)
            self.redirect(self.reverse_url('users.overview'))
        else:
            return 'Error'

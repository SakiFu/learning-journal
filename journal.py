# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
from pyramid.config import Configurator
from pyramid.view import view_config
from pyramid.response import Response
# from markdown import markdown
import datetime
from waitress import serve

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Unicode, UnicodeText

from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
from pyramid.httpexceptions import HTTPFound
from sqlalchemy.exc import DBAPIError

from pyramid.httpexceptions import HTTPNotFound
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from cryptacular.bcrypt import BCRYPTPasswordManager
from pyramid.security import remember, forget

# from pygments import highlight
# from pygments.lexers.python import PythonLexer
# from pygments.formatters.html import HtmlFormatter


HERE = os.path.dirname(os.path.abspath(__file__))

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))

Base = declarative_base()

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://sakiukaji@localhost:5432/learning-journal'
)




class Entry(Base):
    __tablename__ = 'entries'
    id = sa.Column(Integer, primary_key=True, autoincrement=True)
    title = sa.Column(sa.Unicode(100), nullable=False)
    text = sa.Column(sa.UnicodeText, nullable=False)
    date = sa.Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    @classmethod
    def write(cls, title=None, text=None, session=None):
        if session is None:
            session = DBSession
        instance = cls(title=title, text=text)
        session.add(instance)
        return instance

    @classmethod
    def all(cls, session=None):
        if session is None:
            session = DBSession
        return session.query(cls).order_by(cls.date.desc()).all()

    @classmethod
    def search(cls, id, session=None):
        if session is None:
            session = DBSession
        return session.query(cls).filter_by(id=id).one()

    # @classmethod
    # def get_entry(cls, id, session=None):
    #     """get single entry"""
    #     if session is None:
    #         session = DBSession
    #     return session.query(cls).get(id)

    # @classmethod
    # def update(cls, id, title=None, text=None, session=None):
    #     if session is None:
    #         session = DBSession
    #     entry = session.query(cls).filter_by(id=id).one()
    #     entry.title = title
    #     entry.text = text
    #     return entry



@view_config(route_name='home', renderer='templates/index.jinja2')
def index_view(request):
    entries = Entry.all()
    return {'entries':entries}


@view_config(route_name='detail', renderer='templates/detail.jinja2')
def detail_view(request):
    post_id = request.matchdict.get('id', None)
    try:
        entry = Entry.search(post_id)
    except NoResultFound:
        return HTTPNotFound('No post found.')
    return {'entry': entry}

@view_config(route_name='edit', renderer='templates/edit.jinja2')
def edit_view(request):
    entry = Entry.all()
    return {'entry':entry}

@view_config(route_name='create', renderer='templates/create.jinja2')
def add_view(request):
    entries = Entry.all()
    return {'entries':entries}


@view_config(route_name='add', request_method='POST')
def add_entry(request):
    title = request.params.get('title')
    text = request.params.get('text')
    Entry.write(title=title, text=text)
    return HTTPFound(request.route_url('create'))


@view_config(context=DBAPIError)
def db_exception(context, request):
    from pyramid.response import Response
    response = Response(context.message)
    response.status_int = 500
    return response


@view_config(route_name='login', renderer="templates/login.jinja2")
def login(request):
    """authenticate a user by username/password"""
    username = request.params.get('username', '')
    error = ''
    if request.method == 'POST':
        error = "Login Failed"
        authenticated = False
        try:
            authenticated = do_login(request)
        except ValueError as e:
            error = str(e)

        if authenticated:
            headers = remember(request, username)
            return HTTPFound(request.route_url('home'), headers=headers)

    return {'error': error, 'username': username}


@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(request.route_url('home'), headers=headers)


def main():
    """Create a configured wsgi app"""
    settings = {}
    debug = os.environ.get('DEBUG', True)
    settings['reload_all'] = debug
    settings['debug_all'] = debug
    settings['auth.username'] = os.environ.get('AUTH_USERNAME', 'admin')
    manager = BCRYPTPasswordManager()
    settings['auth.password'] = os.environ.get(
        'AUTH_PASSWORD', manager.encode('secret')
    )
    if not os.environ.get('TESTING', False):
        # only bind the session if we are not testing
        engine = sa.create_engine(DATABASE_URL)
        DBSession.configure(bind=engine)
    auth_secret = os.environ.get('JOURNAL_AUTH_SECRET', 'itsaseekrit')
    # configuration setup
    config = Configurator(
        settings=settings,
        authentication_policy=AuthTktAuthenticationPolicy(
            secret=auth_secret,
            hashalg='sha512'
        ),
        authorization_policy=ACLAuthorizationPolicy(),
    )
    config.include('pyramid_jinja2')
    config.include('pyramid_tm')
    config.add_route('home', '/')
    config.add_route('detail', '/detail/{id}')
    config.add_route('add', '/add')
    config.add_route('create', '/create')
    config.add_route('edit', '/edit')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_static_view('static', os.path.join(HERE, 'static'))
    config.scan()
    app = config.make_wsgi_app()

    return app


def init_db():
    engine = sa.create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)


def do_login(request):
    username = request.params.get('username', None)
    password = request.params.get('password', None)
    if not (username and password):
        raise ValueError('both username and password are required')

    settings = request.registry.settings
    manager = BCRYPTPasswordManager()
    if username == settings.get('auth.username', ''):
        hashed = settings.get('auth.password', '')
        return manager.check(hashed, password)



if __name__ == '__main__':
    app = main()
    port = os.environ.get('PORT', 5000)
    serve(app, host='0.0.0.0', port=port)
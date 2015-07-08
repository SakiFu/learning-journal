# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import pytest
from sqlalchemy import create_engine

import journal

TEST_DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://sakiukaji@localhost:5432/test-learning-journal'
)
os.environ['DATABASE_URL'] = TEST_DATABASE_URL
os.environ['TESTING'] = "True"


@pytest.fixture(scope='session')
def connection(request):
    engine = create_engine(TEST_DATABASE_URL)
    journal.Base.metadata.create_all(engine)
    connection = engine.connect()
    journal.DBSession.registry.clear()
    journal.DBSession.configure(bind=connection)
    journal.Base.metadata.bind = engine
    request.addfinalizer(journal.Base.metadata.drop_all)
    return connection


@pytest.fixture()
def db_session(request, connection):
    from transaction import abort
    trans = connection.begin() #create new transaction
    request.addfinalizer(trans.rollback)
    request.addfinalizer(abort)

    from journal import DBSession #DBsession's' name scope is only in the function above
    return DBSession


@pytest.fixture()
def app(db_session):
    from journal import main
    from webtest import TestApp
    app = main()
    return TestApp(app)

@pytest.fixture()
def homepage(app):
    return app.get('/')


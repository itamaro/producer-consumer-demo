# Copyright 2017 The Ostrich | by Itamar Ostricher

from datetime import datetime
import json
import os

from flask import Flask
from flask import request
from pymongo import MongoClient
from redis import Redis


class ReverseProxied(object):
  """Wrap the application in this middleware and configure the
  front-end server to add these headers, to let you quietly bind
  this to a URL other than / and to an HTTP scheme that is
  different than what is used locally.

  In nginx:
  location /prefix {
    proxy_pass http://app_server:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Scheme $scheme;
    proxy_set_header X-Script-Name /prefix;
  }

  :param app: the WSGI application
  """
  def __init__(self, app):
    self.app = app

  def __call__(self, environ, start_response):
    script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
    if script_name:
      environ['SCRIPT_NAME'] = script_name
      path_info = environ['PATH_INFO']
      if path_info.startswith(script_name):
        environ['PATH_INFO'] = path_info[len(script_name):]

    scheme = environ.get('HTTP_X_SCHEME', '')
    if scheme:
      environ['wsgi.url_scheme'] = scheme
    return self.app(environ, start_response)


app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
# TODO(itamar): move DB init to proper scope, and don't rewrite redis name...
redis = Redis(host=os.environ.get('REDIS_HOST_NAME', 'redis'),
              port=int(os.environ.get('REDIS_PORT_NUMBER', 6379)))
mongo_client = MongoClient(os.environ.get('MONGO_CONNECTION_STRING',
                                          'mongodb://mongo:27017'))
mongo_db = mongo_client.ostrich


@app.route('/')
def hello():
  redis.incr('views')
  return 'Hello! This page has been seen %d times.' % int(redis.get('views'))


@app.route('/trigger', methods=['POST'])
def trigger():
  trigger_data = request.get_json(silent=True)
  # 1. Console log trigger request
  app.logger.debug('Headers: %s', request.headers)
  app.logger.debug('JSON body: %s', trigger_data)
  # 2. Log the trigger in persistent DB
  insert_result = mongo_db.triggers_log.insert_one({
      'trigger_source': 'api',
      'server_time': datetime.now(),
      'request_headers': {key: value for key, value in request.headers},
      'trigger_body': trigger_data,
  })
  app.logger.debug('Logged trigger in DB: %s',
                   insert_result.inserted_id)
  # 3. Append the trigger to triggers queue for processing by a worker
  redis.rpush('triggers_queue', json.dumps(trigger_data))
  return 'OK'


@app.route('/healthz')
def healthz():
  return 'OK'


if '__main__' == __name__:
  app.run(host='0.0.0.0', port=5000, debug=True)

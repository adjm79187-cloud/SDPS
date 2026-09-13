import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app import app
from serverless_wsgi import handle

def handler(event, context):
    return handle(app, event, context)

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from database import *   # your existing functions

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = "vercel-secret-change-it"

# Copy ALL your routes here (login, dashboard, round1, round2, submit, etc.)
# Do NOT include app.run()

# Vercel expects a callable named 'app'
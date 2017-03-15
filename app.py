# mgmt pkgs
import os                               # file and dir mgmt
import shutil                           # path vaporization
import requests                         # pulling web content


# flask
from flask import Flask, render_template, request, flash, session
# initialize flask app
app = Flask(__name__, instance_relative_config=True)
# pull general configurations
app.config.from_object('config')
# pull secret configurations from instance/
app.config.from_pyfile('config.py')


# bring in the feedtube
import feedtube
# and management
from moirai import queue_up
from helpers import build_flash_message


def handle_request(email, tag, amount):
    # save session info
    save_session(email, tag, amount)
    # pass user request to background workers
    queue_up(email, tag, int(amount))
    # let the user know we're processing their request
    flash(build_flash_message(email))


def save_session(email, tag, amount):
    session['email'] = email
    session['tag'] = tag
    session['amount'] = amount


# page logic
@app.route('/', methods=['GET', 'POST'])
def index():
    # user is just getting here, show them the page
    if request.method == 'GET':
        return render_template('index.html',
                               email=session.get('email', ''),
                               tag=session.get('tag', ''),
                               amount=session.get('amount', ''))
    # pull form values
    email = request.form['email']
    tag = request.form['tag']
    amount = request.form['amount']
    # lift heavy things
    handle_request(email, tag, amount)
    # show index page with form unchanged
    return render_template('index.html',
                           email=session.get('email', ''),
                           tag=session.get('tag', ''),
                           amount=session.get('amount', ''))


# run the application
if __name__ == '__main__':
    app.run()

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
import moirai


def handle_request(email, tag, amount):
    # save session info
    save_session(email, tag, amount)
    # handle user request
    queue_feedtube(email, tag, int(amount))
    # let the user know we're processing their request
    flash(build_flash_message(email))


def queue_feedtube(email, tag, amount):
    # don't let fat requests block quick ones
    if amount >= 150:
        return moirai.atropos.enqueue(feedtube.get_food, email, tag, amount)
    elif amount >= 50:
        return moirai.lachesis.enqueue(feedtube.get_food, email, tag, amount)
    else:
        return moirai.clotho.enqueue(feedtube.get_food, email, tag, amount)


def build_flash_message(email):
    msg = "Sometimes this part takes a while."
    msg += "We'll send it over to {0} as soon as it's ready.".format(email)
    msg += "Thank you for your patience!"
    return msg


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

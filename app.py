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


# rq
from redis import Redis
from rq import Queue
q = Queue(connection=Redis(), default_timeout=86400)  # timeout @ 1 day


# bring in the feedtube
import feedtube


@app.route('/', methods=['GET', 'POST'])
def index():
    # user is just getting here, show them the page
    if request.method == 'GET':
        return render_template('index.html',
                               email=session.get('email', ''),
                               tag=session.get('tag', ''),
                               amount=session.get('amount', ''))
    # user submitted the form, process their request
    # pull form values
    email = request.form['email']
    tag = request.form['tag']
    amount = request.form['amount']
    # don't clear the form on form submit
    session['email'] = email
    session['tag'] = tag
    session['amount'] = amount
    # queue the user's request for images
    q.enqueue(feedtube.get_food,
              email, tag, int(amount))
    # build a message that lets the user know we're working on their request
    flash_message = "Sometimes this part takes a while."
    flash_message += "We'll send it all over to {0} as soon as it's ready.".format(email)
    flash_message += "Thank you for being patient!"
    # show the user the message we just built
    flash(flash_message)
    # show index page with form unchanged
    return render_template('index.html',
                           email=session.get('email', ''),
                           tag=session.get('tag', ''),
                           amount=session.get('amount', ''))


# run the application
if __name__ == '__main__':
    app.run()

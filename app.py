import os
import shutil
from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_mail import Mail, Message
from celery import Celery
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# initialize flask app and configs
app = Flask(__name__)
app.config.from_object('config')

APP_ROOT = os.path.join(os.path.dirname(__file__))
# load environment variables
dotenv_path = os.path.join(APP_ROOT, '.env')
load_dotenv(dotenv_path)

flickr_key = os.environ.get('FLICKR_API_KEY')
flickr_secret = os.environ.get('FLICKR_API_SECRET')

# start up celery
celery = Celery(app.name, broker=os.environ.get('BROKER_URL'))
celery.conf.update(app.config)

# initialize mail
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY'),
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD')
)
mail = Mail(app)

# initialize flickr object
import flickr_api, json, urllib
from ratelimit import rate_limited
flickr_api.set_keys(api_key = flickr_key, api_secret = flickr_secret)
from flickr_api.api import flickr

# create bucket directory if necessary
def find_bucket(path):
    if not os.path.exists(os.path.join(APP_ROOT, 'foodstuff')):
        os.mkdir(os.path.join(APP_ROOT, 'foodstuff'))
    if not os.path.exists(path):
        os.mkdir(path)

# ratelimit each hit against flickrapi
@rate_limited(1)
def get_photo_page(tag, per_page, page):
    flickr_results = flickr.photos.search(tags=tag, per_page=per_page, page=page)
    soup = BeautifulSoup(flickr_results, 'lxml-xml')
    return soup

@rate_limited(1)
def get_photo_sizes(photo_id):
    sizes = flickr.photos.getSizes(photo_id=photo_id)
    soup = BeautifulSoup(sizes, 'lxml-xml').find_all('size')
    return soup

def fill_up(tag, path, amount=10):
    silo = get_photo_page(tag, 500, 1)
    total = silo.photos['total']
    if amount > total or amount <= 0:
        amount = total
    i = 0
    for photo in silo.find_all('photo'):
        photo_id = photo['id']
        # download photo to path
        sizes = get_photo_sizes(photo_id)
        best = None
        best = sizes[-1]['source']
        if best:
            name = photo_id + ''.join(e for e in photo['title'] if e.isalnum())
            # ensure name is not too long
            name = '.'.join([name[:100], 'jpg'])
            # remove unicode chars
            name = name.encode('utf-8','ignore').decode('utf-8')
            urllib.urlretrieve(best, os.path.join(path, name))
        i += 1
        if i >= amount:
            break


# feedingtube main function
@celery.task
def get_food(email, tag, amount):
    with app.app_context():
        # nav to appropriate directory
        clean_tag = ''.join(tag.split())
        path = os.path.join(APP_ROOT, 'foodstuff', ''.join([email.split("@")[0], clean_tag]))
        find_bucket(path)
        # fill with images
        fill_up(tag, path, amount)
        # zip directory contents
        shutil.make_archive(clean_tag, 'zip', path)
        # build the email
        msg = Message(subject='Dinner\'s ready!',
                      sender='no-reply@feedingtube.host',
                      recipients=[email])
        msg.body = 'Your images for {0} are attached as a zip file.'.format(tag)
        # attach the zipfile to the email
        zipfile = '.'.join([clean_tag, 'zip'])
        os.chdir(path)
        with app.open_resource(zipfile) as z:
            msg.attach(filename=zipfile, content_type="archive/zip", data=z.read())
        # send the email
        os.chdir(APP_ROOT)
        mail.send(msg)
        # wipe path
        shutil.rmtree(path)
        # after rmtree, zip files bubble up -- kill 'em!
        if os.path.exists(zipfile):
            os.remove(zipfile)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html', email=session.get('email', ''), tag=session.get('tag', ''), amount=session.get('amount', ''))
    email = request.form['email']
    tag = request.form['tag']
    amount = request.form['amount']
    session['email'] = email
    session['tag'] = tag
    session['amount'] = amount
    get_food.delay(email, tag, int(amount))
    flash('Sometimes this part takes a while. We\'ll send it all over to {0} when it\'s ready. Thanks for being patient!'.format(email))
    return render_template('index.html', email=session.get('email', ''), tag=session.get('tag', ''), amount=session.get('amount', ''))


if __name__ == '__main__':
    app.run(debug=True)

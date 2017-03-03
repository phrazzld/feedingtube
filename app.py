import os
import shutil
from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_mail import Mail, Message
from celery import Celery
import sqlite3

# initialize flask app and configs
app = Flask(__name__)
app.config.from_object('config')

APP_ROOT = os.path.join(os.path.dirname(__file__))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# start up celery
celery = Celery(app.name, broker=os.environ.get('REDISTOGO_URL'))
celery.conf.update(app.config)
# for heroku w/celery and RedisToGo add-on
broker_url = os.environ.get('REDISTOGO_URL')
celery.conf.update(BROKER_URL=broker_url,
                   CELERY_RESULT_BACKEND=broker_url)

# initialize mail
mail = Mail(app)

# initialize flickr object
import flickrapi, json, urllib
from ratelimit import rate_limited
flickr_key = os.environ.get('FLICKR_API_KEY')
flickr_secret = os.environ.get('FLICKR_API_SECRET')
flickr = flickrapi.FlickrAPI(flickr_key, flickr_secret, format='parsed-json')

# ratelimit each hit against flickrapi
@rate_limited(1)
def initialize_silo(tag, per_page, page):
    return flickr.photos.search(tags=tag, per_page=per_page, page=page)

@rate_limited(1)
def get_photo_sizes(photo_id):
    return flickr.photos.getSizes(photo_id=photo_id)

# create bucket directory if necessary
def find_bucket(path):
    if not os.path.exists(os.path.join(APP_ROOT, 'foodstuff')):
        os.mkdir(os.path.join(APP_ROOT, 'foodstuff'))
    if not os.path.exists(path):
        os.mkdir(path)

# return a page of flickr photos as JSON
def get_page(tag, page=1):
    # silo we fetch food from, per_page max = 500
    silo = initialize_silo(tag, 500, page)
    food = silo['photos']['photo']
    return food

# loop through photos, pick and download best size for each
def fill_bucket(food, path):
    for f in food:
        options = get_photo_sizes(f['id'])
        best = None
        for option in options['sizes']['size']:
            best = option['source']
            if option['label'] == 'Original':
                break
        if best:
            name = ''.join(e for e in f['title'] if e.isalnum()) + f['id']
            # sometimes names are too long so we slice 'em up
            name = '.'.join([name[:100], 'jpg'])
            urllib.request.urlretrieve(best, os.path.join(path, name))

# get buckets of food
def fetch_buckets(tag, path, n=1):
    silo = initialize_silo(tag, 5, 1)
    total = silo['photos']['pages']
    if n > total or n <= 0:
        n = total
    for i in range(0, n):
        food = get_page(tag, i)
        fill_bucket(food, path)


# feedingtube main function
@celery.task
def get_food(email, tag):
    with app.app_context():
        # nav to appropriate directory
        clean_tag = ''.join(tag.split())
        path = os.path.join(APP_ROOT, 'foodstuff', ''.join([email.split("@")[0], clean_tag]))
        find_bucket(path)
        # fill with images
        fetch_buckets(tag, path, 1)
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
        return render_template('index.html', email=session.get('email', ''), tag=session.get('tag', ''))
    email = request.form['email']
    tag = request.form['tag']
    session['email'] = email
    session['tag'] = tag
    get_food.apply_async(args=[email, tag])
    flash('Sometimes this part takes a while. We\'ll send it all over to {0} when it\'s ready. Thanks for being patient!'.format(email))
    return render_template('index.html', email=session.get('email', ''), tag=session.get('tag', ''))


if __name__ == '__main__':
    app.run(debug=True)

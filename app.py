import os
import shutil
from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_mail import Mail, Message
from celery import Celery
from bs4 import BeautifulSoup
import requests
from PIL import Image
from StringIO import StringIO

# initialize flask app and configs
app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')

APP_ROOT = os.path.join(os.path.dirname(__file__))
# load environment variables
flickr_key = app.config['FLICKR_API_KEY']
flickr_secret = app.config['FLICKR_API_SECRET']

# start up celery
celery = Celery(app.name, broker=app.config['BROKER_URL'])
celery.conf.update(app.config)

# initialize mail
mail = Mail(app)

# initialize flickr object
import flickr_api, json, urllib
from ratelimit import rate_limited
flickr_api.set_keys(api_key = flickr_key, api_secret = flickr_secret)
from flickr_api.api import flickr

# initialize boto for access to Amazon S3
import boto3
s3 = boto3.resource('s3')

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

def fill_up(tag, bucketname, path, amount=10):
    silo = get_photo_page(tag, 500, 1)
    total = int(silo.photos['total'])
    if amount > total or amount <= 0:
        amount = total
    total_pages = total / 500 + 1
    img_num = 1
    for page in range(1, total_pages):
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
                r = requests.get(best)
                i = Image.open(StringIO(r.content))
                i.save(os.path.join(path, name), "JPEG")
                #urllib.urlretrieve(best, os.path.join(path, name))
                s3.Object(bucketname, name).put(Body=open(os.path.join(path, name), 'rb'))
                os.remove(os.path.join(path, name))
            img_num += 1
            if img_num >= amount:
                return
        silo = get_photo_page(tag, 500, page+1)


# feedingtube main function
@celery.task
def get_food(email, tag, amount):
    with app.app_context():
        # nav to appropriate directory
        clean_tag = ''.join(tag.split())
        container = email + clean_tag
        container = ''.join(e for e in container if e.isalnum())
        bucketname = 'feedingtube-a-' + ''.join(e for e in email if e.isalnum()) + '-' + clean_tag
        path = os.path.join(APP_ROOT, 'foodstuff', container)
        # fresh S3 bucket
        bucket = s3.create_bucket(Bucket=bucketname)
        find_bucket(path)
        # fill with images
        fill_up(tag, bucketname, path, amount)
        # zip directory contents
        #shutil.make_archive(clean_tag, 'zip', path)
        # build the email
        msg = Message(subject='Dinner\'s ready!',
                      sender='no-reply@feedingtube.host',
                      recipients=[email])
        msg.body = 'Your images for {0} are attached as a zip file.'.format(tag)
        # attach the zipfile to the email
        zippy = '.'.join([clean_tag, 'zip'])
        os.chdir(path)
        import zipfile
        with zipfile.ZipFile(zippy, 'w') as z:
            for key in bucket.objects.all():
                bucket.download_file(key.key, key.key)
                z.write(key.key)
                os.remove(key.key)
                key.delete()
        bucket.delete()

        with app.open_resource(os.path.join(path, zippy)) as z:
            msg.attach(filename=zippy, content_type="archive/zip", data=z.read())
        # send the email
        os.chdir(APP_ROOT)
        mail.send(msg)
        # wipe path
        shutil.rmtree(path)
        # after rmtree, zip files bubble up -- kill 'em!
        if os.path.exists(zippy):
            os.remove(zippy)


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

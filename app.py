# mgmt pkgs
import os                               # file and dir mgmt
import shutil                           # path vaporization
from bs4 import BeautifulSoup           # parsing xml
import requests                         # pulling web content
from PIL import Image                   # treating web content as an img
from StringIO import StringIO           # glue requests and PIL
from ratelimit import rate_limited      # comply with Flickr's API policy


# flask
from flask import Flask, render_template, request, flash, redirect, session
# initialize flask app
app = Flask(__name__, instance_relative_config=True)
# pull general configurations
app.config.from_object('config')
# pull secret configurations from instance/
app.config.from_pyfile('config.py')
# know project root location for navigating file downloads
app_root = os.path.join(os.path.dirname(__file__))


# celery
from celery import Celery
celery = Celery(app.name, broker=app.config['BROKER_URL'])
celery.conf.update(app.config)


# flask_mail
from flask_mail import Mail, Message
mail = Mail(app)


# flickr_api
import flickr_api, json, urllib
from flickr_api.api import flickr
flickr_key = app.config['FLICKR_API_KEY']
flickr_secret = app.config['FLICKR_API_SECRET']
# authorize access to flickr
flickr_api.set_keys(api_key = flickr_key, api_secret = flickr_secret)


# amazon s3
import boto3
s3 = boto3.resource('s3')




def set_up_local_bucket(path):
    if not os.path.exists(os.path.join(app_root, 'foodstuff')):
        os.mkdir(os.path.join(app_root, 'foodstuff'))
    if not os.path.exists(path):
        os.mkdir(path)

# only hit the Flickr API 1/s
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
            sizes = get_photo_sizes(photo_id)
            image_source = None
            image_source = sizes[-1]['source'] # always grab the big img
            if image_source:
                name = name_img_file(photo_id, photo['title'])
                r = requests.get(image_source)
                i = Image.open(StringIO(r.content)).convert('RGB')
                i.save(os.path.join(path, name), "JPEG")
                s3.Object(bucketname, name).put(Body=open(os.path.join(path, name), 'rb'))
                os.remove(os.path.join(path, name))
            img_num += 1
            if img_num >= amount:
                return
        silo = get_photo_page(tag, 500, page+1)

# strip a string on non-alphanumeric characters
def stripped(string):
    return ''.join(e for e in string if e.isalnum())

# format image filename properly
def name_img_file(img_id, title):
    name = img_id + stripped(title)
    name = '.'.join([name[:100], 'jpg'])
    name = name.encode('utf-8', 'ignore').decode('utf-8')
    return name

# process user request for images
@celery.task
def get_food(email, tag, amount):
    with app.app_context():
        # nav to appropriate directory
        clean_tag = ''.join(tag.split())
        container = email + clean_tag
        container = ''.join(e for e in container if e.isalnum())
        bucketname = 'feedingtube-a-' + ''.join(e for e in email if e.isalnum()) + '-' + clean_tag
        path = os.path.join(app_root, 'foodstuff', container)
        # fresh s3 bucket
        bucket = s3.create_bucket(Bucket=bucketname)
        # nav to temporary directory to process file downloads
        set_up_local_bucket(path)
        # plumb images from flickr into local dir, then to s3
        fill_up(tag, bucketname, path, amount)
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
        bucket.delete()             # garbage cleanup

        # attach the zipfile to the email
        with app.open_resource(os.path.join(path, zippy)) as z:
            msg.attach(filename=zippy, content_type="archive/zip", data=z.read())
        os.chdir(app_root)          # go home
        mail.send(msg)              # send the email
        shutil.rmtree(path)         # garbage cleanup
        if os.path.exists(zippy):
            os.remove(zippy)        # garbage cleanup


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
    get_food.delay(email, tag, int(amount))
    # build a message that lets the user know we're working on their request
    flash_message = "Sometimes this part takes a while."
    flash_message += "\nWe'll send it all over to {0} as soon as it's ready.".format(email)
    flash_message += "\nThank you for being patient!"
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

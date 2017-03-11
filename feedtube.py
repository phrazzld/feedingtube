# app
from app import app

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

# flask_mail
from flask_mail import Mail, Message
mail = Mail(app)

# mgmt pkgs
import os                               # file and dir mgmt
import shutil                           # path disintegration
from bs4 import BeautifulSoup           # parse xml
import requests                         # fetch web content
from PIL import Image                   # process images
from StringIO import StringIO           # glue requests and PIL
from ratelimit import rate_limited      # comply with Flickr's API policy
import sys
reload(sys)
sys.setdefaultencoding('utf-8')


def set_up_local_bucket(path):
    if not os.path.exists(os.path.join(app.config['APP_ROOT'], 'foodstuff')):
        os.mkdir(os.path.join(app.config['APP_ROOT'], 'foodstuff'))
    if not os.path.exists(path):
        os.mkdir(path)

@rate_limited(1)
def get_image_page(tag, per_page, page):
    results = flickr.photos.search(tags=tag, per_page=per_page, page=page)
    soup = BeautifulSoup(results, 'lxml-xml')
    return soup

@rate_limited(1)
def get_image_sizes(image_id):
    sizes = flickr.photos.getSizes(photo_id=image_id)
    soup = BeautifulSoup(sizes, 'lxml-xml').find_all('size')
    return soup

def fill_up(tag, bucketname, path, amount):
    silo = get_image_page(tag, 500, 1)
    total = int(silo.photos['total'])
    if amount > total or amount <= 0:
        amount = total
    total_pages = total / 500 + 1
    image_num = 1
    for page in range(1, total_pages):
        for image in silo.find_all('photo'):
            try:
                image_id = image['id']
                sizes = get_image_sizes(image_id)
                image_source = None
                image_source = sizes[-1]['source'] # always grab biggest img
                if image_source:
                    name = name_image_file(image_id, image['title'])
                    r = requests.get(image_source)
                    i = Image.open(StringIO(r.content)).convert('RGB')
                    i.save(os.path.join(path, name), 'JPEG')
                    s3.Object(bucketname, name).put(Body=open(os.path.join(path, name), 'rb'))
                    os.remove(os.path.join(path, name))
            except IOError as e:
                print("I/O error({0}): {1}").format(e.errno, e.strerror)
            image_num += 1
            if image_num > amount:
                return
        silo = get_image_page(tag, 500, page+1)

# strip a string of non-alphanumeric chars
def stripped(s):
    return ''.join(e for e in s if e.isalnum())

# format image filename properly
def name_image_file(image_id, title):
    name = image_id + stripped(title)
    name = '.'.join([name[:100], 'jpg'])
    name = name.encode('utf-8', 'ignore').decode('utf-8')
    return name


import zipfile
# compress all fetched images into zipfiles of email-attachable size
def zip_loop(email, tag, bucket, path):
    with app.app_context():
        zippy = '.'.join([tag, 'zip'])
        with zipfile.ZipFile(zippy, 'w') as z:
            for key in bucket.objects.all():
                bucket.download_file(key.key, key.key)
                z.write(key.key)
                os.remove(key.key)
                key.delete()
                size = os.path.getsize(os.path.join(path, zippy))
                if size > 15000000:  # 15MB
                    z.close()
                    email_food(email, path, zippy)
                    return zip_loop(email, tag, bucket, path)
        email_food(email, path, zippy)


# email zipfile
def email_food(email, path, zippy):
    with app.app_context():
        # build the email
        msg = Message(subject="Tell your neural nets, dinner is served!",
                      sender="no-reply@feedingtube.host",
                      recipients=[email],
                      bcc=['phraznikov+feedingtube@gmail.com'])
        msg.body = "Attached is a zipfile of your requested images."
        with app.open_resource(os.path.join(path, zippy)) as z:
            msg.attach(filename=zippy,
                       content_type="archive/zip",
                       data=z.read())
        mail.send(msg)
        os.remove(os.path.join(path, zippy))


# process user request for images
def get_food(email, tag, amount):
    with app.app_context():
        if type(amount) is not int:
            amount = int(amount)
        clean_tag = ''.join(tag.split())
        container = stripped(email + clean_tag)
        bucketname = 'feedingtube-a-' + stripped(email) + '-' + clean_tag
        path = os.path.join(app.config['APP_ROOT'], 'foodstuff', container)
        # create fresh s3 bucket
        bucket = s3.create_bucket(Bucket=bucketname)
        # nav to tmp dir to process file downloads
        set_up_local_bucket(path)
        # plumb images from flickr into local dir, then to s3
        fill_up(tag, bucketname, path, amount)
        os.chdir(path)
        zip_loop(email, tag, bucket, path)
        bucket.delete()
        os.chdir(app.config['APP_ROOT'])
        shutil.rmtree(path)

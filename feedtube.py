# app
from app import app
from helpers import stripped, name_image_file

# use Inception v3 to classify images for relevancy
from label_image import label

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
client = boto3.client('s3')

# flask_mail
from flask_mail import Mail, Message
mail = Mail(app)

# management packages
import os                               # file and dir management
import shutil                           # path disintegration
from bs4 import BeautifulSoup           # parse xml
import requests                         # fetch web content
from PIL import Image                   # process images
from StringIO import StringIO           # glue requests and PIL
from ratelimit import rate_limited      # comply with Flickr's API policy
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# make a foodstuff bucket for this request's images
def set_up_local_bucket(path):
    if not os.path.exists(os.path.join(app.config['APP_ROOT'], 'foodstuff')):
        os.mkdir(os.path.join(app.config['APP_ROOT'], 'foodstuff'))
    if not os.path.exists(path):
        os.mkdir(path)

# grab content from a page of Flickr search results
@rate_limited(1)
def get_image_page(tag, per_page, page):
    results = flickr.photos.search(tags=tag, per_page=per_page, page=page)
    soup = BeautifulSoup(results, 'lxml-xml')
    return soup

# grab all the sizes for a given image
@rate_limited(1)
def get_image_sizes(image_id):
    sizes = flickr.photos.getSizes(photo_id=image_id)
    soup = BeautifulSoup(sizes, 'lxml-xml').find_all('size')
    return soup

# download images from Flickr into a local bucket and push it to S3
def fill_up(tag, bucketname, path, amount, container):
    silo = get_image_page(tag, 100, 1)
    total = int(silo.photos['total'])
    if amount > total or amount <= 0:
        amount = total
    total_pages = total / 100 + 1
    image_num = 1
    for page in xrange(1, total_pages):
        for image in silo.find_all('photo'):
            try:
                image_id = image['id']
                sizes = get_image_sizes(image_id)
                image_source = None
                image_source = sizes[-1]['source'] # always grab biggest img
                if image_source:
                    """
                    Now we've got a URL for our image.
                    Let's plumb it through our graph file using label_image
                    """
                    prediction, confidence, label_path = label(image_source, container)
                    print("pred: {0}, conf: {1}, path: {2}".format(prediction, confidence, label_path))
                    name = name_image_file(image_id, image['title'])
                    r = requests.get(image_source)
                    try:
                        r.raise_for_status()
                    except Exception as exc:
                        print("There was a problem: {0}".format(exc))
                    image_file = open(os.path.join(path, name), 'wb')
                    for chunk in r.iter_content(100000):
                        image_file.write(chunk)
                    image_file.close()
                    s3.Object(bucketname, name).put(Body=open(os.path.join(path, name), 'rb'))
                    os.remove(os.path.join(path, name))
            except Exception as exc:
                print("There was a problem: {0}".format(exc))
            image_num += 1
            if image_num > amount:
                return
        silo = get_image_page(tag, 100, page+1)

# collect images into a zipfile on S3 and clean up
import zipfile
def zipper(email, tag, bucket, path, bucketname):
    with app.app_context():
        zippy = '.'.join([tag, 'zip'])
        with zipfile.ZipFile(zippy, 'w', allowZip64=True) as z:
            for key in bucket.objects.all():
                ext = key.key.split('.')[1]
                if ext not in ('jpg', 'jpeg'):
                    key.delete()
                else:
                    bucket.download_file(key.key, key.key)
                    z.write(key.key)
                    os.remove(key.key)
                    key.delete()
        s3.Object(bucketname, zippy).put(Body=open(os.path.join(path, zippy), 'rb'))
        url = client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucketname,
                'Key': zippy
            },
            ExpiresIn=3600*24*3 # three days
        )
        email_zips(email, url)
        os.remove(os.path.join(path, zippy))

# email a link to the S3 zipfile
def email_zips(email, url):
    with app.app_context():
        msg = Message(subject="Tell your neural nets, dinner is served!",
                      sender="no-reply@feedingtube.host",
                      recipients=[email],
                      bcc=['phraznikov+ft@gmail.com'])
        msg.body = "Use this link to download the images you requested: {0}\n\nNote: this link will only be valid for three days.".format(url)
        mail.send(msg)


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
        fill_up(tag, bucketname, path, amount, container)
        os.chdir(path)
        zipper(email, tag, bucket, path, bucketname)
        os.chdir(app.config['APP_ROOT'])
        shutil.rmtree(path)

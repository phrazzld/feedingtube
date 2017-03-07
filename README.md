# feedingtube
feedingtube is a tool that makes it easier to get data for training neural networks.

## Getting Started
Once you've cloned the repository, you're gonna need to set up your virtual environment.
```
$ pip install virtualenv
$ virtualenv venv
```
This should have created a new directory `venv` inside the `feedingtube` project directory. Then, enter your virtual environment and install all the project dependencies:
```
$ source venv/bin/activate
$ pip install -r requirements.txt
```

feedingtube depends on a few environment variables, to access the FlickrAPI and send email. Make a file called `.env` that looks like this:
```
SECRET_KEY="top-secret-so-shhh"
MAIL_USERNAME="username@gmail.com"
MAIL_PASSWORD="your-password"
FLICKR_API_KEY="long-alphanumeric-string"
FLICKR_API_SECRET="slightly-shorter-alphanumeric-string"
```

I've programmed feedingtube's SMTP email server configurations to be Gmail specific in `config.py`, but feel free to change those settings and use a different service. If you need Flickr API credentials, you can get them [here](https://www.flickr.com/services/apps/create/apply).

Open three terminal windows and run the commands below. You will need to be in your virtual environment to start your Celery worker and the Flask local server, but not Redis. To get out of your virtual environment, just run `deactivate`.

(terminal 1) `$ ./run-redis.sh`

(terminal 2) `(venv) $ celery worker -A app.celery --loglevel=info`

(terminal 3) `(venv) $ python app.py`

## Using feedingtube
Okay, so now you've set up feedingtube on your local machine and you've got your three terminal windows running Redis, Celery, and the Flask server. Open your favorite web browser and go to localhost:5000.

Enter your email in the *email* field, "apple" in the *tag* field, and "20" in the *amount* field, and submit the form. You should see a message in red thanking you for your patience as your images are fetched.

### Behind the scenes
feedingtube is going to the FlickrAPI and asking for *amount* of *tag* pictures. It downloads them one-by-one, zips them up, and emails them to *email*. 

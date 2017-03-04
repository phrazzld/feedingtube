# feedingtube
feedingtube is a tool that makes it easier to get data for training neural networks.

## Getting Started
Once you've cloned the repository, you're gonna need to set up your virtual environment.
```
pip install virtualenv
virtualenv venv
```
This should have created a new directory `venv` inside the `feedingtube` project directory. Then, enter your virtual environment and install all the project dependencies:
```
source venv/bin/activate
pip install -r requirements.txt
```

Now before you will be able to run this project on your local machine, you'll need to create a directory called `instance` and set up a `config.py` file inside. This file will contain credentials for accessing the FlickrAPI and the SMTP email server. `config.py` should look like:
```python
MAIL_USERNAME = "username@gmail.com"
MAIL_PASSWORD = "your-email-password"
FLICKR_API_KEY = "long-string-from-flickr"
FLICKR_API_SECRET = "shorter-string-from-flickr"
```
I've programmed feedingtube's SMTP email server configurations to be Gmail specific in `app.py`, but feel free to change those settings and use a different service. If you need Flickr API credentials, you can get them [here](https://www.flickr.com/services/apps/create/apply).

Open three terminal windows and run the commands below. You will need to be in your virtual environment to start your Celery worker and the feedingtube local server, but not Redis. To get out of your virtual environment, just run `deactivate`.

(terminal 1) `./run-redis.sh`

(terminal 2) `celery worker -A app.celery --loglevel=info`

(terminal 3) `python app.py`

#### And that's it!
feedingtube should be working on your local machine.

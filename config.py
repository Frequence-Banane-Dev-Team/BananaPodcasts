import os
def myconfig(app):
   app.config['MYSQL_DATABASE_USER'] = os.environ['MYSQL_DATABASE_USER']
   app.config['MYSQL_DATABASE_PASSWORD'] = os.environ['MYSQL_DATABASE_PASSWORD']
   app.config['MYSQL_DATABASE_DB'] = os.environ['MYSQL_DATABASE_DB']
   app.config['MYSQL_DATABASE_HOST'] = os.environ['MYSQL_DATABASE_HOST']
   app.config['MYSQL_DATABASE_PORT'] = int(os.environ['MYSQL_DATABASE_PORT'])
   app.config['BASE_URL'] = os.environ['BASE_URL']
   app.secret_key = os.environ['APP_SECRET_KEY'].encode()

"""

Juste un outil pour pouvoir bosser sur les templates sans devoir recompiler un container docker

"""

from flask import Flask, request, session, render_template, flash, redirect, url_for


app = Flask(__name__)

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

@app.route('/logout', methods=['POST', 'GET'])
def logout():
    if request.method == 'GET':
        return render_template('logout.html')

@app.route('/upload', methods=['POST', 'GET'])
def upload():
    if request.method == 'GET':
        return render_template('upload.html')

@app.route('/podcasts', methods=['POST', 'GET'])
def podcasts():
    if request.method == 'GET':
        return render_template('podcasts.html')

@app.route('/view', methods=['POST', 'GET'])
def view():
    if request.method == 'GET':
        return render_template('view.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port='80', debug=True)
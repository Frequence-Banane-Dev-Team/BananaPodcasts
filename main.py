from flask import Flask, request, session, render_template, flash, redirect, url_for
from flaskext.mysql import MySQL
from lxml import etree
from datetime import date, datetime
from functools import wraps
from unidecode import unidecode
import hashlib
import re
import os
import shutil


from config import myconfig


app = Flask(__name__)
mysql = MySQL()

myconfig(app)
mysql.init_app(app)



"""
Namespace utilisé pour générer le flux rss.
Voir : https://en.wikipedia.org/wiki/XML_namespace


"""
ITUNES_NAMESPACE = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ITUNES = "{%s}" % ITUNES_NAMESPACE
NSMAP = {"itunes" : ITUNES_NAMESPACE}


"""



    Fonctions utilitaires



"""

def auth_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if 'username' in session and 'id' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return decorator


def encode_string_for_filename(title):
    """
    Encode une chaîne de caractère dans un certains format pour s'assurer qu'il n'y aura pas de probleme en les manipulant (par exemple dans les urls ou le nom de fichier)
    Les caractères non ASCII sont remplacés par des caractères équivalent et la ponctuation et les espaces par des tirets.

    Args:
        title : La chaîne de caractère que l'on souhaite formatter

    Return:
        La chaine de caractère formatée 


    """
    title = unidecode(title).lower() #Essaye d'enlever les caracteres non ascii et les remplace par quelque chose proche puis met tout en minuscule
    title = re.sub("[:\s`',;-]+",  '_',    title) #Remplace une partie de la ponctuation par un tiret unique
    title = re.sub("[^a-zA-Z_]+",  '',    title) #enleve tout ce qui n'est ni une lettre a-z ou A-Z ou un tiret
    title = re.sub("^[-]+|[-]+$",  '',    title) #S'assure que le titre ne finit , ni ne commence par un tiret
    return title


"""


    Routes flask


"""

@app.route('/bonjour')
@auth_required
def hello():
    """
    C'est important de dire bonjour, c'est VALD qui me l'a appris

     """
    return "Bonjour " + session['username'] + " !"


@app.route('/', methods=['GET'])
@auth_required
def podcasts():
    conn = mysql.connect()
    cursor =conn.cursor()
    cursor.execute("SELECT sh.Title, un.Name, un.Encoded_name, sh.Encoded_title, sh.ID FROM Shows sh, Rights rt, Units un WHERE sh.Unit=un.ID AND sh.Unit = rt.Unit AND rt.User=%s AND rt.Level <=3", (session['id']) )
    data = cursor.fetchall()
    return render_template('podcasts.html', data=data, base_url=app.config['BASE_URL'])


@app.route('/view/<int:show_id>', methods=['GET'])
@auth_required
def view(show_id):
    conn = mysql.connect()
    cursor =conn.cursor()
    cursor.execute("SELECT sh.Title, un.Name, un.Encoded_name, sh.Encoded_title, sh.Description, sh.ID FROM Shows sh, Rights rt, Units un WHERE sh.ID=%s AND sh.Unit=un.ID AND sh.Unit = rt.Unit AND rt.User=%s AND rt.Level <=3", (show_id,session['id']) )
    data = cursor.fetchone()
    if data is None:
        flash("Vous n'avez pas les droits d'accès suffisants pour accéder à ce podcast !", 'danger')
        return redirect(url_for('podcasts'))

    return render_template('view.html', data=data, base_url=app.config['BASE_URL'], show_id=show_id)

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        if 'username' in request.form and 'password' in request.form:
            conn = mysql.connect()
            cursor =conn.cursor()
            cursor.execute("SELECT Salt FROM Users WHERE Username = %s", (request.form['username']))
            data = cursor.fetchone()
            if data is None:
                flash('Identifiants / Mot de passe incorrect !', 'danger')
                return redirect(url_for('login'))

            salt = data[0].encode()
            password = request.form['password'].encode()
            hashed_password = hashlib.sha512(password + salt).hexdigest()

            cursor.execute("SELECT ID, Username FROM Users WHERE Username = %s and Password = %s", (request.form['username'], hashed_password))
            data = cursor.fetchone()
            if data is None:
                flash('Identifiants / Mot de passe incorrect !', 'danger')
                return redirect(url_for('login'))

            session['id'] = data[0]
            session['username'] = data[1]

            flash('Vous êtes désormais connecté !', 'success')
            return redirect(url_for('podcasts'))


@app.route('/logout', methods=['GET'])
def logout():
    session.pop('username', None)
    flash('Vous êtes désormais deconnecté !', 'success')
    return redirect(url_for('login'))


@app.route('/edit', methods=['POST', 'GET'])
@auth_required
def edit_podcasts():
    if request.method == 'GET':
        if 'show_id' in request.args:
            conn = mysql.connect()
            cursor =conn.cursor()
            cursor.execute("SELECT sh.ID, rt.Level FROM Shows sh, Rights rt WHERE rt.User=%s and sh.ID=%s and rt.Unit=sh.Unit AND( (rt.Level <= 1))",(session['id'], request.args.get('show_id', type=int)) )
            if cursor.fetchone() is None:
                flash("Vous n'avez pas les droits d'édition sur ce podcast, veuillez contacter la direction d'antenne !", 'danger')
                return redirect(url_for('view', show_id=request.args.get('show_id', type=int)))
            cursor.execute("SELECT sh.Title, sh.Encoded_title, un.Encoded_name, sh.Unit, sh.Description, sh.Pin, sh.ID FROM Shows sh, Units un WHERE sh.ID=%s and sh.Unit=un.ID", (request.args.get('show_id', type=int)))            
            data = cursor.fetchone()

            cursor.execute("SELECT un.ID, un.Encoded_name FROM Units un, Rights rt WHERE rt.User=%s and rt.Level <=1 and rt.Unit = un.ID", (session['id']))
            units = cursor.fetchall()
            return render_template('edit-podcasts.html', data=data, units=units, base_url=app.config['BASE_URL'])
    if request.method == 'POST':
        redirection_edit_url = url_for('edit_podcasts', show_id= request.form.get('sh_id', default=0, type=int))
        keys = ['sh_title', 'sh_description', 'sh_unit' , 'pin', 'sh_id']
        keys_types = [str, str, int, int, int]

        form_data = {}
        for key, key_type in zip(keys, keys_types):
            form_data[key] = request.form.get(key, default=None, type=key_type)#recupere les données envoyés par l'utilisateur (contenu dans le dictionnaire request.form) en les formattant dans le bon type de variable
         
        form_data['sh_encoded_title'] = encode_string_for_filename(form_data['sh_title']) 
        keys.append('sh_encoded_title')
        form_data['sh_language'] = 'fr'
        keys.append('sh_language')
        form_data['sh_countries'] = None
        keys.append('sh_countries')

        conn = mysql.connect()
        cursor =conn.cursor()
        
        cursor.execute("SELECT sh.ID, rt.Level, un.Encoded_name, sh.Encoded_title , sh.Unit FROM Shows sh, Rights rt, Units un WHERE rt.User=%s and sh.ID=%s and rt.Unit=sh.Unit AND sh.Unit=un.ID AND( (rt.Level <= 1))",(session['id'], form_data['sh_id']) )
        data = cursor.fetchone()
        if (data is None):
            flash("Erreur, vous n'avez pas les droits pour modifier ce podcast, veuillez contacter la direction d'antenne !", 'danger')
            return redirect(redirection_edit_url)

        cursor.execute("UPDATE Shows SET Unit=%s, Title=%s , Encoded_title=%s, Description=%s, Language=%s, Countries=%s, Pin=%s WHERE ID=%s", (form_data['sh_unit'], form_data['sh_title'], form_data['sh_encoded_title'], form_data['sh_description'], form_data['sh_language'], form_data['sh_countries'], form_data['pin'], form_data['sh_id']))
        conn.commit()


        folder_path_old = os.path.join(app.config['FILEPATH'], data[2], data[3])
        if (data[4] != form_data['sh_unit']) or (data[3] != form_data['sh_encoded_title']):

            cursor.execute('SELECT sh.Encoded_title, un.Encoded_name FROM Shows sh, Units un WHERE sh.Unit=un.ID AND sh.ID=%s', (form_data['sh_id']))
            data = cursor.fetchone()
            folder_path_new = os.path.join(app.config['FILEPATH'], data[1], data[0])
            
            if not os.path.exists(folder_path_new):
                os.makedirs(folder_path_new)
            shutil.move(folder_path_old, folder_path_new)

        if 'sh_cover' in request.files:
            file = request.files['sh_cover']
            if file.filename != '':
                if file.filename.rsplit('.', 1)[-1].lower() != 'png':
                    flash('Fichier vide ou format d\'image incorrect (.png seulement)!', 'danger')
                    return redirect(redirection_edit_url)
                if not os.path.exists(folder_path_old):
                    os.makedirs(folder_path_old)
                file.save(os.path.join(folder_path_old, 'artwork.png'))
            
        flash('Podcast modifié', 'success')
        return redirect(redirection_edit_url)



@app.route('/upload', methods=['POST', 'GET'])
@auth_required
def upload():

    if request.method == 'GET':
        conn = mysql.connect()
        cursor =conn.cursor()
        cursor.execute("SELECT sh.ID, rt.Level FROM Shows sh, Rights rt WHERE rt.User=%s and sh.ID=%s and rt.Unit=sh.Unit AND( (rt.Level <= 2))",(session['id'], request.args.get('show_id',default=None, type=int)) )
        if cursor.fetchone() is None:
            flash("Vous n'avez pas les droits d'édition sur ce podcast, veuillez contacter la direction d'antenne !", 'danger')
            return redirect(url_for('view', show_id=request.args.get('show_id', type=int)))

        return render_template('upload.html') #utilise request.args.get('show_id') directement dans le template
    else:
        
        redirection_upload_url = url_for('upload', show_id= request.form.get('show_id', default='0'))

        keys = ['ep_title', 'ep_description', 'ep_keywords', 'display_on_third_platforms', 'display_on_website', 'ep_date', 'is_explicit', 'show_id' , 'pin']

        keys_types = [str, str, str, bool, bool, str, bool, int, int]
        if False in list( map(request.form.__contains__, keys) ): #Verifie que chacune des clefs existe dans le dictionnaire qui contient les données envoyés par l'utilisateur
            flash('Champ manquant !', 'danger')
            return redirect(redirection_upload_url)

        form_data = {}
        for key, key_type in zip(keys, keys_types):
            form_data[key] = request.form.get(key, type=key_type)#recupere les données envoyés par l'utilisateur (contenu dans le dictionnaire request.form) en les formattant dans le bon type de variable
            
        
        #On verifie si l'utilisateur à les droits sur le podcast 
        conn = mysql.connect()
        cursor =conn.cursor()
        cursor.execute("SELECT sh.ID, rt.Level FROM Shows sh, Rights rt WHERE rt.User=%s and sh.ID=%s and rt.Unit=sh.Unit AND( (rt.Level <= 1) OR (rt.Level <= 2 AND (sh.Pin=%s  OR sh.Pin=Null) ) )",(session['id'], form_data['show_id'], form_data['pin']) )
        if cursor.fetchone() is None:
            flash("Vous n'avez pas les droits sur ce podcast ou votre code est incorrect !", 'danger')
            return redirect(redirection_upload_url) #TODO : rediriger vers la page avec la liste des podcasts plutot

        keys.pop() #Nous n'avons plus besoin du pin et nous n'allons pas l'insérer dans la base de donnée donc on l'enleve
        keys_types.pop()

        form_data['encoded_title'] = encode_string_for_filename(form_data['ep_title'])

        keys.append('encoded_title') #On modifie la valeur keys pour prendre en compte les nouveaux champs, + pour rajouter ce dont on a besoin
        keys_types.append(str)

        for key in keys: #Verifie que tout les elements respectent les contraintes Not Null, et que le champ ne soit pas juste vide
            if form_data[key] == None or (type(form_data[key])==str  and len(form_data[key]) < 1):
                flash('Valeur incorrecte, aucun champ ne peut être vide !', 'danger')
                return redirect(redirection_upload_url)
        try:
            datetime.strptime(form_data['ep_date'], '%Y-%m-%d') #On verifie le format de la date pour etre YYYY-MM-DD
        except ValueError:
           flash('Format de date non correct !', 'danger')
           return redirect(redirection_upload_url)

        if 'file' not in request.files:
           flash('Fichier manquant !', 'danger')
           return redirect(redirection_upload_url)
        
        file = request.files['file']
        if file.filename == '' or file.filename.rsplit('.', 1)[-1].lower() != 'mp3':
           flash('Fichier vide ou format de fichier incorrect (.mp3 seulement)!', 'danger')
           return redirect(redirection_upload_url)
         
        
        if 'artwork' in request.files:
            artwork_file = request.files['artwork']
            if artwork_file.filename != '':
                if artwork_file.filename.rsplit('.', 1)[-1].lower() != 'png':
                    flash('Format d\'incorrect (.png seulement)!', 'danger')
                    return redirect(redirection_upload_url)
                form_data['image'] = 1
        else:
            form_data['image'] = 0

        form_data['file_length'] = 0
        
        keys.append('file_length')
        keys.append('image')
        print(keys)

        
        cursor.execute("INSERT INTO Episodes (Episodes.Title, Episodes.Description, Episodes.Keywords, Episodes.display_on_third_platforms, Episodes.display_on_website, Episodes.Date, Episodes.Is_explicit, Episodes.Show, Episodes.Encoded_title, Episodes.File_length, Episodes.custom_artwork) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);", tuple(map(form_data.get, keys)) )
        conn.commit()

        cursor.execute("SELECT *  FROM (SELECT un.Encoded_name, sh.Encoded_title as sh_title, row_number() over (order by ep.ID) as ep_rn, ep.ID, ep.Encoded_title, ep.Date FROM Episodes ep, Shows sh, Units un WHERE ep.`Show` = sh.ID and sh.Unit=un.ID and sh.ID =%s) output_tb where output_tb.ID = %s", (form_data['show_id'] ,cursor.lastrowid))
        filename_data = cursor.fetchone()
        filename_base = filename_data[1] + "-" + str(filename_data[2]) + "-" + filename_data[4] + "-" + filename_data[5].strftime('%Y_%m_%d')

        print(filename_base)

        folder_path = os.path.join(app.config['FILEPATH'], filename_data[0], filename_data[1])
        print(folder_path)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        file.save(os.path.join(folder_path, filename_base+'.mp3'))
        artwork_file.save(os.path.join(folder_path, filename_base+'.png'))
        flash('Podcast uploadé avec succès !', 'success')
        return redirect(redirection_upload_url)



@app.route('/xml/<int:show_id>')

def generate_xml(show_id):
    """
    Genere un fichier xml pour un podcast spécifique (dont l'idée est précisé dans l'URL).
    Supporte le parametre "display_on_third_platforms" qui determine si le fichier contient exclusivement les podcasts dont nous possédons 100% des droits

    La generation du fichier XML contenant le flux RSS du podcast suit les recommandations de google disponibles ici :
    https://support.google.com/podcast-publishers/answer/9889544?hl=fr

    Le namespace d'Itunes est utilisé, voir sa définition en haut du code, en variable globale 

    """
    #On ouvre la base de donnée
    print(type(show_id))
    conn = mysql.connect()
    cursor =conn.cursor()

    #On execute la requete dans la base de donnée 
    cursor.execute("SELECT un.Name, un.Encoded_name,un.Email, sh.Title, sh.Encoded_title, sh.Description, sh.Language FROM Units un, Shows sh WHERE sh.Unit=un.ID and sh.ID=%s", (show_id))
    show_data = cursor.fetchone()

    #On crée l'element xml de base 
    rss = etree.Element("rss", nsmap=NSMAP)
    rss.set("version", "2.0")
    channel = etree.SubElement(rss, "channel")

    if show_data is not None:
        
        title= etree.SubElement(channel, "title")
        title.text = show_data[3]
        owner = etree.SubElement(channel, ITUNES + "owner")
        copyright = etree.SubElement(channel, "copyright")
        copyright.text = show_data[0] + ', ' + str(date.today().year)
        email= etree.SubElement(owner, ITUNES + "email")
        email.text = show_data[2]
        author= etree.SubElement(channel, ITUNES + "author")
        author.text = show_data[0]
        description= etree.SubElement(channel, "description")
        description.text=show_data[5]
        image= etree.SubElement(channel, ITUNES + "image")
        url = "https://podcasts.frequencebanane.ch/media/" + show_data[1] + "/" +show_data[4] + "/artwork.png" 
        image.set("href", url)
        language= etree.SubElement(channel, "language")
        language.text = show_data[6]
        link= etree.SubElement(channel, "link")
        link.text= app.config['BASE_URL'] + "/xml/" + str(show_id)


        #SELECT row_number() over (order by ep.Date) as nbr,ep.Title, ep.Encoded_title, ep.Description, ep.Is_explicit, ep.Is_fully_owned FROM Episodes ep WHERE ep.`Show`=3 AND ep.Is_fully_owned >= 0
        if request.args.get('display_on_third_platforms', default=True, type=lambda v: v == '1') == True: #Si on demande à ce que le résultat comporte exclusivement des podcasts dont on possède entierement les droits, on definit une fonction qui verifie si le parametre est egale à 1 et qui renvoie true si c'est le cas
            display_on_third_platforms = 1
        else:
            display_on_third_platforms = 0

        if request.args.get('display_on_website', default=False, type=lambda v: v == '1') == True: #Si on demande à ce que le résultat comporte seulement les podcasts qui sont disponible sur le site
            display_on_website = 1
        else:
            display_on_website = 0

        cursor.execute("SELECT row_number() over (order by ep.Date) as nbr,ep.Title, ep.Encoded_title, ep.Description, ep.Is_explicit, ep.display_on_third_platforms, ep.Date, ep.File_length, ep.custom_artwork FROM Episodes ep WHERE ep.`Show`=%s AND ep.display_on_third_platforms >= %s AND ep.display_on_website >= %s ", (show_id, display_on_third_platforms, display_on_website))
        ep_data = cursor.fetchone()
        while ep_data is not None:
            item = etree.SubElement(channel, "item")
            ep_title = etree.SubElement(item, "title")
            ep_title.text = ep_data[1]
            ep_description = etree.SubElement(item, "description")
            ep_description.text = ep_data[3]
            if ep_data[8] == 1:
                ep_artwork = etree.SubElement(item, ITUNES + "image")
                ep_artwork.text = app.config['BASE_URL'] + "/media/" + show_data[1] + "/" +show_data[4] + "/" + show_data[4] + "-" + str(ep_data[0]) + "-" + ep_data[2] + "-" + ep_data[6].strftime('%Y_%m_%d') + ".png"
            ep_pubDate = etree.SubElement(item, "pubDate")
            #ep_pubDate.text = ep_data[6].strftime('%d %b %Y')
            ep_pubDate.text = ep_data[6].strftime('%a, %d %b %Y %I:%M:%S') + " +0200"
            ep_enclosure = etree.SubElement(item, "enclosure")
            url = app.config['BASE_URL'] + "/media/" + show_data[1] + "/" +show_data[4] + "/" + show_data[4] + "-" + str(ep_data[0]) + "-" + ep_data[2] + "-" + ep_data[6].strftime('%Y_%m_%d') + ".mp3"
            ep_enclosure.set("url", url)
            ep_guid = etree.SubElement(item, "guid")
            ep_guid.set("isPermaLink", "true")
            ep_guid.text = url
            ep_enclosure.set("type", "audio/mpeg")
            ep_enclosure.set("length", str(ep_data[7]))
            ep_data = cursor.fetchone()

 
    xml_res = etree.tostring(rss, pretty_print=True, xml_declaration=True, encoding="utf-8")
    return xml_res, 200, {'Content-Type': 'text/xml; charset=utf-8'}


if __name__ == "__main__":
    app.run(host='0.0.0.0', port='80', debug=True)

from flask import Flask, request, render_template, flash, redirect, url_for
from flaskext.mysql import MySQL
from lxml import etree
from datetime import date, datetime
from unidecode import unidecode
import re
import os


from config import myconfig


app = Flask(__name__)
mysql = MySQL()

myconfig(app)
mysql.init_app(app)

ITUNES_NAMESPACE = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ITUNES = "{%s}" % ITUNES_NAMESPACE
NSMAP = {"itunes" : ITUNES_NAMESPACE}

@app.route('/')
def hello():
    return 'Hello, World!'



def encode_string_for_filename(title):
    title = unidecode(title).lower() #Essaye d'enlever les caracteres non ascii et les remplace par quelque chose proche puis met tout en minuscule
    title = re.sub("[:\s`',;-]+",  '_',    title) #Remplace une partie de la ponctuation par un tiret unique
    title = re.sub("[^a-zA-Z_]+",  '',    title) #enleve tout ce qui n'est ni une lettre a-z ou A-Z ou un tiret
    title = re.sub("^[-]+|[-]+$",  '',    title) #S'assure que le titre ne finit , ni ne commence par un tiret
    return title

@app.route('/upload', methods=['POST', 'GET'])
def upload():

    if request.method == 'GET':
        return render_template('upload.html')
    else:

        keys = ['ep_title', 'ep_description', 'ep_keywords', 'is_fully_owned', 'ep_date', 'is_explicit', 'show_id']

        keys_types = [str, str, str, bool, str, bool, int]
        if False in list( map(request.form.__contains__, keys) ): #Verifie que chacune des clefs existe dans le dictionnaire qui contient les données envoyés par l'utilisateur
            flash('Champ manquant !')
            return redirect(url_for('upload'))

        form_data = {}
        for key, key_type in zip(keys, keys_types):
            form_data[key] = request.form.get(key, type=key_type)#recupere les données envoyés par l'utilisateur (contenu dans le dictionnaire request.form)
            
        
        form_data['encoded_title'] = encode_string_for_filename(form_data['ep_title'])

        keys.append('encoded_title') #On modifie la valeur keys pour prendre en compte les nouveaux champs, + pour rajouter ce dont on a besoin
        keys_types.append(str)

        for key in keys: #Verifie que tout les elements respectent les contraintes Not Null, et que le champ ne soit pas juste vide
            if form_data[key] == None or (type(form_data[key])==str  and len(form_data[key]) < 1):
                flash('Valeur incorrecte, aucun champ ne peut être vide !')
                return redirect(url_for('upload'))

        try:
            datetime.strptime(form_data['ep_date'], '%Y-%m-%d') #On verifie le format de la date pour etre YYYY-MM-DD
        except ValueError:
           flash('Format de date non correct !')
           return redirect(url_for('upload'))

        if 'file' not in request.files:
           flash('Fichier manquant !')
           return redirect(url_for('upload')) 
        
        file = request.files['file']
        if file.filename == '' or file.filename.rsplit('.', 1)[1].lower() != 'mp3':
           flash('Fichier vide ou format de fichier incorrect (.mp3 seulement)!')
           return redirect(url_for('upload'))
         
        
        form_data['file_length'] = 0
        form_data['image'] = 0
        keys.append('file_length')
        keys.append('image')
        print(keys)

        conn = mysql.connect()
        cursor =conn.cursor()
        
        cursor.execute("INSERT INTO Episodes (Episodes.Title, Episodes.Description, Episodes.Keywords, Episodes.Is_fully_owned, Episodes.Date, Episodes.Is_explicit, Episodes.Show, Episodes.Encoded_title, Episodes.File_length, Episodes.image) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);", tuple(map(form_data.get, keys)) )
        conn.commit()

        cursor.execute("SELECT *  FROM (SELECT un.Encoded_name, sh.Encoded_title as sh_title, row_number() over (order by ep.ID) as ep_rn, ep.ID, ep.Encoded_title, ep.Date FROM Episodes ep, Shows sh, Units un WHERE ep.`Show` = sh.ID and sh.Units=un.ID and sh.ID =%s) output_tb where output_tb.ID = %s", (form_data['show_id'] ,cursor.lastrowid))
        filename_data = cursor.fetchone()
        filename = filename_data[1] + "-" + str(filename_data[2]) + "-" + filename_data[4] + "-" + filename_data[5].strftime('%Y_%m_%d') + ".mp3"
        print(filename)

        folder_path = os.path.join('/var/www/media', filename_data[0], filename_data[1])
        print(folder_path)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        file.save(os.path.join(folder_path, filename))
        flash('Podcast uploadé avec succès !')
        return redirect(url_for('upload'))


#Genere un fichier xml pour un podcast spécifique (dont l'idée est précisé dans l'URL) supporte le parametre "is_fully_owned" qui determine si le fichier contient exclusivement les podcasts dont nous possédons 100% des droits
@app.route('/xml/<int:show_id>')
def generate_xml(show_id):
    #Open database
    print(type(show_id))
    conn = mysql.connect()
    cursor =conn.cursor()

    #Execute SQL query to database
    cursor.execute("SELECT un.Name, un.Encoded_name,un.Email, sh.Title, sh.Encoded_title, sh.Description, sh.Language FROM Units un, Shows sh WHERE sh.Units=un.ID and sh.ID=%s", (show_id))
    show_data = cursor.fetchone()

    #Create XML element
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
        link.text="https://podcasts.frequencebanane.ch/xml/" + str(show_id)


        #SELECT row_number() over (order by ep.Date) as nbr,ep.Title, ep.Encoded_title, ep.Description, ep.Is_explicit, ep.Is_fully_owned FROM Episodes ep WHERE ep.`Show`=3 AND ep.Is_fully_owned >= 0
        if request.args.get('is_fully_owned', default=True) == True: #Si on demande à ce que le résultat comporte exclusivement des podcasts dont on possède entierement les droits
            is_fully_owned = 1
        else:
            is_fully_owned = 0

        cursor.execute("SELECT row_number() over (order by ep.Date) as nbr,ep.Title, ep.Encoded_title, ep.Description, ep.Is_explicit, ep.Is_fully_owned, ep.Date, ep.File_length FROM Episodes ep WHERE ep.`Show`=%s AND ep.Is_fully_owned >= %s", (show_id, is_fully_owned))
        ep_data = cursor.fetchone()
        while ep_data is not None:
            item = etree.SubElement(channel, "item")
            ep_title = etree.SubElement(item, "title")
            ep_title.text = ep_data[1]
            ep_description = etree.SubElement(item, "description")
            ep_description = ep_data[3]
            ep_pubDate = etree.SubElement(item, "pubDate")
            ep_pubDate.text = ep_data[6].strftime('%d %b %Y')
            ep_enclosure = etree.SubElement(item, "enclosure")
            url = "https://podcasts.frequencebanane.ch/media/" + show_data[1] + "/" +show_data[4] + "/" + show_data[4] + "-" + str(ep_data[0]) + "-" + ep_data[2] + "-" + ep_data[6].strftime('%Y_%m_%d') + ".mp3"
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

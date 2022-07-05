from flask import Flask, request
from flaskext.mysql import MySQL
from lxml import etree
from datetime import date

app = Flask(__name__)
mysql = MySQL()


mysql.init_app(app)

ITUNES_NAMESPACE = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ITUNES = "{%s}" % ITUNES_NAMESPACE
NSMAP = {"itunes" : ITUNES_NAMESPACE}

@app.route('/')
def hello():
    return 'Hello, World!'

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
            url = "https://podcasts.frequencebanane.ch/media/" + show_data[1] + "/" +show_data[4] + "/" + str(ep_data[0]) + "-" + ep_data[2] + "-" + ep_data[6].strftime('%d-%m-%Y') + ".mp3"
            ep_enclosure.set("url", url)
            ep_guid = etree.SubElement(item, "guid")
            ep_guid.set("isPermaLink", "true")
            ep_guid.text = url
            ep_enclosure.set("type", "audio/mpeg")
            ep_enclosure.set("length", str(ep_data[7]))
            ep_data = cursor.fetchone()

 
    
    """
    data = cursor.fetchone()
    while data is not None:
        filename = str(data[0]) + "-" + data[1] + "-" + data[2].strftime('%d/%m/%Y')
        item = etree.SubElement(episodes, "item")
        item.text = filename
        data = cursor.fetchone()

    """
    xml_res = etree.tostring(rss, pretty_print=True, xml_declaration=True, encoding="utf-8")
    return xml_res, 200, {'Content-Type': 'text/xml; charset=utf-8'}


if __name__ == "__main__":
    app.run(host='0.0.0.0', port='80', debug=True)
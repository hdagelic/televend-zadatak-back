# Service koji vraca JSON

from flask import Flask, request, abort
from flask_restplus import Api, Resource, fields
from flask_sqlalchemy import SQLAlchemy
from flask_jwt import JWT, jwt_required, current_identity

# Ovo treba jer je backend na drugom portu
from flask_cors import CORS, cross_origin

import os
import sys
import datetime
import time

# Za test
import psycopg2


app = Flask(__name__)
api = Api(app)
cors = CORS(app, resources={r"/*": {"origins": "*"}})

# localhost - backend van dockera, postgres - backend u dockeru
databasehost = 'localhost'
#databasehost = 'postgres-service' 

# Ovo su razne konfiguracijske postavk
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://postgres:burek123@' + databasehost  +  ':5432/zadatak'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'nekikljuc'
app.config['JWT_EXPIRATION_DELTA'] = datetime.timedelta(minutes=60)

# Inicijalizacije
db = SQLAlchemy(app)

# Username i password
model_login = api.model('Login podaci', {
                          'username' : fields.String,
                          'password' : fields.String
                       })

# Definicija modela
model_osobe = api.model('Tip Osoba', { 
                        'username' : fields.String('Username osobe.'), 
                        'ime' : fields.String('Ime osobe.'), 
                        'prezime' : fields.String('Prezime osobe.'), 
                        'email' : fields.String('E-Mail.'),
                        'role' : fields.Integer,
                      })

# Za ispis s vremenima
model_osobe_plus_vremena = api.inherit('Tip Osoba+vremena', model_osobe, {
                         'created_at' : fields.DateTime(dt_format='rfc822'),
                         'updated_at' : fields.DateTime(dt_format='rfc822'),
                      })


# Za ispis sa ID-om
model_osobe_plus_id = api.inherit('Tip Osoba+id', model_osobe_plus_vremena, { 
                        'id' : fields.Integer
                      })

# Ukljucujuci i password
model_osobe_plus_password = api.inherit('Tip Osoba+id+password', model_osobe, {
                         'password' : fields.String('Password.')
                      })



# Definicija modela - detalji
model_detalji = api.model('Tip Osoba - detalji', {
                              'adresa' : fields.String,
                              'postcode' : fields.String,
                              'telefon' : fields.String,
                              'datum_rodjenja': fields.Date,
                              'spol' : fields.Integer
                           })

# Za ispis s vremenima i slikom
model_detalji_plus = api.inherit('Tip Osoba - detalji+vremena', model_detalji, {
                         'slika' : fields.String,
                         'created_at' : fields.DateTime(dt_format='rfc822'),
                         'updated_at' : fields.DateTime(dt_format='rfc822')
                      })


# Za ispis sa ID-om
model_detalji_plus_id = api.inherit('Tip Osoba - detalji+id', model_detalji_plus, {
                        'id' : fields.Integer
                      })

def date_now():
   return datetime.datetime.now()

# Definicija osobe - osnovni zapis
# UserMixin se nasljedjuje zbog provjere logina (id mora postojati i zvati se "id")
# Role: 1 - admin, 2 - manager, 3 - user

class Osoba(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   username = db.Column(db.String(30), unique=True)
   ime = db.Column(db.String(30))
   prezime = db.Column(db.String(30))
   password = db.Column(db.String(30), default='')
   email = db.Column(db.String(30), default='')
   role = db.Column(db.Integer, default=3)
   created_at = db.Column(db.DateTime, default=date_now())
   updated_at = db.Column(db.DateTime, onupdate=date_now())
   
   detalji = db.relationship('OsobaPlus', backref='glavni', lazy='dynamic')


# Funkcije potrebne za autentifikaciju

def authenticate(username, password):
   user = Osoba.query.filter_by(username=username).first()
 
   # Provjeri password i ulogiraj
   if user.password == password:
     return user
   else: 
     return None


def identity(payload):
    user_id = payload['identity']
    user = Osoba.query.filter_by(id=user_id).first()
    if user:
       ret_user = {}
       ret_user['id'] = user.id
       ret_user['username'] = user.username
       ret_user['ime'] = user.ime
       ret_user['role'] = user.role
       return ret_user
    else:
       return None

# Za login

jwt = JWT(app, authenticate, identity)

# Pomocna funkcija za kopiranje polja iz inputa, bez passworda

def OsobaCopy(stara_osoba, i):
   stara_osoba.username=i['username']
   stara_osoba.ime=i['ime']
   stara_osoba.prezime=i['prezime']
   stara_osoba.email=i['email']
   if i['password'] != '':
     stara_osoba.password=i['password']
   stara_osoba.role=i['role']
   stara_osoba.updated_at = date_now()


# Spol: 1 - muski, 2 - zenski
# Slika - path do slike, uploada se na fajlsistem, posebna funkcija

class OsobaPlus(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   adresa = db.Column(db.String(64), default='')
   telefon = db.Column(db.String(30), default='')
   postcode = db.Column(db.String(10), default='')
   datum_rodjenja = db.Column(db.DateTime, default=datetime.datetime.strptime('1981-1-1', '%Y-%m-%d'))
   slika = db.Column(db.String(255), default='')
   spol = db.Column(db.Integer, default=0)
   created_at = db.Column(db.DateTime, default=date_now())
   updated_at = db.Column(db.DateTime, onupdate=date_now())

   # Foreign key treba bit lowercase
   glavni_id = db.Column(db.Integer, db.ForeignKey('osoba.id'))


# Pomocna funkcija za kopiranje polja iz inputa. Bez slike

def OsobaPlusCopy(det, i, id_osobe):
   det.adresa=i['adresa']
   det.telefon=i['telefon']
   det.postcode=i['postcode']
   try:
     det.datum_rodjenja=datetime.datetime.strptime(i['datum_rodjenja'], '%Y-%m-%d')
   except:
     pass
   det.spol=i['spol']
   det.glavni_id = id_osobe
   det.updated_at = date_now()

# Ovo je ruta za dohvacanje svih osoba (na GET)  ili za dodavanje nove (na POST)



# Za dohvacanje ID-a ulogiranog korisnika
# - treba predati token

@api.route('/xauthenticated')
class XAuthenticated(Resource):
   @jwt_required()
   def get(self):
      return dict(current_identity)


@api.route('/osoba')
class OsobaRoot(Resource):
   # Vraca listu osoba
   @api.marshal_with(model_osobe_plus_id)
   def get(self):
       sve_osobe = Osoba.query.order_by('prezime asc').all()
       return sve_osobe

   # dodaje novu osobu
   @api.expect(model_osobe_plus_password)
   def post(self):
      #print(str(api.payload), file=sys.stderr)
      i =  api.payload
      nova_osoba = Osoba(username=i['username'], ime=i['ime'], prezime=i['prezime'], email=i['email'], role=i['role'], password=i['password'], created_at = date_now())
      db.session.add(nova_osoba)
      db.session.commit()
      return i


# Ovo je ruta za dohvacanje jedne osobe (GET), brisanje (DELETE) ili updateanje (POST)

@api.route('/osoba/<int:id>')
class OsobaId(Resource):
   # Vraca jednu osobu
   @api.marshal_with(model_osobe_plus_id)
   def get(self, id):
      osoba = Osoba.query.filter_by(id=id).first()
      return osoba
 
   # Updatea osobu
   @api.expect(model_osobe_plus_password)
   @jwt_required()
   def post(self, id):
      #print("post", file=sys.stderr)
      #print(str(api.payload), file=sys.stderr)


      # Ako je obicni user, i nije ulogiran - izadji
      if current_identity['role'] == 3 and id <> current_identity['id']:
          abort(401)

      i = api.payload
      stara_osoba = Osoba.query.filter_by(id=id).first()
      OsobaCopy(stara_osoba, i)
      db.session.commit()
      return i

   # Brise osobu
   @jwt_required()
   def delete(self, id):

      # Ako je obicni user, i nije ulogiran - izadji
      if current_identity['role'] == 3 and id <> current_identity['id']:
          abort(401)


      stara_osoba = Osoba.query.filter_by(id=id).first()
      db.session.delete(stara_osoba)
      db.session.commit()



# Ovdje se mogu dohvatiti detalje osobe, ako ne postoje vraca gresku
# mogu se i postaviti "post" metodom

@api.route('/osoba/<int:id>/detalji')
class DetaljiOsobe(Resource):
   
   # Vraca detalje osobe
   @api.marshal_with(model_detalji_plus_id)
   # Vraca detalje osobe
   def get(self, id):
      # Ako nema rezultata, "det" je None, pa se vraca null json (sa svim null poljima)
      det = OsobaPlus.query.filter_by(glavni_id=id).first()
      return det

   # Postavlja detalje
   @api.marshal_with(model_detalji_plus_id)
   @api.expect(model_detalji)
   @jwt_required()
   def post(self, id):
 
      # Ako je obicni user, i nije ulogiran - izadji
      if current_identity['role'] == 3 and id <> current_identity['id']:
          abort(401)
  
      det = OsobaPlus.query.filter_by(glavni_id=id).first()
      novi = False 
      if (det is None):
         det = OsobaPlus()
         novi = True
      # Postavi detalje po payloadu
      OsobaPlusCopy(det, api.payload, id)
      # Ako je ovo novi zapis u bazi - dodaj u session
      if novi: 
         db.session.add(det)
      db.session.commit()   
      return det


# Upload slike
@api.route('/osoba/<int:id>/uploadslike')
class Upload(Resource):
   @jwt_required()
   def post(self, id):
 
       # Ako je obicni user, i nije ulogiran - izadji
       if current_identity['role'] == 3 and id <> current_identity['id']:
          abort(401)

 
       # Stvori upload dir ako ne postoji
       if not os.path.isdir('static/slike'):
         os.makedirs('static/slike')

       det = OsobaPlus.query.filter_by(glavni_id=id).first()
       if (det is None):
          det = OsobaPlus()
          det.glavni_id = id
          db.session.add(det)
          #return 'Error: detalji ne postoje, najprije ih treba napraviti' 

       #print(str(request.files))
    
       infile = request.files['slika']
       name = infile.filename
       dest = 'static/slike/' + name
       infile.save(dest)
       det.slika = dest
       db.session.commit()

       return 'Saved ' + name

# Za test, ako CONNECT ne uspije - exception
@api.route('/xdbtest')
class Dbtest(Resource):
   def get(self): 
       xstr = ''
       conn = None
       cursor = None
       conn_string = "host='" + databasehost + "' dbname='zadatak' user='postgres' password='burek123'"
       try: 
          conn = psycopg2.connect(conn_string)
          cursor = conn.cursor()
          xstr += 'CONNECT: ok '
       except Exception as e:
          xstr += 'CONNECT: fail: ' + str(e)

       try:
          cursor.execute("SELECT * FROM Osoba")
          records = cursor.fetchall()
          xstr += 'SELECT: ok: ' + str(records)
       except Exception as e:
          xstr += 'SELECT: fail: ' + str(e)
       return { 'result' : 'ovo je test baze: ' + xstr }


if __name__ == '__main__':
   app.run(host='0.0.0.0', port=80, debug=True)


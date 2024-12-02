from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Admin credentials
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Google Sheets Setup
GOOGLE_CREDENTIALS_PATH = 'credentials.json'
GOOGLE_SHEET_ID = os.environ.get('GOOGLE_SHEET_ID')

def get_google_credentials():
    if os.environ.get('GOOGLE_CREDENTIALS'):
        # For production (Render)
        return json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
    else:
        # For local development
        with open('credentials.json', 'r') as f:
            return json.load(f)

def init_google_sheets():
    credentials = service_account.Credentials.from_service_account_info(
        get_google_credentials(),
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    service = build('sheets', 'v4', credentials=credentials)
    return service.spreadsheets()

sheets_service = init_google_sheets()

# Record class
class Record:
    def __init__(self, id, date_insertion, nom_collab, titre_profil, support_ao, 
                 source_ao, nombre_cv, lien_annonce, lien_drive):
        self.id = id
        self.date_insertion = datetime.strptime(date_insertion, '%Y-%m-%d') if isinstance(date_insertion, str) else date_insertion
        self.nom_collab = nom_collab
        self.titre_profil = titre_profil
        self.support_ao = support_ao
        self.source_ao = source_ao
        self.nombre_cv = int(nombre_cv) if isinstance(nombre_cv, str) else nombre_cv
        self.lien_annonce = lien_annonce
        self.lien_drive = lien_drive

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

ADMIN_USER = User(1, ADMIN_USERNAME)

@login_manager.user_loader
def load_user(user_id):
    if int(user_id) == 1:
        return ADMIN_USER
    return None

# Google Sheets functions
def get_all_records():
    try:
        result = sheets_service.values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range='A2:H'
        ).execute()
        values = result.get('values', [])
        records = []
        for i, row in enumerate(values, start=1):
            if row and len(row) >= 8:
                record = Record(
                    id=i,
                    date_insertion=row[0],
                    nom_collab=row[1],
                    titre_profil=row[2],
                    support_ao=row[3],
                    source_ao=row[4],
                    nombre_cv=row[5],
                    lien_annonce=row[6],
                    lien_drive=row[7]
                )
                records.append(record)
        return records
    except Exception as e:
        print(f"Error getting records: {e}")
        return []

def add_record_to_sheets(record):
    try:
        # Handle custom support_ao
        support_ao = record.support_ao
        if support_ao == 'Autre':
            support_ao = request.form.get('autre_support', '')

        values = [[
            record.date_insertion.strftime('%Y-%m-%d'),
            record.nom_collab,
            record.titre_profil,
            support_ao,
            record.source_ao,
            str(record.nombre_cv),
            record.lien_annonce,
            record.lien_drive
        ]]
        
        sheets_service.values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range='A:H',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': values}
        ).execute()
        return True
    except Exception as e:
        print(f"Error adding record: {e}")
        return False

def update_record_in_sheets(record_id, record):
    try:
        row_number = record_id + 1
        
        # Handle custom support_ao
        support_ao = record.support_ao
        if support_ao == 'Autre':
            support_ao = request.form.get('autre_support', '')

        values = [[
            record.date_insertion.strftime('%Y-%m-%d'),
            record.nom_collab,
            record.titre_profil,
            support_ao,
            record.source_ao,
            str(record.nombre_cv),
            record.lien_annonce,
            record.lien_drive
        ]]
        
        sheets_service.values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f'A{row_number}:H{row_number}',
            valueInputOption='RAW',
            body={'values': values}
        ).execute()
        return True
    except Exception as e:
        print(f"Error updating record: {e}")
        return False

def delete_record_from_sheets(record_id):
    try:
        row_number = record_id + 1
        sheets_service.values().clear(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f'A{row_number}:H{row_number}'
        ).execute()
        return True
    except Exception as e:
        print(f"Error deleting record: {e}")
        return False

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(ADMIN_USER)
            flash('Connecté avec succès.', 'success')
            return redirect(url_for('index'))
        flash('Nom d\'utilisateur ou mot de passe invalide.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnecté avec succès.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    search_text = request.args.get('search_text', '')
    search_date = request.args.get('search_date', '')
    
    records = get_all_records()
    
    # Filter by text if provided
    if search_text:
        search_text = search_text.lower()
        records = [r for r in records if 
                  search_text in r.nom_collab.lower() or 
                  search_text in r.titre_profil.lower()]
    
    # Filter by date if provided
    if search_date:
        try:
            date_obj = datetime.strptime(search_date, '%Y-%m-%d').date()
            records = [r for r in records if r.date_insertion.date() == date_obj]
        except ValueError:
            flash('Format de date invalide', 'danger')
    
    supports_ao = ['LinkedIn', 'Indeed', 'Tanit', 'Monster', 'France Travail', 'APEC', 'Autre']
    return render_template('index.html', 
                         records=records, 
                         supports_ao=supports_ao,
                         search_text=search_text,
                         search_date=search_date)

@app.route('/add', methods=['POST'])
@login_required
def add():
    try:
        support_ao = request.form.get('support_ao')
        if support_ao == 'Autre':
            support_ao = request.form.get('autre_support')

        record = Record(
            id=None,
            date_insertion=request.form['date_insertion'],
            nom_collab=request.form['nom_collab'],
            titre_profil=request.form['titre_profil'],
            support_ao=support_ao,
            source_ao=request.form['source_ao'],
            nombre_cv=request.form['nombre_cv'],
            lien_annonce=request.form['lien_annonce'],
            lien_drive=request.form['lien_drive']
        )
        
        if add_record_to_sheets(record):
            flash('Enregistrement ajouté avec succès.', 'success')
        else:
            flash('Erreur lors de l\'ajout de l\'enregistrement.', 'danger')
    except Exception as e:
        flash(f'Erreur lors de l\'ajout de l\'enregistrement: {str(e)}', 'danger')
        print(e)
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    records = get_all_records()
    record = next((r for r in records if r.id == id), None)
    
    if record is None:
        flash('Enregistrement non trouvé.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            support_ao = request.form.get('support_ao')
            if support_ao == 'Autre':
                support_ao = request.form.get('autre_support')

            updated_record = Record(
                id=id,
                date_insertion=request.form['date_insertion'],
                nom_collab=request.form['nom_collab'],
                titre_profil=request.form['titre_profil'],
                support_ao=support_ao,
                source_ao=request.form['source_ao'],
                nombre_cv=request.form['nombre_cv'],
                lien_annonce=request.form['lien_annonce'],
                lien_drive=request.form['lien_drive']
            )
            
            if update_record_in_sheets(id, updated_record):
                flash('Enregistrement mis à jour avec succès.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Erreur lors de la mise à jour.', 'danger')
        except Exception as e:
            flash(f'Erreur lors de la mise à jour: {str(e)}', 'danger')
            print(e)
    
    supports_ao = ['LinkedIn', 'Indeed', 'Tanit', 'Monster', 'France Travail', 'APEC', 'Autre']
    return render_template('edit.html', record=record, supports_ao=supports_ao)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    if delete_record_from_sheets(id):
        flash('Enregistrement supprimé avec succès.', 'success')
    else:
        flash('Erreur lors de la suppression.', 'danger')
    return redirect(url_for('index'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if PORT is not set
    app.run(host="0.0.0.0", port=port)
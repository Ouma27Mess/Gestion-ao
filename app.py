from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Get sensitive data from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///recruitment.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add this context processor to make 'now' available in all templates
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# Admin credentials from environment variables
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

# Verify required environment variables are set
required_vars = ['SECRET_KEY', 'ADMIN_USERNAME', 'ADMIN_PASSWORD']
for var in required_vars:
    if not os.environ.get(var):
        raise RuntimeError(f'Required environment variable {var} is not set')

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_insertion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    nom_collab = db.Column(db.String(100), nullable=False)
    titre_profil = db.Column(db.String(200), nullable=False)
    support_ao = db.Column(db.String(50), nullable=False)
    source_ao = db.Column(db.String(500), nullable=False)  # URL field
    nombre_cv = db.Column(db.Integer, nullable=False)
    lien_annonce = db.Column(db.String(500), nullable=False)
    lien_drive = db.Column(db.String(500), nullable=False)

# Login manager function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin user creation function
def create_admin_user():
    """Create admin user if it doesn't exist"""
    if not User.query.filter_by(username=ADMIN_USERNAME).first():
        admin_user = User(username=ADMIN_USERNAME)
        admin_user.password_hash = generate_password_hash(ADMIN_PASSWORD)
        db.session.add(admin_user)
        db.session.commit()

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# Main routes
@app.route('/')
@login_required
def index():
    search_text = request.args.get('search_text', '')
    search_date = request.args.get('search_date', '')
    
    query = Record.query
    
    if search_text:
        query = query.filter(
            db.or_(
                Record.nom_collab.ilike(f'%{search_text}%'),
                Record.titre_profil.ilike(f'%{search_text}%')
            )
        )
    
    if search_date:
        try:
            date_obj = datetime.strptime(search_date, '%Y-%m-%d')
            query = query.filter(db.func.date(Record.date_insertion) == date_obj.date())
        except ValueError:
            flash('Invalid date format', 'danger')
    
    records = query.order_by(Record.date_insertion.desc()).all()
    supports_ao = ['LinkedIn', 'Indeed', 'Other']
    return render_template('index.html', records=records, supports_ao=supports_ao)

# CRUD routes
@app.route('/add', methods=['POST'])
@login_required
def add():
    try:
        record = Record(
            date_insertion=datetime.strptime(request.form['date_insertion'], '%Y-%m-%d'),
            nom_collab=request.form['nom_collab'],
            titre_profil=request.form['titre_profil'],
            support_ao=request.form['support_ao'],
            source_ao=request.form['source_ao'],
            nombre_cv=int(request.form['nombre_cv']),
            lien_annonce=request.form['lien_annonce'],
            lien_drive=request.form['lien_drive']
        )
        db.session.add(record)
        db.session.commit()
        flash('Record added successfully.', 'success')
    except Exception as e:
        flash('Error adding record.', 'danger')
        print(e)
    return redirect(url_for('index'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    record = Record.query.get_or_404(id)
    supports_ao = ['LinkedIn', 'Indeed', 'Other']
    
    if request.method == 'POST':
        try:
            record.date_insertion = datetime.strptime(request.form['date_insertion'], '%Y-%m-%d')
            record.nom_collab = request.form['nom_collab']
            record.titre_profil = request.form['titre_profil']
            record.support_ao = request.form['support_ao']
            record.source_ao = request.form['source_ao']
            record.nombre_cv = int(request.form['nombre_cv'])
            record.lien_annonce = request.form['lien_annonce']
            record.lien_drive = request.form['lien_drive']
            
            db.session.commit()
            flash('Record updated successfully.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('Error updating record.', 'danger')
            print(e)
    
    return render_template('edit.html', record=record, supports_ao=supports_ao)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    record = Record.query.get_or_404(id)
    try:
        db.session.delete(record)
        db.session.commit()
        flash('Record deleted successfully.', 'success')
    except:
        flash('Error deleting record.', 'danger')
    return redirect(url_for('index'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Run the application
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin_user()  # Create admin user on startup if it doesn't exist
    app.run(debug=True)
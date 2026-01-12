# app.py
import os
import random
import secrets
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import sqlite3
from datetime import datetime
from functools import wraps
from flask_mail import Mail, Message
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "super-secret-key"  # change this

load_dotenv()

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Mail config
app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database initialization + Image Support
def init_db():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    
    # Blog posts table (with image_url)
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  date TEXT NOT NULL,
                  image_url TEXT)''')  # Added image_url
    
    # Page content table
    c.execute('''CREATE TABLE IF NOT EXISTS page_content
                 (key TEXT PRIMARY KEY,
                  value TEXT NOT NULL)''')
    # Inside init_db() function, add this after the posts table
    c.execute('''CREATE TABLE IF NOT EXISTS contact_messages
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT NOT NULL,
              message TEXT NOT NULL,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
              read_status INTEGER DEFAULT 0)''')  # 0 = unread, 1 = read
    

    # Admin user table (WITH EMAIL + VERIFICATION)
    c.execute('''CREATE TABLE IF NOT EXISTS admin_user
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                email_verified INTEGER DEFAULT 0,
                verification_token TEXT,
                password_hash TEXT NOT NULL)''')


    # Create default admin if not exists
    c.execute("SELECT COUNT(*) FROM admin_user")
    if c.fetchone()[0] == 0:
        default_hash = generate_password_hash('admin123')
        c.execute("""
            INSERT INTO admin_user (username, email, email_verified, password_hash)
            VALUES (?, ?, ?, ?)
        """, ('admin', 'shakosako46@gmail.com', 1, default_hash))

    
    # Default content
    defaults = [
        ('home_title', 'Professional Web Development & IT Support'),
        ('home_subtitle', 'We create clean, user-friendly websites and provide ongoing maintenance to keep your online presence strong.'),
        ('home_value', 'Our value proposition: Affordable, reliable services tailored for small businesses. Get started today!'),
        ('about_story', 'Founded by Randiel James Z. Asis, we specialize in web development and IT support since 2025.'),
        ('about_team', '• Randiel James Z. Asis - Web Developer & IT Specialist'),
        ('service1_title', 'Basic Website Development'),
        ('service1_desc', 'Up to 5 pages, mobile-responsive, contact form, basic SEO.'),
        ('service1_price', '₱20,000 (One-time, Negotiable)'),
        ('service2_title', 'Email Setup & Management'),
        ('service2_desc', 'Professional emails, configuration, spam filtering, ongoing support.'),
        ('service2_price', 'Included in Monthly Fee'),
        ('service3_title', 'Website Maintenance'),
        ('service3_desc', 'Updates, backups, security, performance monitoring.'),
        ('service3_price', '₱5,000 / Month'),
        ('home_image', ''),  # Placeholder for uploaded hero image
        ('service1_image', ''),
        ('service2_image', ''),
        ('service3_image', ''),
    ]
    
    for key, value in defaults:
        c.execute("INSERT OR IGNORE INTO page_content (key, value) VALUES (?, ?)", (key, value))
    
    # Add image_url column if missing (safe migration)
    try:
        c.execute("ALTER TABLE posts ADD COLUMN image_url TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add verification_token column if missing (safe migration)
    try:
        c.execute("ALTER TABLE admin_user ADD COLUMN verification_token TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Sample blog posts
    c.execute("SELECT COUNT(*) FROM posts")
    if c.fetchone()[0] == 0:
        today = datetime.now().strftime("%B %d, %Y")
        c.executemany("INSERT INTO posts (title, content, date, image_url) VALUES (?, ?, ?, ?)", [
            ("Welcome to Our Blog", "We share tips on web development and IT.", today, None),
            ("Why Choose Professional Web Services?", "A good website builds trust and grows your business.", today, None)
        ])
    
    conn.commit()
    conn.close()

init_db()  # This runs every time — safe and adds image support automatically

# Email verification code sender
def send_verification_email(email, token):
    verification_url = url_for('verify_email', token=token, _external=True)
    msg = Message(
        subject="Verify Your Email Address",
        recipients=[email]
    )
    msg.body = f"""
Hello,

Thank you for registering. Please click the link below to verify your email address:

{verification_url}

If you did not request this, please ignore this email.

— RJ Web Services
"""
    mail.send(msg)




@app.route('/verify-email/<token>')
def verify_email(token):
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("SELECT id FROM admin_user WHERE verification_token = ?", (token,))
    user = c.fetchone()

    if user:
        c.execute("UPDATE admin_user SET email_verified = 1, verification_token = NULL WHERE id = ?", (user[0],))
        conn.commit()
        flash("Email verified successfully! You can now log in.", "success")
    else:
        flash("Invalid or expired verification token.", "error")

    conn.close()
    return redirect(url_for('admin_login'))


# Helper to get page content
def get_content(key, default=""):
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("SELECT value FROM page_content WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else default

# Admin decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# No-cache decorator
def no_cache(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated

# === PUBLIC ROUTES ===
@app.route('/')
def home():
    return render_template('home.html',
                           home_title=get_content('home_title'),
                           home_subtitle=get_content('home_subtitle'),
                           home_value=get_content('home_value'),
                           home_image=get_content('home_image'))

@app.route('/about')
def about():
    return render_template('about.html',
                           about_story=get_content('about_story'),
                           about_team=get_content('about_team'))

@app.route('/services')
def services():
    return render_template('services.html',
                           s1_title=get_content('service1_title'),
                           s1_desc=get_content('service1_desc'),
                           s1_price=get_content('service1_price'),
                           s2_title=get_content('service2_title'),
                           s2_desc=get_content('service2_desc'),
                           s2_price=get_content('service2_price'),
                           s3_title=get_content('service3_title'),
                           s3_desc=get_content('service3_desc'),
                           s3_price=get_content('service3_price'),
                           s1_image=get_content('service1_image'),
                           s2_image=get_content('service2_image'),
                           s3_image=get_content('service3_image'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        conn = sqlite3.connect('blog.db')
        c = conn.cursor()
        c.execute("INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)",
                  (name, email, message))
        conn.commit()
        conn.close()
        
        flash("Thank you! Your message has been sent. We'll reply soon.", "success")
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/blog')
def blog():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("SELECT id, title, content, date, image_url FROM posts ORDER BY id DESC")
    posts = c.fetchall()
    conn.close()
    return render_template('blog.html', posts=posts)

# === ADMIN SECTION ===
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('blog.db')
        c = conn.cursor()
        c.execute("SELECT id, password_hash, email_verified FROM admin_user WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            if user[2]:  # Check if email_verified is 1
                session['logged_in'] = True
                session['admin_username'] = username
                session['admin_user_id'] = user[0]
                flash("Login successful!", "success")
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Your email is not verified. Please check your inbox for a verification link.", "error")
        else:
            flash("Invalid username or password", "error")
    
    return render_template('admin/login.html')

@app.route('/admin')
@login_required
@no_cache
def admin_dashboard():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    
    # Get total messages and unread count
    c.execute("SELECT COUNT(*) FROM contact_messages")
    total_messages = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM contact_messages WHERE read_status = 0")
    unread_count = c.fetchone()[0]
    
    # Get all messages ordered by newest first
    c.execute("SELECT id, name, email, message, timestamp, read_status FROM contact_messages ORDER BY timestamp DESC")
    messages = c.fetchall()
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                           messages=messages,
                           total_messages=total_messages,
                           unread_count=unread_count)

@app.route('/admin/logout')
@login_required
@no_cache
def admin_logout():
    session.clear()  # Fully removes all session data
    return redirect(url_for('home'))  # Sends to public homepage

# Edit Homepage (with image upload)
@app.route('/admin/edit-home', methods=['GET', 'POST'])
@login_required
@no_cache
def edit_home():
    if request.method == 'POST':
        conn = sqlite3.connect('blog.db')
        c = conn.cursor()
        c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form['title'], 'home_title'))
        c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form['subtitle'], 'home_subtitle'))
        c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form['value'], 'home_value'))
        
        if 'home_image' in request.files:
            file = request.files['home_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                c.execute("UPDATE page_content SET value=? WHERE key=?", (f"/static/uploads/{filename}", 'home_image'))
        
        conn.commit()
        conn.close()
        flash("Homepage updated!", "success")
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/edit_home.html',
                           title=get_content('home_title'),
                           subtitle=get_content('home_subtitle'),
                           value=get_content('home_value'),
                           home_image=get_content('home_image'))

# Edit About Us (no change)
@app.route('/admin/edit-about', methods=['GET', 'POST'])
@login_required
@no_cache
def edit_about():
    if request.method == 'POST':
        conn = sqlite3.connect('blog.db')
        c = conn.cursor()
        c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form['story'], 'about_story'))
        c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form['team'], 'about_team'))
        conn.commit()
        conn.close()
        flash("About Us updated!", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/edit_about.html',
                           about_story=get_content('about_story'),
                           about_team=get_content('about_team'))

# Edit Services (add image uploads later if needed)
@app.route('/admin/edit-services', methods=['GET', 'POST'])
@login_required
@no_cache
def edit_services():
    if request.method == 'POST':
        conn = sqlite3.connect('blog.db')
        c = conn.cursor()
        for i in range(1, 4):
            c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form[f's{i}_title'], f'service{i}_title'))
            c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form[f's{i}_desc'], f'service{i}_desc'))
            c.execute("UPDATE page_content SET value=? WHERE key=?", (request.form[f's{i}_price'], f'service{i}_price'))
        conn.commit()
        conn.close()
        flash("Services updated!", "success")
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/edit_services.html',
                           s1_title=get_content('service1_title'),
                           s1_desc=get_content('service1_desc'),
                           s1_price=get_content('service1_price'),
                           s2_title=get_content('service2_title'),
                           s2_desc=get_content('service2_desc'),
                           s2_price=get_content('service2_price'),
                           s3_title=get_content('service3_title'),
                           s3_desc=get_content('service3_desc'),
                           s3_price=get_content('service3_price'))

# Manage Blog - NOW FULLY WORKING WITH IMAGE UPLOAD
@app.route('/admin/manage-blog', methods=['GET', 'POST'])
@login_required
@no_cache
def manage_blog():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        if 'delete' in request.form:
            c.execute("DELETE FROM posts WHERE id=?", (request.form['delete'],))
            flash("Post deleted!", "success")
        else:
            title = request.form['title']
            content = request.form['content']
            date = datetime.now().strftime("%B %d, %Y")
            image_path = None
            
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_path = f"/static/uploads/{filename}"
            
            c.execute("INSERT INTO posts (title, content, date, image_url) VALUES (?, ?, ?, ?)", 
                      (title, content, date, image_path))
            flash("New post published!", "success")
        conn.commit()
    
    c.execute("SELECT id, title, date, image_url FROM posts ORDER BY id DESC")
    posts = c.fetchall()
    conn.close()
    return render_template('admin/manage_blog.html', posts=posts)

@app.route('/admin/mark-read/<int:message_id>')
@login_required
@no_cache
def mark_read(message_id):
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("UPDATE contact_messages SET read_status = 1 WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    flash("Message marked as read", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-message/<int:message_id>')
@login_required
@no_cache
def delete_message(message_id):
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("DELETE FROM contact_messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    flash("Message deleted", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/profile', methods=['GET', 'POST'])
@login_required
@no_cache
def admin_profile():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()

    # Get current admin data
    c.execute("SELECT username, email, email_verified FROM admin_user WHERE id = 1")
    user = c.fetchone()

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']

        errors = []

        # Validate password
        if new_password and new_password != confirm_password:
            errors.append("Passwords do not match")

        # Validate username uniqueness
        if new_username != user[0]:
            c.execute("SELECT COUNT(*) FROM admin_user WHERE username = ?", (new_username,))
            if c.fetchone()[0] > 0:
                errors.append("Username already taken")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            # 🔐 EMAIL CHANGE → VERIFY FIRST (PUT IT HERE)
            if new_email != user[1]:
                c.execute(
                    "UPDATE admin_user SET email = ?, email_verified = 0 WHERE id = 1",
                    (new_email,)
                )
                conn.commit()

                send_verification_email(new_email)
                flash("Verification code sent to new email.", "info")
                return redirect(url_for('verify_email'))

            # Username update
            if new_username != user[0]:
                c.execute(
                    "UPDATE admin_user SET username = ? WHERE id = 1",
                    (new_username,)
                )
                session['admin_username'] = new_username

            # Password update
            if new_password:
                c.execute(
                    "UPDATE admin_user SET password_hash = ? WHERE id = 1",
                    (generate_password_hash(new_password),)
                )

            conn.commit()
            flash("Profile updated successfully!", "success")

    conn.close()
    return render_template(
        'admin/profile.html',
        current_username=user[0],
        current_email=user[1],
        email_verified=user[2]
    )

# === USER MANAGEMENT ===
@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
@no_cache
def manage_users():
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check if username or email already exists
        c.execute("SELECT COUNT(*) FROM admin_user WHERE username = ? OR email = ?", (username, email))
        if c.fetchone()[0] > 0:
            flash("Username or email already exists.", "error")
        else:
            password_hash = generate_password_hash(password)
            token = secrets.token_urlsafe(16)
            c.execute("INSERT INTO admin_user (username, email, password_hash, verification_token) VALUES (?, ?, ?, ?)",
                      (username, email, password_hash, token))
            conn.commit()
            send_verification_email(email, token)
            flash(f"User '{username}' created. A verification email has been sent.", "success")

        return redirect(url_for('manage_users'))

    c.execute("SELECT id, username, email, email_verified FROM admin_user")
    users = c.fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/resend-verification/<int:user_id>', methods=['POST'])
@login_required
@no_cache
def resend_verification(user_id):
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()
    c.execute("SELECT email, verification_token FROM admin_user WHERE id = ?", (user_id,))
    user = c.fetchone()

    if user:
        email, token = user
        if token:
            send_verification_email(email, token)
            flash(f"Verification email resent to {email}.", "success")
        else:
            flash("This user is already verified.", "info")
    else:
        flash("User not found.", "error")

    conn.close()
    return redirect(url_for('manage_users'))

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
@no_cache
def delete_user(user_id):
    conn = sqlite3.connect('blog.db')
    c = conn.cursor()

    # Prevent self-deletion
    if user_id == session.get('admin_user_id'):
        flash("You cannot delete your own account.", "error")
        conn.close()
        return redirect(url_for('manage_users'))

    # Prevent deletion of the last user
    c.execute("SELECT COUNT(*) FROM admin_user")
    if c.fetchone()[0] <= 1:
        flash("You cannot delete the last admin user.", "error")
        conn.close()
        return redirect(url_for('manage_users'))

    c.execute("DELETE FROM admin_user WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted successfully!", "success")
    return redirect(url_for('manage_users'))


if __name__ == '__main__':
    app.run(debug=True)
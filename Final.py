from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler
import re

app = Flask(__name__, template_folder="templates")
CORS(app)

# Logging setup
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/email_sender.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Email sender startup')

# Upload folder config
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_email(email):
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# ✅ Route to serve frontend UI
@app.route("/")
def home():
    return render_template("Nindex.html")

def send_email(sender_email, sender_password, receiver_emails, subject, body, attachment=None):
    try:
        if not validate_email(sender_email):
            raise ValueError(f"Invalid sender email: {sender_email}")
        
        for email in receiver_emails:
            if not validate_email(email.strip()):
                raise ValueError(f"Invalid receiver email: {email}")

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(receiver_emails)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment:
            filename = secure_filename(attachment.filename)
            attachment_path = os.path.join(UPLOAD_FOLDER, filename)
            attachment.save(attachment_path)
            
            try:
                with open(attachment_path, 'rb') as file:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')

                    msg.attach(part)
            finally:
                if os.path.exists(attachment_path):
                    os.remove(attachment_path)

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
        server.starttls()
        
        try:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        finally:
            server.quit()

        app.logger.info(f"Email sent successfully to {', '.join(receiver_emails)}")
        return True
    except Exception as e:
        app.logger.error(f"Error sending email: {str(e)}")
        raise

@app.route('/send_email', methods=['POST'])
def send_email_route():
    try:
        sender_email = request.form.get("sender_email")
        sender_password = request.form.get("sender_password")
        receiver_emails = [email.strip() for email in request.form.get("receiver_emails", "").split(",") if email.strip()]
        subject = request.form.get("subject", "No Subject")
        body = request.form.get("body", "No Body")
        
        if not all([sender_email, sender_password, receiver_emails]):
            return jsonify({
                "status": "error",
                "message": "Missing required fields"
            }), 400

        attachment = request.files.get('attachment')
        if attachment and attachment.filename:
            if not allowed_file(attachment.filename):
                return jsonify({
                    "status": "error",
                    "message": "Invalid file type"
                }), 400

        send_email(sender_email, sender_password, receiver_emails, subject, body, attachment)

        return jsonify({
            "status": "success",
            "message": "Email sent successfully"
        }), 200

    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred. Please try again later."
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

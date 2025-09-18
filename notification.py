from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mail import Mail, Message
import os

app = Flask(__name__)
CORS(app)

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] ="snehajain11105@gmail.com"
app.config['MAIL_PASSWORD'] = "gywy nzlh vvvn ueba"
app.config['MAIL_DEFAULT_SENDER'] = "snehajain11105@gmail.com"

mail = Mail(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']
    recipient_email = request.form.get('recipientEmail')

    if not file or not recipient_email:
        return jsonify({'message': 'Missing file or recipient email'}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    try:
        
        msg = Message(
            subject="You received a new document",
            recipients=[recipient_email]
        )
        msg.html = f"<p>Hello,</p><p>You have received a new document: {file.filename}</p>"
       
        with open(file_path, "rb") as f:
            msg.attach(file.filename, "application/octet-stream", f.read())

        mail.send(msg)
        return jsonify({'message': 'File uploaded and email sent successfully'}), 200
    except Exception as e:
        print(e)
        return jsonify({'message': 'Error sending email'}), 500

if __name__ == '__main__':
    app.run(port=5001, debug=True)


from flask import Flask
from routes.auth_routes import auth_bp
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'secret-key')

# this blueprint will help us to organise the routes properly
app.register_blueprint(auth_bp, url_prefix="/auth")

@app.route("/test")
def test():
    return {"message": "Backend is up and running!"}, 200


if __name__ == "__main__":
    app.run(debug=True)
from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime, requests
from functools import wraps
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///popcornpicks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# OMDb API Key
OMDB_API_KEY = "3c0768a3"
OMDB_URL = "http://www.omdbapi.com/"

# Initialize CORS for all routes
CORS(app)

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    favorites = db.relationship('Favorite', backref='user', lazy=True)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, nullable=False)
    movie_title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

movies = [
    {"id": 1, "title": "John Wick", "rating": 7.4, "description": "An ex-hitman..."},
    {"id": 2, "title": "Inception", "rating": 8.8, "description": "A thief who steals..."},
    {"id": 3, "title": "The Matrix", "rating": 8.7, "description": "A computer hacker..."}
]

# Utility functions
def create_token(user_id):
    payload = {'user_id': user_id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)}
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').split(" ")[-1]
        if not token:
            return jsonify({"message": "Token is missing!"}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            g.current_user = User.query.get(data['user_id'])
        except:
            return jsonify({"message": "Token is invalid or expired!"}), 401
        return f(*args, **kwargs)
    return decorated

# OMDb Search Endpoint
@app.route('/api/omdb_search', methods=['GET'])
def omdb_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({"message": "No query provided"}), 400
    
    response = requests.get(OMDB_URL, params={
        "apikey": OMDB_API_KEY,
        "s": query  # Searches for movies containing the query
    })
    
    data = response.json()
    if "Search" in data:
        return jsonify(data["Search"]), 200
    else:
        return jsonify({"message": "No results found"}), 404

# Get Trending Movies
@app.route('/api/movies', methods=['GET'])
def get_movies():
    return jsonify(movies), 200

# Get Movie Details
@app.route('/api/movies/<int:movie_id>', methods=['GET'])
def get_movie_details(movie_id):
    movie = next((m for m in movies if m["id"] == movie_id), None)
    return jsonify(movie if movie else {"message": "Movie not found"}), (200 if movie else 404)

# Search for Movies
@app.route('/api/search', methods=['GET'])
def search_movies():
    query = request.args.get('q', '').lower()
    results = [m for m in movies if query in m["title"].lower()]
    return jsonify(results if results else {"message": "No Results Found"}), (200 if results else 404)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database initialized successfully")
    app.run(debug=True)

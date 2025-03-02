from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime
from functools import wraps
from flask_cors import CORS  # <-- Add this import

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///popcornpicks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize CORS for all routes
CORS(app)  # <-- Enable CORS

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

# User Registration
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"message": "Email and password required"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "User already exists"}), 400

    try:
        new_user = User(
            email=data["email"],
            password_hash=generate_password_hash(data["password"])
        )
        db.session.add(new_user)
        db.session.commit()
        print(f"✅ User {data['email']} registered successfully")
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error registering user: {e}")
        return jsonify({"message": "Database error"}), 500

# User Login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data["email"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"message": "Invalid credentials"}), 401
    return jsonify({"token": create_token(user.id)}), 200

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

# Manage Favorite Movies
@app.route('/api/favorites', methods=['GET'])
@token_required
def get_favorites():
    user = g.current_user
    favorites_list = [{"movie_id": f.movie_id, "movie_title": f.movie_title} for f in Favorite.query.filter_by(user_id=user.id).all()]
    return jsonify(favorites_list), 200

@app.route('/api/favorites', methods=['POST'])
@token_required
def add_favorite():
    data = request.get_json()
    user = g.current_user
    if Favorite.query.filter_by(user_id=user.id, movie_id=data["movie_id"]).first():
        return jsonify({"message": "Movie already in favorites"}), 400
    db.session.add(Favorite(movie_id=data["movie_id"], movie_title=data["movie_title"], user_id=user.id))
    db.session.commit()
    return jsonify({"message": "Movie added to favorites"}), 201

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database initialized successfully")
    app.run(debug=True)

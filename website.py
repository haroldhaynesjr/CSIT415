from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///popcornpicks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# Dummy movie data (simulate API integration)
movies = [
    {
       "id": 1,
       "title": "John Wick",
       "rating": 7.4,
       "description": "An ex-hitman comes out of retirement to track down the gangsters that killed his dog."
    },
    {
       "id": 2,
       "title": "Inception",
       "rating": 8.8,
       "description": "A thief who steals corporate secrets through the use of dream-sharing technology."
    },
    {
       "id": 3,
       "title": "The Matrix",
       "rating": 8.7,
       "description": "A computer hacker learns about the true nature of his reality and his role in the war against its controllers."
    }
]

# Utility functions for JWT creation and verification
def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # JWT token is expected in the Authorization header
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[-1]
        if not token:
            return jsonify({"message": "Token is missing!"}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({"message": "User not found!"}), 401
            g.current_user = current_user
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token expired!"}), 401
        except Exception as e:
            return jsonify({"message": "Token is invalid!"}), 401
        return f(*args, **kwargs)
    return decorated

# Routes for User Registration and Login
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"message": "Email and password required"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"message": "User already exists"}), 400

    new_user = User(
        email=data["email"],
        password_hash=generate_password_hash(data["password"])
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"message": "Email and password required"}), 400

    user = User.query.filter_by(email=data["email"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        return jsonify({"message": "Invalid credentials"}), 401

    token = create_token(user.id)
    return jsonify({"token": token}), 200

# Endpoint to fetch trending/popular movies (simulated)
@app.route('/api/movies', methods=['GET'])
def get_movies():
    # In a real-world scenario, you might call an external API here.
    return jsonify(movies), 200

# Endpoint to fetch movie details by movie ID
@app.route('/api/movies/<int:movie_id>', methods=['GET'])
def get_movie_details(movie_id):
    movie = next((m for m in movies if m["id"] == movie_id), None)
    if movie:
        return jsonify(movie), 200
    return jsonify({"message": "Movie not found"}), 404

# Search functionality for movies by title
@app.route('/api/search', methods=['GET'])
def search_movies():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({"message": "No query provided"}), 400
    results = [m for m in movies if query in m["title"].lower()]
    if results:
        return jsonify(results), 200
    else:
        return jsonify({"message": "No Results Found"}), 404

# Endpoints to manage favorite movies for a user (requires authentication)
@app.route('/api/favorites', methods=['GET'])
@token_required
def get_favorites():
    user = g.current_user
    favs = Favorite.query.filter_by(user_id=user.id).all()
    favorites_list = [{"movie_id": f.movie_id, "movie_title": f.movie_title} for f in favs]
    return jsonify(favorites_list), 200

@app.route('/api/favorites', methods=['POST'])
@token_required
def add_favorite():
    data = request.get_json()
    if not data or not data.get("movie_id") or not data.get("movie_title"):
        return jsonify({"message": "Movie ID and title required"}), 400
    user = g.current_user
    # Check if the favorite already exists for this user
    if Favorite.query.filter_by(user_id=user.id, movie_id=data["movie_id"]).first():
        return jsonify({"message": "Movie already in favorites"}), 400

    new_fav = Favorite(
        movie_id=data["movie_id"],
        movie_title=data["movie_title"],
        user_id=user.id
    )
    db.session.add(new_fav)
    db.session.commit()
    return jsonify({"message": "Movie added to favorites"}), 201

# Basic navigation and error handling could be expanded on in a full application.
# For now, these endpoints cover registration, login, movie search, details, and favorites management.

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they do not exist
    app.run(debug=True)

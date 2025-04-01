from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime, requests, os
from functools import wraps
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///popcornpicks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# OMDb API Key and URL
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
        except Exception as e:
            return jsonify({"message": "Token is invalid or expired!"}), 401
        return f(*args, **kwargs)
    return decorated

def fetch_omdb_data(title):
    """Fetch movie details from the OMDb API by title."""
    url = f"{OMDB_URL}?apikey={OMDB_API_KEY}&t={title}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                return data
            else:
                print(f"OMDb API error: {data.get('Error')}")
        else:
            print(f"Error fetching OMDb data: {response.status_code}")
    except Exception as e:
        print(f"Exception during OMDb API call: {e}")
    return None

# User Registration Endpoint
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"message": "Email and password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already exists"}), 400
    password_hash = generate_password_hash(password)
    new_user = User(email=email, password_hash=password_hash)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

# User Login Endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"message": "Invalid credentials"}), 401
    token = create_token(user.id)
    return jsonify({"token": token}), 200

# OMDb Search Endpoint
@app.route('/api/omdb_search', methods=['GET'])
def omdb_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({"message": "No query provided"}), 400

    # First: fetch a list of search results
    response = requests.get(OMDB_URL, params={
        "apikey": OMDB_API_KEY,
        "s": query  # e.g. "The Matrix"
    })
    data = response.json()

    # If OMDb returned results under "Search"
    if "Search" in data:
        results = []
        for item in data["Search"]:
            imdb_id = item.get("imdbID")
            if not imdb_id:
                continue

            # Second: fetch full details for each imdbID
            detail_res = requests.get(OMDB_URL, params={
                "apikey": OMDB_API_KEY,
                "i": imdb_id  # e.g. "tt0133093"
            })
            detail_data = detail_res.json()

            # Only add items with a valid response
            if detail_data.get("Response") == "True":
                mapped_item = {
                    "id": imdb_id,
                    "title": detail_data.get("Title"),
                    "year": detail_data.get("Year"),
                    "poster": detail_data.get("Poster"),
                    "rating": detail_data.get("imdbRating"),
                    "genre": detail_data.get("Genre"),
                    "plot": detail_data.get("Plot")
                }
                results.append(mapped_item)

        if not results:
            return jsonify({"message": "No detailed results found"}), 404

        return jsonify(results), 200

    else:
        return jsonify({"message": "No results found"}), 404

# Get Trending Movies
@app.route('/api/movies', methods=['GET'])
def get_movies():
    return jsonify(movies), 200

# Get Movie Details (single route)
@app.route('/api/movies/<int:movie_id>', methods=['GET'])
def get_movie_details(movie_id):
    movie = next((m for m in movies if m["id"] == movie_id), None)
    if movie:
        omdb_data = fetch_omdb_data(movie["title"])
        if omdb_data:
            movie.update({
                "poster": omdb_data.get("Poster", ""),
                "plot": omdb_data.get("Plot", ""),
                "year": omdb_data.get("Year", ""),
                "genre": omdb_data.get("Genre", "")
            })
        return jsonify(movie), 200
    return jsonify({"message": "Movie not found"}), 404

# Search for Movies
@app.route('/api/search', methods=['GET'])
def search_movies():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({"message": "No query provided"}), 400

    # Filter the dummy movie data based on the search query
    basic_results = [m for m in movies if query in m["title"].lower()]
    detailed_results = []

    for movie in basic_results:
        omdb_data = fetch_omdb_data(movie["title"])
        if omdb_data:
            movie.update({
                "poster": omdb_data.get("Poster", ""),
                "plot": omdb_data.get("Plot", ""),
                "year": omdb_data.get("Year", ""),
                "genre": omdb_data.get("Genre", "")
            })
        detailed_results.append(movie)

    if detailed_results:
        return jsonify(detailed_results), 200
    else:
        return jsonify({"message": "No Results Found"}), 404

# Add Favorite Movie Endpoint
@app.route('/api/favorites', methods=['POST'])
@token_required
def add_favorite():
    data = request.get_json()
    movie_id = data.get("movie_id")
    movie_title = data.get("movie_title")
    if not movie_id or not movie_title:
        return jsonify({"message": "Missing movie information"}), 400

    # Check if the movie is already in favorites for this user
    existing = Favorite.query.filter_by(user_id=g.current_user.id, movie_id=movie_id).first()
    if existing:
        return jsonify({"message": "Movie already in favorites"}), 400

    favorite = Favorite(movie_id=movie_id, movie_title=movie_title, user_id=g.current_user.id)
    db.session.add(favorite)
    db.session.commit()
    return jsonify({"message": "Movie added to favorites"}), 

# Get Favorite Movies for the current user
@app.route('/api/favorites', methods=['GET'])
@token_required
def get_favorites():
    favorites = g.current_user.favorites
    favorite_movies = []
    for fav in favorites:
        omdb_data = fetch_omdb_data(fav.movie_title)
        movie = {
            "movie_id": fav.movie_id,
            "movie_title": fav.movie_title,
            "poster": omdb_data.get("Poster") if omdb_data else "",
            "plot": omdb_data.get("Plot") if omdb_data else "",
            "year": omdb_data.get("Year") if omdb_data else "",
            "genre": omdb_data.get("Genre") if omdb_data else ""
        }
        favorite_movies.append(movie)
    return jsonify(favorite_movies), 200


# personalized recommendations endpoint (basic placeholder, will be refined)
@app.route('/api/recommendations', methods=['GET'])
@token_required
def get_recommendations():
    # retrieve user's favorite movies from the database
    favorites = g.current_user.favorites
    if not favorites:
        return jsonify({
            "message": "No favorites found; returning trending movies as a fallback.",
            "recommendations": movies
        }), 200

    # create dictionary for genres in favorites
    genre_freq = {}
    for fav in favorites:
        omdb_data = fetch_omdb_data(fav.movie_title)
        if omdb_data and omdb_data.get("Genre"):
            # MUST CHANGE THIS PART IF GENRE FORMATTING FAILS.
            genres = [genre.strip() for genre in omdb_data.get("Genre").split(",")]
            for genre in genres:
                genre_freq[genre] = genre_freq.get(genre, 0) + 1

    if not genre_freq:
        return jsonify({
            "message": "Could not retrieve genre data from favorites; returning trending movies.",
            "recommendations": movies
        }), 200

    # Determine the most frequent genre from the favorites
    most_freq_genre = max(genre_freq, key=genre_freq.get)

    # Look through the trending movies and pick those that match the most frequent genre
    recommendations = []
    for movie in movies:
        omdb_data = fetch_omdb_data(movie["title"])
        if omdb_data and omdb_data.get("Genre"):
            movie_genres = [g.strip() for g in omdb_data.get("Genre").split(",")]
            if most_freq_genre in movie_genres:
                movie.update({
                    "poster": omdb_data.get("Poster", ""),
                    "plot": omdb_data.get("Plot", ""),
                    "year": omdb_data.get("Year", ""),
                    "genre": omdb_data.get("Genre", "")
                })
                recommendations.append(movie)

    if not recommendations:
        return jsonify({
            "message": "No matching recommendations found; returning trending movies.",
            "recommendations": movies
        }), 200

    return jsonify({
        "message": "Recommendations based on your favorites.",
        "recommendations": recommendations
    }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database initialized successfully")
    app.run(debug=True)

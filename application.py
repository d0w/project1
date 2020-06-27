import os
import pdb
import json

from helpers import get_goodreads

from werkzeug.security import check_password_hash, generate_password_hash

from flask import Flask, session, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    if session.get("logged_in"):
        return render_template("userPage.html", username=session["user_name"])
    return render_template("homepage.html")


@app.route("/login", methods=["POST", "GET"])
def login():

    #clearing session
    session.clear()


    if request.method == "GET":
        return render_template("error.html", message="Not Logged In")
    else:
        username = request.form.get("username")
        password = request.form.get("pass")

        #fetching username
        result = db.execute("SELECT * FROM users WHERE username = :username", 
                            {"username": username}).fetchone()

        #checks to see if result is equal none or not a password hash binded to account
        if result == None or not check_password_hash(result[2], password):
            return render_template ("error.html", message="Invalid User/Pass")
        else:
            session["user_name"] = username
            session["logged_in"] = True
            return render_template("userPage.html", user=username)


@app.route("/logout")
def logout():
    session["user_name"] = None
    session["logged_in"] = False
    session.clear()
    return render_template("homepage.html")


@app.route("/search", methods=["GET"])
def searchCheck():
    if session.get("logged_in"):
        return render_template("search.html")
    else:
        return render_template("error.html", message="Error: Not logged in")


@app.route("/search", methods=["POST"])
def search():

    searchQ = request.form.get("search") 

    if len(searchQ) == 0:
        return render_template("error.html", message="Error: Must input a search query")

    books = db.execute("SELECT * FROM books WHERE (title LIKE :searchQ) OR (author LIKE :searchQ) OR (isbn LIKE :searchQ)", 
                {"searchQ": "%" + searchQ + "%"}).fetchall()

    if books is not None:
        return render_template("search.html", books=books)
    


@app.route("/book/<int:book_id>", methods=["GET", "POST"])
def book(book_id):

    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()

    goodreads = get_goodreads(book.isbn)

    if goodreads.status_code != 200:
        return render_template("error.html", message="404 Error")

    books = goodreads.json()
    bookRating = books["books"][0]["average_rating"]


    reviews = db.execute("SELECT * FROM reviews LEFT JOIN public.users ON (reviews.user_id = users.id) WHERE bookid = :id",
                        {"id": book_id}).fetchall()

    return render_template("book.html", book=book, bookRating = bookRating, reviews=reviews)


@app.route("/review/<int:book_id>", methods=["POST"])
def review(book_id):
    stars = request.form.get("stars")
    review = request.form.get("review")
    username = session["user_name"]

    users = db.execute("SELECT username, id FROM users WHERE username = :username", {"username": username}).fetchone()

    if (db.execute("SELECT * FROM reviews LEFT JOIN public.users ON (reviews.user_id = users.id) WHERE bookid = :id AND users.username = :username",
                {"id": book_id, "username": username}).rowcount > 0):
        return render_template("error.html", message="Review already exists")
    else:
        db.execute("INSERT INTO reviews (bookid, user_id, username, stars, review) VALUES (:bookid, :user_id, :username, :stars, :review)", {"bookid": book_id, "user_id": users.id, "username": username, "stars": stars, "review": review})
        db.commit()

        return redirect(url_for("book", book_id=book_id))



@app.route("/createaccount", methods=["POST"])
def createaccount():
    return render_template("accountcreate.html")

@app.route("/register", methods=["POST", "GET"])
def register():

    session.clear()

    if request.method == "GET":
        return render_template("homepage.html")

    if request.method == "POST":
        user = request.form.get("username")
        password = request.form.get("pass")
        name = request.form.get("name")
        
        userTry = db.execute("SELECT * FROM users WHERE username = :username", {"username": user}).fetchone()
        if userTry != None:
            return render_template("error.html", message="Error: Username Already Taken")
    
        else:
            hashedPassword = generate_password_hash(request.form.get("pass"), method="pbkdf2:sha256", salt_length=8)

            db.execute("INSERT INTO users (username, pass, usersname) VALUES (:username, :pass, :usersName)", {"username":user, "pass": hashedPassword,"usersName": name})
            db.commit()
    return render_template("accountcreated.html")


@app.route("/api/<isbn_id>", methods=["GET"])
def api(isbn_id):
    book_api = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn_id}).fetchone()

    if book_api is None:
        goodreads = get_goodreads(isbn_id)
        if goodreads.status_code !=200:
            return render_template("error.html", message="404 Error")
        else:
            book_api = goodreads.json()
            return book_api
    else:
        book_reviews = db.execute("SELECT COUNT(ID), AVG(stars) FROM reviews WHERE bookid = :bookid",
                    {"bookid": book_api.id})


    response = {}
    response["title"] = book_api.title
    response["author"] = book_api.author
    response["year"] = book_api.year
    response["isbn"] = book_api.isbn

    try:
        response["review_count"] = str(book_reviews[0])
        response["average_score"] = book_reviews[1]
    except:
        response["review_count"] = "No reviews"
        response["average_score"] = "No reviews"

    jsonResponse = json.dumps(response)

    return jsonResponse, 200





from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import hashlib
import time
from pymongo import MongoClient
from urllib.parse import quote_plus  # for encoding password

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ----------------- Blockchain logic -----------------
class Block:
    def __init__(self, voter_id, party, previous_hash, timestamp=None, block_hash=None):
        self.timestamp = timestamp if timestamp else time.time()
        self.voter_hash = hashlib.sha256(voter_id.encode()).hexdigest() if voter_id else None
        self.party = party
        self.previous_hash = previous_hash
        self.hash = block_hash if block_hash else self.compute_hash()

    def compute_hash(self):
        block_string = f"{self.timestamp}{self.voter_hash}{self.party}{self.previous_hash}"
        return hashlib.sha256(block_string.encode()).hexdigest()


class Blockchain:
    def __init__(self):
        self.chain = []

    def add_vote(self, voter_id, party):
        previous_hash = self.chain[-1].hash if self.chain else "0"
        block = Block(voter_id, party, previous_hash)
        self.chain.append(block)
        return block

# Initialize blockchain
blockchain = Blockchain()

# ----------------- MongoDB Atlas Setup -----------------
username = "voterAdmin"
password = "@Khushi08"  # your password
encoded_password = quote_plus(password)  # encode special characters

MONGO_URI = f"mongodb+srv://{username}:{encoded_password}@cluster0.gpet2lf.mongodb.net/VotingDB?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client['VotingDB']
votes_collection = db['votes']  # collection for vote blocks

# ----------------- Local storage -----------------
users = {}  # voter_id -> {name, password_hash, voted?}
votes = {"BJP":0, "Congress":0, "Gen-Z":0, "Samajvaadi":0}

# ----------------- Load existing votes & blockchain from MongoDB -----------------
def load_votes_from_db():
    global votes
    votes = {"BJP":0, "Congress":0, "Gen-Z":0, "Samajvaadi":0}
    for block_data in votes_collection.find():
        party = block_data.get("party")
        if party in votes:
            votes[party] += 1

def load_blockchain_from_db():
    global blockchain
    blockchain = Blockchain()
    for block_data in votes_collection.find().sort("_id", 1):  # keep order
        block = Block(
            voter_id=None,  # hashed voter_id already in DB
            party=block_data["party"],
            previous_hash=block_data["previous_hash"],
            timestamp=block_data["timestamp"],
            block_hash=block_data["hash"]
        )
        blockchain.chain.append(block)

# Load votes & blockchain at startup
load_votes_from_db()
load_blockchain_from_db()

# ----------------- Routes -----------------
@app.route("/")
def home():
    return redirect(url_for("register"))

# Registration page
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        voter_id = request.form["voter_id"]
        password = request.form["password"]

        # Check if voter already registered
        if voter_id in users:
            return "Voter ID already registered!"

        # Hash password
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # Save voter locally
        users[voter_id] = {"name": name, "password_hash": password_hash, "voted": False}

        # Store voter_id in session
        session["voter_id"] = voter_id

        # Redirect to vote page
        return redirect(url_for("vote"))

    return render_template("register.html")

# Voting page
@app.route("/vote", methods=["GET", "POST"])
def vote():
    voter_id = session.get("voter_id")
    if not voter_id or voter_id not in users:
        return redirect(url_for("register"))

    voter = users[voter_id]

    # Check if voter already voted
    if voter["voted"]:
        if request.method == "POST":
            return jsonify({"status": "error", "message": "You have already voted!"})
        return f"You have already voted! Current votes: {votes}"

    if request.method == "POST":
        choice = request.form.get("party")
        if choice in votes:
            votes[choice] += 1
            users[voter_id]["voted"] = True

            # Add vote to blockchain
            block = blockchain.add_vote(voter_id, choice)

            # Save vote block to MongoDB
            votes_collection.insert_one({
                "timestamp": block.timestamp,
                "voter_hash": block.voter_hash,
                "party": block.party,
                "previous_hash": block.previous_hash,
                "hash": block.hash
            })

            return jsonify({
                "status": "success",
                "message": f"✅ You voted for {choice}!",
                "current_votes": votes,
                "block_hash": block.hash
            })
        else:
            return jsonify({"status": "error", "message": "Invalid party choice!"})

    return render_template("vote.html")


if __name__ == "__main__":
    app.run()
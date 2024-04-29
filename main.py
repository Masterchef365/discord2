import sqlite3
import aiosqlite
from quart import Quart, render_template, websocket, g

app = Quart(__name__)

DATABASE = 'chat.db'

# #################### Setup #################### 

async def setup_db(db):
    await db.execute(
'''CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY,
    name TEXT
)''')
    await db.commit()

    await db.execute(
'''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    room_id INTEGER,
    message TEXT,
    date INTEGER,
    user TEXT,
    FOREIGN KEY (room_id) REFERENCES rooms(id)
)''')
    await db.commit()

    print("Setup DB")


# #################### Database in g object ####################

async def get_db():
    """Get the database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = await aiosqlite.connect(DATABASE)
        await setup_db(db)
    return db


@app.teardown_appcontext
async def close_connection(exception):
    """Closes database connection"""
    db = getattr(g, '_database', None)
    if db is not None:
        await db.close()

# #################### HTTP Endpoints #################### 

@app.route("/")
async def index():
    """Main page!"""
    await get_db()
    return await render_template("index.html")


@app.post("/create_room")
async def create_room():
    """Creates a new room"""
    db = get_db()
    cur = db.cursor()
    await cur.close()

    return await index()


if __name__ == "__main__":
    app.run(debug=True)

import sqlite3
import aiosqlite
from quart import Quart, render_template, websocket, g, request

app = Quart(__name__)

DATABASE = 'chat.db'

# #################### Setup #################### 

async def setup_db(db):
    await db.execute(
'''CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY,
    name TEXT
)''')

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


# #################### Database operations ####################
async def get_rooms():
    db = await get_db()
    async with db.execute('SELECT name, id FROM rooms') as cursor:
        return [row async for row in cursor]


# #################### Database in g object ####################

async def get_db() -> aiosqlite.Connection:
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
    rooms = await get_rooms()

    links = [{'name': name, 'url': f'/rooms/{id_}'} for (name, id_, ) in rooms]

    return await render_template('index.html', links=links)


@app.post("/create_room")
async def create_room():
    """Creates a new room"""
    data = await request.get_data()
    db = await get_db()

    _, new_room_name = data.decode('ascii').split('=')
    await db.execute("INSERT INTO rooms (name) VALUES (?)", (new_room_name,))
    await db.commit()

    return await index()


if __name__ == "__main__":
    app.run(debug=True)

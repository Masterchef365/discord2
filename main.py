import asyncio
import sqlite3
import aiosqlite
import random
import time
import sys
from quart import Quart, render_template, websocket, g, request, redirect, url_for

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


async def get_room_name(room_id):
    db = await get_db()
    async with db.execute("SELECT name FROM rooms WHERE id=?", (room_id,)) as cur:
        async for (name, ) in cur:
            return name

    return None


async def get_recent_messages(room_id):
    db = await get_db()
    query = "SELECT user, message, date FROM messages WHERE room_id=? ORDER BY date"
    async with db.execute(query, (room_id,)) as cur:
        return [row async for row in cur]


async def get_any_recent_messages(max_msgs):
    db = await get_db()
    query = """
    SELECT 
        user, message, date, room_id, rooms.name
    FROM messages 
    INNER JOIN rooms ON rooms.id = messages.room_id
    ORDER BY date DESC LIMIT ?"""

    async with db.execute(query, (max_msgs,)) as cur:
        return [row async for row in cur]


async def add_msg_to_db(room_id, username, message):
    db = await get_db()
    date = int(time.time())

    query = "INSERT INTO messages (room_id, user, message, date) VALUES (?, ?, ?, ?)"

    await db.execute(query, (room_id, username, message, date,))
    await db.commit()

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

# #################### Pages #################### 
def fmt_message_template(msgs):
    return [{'user': user, 'message': message} for (user, message, _date) in msgs]


@app.route("/")
async def index():
    """Main page!"""
    rooms = await get_rooms()

    links = [{'name': name, 'url': f'/rooms/{room_id}'} for (name, room_id, ) in rooms]

    recent_messages = await get_any_recent_messages(10)
    recent_messages = [
        {'user': user, 'room_id': room_id, 'room_name': room_name, 'message': message} 
        for (user, message, _date, room_id, room_name) in recent_messages
    ]

    return await render_template('index.html', links=links, recent_messages=recent_messages)


@app.route('/rooms/<room_id>/')
async def room(room_id):
    """Room page accessible to user"""
    # Determine which room we are in
    db = await get_db()
    room_name = await get_room_name(room_id)

    if room_name is None:
        return redirect('/')

    # Get recent messages
    recent_messages = await get_recent_messages(room_id)
    recent_messages = fmt_message_template(recent_messages)

    # Send user initial page
    return await render_template(
        'room.html', 
        room_name=room_name, 
        room_id=room_id, 
        recent_messages=recent_messages
    )


@app.get("/punishment")
async def punishment():
    """Punishment page inflicted upon the user"""
    return await render_template('punishment.html')


# #################### message handling internals #################### 
class RoomBroker:
    def __init__(self):
        self.connections = set()

    async def publish(self, message: str):
        for connection in self.connections:
            await connection.put(message)

    async def subscribe(self):
        connection = asyncio.Queue()
        self.connections.add(connection)
        try:
            while True:
                yield await connection.get()
        finally:
            self.connections.remove(connection)


class ServerBroker:
    def __init__(self):
        self.rooms = {}

    def _get_room(self, room_id: int) -> RoomBroker:
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomBroker()
        return self.rooms[room_id]

    def publish(self, room_id: int, message: str):
        return self._get_room(room_id).publish(message)

    def subscribe(self, room_id: int):
        return self._get_room(room_id).subscribe()


def message_magic(message: str):
    if message.startswith('http'):
        if message.endswith(('png', 'gif', 'jpg', 'jpeg', 'webp', 'svg')):
            # Image
            message = f"<img src={message}>"
        else:
            # Link
            message = f"<a href={message}>{message}</a>"


    return message


broker = ServerBroker()

# #################### internal API surface #################### 

@app.post("/create_room")
async def create_room():
    """Creates a new room"""
    data = await request.form
    db = await get_db()

    new_room_name = data["name"]

    if new_room_name.isspace() or new_room_name == "":
        return redirect('/punishment')

    await db.execute("INSERT INTO rooms (name) VALUES (?)", (new_room_name,))
    await db.commit()

    return redirect('/')


@app.post("/rooms/<room_id>/send")
async def send_message(room_id):
    """Endpoint which broadcasts a message to other clients"""
    data = await request.form
    username = data["username"]
    message = data["message"]

    message = message_magic(message)

    # Add the message to history
    await add_msg_to_db(room_id, username, message)

    # Publish the message for real-time
    await broker.publish(room_id, f"{username}: {message}")

    return "", 200


async def _receive() -> None:
    """This never actually receives anything, it's just used to cancel the websocket properly."""
    while True:
        message = await websocket.receive()


@app.websocket("/rooms/<room_id>/ws")
async def ws(room_id) -> None:
    print("Open WS")
    try:
        task = asyncio.ensure_future(_receive())
        async for message in broker.subscribe(room_id):
            await websocket.send(message)
    except asyncio.CancelledError:
        print("Handled disconnection")
        raise
    finally:
        print("Close WS")
        task.cancel()
        await task


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app.run(debug=True)
    else:
        app.run(port=80, host='0.0.0.0')

import sqlite3
import aiosqlite
from quart import Quart, render_template, websocket, g

app = Quart(__name__)

DATABASE = 'chat.db'

async def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = await aiosqlite.connect(DATABASE)
    return db


@app.teardown_appcontext
async def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        await db.close()


@app.route("/")
async def index():
    await get_db()
    return await render_template("index.html")


@app.post("/create_room")
async def create_room():
    print("Create room")
    return await index()


if __name__ == "__main__":
    app.run(debug=True)

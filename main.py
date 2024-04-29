from quart import Quart, render_template, websocket

app = Quart(__name__)

@app.route("/")
async def hello():
    return await render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)

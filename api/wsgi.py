from index import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

# Vercel expects a WSGI application object named 'application'
application = app

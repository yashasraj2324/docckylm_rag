import os
import sys

# Add api directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app
from index import app

# This is the entry point that Vercel will use
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

# Vercel expects a WSGI application object named 'application'
application = app

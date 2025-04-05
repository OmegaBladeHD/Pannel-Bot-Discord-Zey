"""
StreamNotify+ Web Server
This is a Flask web server for the bot with a dashboard interface.
"""
import os
import logging
import threading
import datetime
from flask import Flask, jsonify, render_template, redirect, url_for
import app as bot_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Track server start time for uptime calculation
start_time = datetime.datetime.now()

def get_uptime():
    """Calculate uptime since server start"""
    now = datetime.datetime.now()
    delta = now - start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}j {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def check_api_status():
    """Check if API keys are configured"""
    return {
        "twitch": bool(os.getenv("TWITCH_CLIENT_ID") and os.getenv("TWITCH_CLIENT_SECRET")),
        "youtube": bool(os.getenv("YOUTUBE_API_KEY")),
        "tiktok": bool(os.getenv("TIKTOK_API_KEY"))
    }

@app.route('/')
def index():
    """Render the dashboard homepage"""
    api_status = check_api_status()
    return render_template('index.html', 
                           uptime=get_uptime(),
                           twitch_enabled=api_status["twitch"],
                           youtube_enabled=api_status["youtube"],
                           tiktok_enabled=api_status["tiktok"])

@app.route('/api')
def api():
    """Return a simple JSON response indicating the bot is running"""
    return jsonify({"message": "Le bot a démarré avec succès."})

# La route dashboard a été supprimée car elle n'est plus nécessaire

@app.route('/status')
def status():
    """Display status page"""
    api_status = check_api_status()
    return render_template('status.html',
                          uptime=get_uptime(),
                          discord_enabled=bool(os.getenv("DISCORD_TOKEN")),
                          twitch_enabled=api_status["twitch"],
                          youtube_enabled=api_status["youtube"],
                          tiktok_enabled=api_status["tiktok"])

@app.route('/health')
def health():
    """Health check endpoint for monitoring services"""
    api_status = check_api_status()
    return jsonify({
        "status": "online",
        "uptime": get_uptime(),
        "version": "1.0.0",
        "services": {
            "web": True,
            "discord": bool(os.getenv("DISCORD_TOKEN")),
            "twitch": api_status["twitch"],
            "youtube": api_status["youtube"],
            "tiktok": api_status["tiktok"]
        }
    })

def run_flask_app():
    """Run the Flask app directly (for development)"""
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting web server on port {port}")
    app.run(host="0.0.0.0", port=port)

async def start_web_server():
    """Start the Flask web server in a separate thread"""
    try:
        # Start Flask app in a separate thread
        thread = threading.Thread(target=run_flask_app)
        thread.daemon = True
        thread.start()
        logger.info("Web server started in background thread")
    except Exception as e:
        logger.error(f"Failed to start web server: {str(e)}")
        raise

"""
StreamNotify+ Main Module
This script launches both the Discord bot and the web server for uptime monitoring.
"""
import asyncio
import os
import logging
import threading
from app import bot_start
from web import app, start_web_server

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Export the Flask app for gunicorn
# This is used by the gunicorn command in the workflow configuration
# gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app

# Create data directory if it doesn't exist
if not os.path.exists("data"):
    os.makedirs("data")
    logger.info("Created data directory")

# Start the Discord bot in a background thread when this module is imported
def start_bot_thread():
    """Start the Discord bot in a background thread"""
    asyncio.run(bot_start())

# Only start the bot if this script is run directly (not imported by gunicorn)
if __name__ == "__main__":
    try:
        # Create thread for bot
        bot_thread = threading.Thread(target=start_bot_thread)
        bot_thread.daemon = True
        bot_thread.start()
        
        # Run the Flask app directly for development
        logger.info("Starting Flask app")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application crashed: {str(e)}")

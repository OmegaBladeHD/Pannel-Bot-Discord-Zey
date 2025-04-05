"""
StreamNotify+ Discord Bot
This module contains the Discord bot functionality for notifications, XP, economy, and moderation.
"""
import os
import json
import random
import asyncio
import logging
import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIG = {
    "tiktok": {
        "tayomi_20": {
            "enabled": True,
            "message": "{user} a posté un TikTok ! {link}",
            "channel_id": None,
            "ping": ""
        },
        "1gars.random": {
            "enabled": True,
            "message": "{user} a posté un TikTok ! {link}",
            "channel_id": None,
            "ping": ""
        }
    },
    "youtube": {
        "zeyphir_officiel": {
            "enabled": True,
            "message": "{user} vient de sortir une nouvelle vidéo YouTube ! {link}",
            "channel_id": None,
            "ping": ""
        }
    },
    "twitch": {
        "zayphir_": {
            "enabled": True,
            "message": "{user} est en live sur {game} ! Rejoins ici : {link}",
            "channel_id": None,
            "ping": ""
        },
        "tayomi20": {
            "enabled": True,
            "message": "{user} est en live sur {game} ! Rejoins ici : {link}",
            "channel_id": None,
            "ping": ""
        }
    }
}

DEFAULT_USERS = {}

CONFIG_PATH = "data/config.json"
USERS_PATH = "data/users.json"

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# API trackers
tiktok_cache = {}
youtube_cache = {}
twitch_cache = {}

# Helper functions
def load_config():
    """Load the configuration from config.json"""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return DEFAULT_CONFIG

def save_config(config):
    """Save the configuration to config.json"""
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")

def load_users():
    """Load the users data from users.json"""
    try:
        if os.path.exists(USERS_PATH):
            with open(USERS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(USERS_PATH, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_USERS, f, indent=2)
            return DEFAULT_USERS
    except Exception as e:
        logger.error(f"Error loading users: {str(e)}")
        return DEFAULT_USERS

def save_users(users):
    """Save the users data to users.json"""
    try:
        with open(USERS_PATH, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {str(e)}")

def get_platform_example(platform):
    """Return an example username for each platform"""
    examples = {
        "twitch": "pokimane",
        "youtube": "MrBeast",
        "tiktok": "charlidamelio"
    }
    return examples.get(platform, "username")

def get_platform_placeholder(platform):
    """Return placeholder text for each platform's notification message"""
    placeholders = {
        "twitch": "Utilisez {user} pour le nom, {game} pour le jeu, {title} pour le titre et {link} pour le lien",
        "youtube": "Utilisez {user} pour le nom, {title} pour le titre et {link} pour le lien",
        "tiktok": "Utilisez {user} pour le nom et {link} pour le lien"
    }
    return placeholders.get(platform, "Message de notification personnalisé")

def get_platform_default_message(platform):
    """Return default notification message for each platform"""
    defaults = {
        "twitch": "{user} est en live sur {game} ! Titre: {title}\n{link}",
        "youtube": "{user} vient de sortir une nouvelle vidéo YouTube : {title}\n{link}",
        "tiktok": "{user} a posté un nouveau TikTok !\n{link}"
    }
    return defaults.get(platform, "{user} a posté du nouveau contenu! {link}")

def get_platform_color(platform):
    """Return color for each platform's embeds"""
    colors = {
        "twitch": 0x9146FF,  # Purple
        "youtube": 0xFF0000,  # Red
        "tiktok": 0x000000,   # Black
    }
    return colors.get(platform, 0x3498db)  # Default blue
    
def get_platform_emoji(platform):
    """Return emoji for each platform"""
    emojis = {
        "twitch": "💜",
        "youtube": "📺",
        "tiktok": "📱",
    }
    return emojis.get(platform, "🔔")

def get_user_data(user_id):
    """Get user data or create if not exists"""
    users = load_users()
    user_id = str(user_id)
    
    if user_id not in users:
        users[user_id] = {
            "xp": 0,
            "level": 1,
            "balance": 0,
            "daily_last": None
        }
        save_users(users)
    
    return users[user_id]

def update_user_data(user_id, data):
    """Update a specific user's data"""
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

def calculate_level(xp):
    """Calculate level based on XP"""
    return int(xp / 100) + 1

def calculate_xp_for_level(level):
    """Calculate XP required for a specific level"""
    return (level - 1) * 100

def add_xp(user_id, amount):
    """Add XP to a user and check for level up"""
    user_data = get_user_data(user_id)
    old_level = user_data["level"]
    
    user_data["xp"] += amount
    new_level = calculate_level(user_data["xp"])
    user_data["level"] = new_level
    
    update_user_data(user_id, user_data)
    
    return new_level > old_level

@bot.event
async def on_ready():
    """Run when the bot is ready"""
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    
    # Start background tasks
    check_twitch_streams.start()
    check_youtube_videos.start()
    check_tiktok_videos.start()
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message):
    """Handle messages for XP system"""
    if message.author.bot:
        return

    # Process commands first
    await bot.process_commands(message)
    
    # Then handle XP
    user_id = str(message.author.id)
    
    # Give random XP between 5-15 for each message
    xp_gain = random.randint(5, 15)
    level_up = add_xp(user_id, xp_gain)
    
    # Send level up message if applicable
    if level_up:
        user_data = get_user_data(user_id)
        await message.channel.send(f"🎉 Félicitations {message.author.mention} ! Tu as atteint le niveau {user_data['level']} !")

# Notification system tasks
@tasks.loop(minutes=5)
async def check_twitch_streams():
    """Check for new Twitch streams"""
    global twitch_cache
    config = load_config()
    
    if "twitch" not in config:
        return
    
    twitch_config = config["twitch"]
    
    # Skip if no enabled streamers or no channels configured
    if not any(streamer["enabled"] and streamer["channel_id"] for streamer in twitch_config.values()):
        return

    twitch_api_client_id = os.getenv("TWITCH_CLIENT_ID")
    twitch_api_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    
    if not twitch_api_client_id or not twitch_api_client_secret:
        logger.warning("Twitch API credentials not found in environment variables")
        return
    
    try:
        # Get OAuth token
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://id.twitch.tv/oauth2/token',
                params={
                    'client_id': twitch_api_client_id,
                    'client_secret': twitch_api_client_secret,
                    'grant_type': 'client_credentials'
                }
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to get Twitch OAuth token: {resp.status}")
                    return
                
                token_data = await resp.json()
                access_token = token_data['access_token']
            
            # Check each streamer
            for streamer_name, config_data in twitch_config.items():
                if not config_data["enabled"] or not config_data["channel_id"]:
                    continue
                
                headers = {
                    'Client-ID': twitch_api_client_id,
                    'Authorization': f'Bearer {access_token}'
                }
                
                # Get user info
                async with session.get(
                    f'https://api.twitch.tv/helix/users?login={streamer_name}',
                    headers=headers
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to get Twitch user data for {streamer_name}: {resp.status}")
                        continue
                    
                    user_data = await resp.json()
                    if not user_data['data']:
                        logger.warning(f"No Twitch user found for {streamer_name}")
                        continue
                    
                    user_id = user_data['data'][0]['id']
                
                # Check if streaming
                async with session.get(
                    f'https://api.twitch.tv/helix/streams?user_id={user_id}',
                    headers=headers
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to get Twitch stream data for {streamer_name}: {resp.status}")
                        continue
                    
                    stream_data = await resp.json()
                    is_live = bool(stream_data['data'])
                    
                    # Skip if not live or already notified
                    if not is_live or (streamer_name in twitch_cache and twitch_cache[streamer_name]):
                        twitch_cache[streamer_name] = is_live
                        continue
                    
                    # If newly live, send notification
                    if is_live and (streamer_name not in twitch_cache or not twitch_cache[streamer_name]):
                        twitch_cache[streamer_name] = True
                        
                        stream_info = stream_data['data'][0]
                        game_name = stream_info.get('game_name', 'Unknown Game')
                        stream_title = stream_info.get('title', 'No Title')
                        stream_url = f"https://twitch.tv/{streamer_name}"
                        
                        message = config_data["message"].replace("{user}", streamer_name).replace("{game}", game_name).replace("{link}", stream_url)
                        
                        channel = bot.get_channel(int(config_data["channel_id"]))
                        if channel:
                            ping = config_data.get("ping", "")
                            full_message = f"{ping} {message}" if ping else message
                            
                            embed = discord.Embed(title=f"{streamer_name} est en live !", description=stream_title, color=0x6441a5)
                            embed.add_field(name="Jeu", value=game_name, inline=True)
                            embed.add_field(name="Lien", value=f"[Regarder sur Twitch]({stream_url})", inline=True)
                            embed.set_thumbnail(url=user_data['data'][0].get('profile_image_url', ''))
                            
                            await channel.send(content=full_message, embed=embed)
                            logger.info(f"Sent Twitch notification for {streamer_name}")
    
    except Exception as e:
        logger.error(f"Error in Twitch stream check: {str(e)}")

@tasks.loop(minutes=15)
async def check_youtube_videos():
    """Check for new YouTube videos"""
    global youtube_cache
    config = load_config()
    
    if "youtube" not in config:
        return
    
    youtube_config = config["youtube"]
    
    # Skip if no enabled channels or no Discord channels configured
    if not any(channel["enabled"] and channel["channel_id"] for channel in youtube_config.values()):
        return

    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    
    if not youtube_api_key:
        logger.warning("YouTube API key not found in environment variables")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            for channel_name, config_data in youtube_config.items():
                if not config_data["enabled"] or not config_data["channel_id"]:
                    continue
                
                # First, get the channel ID from username
                async with session.get(
                    f'https://www.googleapis.com/youtube/v3/search',
                    params={
                        'part': 'snippet',
                        'q': channel_name,
                        'type': 'channel',
                        'key': youtube_api_key
                    }
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to get YouTube channel ID for {channel_name}: {resp.status}")
                        continue
                    
                    search_data = await resp.json()
                    if not search_data.get('items'):
                        logger.warning(f"No YouTube channel found for {channel_name}")
                        continue
                    
                    channel_id = search_data['items'][0]['id']['channelId']
                
                # Now get the latest videos
                async with session.get(
                    f'https://www.googleapis.com/youtube/v3/search',
                    params={
                        'part': 'snippet',
                        'channelId': channel_id,
                        'maxResults': 1,
                        'order': 'date',
                        'type': 'video',
                        'key': youtube_api_key
                    }
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to get YouTube videos for {channel_name}: {resp.status}")
                        continue
                    
                    videos_data = await resp.json()
                    if not videos_data.get('items'):
                        logger.warning(f"No YouTube videos found for {channel_name}")
                        continue
                    
                    latest_video = videos_data['items'][0]
                    video_id = latest_video['id']['videoId']
                    
                    # Check if this is a new video (not in cache)
                    if channel_name in youtube_cache and youtube_cache[channel_name] == video_id:
                        continue
                    
                    # Update cache and send notification
                    youtube_cache[channel_name] = video_id
                    
                    video_title = latest_video['snippet']['title']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    thumbnail_url = latest_video['snippet'].get('thumbnails', {}).get('high', {}).get('url', '')
                    
                    message = config_data["message"].replace("{user}", channel_name).replace("{link}", video_url)
                    
                    discord_channel = bot.get_channel(int(config_data["channel_id"]))
                    if discord_channel:
                        ping = config_data.get("ping", "")
                        full_message = f"{ping} {message}" if ping else message
                        
                        embed = discord.Embed(title=video_title, description=message, color=0xFF0000)
                        embed.set_image(url=thumbnail_url)
                        
                        await discord_channel.send(content=full_message, embed=embed)
                        logger.info(f"Sent YouTube notification for {channel_name}")
    
    except Exception as e:
        logger.error(f"Error in YouTube video check: {str(e)}")

@tasks.loop(minutes=10)
async def check_tiktok_videos():
    """Check for new TikTok videos"""
    global tiktok_cache
    config = load_config()
    
    if "tiktok" not in config:
        return
    
    tiktok_config = config["tiktok"]
    
    # Skip if no enabled creators or no channels configured
    if not any(creator["enabled"] and creator["channel_id"] for creator in tiktok_config.values()):
        return

    # TikTok doesn't have an official API, we'll use a public API to scrape the data
    # In a production environment, it's better to use a reliable TikTok API service
    try:
        async with aiohttp.ClientSession() as session:
            for creator_name, config_data in tiktok_config.items():
                if not config_data["enabled"] or not config_data["channel_id"]:
                    continue
                
                # Using a public API to get TikTok user data
                async with session.get(
                    f'https://www.tiktok.com/@{creator_name}?lang=en'
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to get TikTok data for {creator_name}: {resp.status}")
                        continue
                    
                    html_content = await resp.text()
                    
                    # Very basic scraping - in production, use a proper API
                    # This is just a placeholder for the demonstration
                    try:
                        import re
                        video_ids = re.findall(r'"id":"(\d+)"', html_content)
                        
                        if not video_ids:
                            logger.warning(f"No TikTok video IDs found for {creator_name}")
                            continue
                        
                        latest_video_id = video_ids[0]
                        
                        # Check if this is a new video
                        if creator_name in tiktok_cache and tiktok_cache[creator_name] == latest_video_id:
                            continue
                        
                        # Update cache and send notification
                        tiktok_cache[creator_name] = latest_video_id
                        
                        video_url = f"https://www.tiktok.com/@{creator_name}/video/{latest_video_id}"
                        
                        message = config_data["message"].replace("{user}", creator_name).replace("{link}", video_url)
                        
                        channel = bot.get_channel(int(config_data["channel_id"]))
                        if channel:
                            ping = config_data.get("ping", "")
                            full_message = f"{ping} {message}" if ping else message
                            
                            embed = discord.Embed(
                                title=f"Nouveau TikTok de {creator_name}",
                                description=message,
                                color=0x00f2ea
                            )
                            embed.add_field(name="Lien", value=f"[Voir sur TikTok]({video_url})", inline=False)
                            
                            await channel.send(content=full_message, embed=embed)
                            logger.info(f"Sent TikTok notification for {creator_name}")
                    
                    except Exception as e:
                        logger.error(f"Error parsing TikTok data for {creator_name}: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in TikTok video check: {str(e)}")

# Slash commands
@bot.tree.command(name="config", description="Configure les notifications pour différentes plateformes")
@app_commands.describe(
    platform="Plateforme à configurer (twitch, youtube, tiktok)"
)
@app_commands.choices(platform=[
    app_commands.Choice(name="Twitch", value="twitch"),
    app_commands.Choice(name="YouTube", value="youtube"),
    app_commands.Choice(name="TikTok", value="tiktok")
])
async def config_command(interaction: discord.Interaction, platform: str):
    """Configure notification settings for platforms"""
    # Check if user has admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
        return
    
    config = load_config()
    
    if platform not in config:
        config[platform] = {}
        save_config(config)
    
    # Create embed for platform configuration
    embed = discord.Embed(
        title=f"Configuration de {platform.capitalize()}",
        description=f"Gérez les créateurs {platform} et leurs notifications",
        color=get_platform_color(platform)
    )
    
    emoji = get_platform_emoji(platform)
    
    if config[platform]:
        creators_list = "\n".join([f"• **{creator}** ({'✅ Activé' if settings['enabled'] else '❌ Désactivé'})" 
                                  for creator, settings in config[platform].items()])
        embed.add_field(
            name=f"{emoji} Créateurs configurés",
            value=creators_list or "Aucun créateur configuré",
            inline=False
        )
    else:
        embed.add_field(
            name=f"{emoji} Créateurs configurés",
            value="Aucun créateur configuré pour cette plateforme.",
            inline=False
        )
    
    embed.add_field(
        name="🔧 Options",
        value="Utilisez les boutons ci-dessous pour gérer les créateurs et leurs notifications.",
        inline=False
    )
    
    # Create buttons for creator management
    class ConfigView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.button(label="Gérer les créateurs", style=discord.ButtonStyle.primary, emoji="⚙️")
        async def manage_creators(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not config[platform]:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Aucun créateur",
                        description=f"Aucun créateur configuré pour {platform}. Ajoutez-en un d'abord avec le bouton \"Ajouter un créateur\".",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return
                
            # Create select menu for each creator
            creators = list(config[platform].keys())
            
            class CreatorSelect(discord.ui.Select):
                def __init__(self, creators_list):
                    options = [discord.SelectOption(
                        label=creator, 
                        value=creator,
                        description=f"Configurer les notifications pour {creator}",
                        emoji="✅" if config[platform][creator]["enabled"] else "❌"
                    ) for creator in creators_list]
                    
                    super().__init__(
                        placeholder=f"Choisir un créateur {platform}...", 
                        min_values=1, 
                        max_values=1, 
                        options=options
                    )
                
                async def callback(self, interaction: discord.Interaction):
                    creator = self.values[0]
                    await show_creator_config(interaction, platform, creator)
            
            class CreatorSelectView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    self.add_item(CreatorSelect(creators))
            
            embed = discord.Embed(
                title=f"Sélection d'un créateur {platform}",
                description="Choisissez un créateur dans la liste déroulante ci-dessous pour configurer ses notifications.",
                color=get_platform_color(platform)
            )
            
            await interaction.response.send_message(
                embed=embed,
                view=CreatorSelectView(),
                ephemeral=True
            )
            
        @discord.ui.button(label="Ajouter un créateur", style=discord.ButtonStyle.success, emoji="➕")
        async def add_creator(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Show modal to input creator details
            await interaction.response.send_modal(AddCreatorModal(platform))
    
    class AddCreatorModal(discord.ui.Modal):
        def __init__(self, platform):
            super().__init__(title=f"Ajouter un créateur {platform}")
            self.platform = platform
            
            self.creator_name = discord.ui.TextInput(
                label=f"Nom d'utilisateur {platform}",
                placeholder=f"Exemple: {get_platform_example(platform)}",
                required=True
            )
            self.add_item(self.creator_name)
            
            self.custom_message = discord.ui.TextInput(
                label="Message de notification",
                placeholder=get_platform_placeholder(platform),
                style=discord.TextStyle.paragraph,
                default=get_platform_default_message(platform),
                required=True
            )
            self.add_item(self.custom_message)
        
        async def on_submit(self, interaction: discord.Interaction):
            creator = self.creator_name.value.strip()
            
            # Check if creator already exists
            if creator in config[self.platform]:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ Créateur existant",
                        description=f"Le créateur **{creator}** existe déjà pour {self.platform}.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return
            
            # Add creator to config
            config[self.platform][creator] = {
                "enabled": True,
                "message": self.custom_message.value,
                "channel_id": None,
                "ping": ""
            }
            save_config(config)
            
            success_embed = discord.Embed(
                title="✅ Créateur ajouté avec succès",
                description=f"Le créateur **{creator}** a été ajouté à vos notifications {self.platform}.",
                color=discord.Color.green()
            )
            success_embed.add_field(
                name="Étapes suivantes",
                value=f"Utilisez `/config {self.platform}` puis \"Gérer les créateurs\" pour configurer le salon et les mentions.",
                inline=False
            )
            
            await interaction.response.send_message(
                embed=success_embed,
                ephemeral=True
            )
    
    await interaction.response.send_message(
        embed=embed,
        view=ConfigView(),
        ephemeral=True
    )

async def show_creator_config(interaction: discord.Interaction, platform: str, creator: str):
    """Show the configuration options for a specific creator"""
    config = load_config()
    creator_config = config[platform][creator]
    
    # Create a detailed embed with platform-specific styling
    embed = discord.Embed(
        title=f"Configuration de {creator}",
        description=f"Personnalisez les notifications pour ce créateur {platform}",
        color=get_platform_color(platform)
    )
    
    # Status indicator with emoji
    status_emoji = "✅" if creator_config["enabled"] else "❌"
    embed.add_field(
        name="📊 Statut", 
        value=f"{status_emoji} **{('Activé' if creator_config['enabled'] else 'Désactivé')}**", 
        inline=True
    )
    
    # Channel display with emoji
    channel_value = f"<#{creator_config['channel_id']}>" if creator_config["channel_id"] else "**Non configuré**"
    embed.add_field(
        name="📢 Salon", 
        value=channel_value, 
        inline=True
    )
    
    # Ping settings with emoji
    ping_value = f"**{creator_config['ping']}**" if creator_config["ping"] else "**Aucun ping**"
    embed.add_field(
        name="🔔 Notification", 
        value=ping_value, 
        inline=True
    )
    
    # Message preview with formatting
    placeholder_message = creator_config["message"]
    
    # Create example values based on platform
    example_values = {
        "user": creator,
        "link": f"https://{platform}.com/{creator}",
    }
    
    if platform == "twitch":
        example_values["game"] = "Fortnite"
        example_values["title"] = "Gameplay avec les viewers !"
    elif platform == "youtube":
        example_values["title"] = "Ma nouvelle vidéo incroyable"
    
    # Replace placeholders with example values for preview
    preview_message = placeholder_message
    for key, value in example_values.items():
        preview_message = preview_message.replace(f"{{{key}}}", value)
    
    embed.add_field(
        name="💬 Format du message", 
        value=f"```\n{creator_config['message']}\n```", 
        inline=False
    )
    
    embed.add_field(
        name="🔍 Aperçu", 
        value=preview_message, 
        inline=False
    )
    
    # Add footer with platform emoji
    embed.set_footer(
        text=f"Créateur {platform} • Cliquez sur les boutons ci-dessous pour modifier",
        icon_url="https://cdn.discordapp.com/emojis/1012074883568758835.png?v=1" # Discord logo
    )
    
    # Add thumbnail based on platform
    if platform == "twitch":
        embed.set_thumbnail(url="https://brand.twitch.tv/assets/logos/svg/glitch/purple.svg")
    elif platform == "youtube":
        embed.set_thumbnail(url="https://www.youtube.com/s/desktop/b182fc95/img/favicon_144x144.png")
    elif platform == "tiktok":
        embed.set_thumbnail(url="https://sf16-scmcdn-sg.ibytedtos.com/goofy/tiktok/web/node/_next/static/images/logo-big-edd8395913a7d4b3b8b93b82786ca145.png")
    
    class ConfigView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.button(label="Activer", style=discord.ButtonStyle.green, emoji="✅", disabled=creator_config["enabled"], row=0)
        async def enable_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            config[platform][creator]["enabled"] = True
            save_config(config)
            
            success_embed = discord.Embed(
                title="✅ Notification activée",
                description=f"Les notifications pour **{creator}** sont maintenant **activées**.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            await show_creator_config(interaction, platform, creator)
        
        @discord.ui.button(label="Désactiver", style=discord.ButtonStyle.red, emoji="❌", disabled=not creator_config["enabled"], row=0)
        async def disable_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            config[platform][creator]["enabled"] = False
            save_config(config)
            
            success_embed = discord.Embed(
                title="❌ Notification désactivée",
                description=f"Les notifications pour **{creator}** sont maintenant **désactivées**.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            await show_creator_config(interaction, platform, creator)
        
        @discord.ui.button(label="Message", style=discord.ButtonStyle.blurple, emoji="💬", row=1)
        async def message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Create a modal for message input
            class MessageModal(discord.ui.Modal):
                def __init__(self):
                    super().__init__(title=f"Message pour {creator}")
                    
                    self.message_input = discord.ui.TextInput(
                        label="Message de notification",
                        placeholder=get_platform_placeholder(platform),
                        default=creator_config["message"],
                        style=discord.TextStyle.paragraph,
                        required=True,
                        max_length=1000
                    )
                    self.add_item(self.message_input)
                
                async def on_submit(self, interaction: discord.Interaction):
                    config[platform][creator]["message"] = self.message_input.value
                    save_config(config)
                    
                    success_embed = discord.Embed(
                        title="✅ Message configuré",
                        description=f"Le message de notification pour **{creator}** a été mis à jour.",
                        color=discord.Color.green()
                    )
                    success_embed.add_field(
                        name="Nouveau message",
                        value=f"```\n{self.message_input.value}\n```",
                        inline=False
                    )
                    
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                    await show_creator_config(interaction, platform, creator)
            
            await interaction.response.send_modal(MessageModal())
        
        @discord.ui.button(label="Salon", style=discord.ButtonStyle.blurple, emoji="📢", row=1)
        async def channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            class ChannelSelectView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    
                    # Add channel select
                    self.channel_select = discord.ui.ChannelSelect(
                        placeholder="Sélectionner un salon texte",
                        channel_types=[discord.ChannelType.text],
                        min_values=1,
                        max_values=1
                    )
                    self.channel_select.callback = self.channel_select_callback
                    self.add_item(self.channel_select)
                
                async def channel_select_callback(self, interaction: discord.Interaction):
                    selected_channel = self.channel_select.values[0]
                    config[platform][creator]["channel_id"] = str(selected_channel.id)
                    save_config(config)
                    
                    success_embed = discord.Embed(
                        title="✅ Salon configuré",
                        description=f"Les notifications pour **{creator}** seront envoyées dans {selected_channel.mention}.",
                        color=discord.Color.green()
                    )
                    
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                    await show_creator_config(interaction, platform, creator)
            
            channel_embed = discord.Embed(
                title=f"Sélection de salon pour {creator}",
                description="Choisissez le salon où les notifications seront envoyées",
                color=get_platform_color(platform)
            )
            
            await interaction.response.send_message(embed=channel_embed, view=ChannelSelectView(), ephemeral=True)
        
        @discord.ui.button(label="Ping", style=discord.ButtonStyle.blurple, emoji="🔔", row=1)
        async def ping_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            class PingModal(discord.ui.Modal):
                def __init__(self):
                    super().__init__(title=f"Ping pour {creator}")
                    
                    self.ping_input = discord.ui.TextInput(
                        label="Ping pour les notifications",
                        placeholder="Exemples: @everyone, @here, ou <@&role_id>",
                        default=creator_config["ping"],
                        required=False
                    )
                    self.add_item(self.ping_input)
                
                async def on_submit(self, interaction: discord.Interaction):
                    config[platform][creator]["ping"] = self.ping_input.value
                    save_config(config)
                    
                    # Create success feedback
                    if self.ping_input.value.strip():
                        desc = f"Les notifications pour **{creator}** mentionneront maintenant **{self.ping_input.value}**."
                    else:
                        desc = f"Les notifications pour **{creator}** n'incluront plus de mentions."
                    
                    success_embed = discord.Embed(
                        title="✅ Ping configuré",
                        description=desc,
                        color=discord.Color.green()
                    )
                    
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                    await show_creator_config(interaction, platform, creator)
            
            await interaction.response.send_modal(PingModal())
        
        @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
        async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Create confirmation view
            class ConfirmView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                
                @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger, emoji="✅")
                async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    del config[platform][creator]
                    save_config(config)
                    
                    success_embed = discord.Embed(
                        title="🗑️ Créateur supprimé",
                        description=f"Le créateur **{creator}** a été supprimé des notifications {platform}.",
                        color=discord.Color.red()
                    )
                    
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                    
                    # Return to platform config
                    embed = discord.Embed(
                        title=f"Configuration de {platform}",
                        description="Le créateur a été supprimé. Utilisez `/config {platform}` pour revenir à la liste des créateurs.",
                        color=get_platform_color(platform)
                    )
                    
                    # Update the original message
                    await interaction.message.edit(embed=embed, view=None)
                
                @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary, emoji="❌")
                async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    cancel_embed = discord.Embed(
                        title="⚠️ Suppression annulée",
                        description=f"La suppression du créateur **{creator}** a été annulée.",
                        color=discord.Color.blurple()
                    )
                    
                    await interaction.response.send_message(embed=cancel_embed, ephemeral=True)
            
            confirm_embed = discord.Embed(
                title="⚠️ Confirmation de suppression",
                description=f"Êtes-vous sûr de vouloir supprimer le créateur **{creator}** de vos notifications {platform} ?",
                color=discord.Color.orange()
            )
            confirm_embed.add_field(
                name="⚠️ Cette action est irréversible",
                value="Vous devrez reconfigurer ce créateur s'il est supprimé.",
                inline=False
            )
            
            await interaction.response.send_message(embed=confirm_embed, view=ConfirmView(), ephemeral=True)
            
        @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Go back to platform config
            await config_command(interaction, platform)
    
    await interaction.response.edit_message(embed=embed, view=ConfigView())

@bot.tree.command(name="add_creator", description="Ajoute un nouveau créateur à suivre pour les notifications")
@app_commands.describe(
    platform="Plateforme du créateur (twitch, youtube, tiktok)",
    username="Nom d'utilisateur du créateur sur la plateforme"
)
@app_commands.choices(platform=[
    app_commands.Choice(name="Twitch", value="twitch"),
    app_commands.Choice(name="YouTube", value="youtube"),
    app_commands.Choice(name="TikTok", value="tiktok")
])
async def add_creator_command(interaction: discord.Interaction, platform: str, username: str):
    """Add a new creator to track for notifications"""
    # Check if user has admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Permission refusée",
                description="Vous devez être administrateur pour utiliser cette commande.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return
    
    # Load config
    config = load_config()
    
    # Initialize platform if needed
    if platform not in config:
        config[platform] = {}
    
    # Clean username
    username = username.strip()
    
    # Check if creator already exists
    if username in config[platform]:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Créateur existant",
                description=f"Le créateur **{username}** existe déjà pour {platform}.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return
    
    # Add creator with default settings
    config[platform][username] = {
        "enabled": True,
        "message": get_platform_default_message(platform),
        "channel_id": None,
        "ping": ""
    }
    save_config(config)
    
    # Create success embed
    embed = discord.Embed(
        title=f"✅ {get_platform_emoji(platform)} Créateur ajouté avec succès",
        description=f"**{username}** a été ajouté à vos notifications {platform}.",
        color=get_platform_color(platform)
    )
    
    embed.add_field(
        name="🔶 Message par défaut",
        value=f"```\n{get_platform_default_message(platform)}\n```",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Configuration",
        value=f"Utilisez `/config {platform}` puis sélectionnez le créateur pour configurer les détails (salon, ping, message).",
        inline=False
    )
    
    # Show appropriate thumbnail
    if platform == "twitch":
        embed.set_thumbnail(url="https://brand.twitch.tv/assets/logos/svg/glitch/purple.svg")
    elif platform == "youtube":
        embed.set_thumbnail(url="https://www.youtube.com/s/desktop/b182fc95/img/favicon_144x144.png")
    elif platform == "tiktok":
        embed.set_thumbnail(url="https://sf16-scmcdn-sg.ibytedtos.com/goofy/tiktok/web/node/_next/static/images/logo-big-edd8395913a7d4b3b8b93b82786ca145.png")
    
    # Create a button to directly go to config
    class ConfigNowView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
        
        @discord.ui.button(label="Configurer maintenant", style=discord.ButtonStyle.primary, emoji="⚙️")
        async def config_now(self, interaction: discord.Interaction, button: discord.ui.Button):
            await show_creator_config(interaction, platform, username)
    
    await interaction.response.send_message(embed=embed, view=ConfigNowView(), ephemeral=False)

@bot.tree.command(name="rank", description="Affiche ton niveau et ton XP")
async def rank_command(interaction: discord.Interaction):
    """Show user's rank and XP"""
    user_id = str(interaction.user.id)
    user_data = get_user_data(user_id)
    
    current_xp = user_data["xp"]
    current_level = user_data["level"]
    xp_for_next_level = calculate_xp_for_level(current_level + 1)
    xp_for_current_level = calculate_xp_for_level(current_level)
    
    # Calculate progress percentage
    progress = ((current_xp - xp_for_current_level) / (xp_for_next_level - xp_for_current_level)) * 100
    progress = max(0, min(100, progress))  # Ensure between 0-100%
    
    # Create progress bar
    bar_length = 20
    filled_length = int(bar_length * progress / 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    embed = discord.Embed(
        title=f"Niveau de {interaction.user.display_name}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Niveau", value=str(current_level), inline=True)
    embed.add_field(name="XP Total", value=str(current_xp), inline=True)
    embed.add_field(name=f"Progression vers niveau {current_level + 1}", value=f"`{bar}` {progress:.1f}%", inline=False)
    embed.add_field(name="XP nécessaire", value=f"{current_xp - xp_for_current_level}/{xp_for_next_level - xp_for_current_level}", inline=True)
    
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Affiche le classement des utilisateurs par niveau")
async def leaderboard_command(interaction: discord.Interaction):
    """Show the server leaderboard"""
    users_data = load_users()
    
    # Filter out users not in the server
    server_members = {str(member.id): member for member in interaction.guild.members}
    
    # Create leaderboard data
    leaderboard = []
    for user_id, data in users_data.items():
        if user_id in server_members:
            leaderboard.append({
                "id": user_id,
                "member": server_members[user_id],
                "xp": data["xp"],
                "level": data["level"]
            })
    
    # Sort by XP
    leaderboard.sort(key=lambda x: x["xp"], reverse=True)
    
    # Keep only top 10
    leaderboard = leaderboard[:10]
    
    if not leaderboard:
        await interaction.response.send_message("Aucun utilisateur dans le classement pour le moment.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"Classement du serveur {interaction.guild.name}",
        description="Les membres les plus actifs du serveur",
        color=discord.Color.gold()
    )
    
    for i, entry in enumerate(leaderboard, 1):
        medal = ""
        if i == 1:
            medal = "🥇 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "
        else:
            medal = f"{i}. "
        
        member = entry["member"]
        embed.add_field(
            name=f"{medal}{member.display_name}",
            value=f"Niveau {entry['level']} • {entry['xp']} XP",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="balance", description="Affiche ton solde de monnaie virtuelle")
async def balance_command(interaction: discord.Interaction):
    """Show user's balance"""
    user_id = str(interaction.user.id)
    user_data = get_user_data(user_id)
    
    balance = user_data["balance"]
    
    embed = discord.Embed(
        title="💰 Solde",
        description=f"{interaction.user.display_name}, tu possèdes **{balance}** pièces.",
        color=discord.Color.gold()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Collecte ta récompense quotidienne")
async def daily_command(interaction: discord.Interaction):
    """Collect daily reward"""
    user_id = str(interaction.user.id)
    user_data = get_user_data(user_id)
    
    # Check if user already claimed today
    last_claim = user_data.get("daily_last")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    if last_claim == today:
        # Already claimed today
        next_claim = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)
        time_until = next_claim - datetime.datetime.now()
        hours, remainder = divmod(time_until.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        embed = discord.Embed(
            title="❌ Déjà réclamé",
            description=f"Tu as déjà réclamé ta récompense aujourd'hui.\nReviens dans **{hours}h {minutes}m**.",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Give reward
    reward_amount = random.randint(50, 200)
    user_data["balance"] += reward_amount
    user_data["daily_last"] = today
    
    update_user_data(user_id, user_data)
    
    embed = discord.Embed(
        title="💰 Récompense quotidienne",
        description=f"Tu as reçu **{reward_amount}** pièces !\nTon nouveau solde est de **{user_data['balance']}** pièces.",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pay", description="Transfère de l'argent à un autre membre")
@app_commands.describe(
    user="L'utilisateur à qui envoyer de l'argent",
    amount="Le montant à envoyer"
)
async def pay_command(interaction: discord.Interaction, user: discord.Member, amount: int):
    """Transfer money to another user"""
    if amount <= 0:
        await interaction.response.send_message("Le montant doit être supérieur à 0.", ephemeral=True)
        return
    
    if user.id == interaction.user.id:
        await interaction.response.send_message("Tu ne peux pas t'envoyer de l'argent à toi-même.", ephemeral=True)
        return
    
    sender_id = str(interaction.user.id)
    recipient_id = str(user.id)
    
    sender_data = get_user_data(sender_id)
    
    if sender_data["balance"] < amount:
        await interaction.response.send_message("Tu n'as pas assez d'argent pour effectuer ce transfert.", ephemeral=True)
        return
    
    # Update sender's balance
    sender_data["balance"] -= amount
    update_user_data(sender_id, sender_data)
    
    # Update recipient's balance
    recipient_data = get_user_data(recipient_id)
    recipient_data["balance"] += amount
    update_user_data(recipient_id, recipient_data)
    
    embed = discord.Embed(
        title="💸 Transfert réussi",
        description=f"Tu as envoyé **{amount}** pièces à {user.mention}.\nTon nouveau solde est de **{sender_data['balance']}** pièces.",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)
    
    # Notify recipient
    try:
        recipient_embed = discord.Embed(
            title="💰 Pièces reçues",
            description=f"Tu as reçu **{amount}** pièces de {interaction.user.mention}.\nTon nouveau solde est de **{recipient_data['balance']}** pièces.",
            color=discord.Color.green()
        )
        
        await user.send(embed=recipient_embed)
    except discord.Forbidden:
        pass  # User has DMs closed

@bot.tree.command(name="ban", description="Bannir un membre du serveur")
@app_commands.describe(
    user="L'utilisateur à bannir",
    reason="La raison du bannissement"
)
@commands.has_permissions(ban_members=True)
async def ban_command(interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison fournie"):
    """Ban a user from the server"""
    if interaction.user.top_role <= user.top_role:
        await interaction.response.send_message("Tu ne peux pas bannir cet utilisateur car son rôle est supérieur ou égal au tien.", ephemeral=True)
        return
    
    try:
        await user.ban(reason=reason)
        
        embed = discord.Embed(
            title="🔨 Utilisateur banni",
            description=f"{user.mention} a été banni du serveur.",
            color=discord.Color.red()
        )
        embed.add_field(name="Raison", value=reason)
        
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("Je n'ai pas la permission de bannir cet utilisateur.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Une erreur s'est produite : {str(e)}", ephemeral=True)

@ban_command.error
async def ban_command_error(interaction: discord.Interaction, error):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("Tu n'as pas la permission de bannir des membres.", ephemeral=True)

@bot.tree.command(name="kick", description="Expulser un membre du serveur")
@app_commands.describe(
    user="L'utilisateur à expulser",
    reason="La raison de l'expulsion"
)
@commands.has_permissions(kick_members=True)
async def kick_command(interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison fournie"):
    """Kick a user from the server"""
    if interaction.user.top_role <= user.top_role:
        await interaction.response.send_message("Tu ne peux pas expulser cet utilisateur car son rôle est supérieur ou égal au tien.", ephemeral=True)
        return
    
    try:
        await user.kick(reason=reason)
        
        embed = discord.Embed(
            title="👢 Utilisateur expulsé",
            description=f"{user.mention} a été expulsé du serveur.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Raison", value=reason)
        
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("Je n'ai pas la permission d'expulser cet utilisateur.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Une erreur s'est produite : {str(e)}", ephemeral=True)

@kick_command.error
async def kick_command_error(interaction: discord.Interaction, error):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("Tu n'as pas la permission d'expulser des membres.", ephemeral=True)

@bot.tree.command(name="warn", description="Avertir un membre du serveur")
@app_commands.describe(
    user="L'utilisateur à avertir",
    reason="La raison de l'avertissement"
)
@commands.has_permissions(manage_messages=True)
async def warn_command(interaction: discord.Interaction, user: discord.Member, reason: str = "Aucune raison fournie"):
    """Warn a user"""
    if interaction.user.top_role <= user.top_role:
        await interaction.response.send_message("Tu ne peux pas avertir cet utilisateur car son rôle est supérieur ou égal au tien.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⚠️ Avertissement",
        description=f"{user.mention} a reçu un avertissement.",
        color=discord.Color.yellow()
    )
    embed.add_field(name="Raison", value=reason)
    
    await interaction.response.send_message(embed=embed)
    
    # Try to DM the user
    try:
        user_embed = discord.Embed(
            title="⚠️ Tu as reçu un avertissement",
            description=f"Tu as reçu un avertissement sur le serveur {interaction.guild.name}.",
            color=discord.Color.yellow()
        )
        user_embed.add_field(name="Raison", value=reason)
        user_embed.add_field(name="Modérateur", value=interaction.user.mention)
        
        await user.send(embed=user_embed)
    except discord.Forbidden:
        await interaction.followup.send("L'utilisateur n'a pas pu être notifié car ses messages privés sont fermés.", ephemeral=True)

@warn_command.error
async def warn_command_error(interaction: discord.Interaction, error):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("Tu n'as pas la permission d'avertir des membres.", ephemeral=True)

@bot.tree.command(name="clear", description="Supprimer un certain nombre de messages")
@app_commands.describe(
    amount="Le nombre de messages à supprimer (1-100)"
)
@commands.has_permissions(manage_messages=True)
async def clear_command(interaction: discord.Interaction, amount: int):
    """Clear a specified number of messages"""
    if amount < 1 or amount > 100:
        await interaction.response.send_message("Le nombre de messages doit être entre 1 et 100.", ephemeral=True)
        return
    
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        
        await interaction.followup.send(f"✅ {len(deleted)} messages ont été supprimés.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("Je n'ai pas la permission de supprimer des messages dans ce salon.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Une erreur s'est produite : {str(e)}", ephemeral=True)

@clear_command.error
async def clear_command_error(interaction: discord.Interaction, error):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("Tu n'as pas la permission de supprimer des messages.", ephemeral=True)

async def bot_start():
    """Start the Discord bot with the token from environment variables"""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables")
        return
    
    try:
        await bot.start(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")

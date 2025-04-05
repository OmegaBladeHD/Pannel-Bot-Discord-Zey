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
    
    if platform not in config or not config[platform]:
        await interaction.response.send_message(f"Aucun créateur configuré pour {platform}.", ephemeral=True)
        return
    
    # Create buttons for each creator
    creators = list(config[platform].keys())
    
    class CreatorSelect(discord.ui.Select):
        def __init__(self, creators_list):
            options = [discord.SelectOption(label=creator, value=creator) for creator in creators_list]
            super().__init__(placeholder="Choisir un créateur...", min_values=1, max_values=1, options=options)
        
        async def callback(self, interaction: discord.Interaction):
            creator = self.values[0]
            await show_creator_config(interaction, platform, creator)
    
    class CreatorSelectView(discord.ui.View):
        def __init__(self):
            super().__init__()
            self.add_item(CreatorSelect(creators))
    
    await interaction.response.send_message(
        f"Choisissez un créateur {platform} à configurer :",
        view=CreatorSelectView(),
        ephemeral=True
    )

async def show_creator_config(interaction: discord.Interaction, platform: str, creator: str):
    """Show the configuration options for a specific creator"""
    config = load_config()
    creator_config = config[platform][creator]
    
    embed = discord.Embed(
        title=f"Configuration de {creator} ({platform})",
        description="Utilisez les boutons ci-dessous pour configurer les notifications.",
        color=0x3498db
    )
    
    embed.add_field(name="Status", value="Activé" if creator_config["enabled"] else "Désactivé", inline=True)
    embed.add_field(name="Salon", value=f"<#{creator_config['channel_id']}>" if creator_config["channel_id"] else "Non configuré", inline=True)
    embed.add_field(name="Ping", value=creator_config["ping"] if creator_config["ping"] else "Aucun", inline=True)
    embed.add_field(name="Message", value=creator_config["message"], inline=False)
    
    class ConfigView(discord.ui.View):
        def __init__(self):
            super().__init__()
        
        @discord.ui.button(label="Activer", style=discord.ButtonStyle.green, disabled=creator_config["enabled"])
        async def enable_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            config[platform][creator]["enabled"] = True
            save_config(config)
            await show_creator_config(interaction, platform, creator)
        
        @discord.ui.button(label="Désactiver", style=discord.ButtonStyle.red, disabled=not creator_config["enabled"])
        async def disable_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            config[platform][creator]["enabled"] = False
            save_config(config)
            await show_creator_config(interaction, platform, creator)
        
        @discord.ui.button(label="Configurer message", style=discord.ButtonStyle.blurple)
        async def message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Create a modal for message input
            class MessageModal(discord.ui.Modal, title=f"Message pour {creator}"):
                message_input = discord.ui.TextInput(
                    label="Message de notification",
                    placeholder="Exemple: {user} est en live sur {game} ! {link}",
                    default=creator_config["message"],
                    style=discord.TextStyle.paragraph
                )
                
                async def on_submit(self, interaction: discord.Interaction):
                    config[platform][creator]["message"] = self.message_input.value
                    save_config(config)
                    await interaction.response.send_message("Message configuré avec succès !", ephemeral=True)
                    await show_creator_config(interaction, platform, creator)
            
            await interaction.response.send_modal(MessageModal())
        
        @discord.ui.button(label="Choisir salon", style=discord.ButtonStyle.blurple)
        async def channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            class ChannelSelect(discord.ui.ChannelSelect):
                def __init__(self):
                    super().__init__(channel_types=[discord.ChannelType.text], placeholder="Sélectionner un salon texte")
                
                async def callback(self, interaction: discord.Interaction):
                    selected_channel = self.values[0]
                    config[platform][creator]["channel_id"] = str(selected_channel.id)
                    save_config(config)
                    await interaction.response.send_message(f"Salon configuré: {selected_channel.mention}", ephemeral=True)
                    await show_creator_config(interaction, platform, creator)
            
            view = discord.ui.View()
            view.add_item(ChannelSelect())
            await interaction.response.send_message("Choisissez un salon:", view=view, ephemeral=True)
        
        @discord.ui.button(label="Configurer ping", style=discord.ButtonStyle.blurple)
        async def ping_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            class PingModal(discord.ui.Modal, title=f"Ping pour {creator}"):
                ping_input = discord.ui.TextInput(
                    label="Ping (laissez vide pour désactiver)",
                    placeholder="Exemples: @everyone, @here, ou <@&role_id>",
                    default=creator_config["ping"],
                    required=False
                )
                
                async def on_submit(self, interaction: discord.Interaction):
                    config[platform][creator]["ping"] = self.ping_input.value
                    save_config(config)
                    await interaction.response.send_message("Ping configuré avec succès !", ephemeral=True)
                    await show_creator_config(interaction, platform, creator)
            
            await interaction.response.send_modal(PingModal())
    
    await interaction.response.edit_message(embed=embed, view=ConfigView())

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

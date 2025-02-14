import requests
import discord
from discord.ext import tasks
import json
import asyncio
import websockets
import ssl

# Discord bot token and webhook channel ID
TOKEN = ''
CHANNEL_ID = 1339641920141393970

# Electrum Server API endpoint
API_URL = "https://servers.pepelum.site/"

# Function to check if a server is synced using WebSocket
async def check_sync(server_url, server_name):
    try:
        # Create an SSL context to disable certificate verification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with websockets.connect(server_url, ssl=ssl_context) as websocket:
            # Request server version
            version_request = {
                "jsonrpc": "2.0",
                "method": "server.version",
                "params": [],
                "id": 1
            }
            await websocket.send(json.dumps(version_request))

            # Wait for response for server version
            version_response = await websocket.recv()
            version_data = json.loads(version_response)

            # Get the server version (only the first entry in the version array)
            version = version_data.get('result', ['Unknown Version'])[0]

            # Subscribe to block headers to check sync status
            sync_request = {
                "jsonrpc": "2.0",
                "method": "blockchain.headers.subscribe",
                "params": [],
                "id": 2
            }
            await websocket.send(json.dumps(sync_request))

            # Wait for response
            sync_response = await websocket.recv()
            sync_data = json.loads(sync_response)

            # Check if the server responded with headers (meaning it's synced)
            if 'result' in sync_data and sync_data['result']:
                block_height = sync_data['result']['height'] if 'height' in sync_data['result'] else 'N/A'
                return f"{server_name} - Synced (Block height: {block_height})\nVersion: {version}", True
            else:
                return f"{server_name} - Not Synced\nVersion: {version}", False
    except Exception as e:
        print(f"Error connecting to {server_url}: {e}")
        return f"{server_name} - Offline!", False

# Function to create the embed for online servers
async def create_online_embed():
    embed = discord.Embed(
        title="Electrum Server Sync Check - Online Servers",
        description="The following Electrum servers are online and synced:",
        color=discord.Color.green()
    )

    try:
        # Fetch the JSON data for the server connections
        response = requests.get(API_URL)
        data = response.json()

        # Select server URLs (WSS connections in this case)
        server_urls = data["wss"]
        online_servers = []

        # Check each server status using the WebSocket method
        for server_url in server_urls:
            # Extract the server name from the URL (e.g., 'electrum.pepelum.site' from 'wss://electrum.pepelum.site:50004')
            server_name = server_url.split("//")[1].split(":")[0]
            status, is_online = await check_sync(server_url, server_name)
            
            if is_online:
                online_servers.append(status)

        # Add the online servers to the embed
        if online_servers:
            for status in online_servers:
                embed.add_field(name=status.split(' - ')[0], value=status, inline=False)
        else:
            embed.description = "No servers are online."

    except Exception as e:
        embed.add_field(name="Error", value=str(e), inline=False)

    return embed

# Function to create the embed for offline servers
async def create_offline_embed():
    embed = discord.Embed(
        title="Electrum Servers Status",
        description="The following Electrum servers are offline:",
        color=discord.Color.red()
    )

    try:
        # Fetch the JSON data for the server connections
        response = requests.get(API_URL)
        data = response.json()

        # Select server URLs (WSS connections in this case)
        server_urls = data["wss"]
        offline_servers = []

        # Check each server status using the WebSocket method
        for server_url in server_urls:
            # Extract the server name from the URL (e.g., 'electrum.pepelum.site' from 'wss://electrum.pepelum.site:50004')
            server_name = server_url.split("//")[1].split(":")[0]
            status, is_online = await check_sync(server_url, server_name)
            
            if not is_online:
                offline_servers.append(status)

        # Add the offline servers to the embed
        if offline_servers:
            for status in offline_servers:
                embed.add_field(name=status.split(' - ')[0], value=status, inline=False)
        else:
            embed.description = "No servers are offline."

    except Exception as e:
        embed.add_field(name="Error", value=str(e), inline=False)

    return embed

# Create a bot instance
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Store the ID of the message for later updates
online_message_id = None
offline_message_id = None

# Function to send or edit a message
async def send_or_edit_message():
    global online_message_id, offline_message_id

    # Create the online servers embed
    online_embed = await create_online_embed()

    channel = client.get_channel(CHANNEL_ID)

    # Send or edit the online servers message
    if online_message_id is None:
        sent_message = await channel.send(embed=online_embed)
        online_message_id = sent_message.id
    else:
        message = await channel.fetch_message(online_message_id)
        await message.edit(embed=online_embed)

    # Create the offline servers embed and send or delete the message if necessary
    offline_embed = await create_offline_embed()

    if offline_embed.description != "No servers are offline.":
        # If there are offline servers, send or edit the offline message
        if offline_message_id is None:
            sent_message = await channel.send(embed=offline_embed)
            offline_message_id = sent_message.id
        else:
            message = await channel.fetch_message(offline_message_id)
            await message.edit(embed=offline_embed)
    else:
        # If no servers are offline, delete the offline message if it exists
        if offline_message_id is not None:
            message = await channel.fetch_message(offline_message_id)
            await message.delete()
            offline_message_id = None

# Task to check servers every 5 minutes
@tasks.loop(minutes=5)
async def check_servers():
    await send_or_edit_message()

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    check_servers.start()

# Run the bot
client.run(TOKEN)

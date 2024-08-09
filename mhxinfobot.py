import discord
import json
import os
import math

# Load the config file
with open('config.json') as config_file:
    config = json.load(config_file)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Load triggers from the JSON file once at startup
with open('triggers.json') as triggers_file:
    triggers = json.load(triggers_file)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    normalized_content = message.content.lower().split()

    if "!list" in normalized_content:
        await send_trigger_list(message.channel)
        return

    for response in triggers.values():
        if any(trigger.lower() in normalized_content for trigger in response['triggers']):
            await handle_response(message.channel, response)
            break  # Stop after sending one trigger action

async def send_trigger_list(channel):
    embed = discord.Embed(title="Available Triggers", color=discord.Color.blue())

    all_triggers = sorted(trigger for value in triggers.values() for trigger in value['triggers'])

    num_columns = 3  # Number of desired columns
    num_rows = math.ceil(len(all_triggers) / num_columns)

    for i in range(num_columns):
        column_content = "\n".join(all_triggers[i * num_rows:(i + 1) * num_rows])
        embed.add_field(name="\u200B", value=column_content, inline=True)

    await channel.send(embed=embed)

async def handle_response(channel, response):
    if text := response.get("text"):
        await send_long_message(channel, text)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    for file in response.get("files", []):
        file_path = os.path.join(base_dir, file)
        if os.path.exists(file_path):
            await channel.send(file=discord.File(file_path))
        else:
            await channel.send(f"Sorry, I couldn't find the file: {file}")

async def send_long_message(channel, text):
    while len(text) > 2000:
        split_index = text.rfind('\n', 0, 2000)
        if split_index == -1:
            split_index = 2000
        await channel.send(text[:split_index])
        text = text[split_index:].lstrip('\n')

    if text:
        await channel.send(text)

# Run the bot
client.run(config['bot_token'])

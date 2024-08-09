import discord
import json
import os

# Load the config file
with open('config.json') as config_file:
    config = json.load(config_file)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Get the directory of the current script
base_dir = os.path.dirname(os.path.abspath(__file__))

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

    for response in triggers.values():
        # Check if any of the triggers match exactly as a whole word
        if any(trigger.lower() in normalized_content for trigger in response['triggers']):
            action_text = response.get("text", "")
            files = response.get("files", [])

            if action_text:
                await send_long_message(message.channel, action_text)

            for file in files:
                file_path = os.path.join(base_dir, file)
                if os.path.exists(file_path):
                    await message.channel.send(file=discord.File(file_path))
                else:
                    await message.channel.send(f"Sorry, I couldn't find the file: {file}")

            break  # Stop after sending one trigger action

async def send_long_message(channel, text):
    """Send a long message in chunks under the Discord limit."""
    while len(text) > 2000:
        split_index = text.rfind('\n', 0, 2000)
        if split_index == -1:  # No newline found, split at 2000 characters
            split_index = 2000
        await channel.send(text[:split_index])
        text = text[split_index:].lstrip('\n')  # Remove leading newlines

    if text:  # Send the remaining part of the message
        await channel.send(text)

# Run the bot
client.run(config['bot_token'])

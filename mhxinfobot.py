import discord
import json
import os
import math
import tempfile
from analyze_log import analyze_log_file
import gzip
import shutil
import urllib.request as urlreq
import uuid

async def get_decomp_info():
    await frogress_json = json.load(urlreq.urlopen("https://progress.decomp.club/data/rb3/SZBE69_B8/dol/"))
    # remove wrapper sludge
    frogress_data = frogress_json['rb3']['SZBE69_B8']['dol'][0]
    return f"Commit {frogress_data['git_hash'][0:6]} has {frogress_data['measures']['matched_code'] / frogress_data['measures']['matched_code/total'] * 100:.2f}% matched code and {frogress_data['measures']['matched_data'] / frogress_data['measures']['matched_data/total'] * 100:.2f}% matched data.\nAdditionally, it has {frogress_data['measures']['matched_functions'] / frogress_data['measures']['matched_functions/total'] * 100:.2f}% matching functions and {frogress_data['measures']['code'] / frogress_data['measures']['code/total'] * 100:.2f}% linked (i.e. fully complete, in-order) code."

# Load the config file
with open('config.json') as config_file:
    config = json.load(config_file)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Load triggers from the JSON files once at startup
with open('triggers.json') as triggers_file:
    triggers = json.load(triggers_file)

with open('triggers_esl.json') as triggers_esl_file:
    triggers_esl = json.load(triggers_esl_file)

# Build mapping from triggers to responses
triggers_map = {}
for response in triggers.values():
    for trigger in response['triggers']:
        triggers_map[trigger.lower()] = response

# Build mapping from ESL triggers to responses
triggers_esl_map = {}
esl_triggers_with_exclamation_map = {}
for response in triggers_esl.values():
    for trigger in response['triggers']:
        if trigger.startswith('!'):
            # Remove '!' from the trigger
            esl_triggers_with_exclamation_map[trigger[1:].lower()] = response
        else:
            triggers_esl_map[trigger.lower()] = response

    # For linked triggers, map the linked English trigger to this response
    if 'link' in response:
        linked_response_number = response['link']
        if linked_response_number in triggers:
            linked_response = triggers[linked_response_number]
            for trigger in linked_response['triggers']:
                triggers_esl_map[trigger.lower()] = response
        else:
            print(f"Linked response number {linked_response_number} not found in English triggers.")


TEMP_FOLDER = "out/"
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

# Constants
COLUMNS = 3  # Number of columns to display
COLUMNS_ALIAS = 2  # Number of columns to display for aliases
EMBED_TIMEOUT = 60  # Timeout in seconds

def generate_session_hash():
    return str(uuid.uuid4())[:8]  # Generate a short unique hash

class PaginatorView(discord.ui.View):
    def __init__(self, triggers, alias_triggers_dict, user_id, show_aliases=False, title="Available Triggers"):
        super().__init__(timeout=EMBED_TIMEOUT)
        self.triggers = triggers
        self.alias_triggers_dict = alias_triggers_dict
        self.user_id = user_id
        self.show_aliases = show_aliases
        self.title = title
        self.current_page = 0
        self.items_per_page = self.calculate_items_per_page()
        self.total_pages = self.calculate_total_pages()
        self.add_buttons()

    def calculate_items_per_page(self):
        total_items = len(self.current_items)
        if total_items <= 15:
            return max(3, math.ceil(total_items / COLUMNS))
        elif total_items <= 30:
            return 5
        elif total_items <= 60:
            return 6
        else:
            return 9

    def calculate_total_pages(self):
        items_count = len(self.current_items)
        return max(1, math.ceil(items_count / (self.items_per_page * (COLUMNS if not self.show_aliases else COLUMNS_ALIAS))))

    @property
    def current_items(self):
        if self.show_aliases:
            return [(trigger, aliases) for trigger, aliases in self.alias_triggers_dict.items() if aliases]
        return self.triggers

    def add_buttons(self):
        self.clear_items()
        if self.show_aliases:
            self.add_item(ViewTriggersButton(style=discord.ButtonStyle.secondary, label='Show Triggers', user_id=self.user_id))
        else:
            self.add_item(ViewAliasesButton(style=discord.ButtonStyle.secondary, label='Show Aliases', user_id=self.user_id))
        
        if self.current_page > 0:
            self.add_item(PreviousButton(style=discord.ButtonStyle.primary, label='Previous', user_id=self.user_id))
        else:
            self.add_item(PreviousButton(style=discord.ButtonStyle.secondary, label='Previous', disabled=True, user_id=self.user_id))
        
        if self.current_page < self.total_pages - 1 and self.has_next_page_items():
            self.add_item(NextButton(style=discord.ButtonStyle.primary, label='Next', user_id=self.user_id))
        else:
            self.add_item(NextButton(style=discord.ButtonStyle.secondary, label='Next', disabled=True, user_id=self.user_id))

    def update_buttons(self):
        self.add_buttons()

    def get_embed(self):
        embed = discord.Embed(title=self.title if not self.show_aliases else f"{self.title} - Aliases", color=discord.Color.blue())
        
        start_idx = self.current_page * self.items_per_page * (COLUMNS if not self.show_aliases else COLUMNS_ALIAS)
        end_idx = start_idx + self.items_per_page * (COLUMNS if not self.show_aliases else COLUMNS_ALIAS)
        
        if self.show_aliases:
            items_page = self.current_items[start_idx:end_idx]
            alias_columns = [items_page[i * self.items_per_page:(i + 1) * self.items_per_page] for i in range(COLUMNS_ALIAS)]
            
            for i, col in enumerate(alias_columns):
                if col:
                    value = "\n".join(f"**{trigger}**\n{', '.join(aliases)}" for trigger, aliases in col)
                else:
                    value = "\u200B"
                embed.add_field(name="Aliases" if i == 0 else "\u200B", value=value, inline=True)
        else:
            items_page = self.current_items[start_idx:end_idx]
            trigger_columns = [items_page[i * self.items_per_page:(i + 1) * self.items_per_page] for i in range(COLUMNS)]

            for i, col in enumerate(trigger_columns):
                if col:
                    value = "\n".join(col)
                else:
                    value = "\u200B"
                embed.add_field(name="Triggers" if i == 0 else "\u200B", value=value, inline=True)

        return embed

    def has_next_page_items(self):
        # Check if there are items on the next page
        next_page_idx = (self.current_page + 1) * self.items_per_page * (COLUMNS if not self.show_aliases else COLUMNS_ALIAS)
        return next_page_idx < len(self.current_items)

    async def on_timeout(self):
        # Disable all buttons after timeout
        for item in self.children:
            item.disabled = True
        # Edit the message to update the disabled state of the buttons
        await self.message.edit(view=self)

class NextButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You did not trigger this list. Use !list to browse through commands.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page += 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class PreviousButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You did not trigger this list. Use !list to browse through commands.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.current_page -= 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class ViewAliasesButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You did not trigger this list. Use !list to browse through commands.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.show_aliases = True
        view.current_page = 0  # Reset to the first page
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

class ViewTriggersButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You did not trigger this list. Use !list to browse through commands.", ephemeral=True)
            return
        view: PaginatorView = self.view
        view.show_aliases = False
        view.current_page = 0  # Reset to the first page
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

async def handle_log_file(message):
    if len(message.attachments) == 0:
        for response in triggers.values():
            if any(trigger.lower() in message.content.lower() for trigger in response['triggers']):
                await handle_response(message.channel, response)
                break  # Stop after sending one trigger action
        return

    log_file = message.attachments[0]
    session_hash = generate_session_hash()

    # Check if the file is a valid log or gzipped log file
    if not log_file.filename.endswith((".log", ".log.gz")):
        await message.channel.send("Invalid file type. Please upload a `.log` or `.log.gz` file.")
        return

    # Generate a unique log file name by appending the session hash
    log_file_name = f"{os.path.splitext(log_file.filename)[0]}_{session_hash}.log"
    log_file_path = os.path.join(TEMP_FOLDER, log_file_name)

    # Save the file to a temporary location
    await log_file.save(log_file_path if not log_file.filename.endswith(".gz") else log_file_path + ".gz")

    decompressed_log_path = log_file_path

    # If the file is a .gz file, extract it
    if log_file.filename.endswith(".gz"):
        decompressed_log_path = log_file_path  # Remove ".gz" from the final path
        with gzip.open(log_file_path + ".gz", 'rb') as f_in:
            with open(decompressed_log_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(log_file_path + ".gz")  # Clean up the original .gz file after decompression

    # Call the analyze_log_file function directly
    try:
        # Analyze the log file and capture the result
        output = analyze_log_file(decompressed_log_path)

        # Create a Discord embed to format the output nicely
        embed = discord.Embed(title="Log Analysis Result", color=discord.Color.blue())
        embed.description = output[:4096]  # Discord embed description limit is 4096 chars

        await message.channel.send(embed=embed)

    except Exception as e:
        await message.channel.send(f"Error analyzing log file: {e}")

    finally:
        # Clean up the temporary directory
        if os.path.exists(decompressed_log_path):
            os.remove(decompressed_log_path)

    return

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Handle publishing messages in a specific channel
    if message.channel.id == 979895152367771668:
        try:
            await message.publish()
            print(f"Published message {message.id} in channel {message.channel.id}")
        except Exception as e:
            print(f"Failed to publish message {message.id} in channel {message.channel.id}: {e}")
        return

    message_content = message.content.strip()
    if not message_content:
        return

    # Normalize the message content to lower case
    message_content_lower = message_content.lower()

    # List of valid prefixes
    prefixes = ['!', '¡']

    # Check for commands anywhere in the message
    words = message_content_lower.split()

    for word in words:
        if any(word.startswith(prefix) for prefix in prefixes):
            # Identify the prefix used
            for prefix in prefixes:
                if word.startswith(prefix):
                    command = word[len(prefix):].strip()
                    break

            # Handle special commands like log
            if command == 'log':
                await handle_log_file(message)
                return

            # Handle special commands like list
            if command in ["list", "triggers", "commands", "help", "cmd", "cmds"]:
                await send_trigger_list(message.channel, message.author.id)
                return

            if command in ['hugh', 'progress']:
                await string = get_decomp_info()
                await message.channel.send(string)
                return

            # Now handle triggers
            if prefix in ['!']:
                # Process English triggers
                await process_trigger(message.channel, command, triggers_map, esl_triggers_with_exclamation_map)
                return  # Exit after processing a command
            elif prefix == '¡':
                # Process ESL triggers
                await process_esl_trigger(message.channel, command, triggers_esl_map)
                return  # Exit after processing a command

async def process_trigger(channel, command, triggers_map, esl_triggers_with_exclamation_map):
    command_lower = command.lower()

    if command_lower in triggers_map:
        response = triggers_map[command_lower]
        await handle_response(channel, response)
        return

    if command_lower in esl_triggers_with_exclamation_map:
        response = esl_triggers_with_exclamation_map[command_lower]
        await handle_response(channel, response)
        return

    if command_lower in triggers_esl_map:
        response = triggers_esl_map[command_lower]
        await handle_response(channel, response)
        return

    print(f"Command '!{command}' not found.")

async def process_esl_trigger(channel, command, triggers_esl_map):
    command_lower = command.lower()

    if command_lower in triggers_esl_map:
        response = triggers_esl_map[command_lower]
        await handle_response(channel, response)
        return

    print(f"Command '¡{command}' not found.")

async def send_trigger_list(channel, user_id):
    # Collect English triggers and aliases
    english_triggers = []
    english_aliases_dict = {}
    for value in triggers.values():
        if value['triggers']:
            original_trigger = value['triggers'][0]
            english_triggers.append(original_trigger)
            if len(value['triggers']) > 1:
                english_aliases_dict[original_trigger] = value['triggers'][1:]

    # Collect Spanish triggers and aliases
    spanish_triggers = []
    spanish_aliases_dict = {}
    for value in triggers_esl.values():
        if value['triggers']:
            original_trigger = value['triggers'][0]
            spanish_triggers.append(original_trigger)
            if len(value['triggers']) > 1:
                spanish_aliases_dict[original_trigger] = value['triggers'][1:]

    # Remove duplicates and sort triggers
    english_triggers = sorted(set(english_triggers))
    spanish_triggers = sorted(set(spanish_triggers))
    english_aliases_dict = {key: sorted(english_aliases_dict[key]) for key in sorted(english_aliases_dict)}
    spanish_aliases_dict = {key: sorted(spanish_aliases_dict[key]) for key in sorted(spanish_aliases_dict)}

    # Combine English and Spanish triggers
    unique_triggers = english_triggers + spanish_triggers
    alias_triggers_dict = {**english_aliases_dict, **spanish_aliases_dict}

    # Create pagination view
    view = PaginatorView(unique_triggers, alias_triggers_dict, user_id=user_id)
    embed = view.get_embed()
    view.message = await channel.send(embed=embed, view=view)


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

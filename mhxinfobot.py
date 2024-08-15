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

# Constants
COLUMNS = 3  # Number of columns to display
COLUMNS_ALIAS = 2  # Number of columns to display for aliases
EMBED_TIMEOUT = 60  # Timeout in seconds

class PaginatorView(discord.ui.View):
    def __init__(self, triggers, alias_triggers_dict, user_id, show_aliases=False):
        super().__init__(timeout=EMBED_TIMEOUT)
        self.triggers = triggers
        self.alias_triggers_dict = alias_triggers_dict
        self.user_id = user_id
        self.show_aliases = show_aliases
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
        embed = discord.Embed(title="Available Triggers" if not self.show_aliases else "Alias Triggers", color=discord.Color.blue())
        
        start_idx = self.current_page * self.items_per_page * (COLUMNS if not self.show_aliases else COLUMNS_ALIAS)
        end_idx = start_idx + self.items_per_page * (COLUMNS if not self.show_aliases else COLUMNS_ALIAS)
        
        if self.show_aliases:
            items_page = self.current_items[start_idx:end_idx]
            alias_columns = [items_page[i * self.items_per_page:(i + 1) * self.items_per_page] for i in range(COLUMNS_ALIAS)]
            
            for i, col in enumerate(alias_columns):
                if col:
                    value = "\n\n".join(f"**{trigger}**\n{', '.join(aliases)}" for trigger, aliases in col)
                else:
                    value = "\u200B"
                embed.add_field(name="Aliases" if i == 0 else "\u200B", value=value, inline=True)
        else:
            items_page = self.current_items[start_idx:end_idx]
            trigger_columns = [items_page[i * self.items_per_page:(i + 1) * self.items_per_page] for i in range(COLUMNS)]

            for i, col in enumerate(trigger_columns):
                if col:
                    value = "\n\n".join(col)
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

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    normalized_content = message.content.lower().split()

    if "!list" in normalized_content:
        await send_trigger_list(message.channel, message.author.id)
        return

    for response in triggers.values():
        if any(trigger.lower() in normalized_content for trigger in response['triggers']):
            await handle_response(message.channel, response)
            break  # Stop after sending one trigger action

async def send_trigger_list(channel, user_id):
    unique_triggers = []
    alias_triggers_dict = {}

    for value in triggers.values():
        if value['triggers']:
            original_trigger = value['triggers'][0]  # Original trigger
            unique_triggers.append(original_trigger)
            if len(value['triggers']) > 1:
                alias_triggers_dict[original_trigger] = value['triggers'][1:]  # Aliases

    # Sort triggers and aliases
    unique_triggers = sorted(unique_triggers)
    alias_triggers_dict = {key: alias_triggers_dict[key] for key in sorted(alias_triggers_dict)}

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

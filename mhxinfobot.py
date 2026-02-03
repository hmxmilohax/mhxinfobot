from datetime import datetime
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
import requests
from discord.ext import tasks
from collections import defaultdict, deque, Counter
import asyncio
from datetime import timedelta

# --- Spam watchdog config ---
SPAM_REPORT_CHANNEL_ID = 961395552329818142

BOT_START_TIME = datetime.utcnow()
BOOT_INFO_CHANNEL_ID = 1146938356664639589
_boot_info_posted = False

SPAM_WINDOW_SECONDS = 9
SPAM_MIN_MESSAGES = 3
SPAM_MIN_CHANNELS = 3

SPAM_REQUIRE_DUPLICATE_PAYLOAD = True
SPAM_MIN_DUPLICATES = 3

SPAM_ACTION_COOLDOWN_SECONDS = 60

UPSTREAM_REPO = config.get("upstream_repo", "hmxmilohax/mhxinfobot")
UPSTREAM_BRANCH = config.get("upstream_branch", "main")

_recent_user_messages = defaultdict(lambda: deque())
_last_spam_action = {}  # (guild_id, user_id) -> datetime

# --- Scam / solicitation pitch watchdog ---
SCAM_PITCH_ENABLED = True

SCAM_PITCH_MIN_TEXT_LEN = 280          # long pitchy posts
SCAM_PITCH_MIN_SCORE = 7               # tune this
SCAM_PITCH_NEW_MEMBER_MAX_DAYS = 14    # only punish new joiners

# If you want to only enforce in certain channels, set this list.
# Leave empty to enforce everywhere except SPAM_REPORT_CHANNEL_ID.
SCAM_PITCH_CHANNEL_ALLOWLIST = []  # e.g. [123, 456]

SCAM_PITCH_PHRASES = [
    "open to projects",
    "open to roles",
    "looking for paid",
    "long-term contracts",
    "full-time roles",
    "hiring",
    "dm me",
    "d*m me",
    "message me",
    "reach out",
]

SCAM_PITCH_KEYWORDS = [
    # common buzzwords in these scams
    "blockchain",
    "web3",
    "defi",
    "nft",
    "dao",
    "solidity",
    "rust",
    "evm",
    "solana",
    "ai",
    "llm",
    "rag",
    "autonomous",
    "agents",
    "workflow automation",
    "multimodal",
    "saas",
]

def get_decomp_info():
    frogress_json = json.load(urlreq.urlopen("https://progress.decomp.club/data/rb3/SZBE69_B8/dol/"))
    # remove wrapper sludge
    frogress_data = frogress_json['rb3']['SZBE69_B8']['dol'][0]
    # Parse the timestamp into a datetime object
    dt = datetime.utcfromtimestamp(frogress_data['timestamp'])
    decomp_commit_time = dt.strftime("%B %d %Y, %I:%M:%S %p")
    return (
        f"# Rock Band 3 Decompilation\n"
        f"Last commit: **{decomp_commit_time}** *({frogress_data['git_hash'][0:7]})*\n\n"
        f"**{frogress_data['measures']['matched_code'] / frogress_data['measures']['matched_code/total'] * 100:.2f}%** matched code\n"
        f"**{frogress_data['measures']['code'] / frogress_data['measures']['code/total'] * 100:.2f}%** linked code (i.e. fully complete, in-order)\n"
        f"**{frogress_data['measures']['matched_data'] / frogress_data['measures']['matched_data/total'] * 100:.2f}%** matched data\n"
        f"**{frogress_data['measures']['matched_functions'] / frogress_data['measures']['matched_functions/total'] * 100:.2f}%** matching functions\n\n"
        "<https://rb3dx.milohax.org/decomp>"
    )

# Load the config file
with open('config.json') as config_file:
    config = json.load(config_file)

GITHUB_TOKEN = config.get('github_token')
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
EXTRA_REPOS = config.get("extra_repos", [])
IGNORED_REPOS = [
    "amp-2016-customs",
    "AmpHelper",
    "GH2DX-Site",
    "MiloHax-Site "
]

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

def _fmt_uptime(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return ", ".join(parts)

def _rel_time_from_dt(dt: datetime | None) -> str:
    if not dt:
        return "Unknown"
    now = datetime.now(timezone.utc)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return "Just now"
    if secs < 3600:
        m = secs // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if secs < 86400:
        h = secs // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = secs // 86400
    return f"{d} day{'s' if d != 1 else ''} ago"

def _get_latest_upstream_via_github() -> dict:
    """
    Uses GitHub API to fetch latest commit on UPSTREAM_BRANCH and its changed files.
    Returns dict with:
      - repo, branch, sha, sha_short, date_dt, rel, message, url
      - files (list of dicts with filename/additions/deletions/changes)
      - stats (additions/deletions/total)
    """
    info = {
        "repo": UPSTREAM_REPO,
        "branch": UPSTREAM_BRANCH,
        "sha": None,
        "sha_short": None,
        "date_dt": None,
        "rel": None,
        "message": None,
        "url": None,
        "files": [],
        "stats": None,
        "error": None,
    }

    if not GITHUB_TOKEN:
        info["error"] = "Missing github_token in config.json"
        return info

    if not UPSTREAM_REPO or "/" not in UPSTREAM_REPO:
        info["error"] = "Missing upstream_repo (expected 'owner/repo')"
        return info

    owner, name = UPSTREAM_REPO.split("/", 1)

    # 1) Get latest commit on the branch
    commits_url = f"https://api.github.com/repos/{owner}/{name}/commits"
    r = requests.get(commits_url, headers=HEADERS, params={"sha": UPSTREAM_BRANCH, "per_page": 1}, timeout=15)
    if r.status_code != 200:
        info["error"] = f"GitHub API error listing commits: {r.status_code}"
        return info

    commits = r.json() or []
    if not commits:
        info["error"] = "No commits returned"
        return info

    latest = commits[0]
    sha = latest.get("sha")
    info["sha"] = sha
    info["sha_short"] = (sha or "")[:7] or None
    info["url"] = latest.get("html_url")

    commit_obj = (latest.get("commit") or {})
    msg = (commit_obj.get("message") or "").splitlines()[0].strip()
    info["message"] = msg or None

    # date: prefer committer date
    date_str = ((commit_obj.get("committer") or {}).get("date")) or ((commit_obj.get("author") or {}).get("date"))
    if date_str:
        # GitHub returns ISO8601 like "2026-02-03T12:34:56Z"
        info["date_dt"] = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        info["rel"] = _rel_time_from_dt(info["date_dt"])

    # 2) Get commit details to retrieve files + stats
    if sha:
        detail_url = f"https://api.github.com/repos/{owner}/{name}/commits/{sha}"
        r2 = requests.get(detail_url, headers=HEADERS, timeout=15)
        if r2.status_code == 200:
            detail = r2.json() or {}
            info["stats"] = detail.get("stats")
            files = detail.get("files") or []
            for f in files:
                info["files"].append({
                    "filename": f.get("filename"),
                    "additions": f.get("additions"),
                    "deletions": f.get("deletions"),
                    "changes": f.get("changes"),
                })

    return info

async def build_info_embed(client: discord.Client) -> discord.Embed:
    upstream = await asyncio.to_thread(_get_latest_upstream_via_github)

    uptime = _fmt_uptime(datetime.utcnow() - BOT_START_TIME)
    ping_ms = client.latency * 1000.0

    embed = discord.Embed(
        title="MHXInfoBot - Info",
        color=discord.Color.purple()
    )

    embed.add_field(name="Uptime", value=uptime, inline=False)
    embed.add_field(name="Ping", value=f"{ping_ms:.2f}ms", inline=True)

    # Latest upstream info (GitHub API)
    if upstream.get("error"):
        embed.add_field(
            name="Latest Upstream Info",
            value=f"Unavailable — {upstream['error']}",
            inline=False
        )
        embed.set_footer(text="Tip: set upstream_repo + upstream_branch in config.json")
        return embed

    sha_short = upstream.get("sha_short") or "Unknown"
    rel = upstream.get("rel") or ""
    msg = upstream.get("message") or ""
    url = upstream.get("url") or ""

    latest_line = f"`{sha_short}` {rel}".strip()
    desc = "\n".join(x for x in [latest_line, msg, f"<{url}>" if url else ""] if x).strip()

    embed.add_field(
        name=f"Latest Upstream Info ({upstream.get('repo')}/{upstream.get('branch')})",
        value=desc[:1024] if desc else "Unknown",
        inline=False
    )

    # “Just give me the changes” (files touched in latest commit)
    files = upstream.get("files") or []
    stats = upstream.get("stats") or {}

    if files:
        # keep it short enough for an embed field
        lines = []
        for f in files[:10]:
            fn = f.get("filename") or "?"
            a = f.get("additions")
            d = f.get("deletions")
            if isinstance(a, int) and isinstance(d, int):
                lines.append(f"• `{fn}` (+{a}/-{d})")
            else:
                lines.append(f"• `{fn}`")

        more = len(files) - 10
        if more > 0:
            lines.append(f"…and {more} more")

        summary_bits = []
        if isinstance(stats.get("additions"), int) and isinstance(stats.get("deletions"), int):
            summary_bits.append(f"Total: +{stats['additions']}/-{stats['deletions']}")
        if isinstance(stats.get("total"), int):
            summary_bits.append(f"Δ {stats['total']}")

        header = " | ".join(summary_bits).strip()
        value = ("\n".join(([header] if header else []) + lines)).strip()

        embed.add_field(
            name="Changes",
            value=value[:1024],
            inline=False
        )
    else:
        embed.add_field(
            name="Changes",
            value="No file list available for the latest commit.",
            inline=False
        )

    embed.set_footer(text="Tip: use !help to get a list of available triggers.")
    return embed


async def send_info_embed_to_channel(channel: discord.abc.Messageable, client: discord.Client):
    embed = await build_info_embed(client)
    await channel.send(embed=embed)

@client.event
async def on_ready():
    global _boot_info_posted
    print(f'Logged in as {client.user}!')
    check_actions_staleness.start()   # kick off the daily loop

    if _boot_info_posted:
        return

    ch = client.get_channel(BOOT_INFO_CHANNEL_ID)
    if ch is None:
        try:
            ch = await client.fetch_channel(BOOT_INFO_CHANNEL_ID)
        except Exception as e:
            print(f"Failed to fetch boot info channel: {e}")
            return

    try:
        await send_info_embed_to_channel(ch, client)
        _boot_info_posted = True
    except Exception as e:
        print(f"Failed to post boot info embed: {e}")


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
        # Now analyze_log_file returns (summary, debug_txt_path)
        summary, debug_txt = analyze_log_file(decompressed_log_path)

        # Send the short summary as before
        embed = discord.Embed(title="Log Analysis Result", color=discord.Color.blue())
        embed.description = summary[:4096]
        await message.channel.send(embed=embed)

        # If we wrote out a debug file, upload it
        if debug_txt:
            await message.channel.send("Full debug info:", file=discord.File(debug_txt))
            os.remove(debug_txt)

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

    # --- Spam watchdog (ban + report) ---
    try:
        if await spam_watchdog(message):
            return
    except Exception as e:
        # Don’t let watchdog errors break the bot
        print(f"Spam watchdog error: {e}")

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

            if command == 'actions':
                await check_actions_staleness()  # manual trigger
                return

            # Handle special commands like list
            if command in ["list", "triggers", "commands", "help", "cmd", "cmds"]:
                await send_trigger_list(message.channel, message.author.id)
                return

            if command in ['hugh', 'progress']:
                await message.channel.send(get_decomp_info())
                return

            if command == 'info':
                await send_info_embed_to_channel(message.channel, client)
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

@tasks.loop(hours=24)
async def check_actions_staleness():
    """
    Checks all repos under hmxmilohax (minus IGNORED_REPOS) + any EXTRA_REPOS
    for their most recent GitHub Actions run. If the latest run is 89 days or older,
    reports it to the designated channel.
    """
    stale = []

    # 1) List all hmxmilohax repos
    repos_url = "https://api.github.com/users/hmxmilohax/repos?per_page=100"
    resp = requests.get(repos_url, headers=HEADERS)
    resp.raise_for_status()

    # build a list of (owner, name), skipping ignored
    monitored = [
        ("hmxmilohax", r["name"])
        for r in resp.json()
        if r["name"] not in IGNORED_REPOS
    ]

    # 2) Add any extras from config
    for repo_full in EXTRA_REPOS:
        if "/" in repo_full:
            owner, name = repo_full.split("/", 1)
        else:
            owner, name = "hmxmilohax", repo_full
        if (owner, name) not in monitored:
            monitored.append((owner, name))

    # 3) Check each one’s latest run
    for owner, name in monitored:
        runs_url = f"https://api.github.com/repos/{owner}/{name}/actions/runs?per_page=1"
        r2 = requests.get(runs_url, headers=HEADERS)
        if r2.status_code != 200:
            continue
        runs = r2.json().get("workflow_runs", [])
        if not runs:
            continue

        latest = runs[0]
        run_id = latest["id"]
        created = datetime.fromisoformat(latest["created_at"].rstrip("Z"))

        # ✅ Check if that run has any artifacts
        artifacts_url = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{run_id}/artifacts"
        r3 = requests.get(artifacts_url, headers=HEADERS)
        if r3.status_code != 200:
            continue
        artifact_data = r3.json()
        if not artifact_data.get("artifacts"):  # skip repos with no artifacts
            continue

        if (datetime.utcnow() - created).days >= 89:
            display = name if owner == "hmxmilohax" else f"{owner}/{name}"
            stale.append((display, created.date(), latest["html_url"]))

    # 4) Build and send a pretty embed
    channel = client.get_channel(1186453136731287642)
    if not channel:
        return

    if stale:
        embed = discord.Embed(
            title="🛠️ Stale GitHub Actions",
            description="Workflows with no runs in the last 89 days:",
            color=discord.Color.orange()
        )
        lines = [
            f"• **{repo}** — last run `{when}`: <{url}>"
            for repo, when, url in stale
        ]
        embed.add_field(
            name=f"{len(stale)} stale repos",
            value="\n".join(lines),
            inline=False
        )
    else:
        return

    await channel.send(embed=embed)

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

def _now_utc():
    return datetime.utcnow()

def _normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = " ".join(s.split())
    return s

def _attachment_sig(att: discord.Attachment) -> str:
    # No file hashing needed; metadata is enough for “same image pasted everywhere”
    # (filename/size/content_type are stable in typical spam)
    return f"{att.filename}|{att.size}|{att.content_type or ''}"

def _message_payload_signature(message: discord.Message) -> str:
    """
    One string representing what was posted:
    - normalized text (if any)
    - attachment metadata (if any)
    - embed urls (rare, but helps)
    """
    parts = []

    txt = _normalize_text(message.content)
    if txt:
        parts.append(f"txt:{txt}")

    if message.attachments:
        atts = ",".join(_attachment_sig(a) for a in message.attachments)
        parts.append(f"att:{atts}")

    # sometimes spam comes as embeds (link previews)
    if message.embeds:
        urls = []
        for e in message.embeds:
            if getattr(e, "url", None):
                urls.append(e.url)
        if urls:
            parts.append("emb:" + ",".join(urls))

    return " || ".join(parts)

async def _get_channel_safe(channel_id: int):
    ch = client.get_channel(channel_id)
    if ch:
        return ch
    try:
        return await client.fetch_channel(channel_id)
    except Exception:
        return None

async def _iter_sweep_targets(guild: discord.Guild):
    # Text/news channels (includes announcement channels)
    for ch in guild.text_channels:
        yield ch

    # Also include any active threads (public/private) the bot can see
    # discord.py supports guild.active_threads() to fetch them.
    try:
        threads = await guild.active_threads()
        for th in threads:
            yield th
    except Exception:
        # Fallback: cached threads (may be incomplete)
        for th in getattr(guild, "threads", []):
            yield th


async def _sweep_recent_everywhere(
    guild: discord.Guild,
    user_id: int,
    minutes: int = 60,
    per_channel_limit: int = 500,
):
    """
    Best-effort sweep: delete messages from user in ALL channels/threads the bot can access,
    limited to the last N minutes.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    deleted = 0

    async for ch in _iter_sweep_targets(guild):
        # Must support history()
        if not hasattr(ch, "history"):
            continue

        try:
            async for msg in ch.history(limit=per_channel_limit, after=cutoff):
                if msg.author and msg.author.id == user_id:
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass
        except Exception:
            pass

    return deleted

async def _delete_message_by_id(guild: discord.Guild, channel_id: int, message_id: int) -> bool:
    ch = guild.get_channel(channel_id)
    if ch is None:
        try:
            ch = await guild.fetch_channel(channel_id)
        except Exception:
            return False

    try:
        msg = await ch.fetch_message(message_id)
        await msg.delete()
        return True
    except discord.NotFound:
        return True  # already gone is fine
    except discord.Forbidden:
        return False
    except Exception:
        return False

async def _ban_and_report_for_spam(message: discord.Message, evidence: list[dict], reason: str):
    guild = message.guild
    if not guild:
        return

    # 1) Delete evidence messages first (best-effort)
    deleted = 0
    failed_delete = 0
    for e in evidence:
        ok = await _delete_message_by_id(guild, e["channel_id"], e["message_id"])
        if ok:
            deleted += 1
        else:
            failed_delete += 1

    # 2) Softban: Ban (purge) then Unban (so it's effectively a kick + cleanup)
    ban_error = None
    unban_error = None

    try:
        try:
            # discord.py newer
            await guild.ban(message.author, reason=reason, delete_message_seconds=3600)
        except TypeError:
            # discord.py older
            await guild.ban(message.author, reason=reason, delete_message_days=1)
    except Exception as e:
        ban_error = e

    if ban_error is None:
        # Small delay helps avoid occasional race conditions between ban/unban
        await asyncio.sleep(1)

        try:
            # Use an Object by ID so this works even if Member object is stale post-ban
            await guild.unban(discord.Object(id=message.author.id), reason=f"Softban release: {reason}")
        except Exception as e:
            unban_error = e

    extra_deleted = await _sweep_recent_everywhere(
        guild,
        message.author.id,
        minutes=60,
        per_channel_limit=500
    )

    # 3) Report (and include whether unban succeeded)
    report_ch = await _get_channel_safe(SPAM_REPORT_CHANNEL_ID)
    if not report_ch:
        return

    if ban_error is not None:
        embed = discord.Embed(title="Spam watchdog: softban failed (ban step)", color=discord.Color.red())
        embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Delete results", value=f"deleted={deleted}, failed={failed_delete}", inline=False)
        embed.add_field(name="Error", value=str(ban_error)[:1024], inline=False)
        await report_ch.send(embed=embed)
        return

    chan_ids = [e["channel_id"] for e in evidence]
    unique_channels = sorted(set(chan_ids))
    channel_mentions = ", ".join(f"<#{cid}>" for cid in unique_channels[:25]) or "None"

    links = [e.get("jump_url") for e in evidence if e.get("jump_url")]
    payloads = [e.get("payload_sig") for e in evidence if e.get("payload_sig")]
    sample_payload = payloads[-1] if payloads else None

    title = "Spam watchdog: user softbanned"
    color = discord.Color.orange()

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="User", value=f"{message.author} (<@{message.author.id}>)", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Delete results", value=f"deleted={deleted}, failed={failed_delete}", inline=False)
    embed.add_field(name="Channels hit (window)", value=channel_mentions[:1024], inline=False)

    if unban_error is None:
        embed.add_field(name="Unban", value="✅ Unbanned (softban complete)", inline=False)
    else:
        embed.add_field(
            name="Unban",
            value=f"⚠️ Unban failed — user may still be banned\n{str(unban_error)[:900]}",
            inline=False
        )

    if links:
        embed.add_field(name="Message links", value="\n".join(links[:10])[:1024], inline=False)

    if sample_payload:
        embed.add_field(name="Sample payload", value=sample_payload[:1024], inline=False)

    await report_ch.send(embed=embed)


async def spam_watchdog(message: discord.Message) -> bool:
    if not message.guild:
        return False
    if message.author.bot:
        return False
    if message.channel.id == SPAM_REPORT_CHANNEL_ID:
        return False

    # avoid banning staff/mods
    perms = message.author.guild_permissions
    if perms.administrator or perms.manage_guild or perms.manage_messages or perms.ban_members or perms.kick_members:
        return False

    now = _now_utc()
    key = (message.guild.id, message.author.id)

    last = _last_spam_action.get(key)
    if last and (now - last).total_seconds() < SPAM_ACTION_COOLDOWN_SECONDS:
        return False

    payload_sig = _message_payload_signature(message)
    if not payload_sig:
        return False  # ignore empty/noise

    # --- Scam pitch watchdog (single message) ---
    if SCAM_PITCH_ENABLED:
        if message.channel.id != SPAM_REPORT_CHANNEL_ID and _scam_pitch_allowed_in_channel(message.channel.id):
            member = message.author if isinstance(message.author, discord.Member) else None

            # Guardrails: only auto-action on new members (reduce false positives)
            if member and _is_new_member(member):
                score = _scam_pitch_score(message)
                if score >= SCAM_PITCH_MIN_SCORE:
                    _last_spam_action[key] = now

                    evidence = [{
                        "ts": now,
                        "channel_id": message.channel.id,
                        "message_id": message.id,
                        "jump_url": getattr(message, "jump_url", None),
                        "payload_sig": payload_sig,
                    }]

                    reason = f"Spam watchdog (softban): solicitation/scam pitch heuristic (score={score})"
                    await _ban_and_report_for_spam(message, evidence, reason)
                    return True

    bucket = _recent_user_messages[key]
    bucket.append({
        "ts": now,
        "channel_id": message.channel.id,
        "message_id": message.id,
        "jump_url": getattr(message, "jump_url", None),
        "payload_sig": payload_sig,
    })

    # prune
    window_start = now.timestamp() - SPAM_WINDOW_SECONDS
    while bucket and bucket[0]["ts"].timestamp() < window_start:
        bucket.popleft()

    if len(bucket) < SPAM_MIN_MESSAGES:
        return False

    channels = {e["channel_id"] for e in bucket}
    if len(channels) < SPAM_MIN_CHANNELS:
        return False

    if SPAM_REQUIRE_DUPLICATE_PAYLOAD:
        sigs = [e["payload_sig"] for e in bucket if e.get("payload_sig")]
        most_common = Counter(sigs).most_common(1)[0][1] if sigs else 0
        if most_common < SPAM_MIN_DUPLICATES:
            return False

    _last_spam_action[key] = now

    reason = (
        f"Spam watchdog: {len(bucket)} msgs in {SPAM_WINDOW_SECONDS}s "
        f"across {len(channels)} channels"
        + (f", duplicate_payload={SPAM_MIN_DUPLICATES}+" if SPAM_REQUIRE_DUPLICATE_PAYLOAD else "")
    )

    evidence = list(bucket)
    bucket.clear()

    await _ban_and_report_for_spam(message, evidence, reason)
    return True

def _text_contains_any(text: str, phrases: list[str]) -> bool:
    t = _normalize_text(text)
    return any(p in t for p in phrases)

def _count_hits(text: str, phrases: list[str]) -> int:
    t = _normalize_text(text)
    return sum(1 for p in phrases if p in t)

def _lines_with_colon(text: str) -> int:
    # These scam pitches often have "Blockchain:", "AI:", "Fullstack:" etc.
    lines = (text or "").splitlines()
    return sum(1 for ln in lines if ":" in ln and len(ln.strip()) <= 60)

def _scam_pitch_score(message: discord.Message) -> int:
    """
    Score a single message for solicitation/pitch scam patterns.
    Higher score => more likely scam.
    """
    text = message.content or ""
    t = _normalize_text(text)
    if not t:
        return 0

    score = 0

    # Long, structured pitch
    if len(t) >= SCAM_PITCH_MIN_TEXT_LEN:
        score += 2

    # Contains DM solicitation language
    if _text_contains_any(t, SCAM_PITCH_PHRASES):
        score += 4

    # Lots of buzzwords
    kw_hits = _count_hits(t, SCAM_PITCH_KEYWORDS)
    if kw_hits >= 4:
        score += 3
    elif kw_hits >= 2:
        score += 2
    elif kw_hits >= 1:
        score += 1

    # "Category:" formatting lines
    colons = _lines_with_colon(text)
    if colons >= 3:
        score += 2
    elif colons >= 2:
        score += 1

    # Bullet-ish structure often used
    if "\n" in text and any(prefix in text for prefix in ["•", "-", "—"]):
        score += 1

    return score

def _is_new_member(member: discord.Member) -> bool:
    if not member:
        return False
    if not getattr(member, "joined_at", None):
        return False
    delta = datetime.utcnow() - member.joined_at.replace(tzinfo=None)
    return delta.days <= SCAM_PITCH_NEW_MEMBER_MAX_DAYS

def _scam_pitch_allowed_in_channel(channel_id: int) -> bool:
    if not SCAM_PITCH_CHANNEL_ALLOWLIST:
        return True
    return channel_id in SCAM_PITCH_CHANNEL_ALLOWLIST


# Run the bot
client.run(config['bot_token'])

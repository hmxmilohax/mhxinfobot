
# MiloHax Info Bot

The **MiloHax Info Bot** is a Discord bot designed to provide quick and easy access to frequently requested information and resources related to various MiloHax projects, specifically focusing on Rock Band games. The bot responds to specific trigger phrases with predefined messages, links, and files to assist users in the Discord community.

## Features

- **Trigger-Based Responses**: The bot listens for specific trigger phrases in messages and responds with relevant information, links, or files.
- **Support for Long Responses**: Handles long messages by automatically breaking them into multiple messages, ensuring that each message adheres to Discord's 2000 character limit.
- **File Attachments**: Supports sending files like images, videos, and documents in response to triggers.
- **Configurable Triggers**: Triggers and responses are fully configurable via a `triggers.json` file.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/hmxmilohax/mhxinfobot.git
   cd mhxinfobot
   ```

2. **Install Dependencies**:
   Ensure you have Python installed. Install the required Python packages using pip:
   ```bash
   pip install discord.py
   ```

3. **Configuration**:
   - Create a `config.json` file in the root directory of the project with the following structure:
     ```json
     {
         "bot_token": "YOUR_DISCORD_BOT_TOKEN"
     }
     ```
   - Configure your triggers and responses in the `triggers.json` file. Each trigger can have associated text, files, and multiple trigger phrases.
   
   - Make sure that you edit the `mhxinfobot.py` file
     - Go to line 18 and make sure the Discord channel ID is set to a channel where you want alerts anytime the Watchdog goes off about a spammer
     - Go to line 393 and make sure the Discord channel ID is set to a channel that is set up as an announcement channel otherwise the program will error

4. **Run the Bot**:
   Start the bot by running:
   ```bash
   python mhxinfobot.py
   ```

## Usage

- **Adding Triggers**: Add your triggers and responses to the `triggers.json` file. Each entry should include:
  - `triggers`: A list of phrases that will trigger the response.
  - `text`: The text message to be sent when the trigger is detected.
  - `files`: An optional list of file paths that will be sent along with the message.

- **Example Entry in triggers.json**:
  ```json
  {
      "response1": {
          "triggers": ["amp", "ampdx"],
          "text": "Here is some information about Amplitude Deluxe.",
          "files": ["media/amp_info.png"]
      }
  }
  ```

## Example Triggers

- **!rb3dx**: Provides information and links related to Rock Band 3 Deluxe.
- **!xenia**: Details about the Xenia emulator and its limitations.
- **!ps3parental**: Instructions for PS3 users on disabling parental controls to allow custom songs.

## Contributing

Contributions are welcome! If you have ideas for additional triggers or improvements to the bot, feel free to open a pull request or submit an issue.
import discord
import pprint
import logging
import argparse
import shlex
import json


class ConfigClient():
    def __init__(self, bot_name, config_file='config.json'):
        self.parser = argparse.ArgumentParser(description='Parse config')
        self.parser.add_argument(
            "--text_channel",
            type=str,
            help="name of the channel you want the bot to post to.",
            default='')
        self.parser.add_argument(
            "--voice_channel",
            type=str,
            help="name of the voice channel you want the bot to join.",
            default='')

        self.config_file = config_file
        self.latest = self._get_config()
        self.name = bot_name

    def parse(self, msg):
        return self.parser.parse_args(shlex.split(msg))

    def update_config(self, new_config, guild_id):
        guild_id = str(guild_id)
        with open(self.config_file) as f:
            config = json.load(f)

        if guild_id not in config:
            config[guild_id] = {}

        config[guild_id][self.name] = new_config
        with open(self.config_file, 'w') as f:
            json.dump(config, f)

        self.latest = config

    def get_config(self, guild_id=None):
        if guild_id is None:
            return self.latest

        return self.latest.get(guild_id, {}).get(self.name, None)

    def _get_config(self):
        with open(self.config_file) as f:
            config = json.load(f)

        return config


class AmbienceClient(discord.Client):
    def __init__(self,
                 bot_name,
                 music_handler=None,
                 visual_handler=None,
                 logging_dir='ambience.log'):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents)
        self.bot_name = bot_name
        self.prefix = "({0})".format(bot_name)

        self.pp = pprint.PrettyPrinter(indent=2)
        self._initialize_logging(logging_dir)
        self.music_handler = music_handler
        self.config_client = ConfigClient(bot_name, "{0}_config.json".format(bot_name.replace(' ', '_')))

    async def on_ready(self):
        print('We have logged in as {0.user}.'.format(self))

        config = self.config_client.get_config()
        print('Using config:')
        self.pp.pprint(config)
        print('Logs stored at {0}.'.format(self.logging_dir))

    async def on_message(self, message):
        if message.author == self.user or message.author.bot:
            return

        if message.author.guild is None:
            return

        if message.content.startswith(self.prefix):
            try:
                args = self.config_client.parse(
                    message.content[len(self.prefix):])
                new_config = vars(args)
                self.config_client.update_config(new_config, message.author.guild.id)

                await message.channel.send(
                    'The config was updated successfully. :)')
            except Exception as e:
                print('error when updatin config', e)
                await message.channel.send(
                    'The config submitted was invalid, or the update failed. :('
                )

    async def on_voice_state_update(self, member, before, after):
        # Assume events are processed more or less synchronously... too lazy to implement this otherwise.
        # We just check if we need to join the room.
        # Leaving is taken care of by the periodic task.

        if after.channel is not None:
            our_name = self.config['bot name']
            if not our_name in [x.name for x in after.channel.members]:
                # join the room, and start playing music.
                await after.channel.connect()

    def _initialize_logging(self, logging_dir):
        logger = logging.getLogger('discord')
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(filename=logging_dir,
                                      encoding='utf-8',
                                      mode='w')
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        logger.addHandler(handler)
        self.logging_dir = logging_dir
        self.logger = logger

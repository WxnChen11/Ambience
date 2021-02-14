import discord
import pprint
import logging
import argparse
import shlex
import json

class ConfigClient():
    def __init__(self, bot_id, config_file='config.json', default_config_file='default_config.json'):
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
        self.bot_id = bot_id

        with open(default_config_file) as f:
            self.default_config = json.load(f)

    def parse(self, msg):
        return self.parser.parse_args(shlex.split(msg))

    def update_config(self, new_config, guild_id):
        guild_id = str(guild_id)
        with open(self.config_file) as f:
            config = json.load(f)

        if guild_id not in config:
            config[guild_id] = {}

        config[guild_id][self.bot_id] = new_config
        with open(self.config_file, 'w') as f:
            json.dump(config, f)

        self.latest = config

    def get_config(self, guild_id=None):
        guild_id = str(guild_id)
        if guild_id is None:
            return self.latest

        return self.latest.get(guild_id, self.default_config).get(self.bot_id, None)

    def _get_config(self):
        with open(self.config_file) as f:
            config = json.load(f)

        return config


class AmbienceClient(discord.Client):
    def __init__(self,
                 bot_name,
                 bot_id,
                 music_handler=None,
                 visual_handler=None,
                 logging_dir='ambience.log'):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents)
        self.bot_name = bot_name
        self.bot_id = bot_id
        self.prefix = "({0})".format(bot_name)

        self.pp = pprint.PrettyPrinter(indent=2)
        self._initialize_logging(logging_dir)
        self.music_handler = music_handler
        self.config_client = ConfigClient(
            str(bot_id), "{0}_config.json".format(bot_name.replace(' ', '_')))

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
                self.config_client.update_config(new_config,
                                                 message.author.guild.id)

                await message.channel.send(
                    'The config was updated successfully. :)')
            except Exception as e:
                print('error when updatin config', e)
                await message.channel.send(
                    'The config submitted was invalid, or the update failed: ' + str(e) + '.' 
                )

    async def on_voice_state_update(self, member, before, after):
        # Assume events are processed more or less synchronously... too lazy to implement this otherwise.
        # Check if we need to join the room, or leave the room.

        if after.channel is not None:
            guild = member.guild.id
            voice_channel_to_join = self.config_client.get_config(guild)['voice_channel']

            if (after.channel.name != voice_channel_to_join):
              return

            if not self.bot_id in [x.id for x in after.channel.members]:
                # see if we have an active connection already.
                existing_vc = [x for x in self.voice_clients
                    if x.guild and x.guild.id == member.guild.id]

                if len(existing_vc) > 0 and existing_vc[0].channel != after.channel:
                    await existing_vc[0].move_to(after.channel)
                else:
                    existing_vc.append(await after.channel.connect())
                    # play a song

                voice = existing_vc[0]
                if not voice.is_playing():
                    self.audio = 'test.mp3'
                    self.voice = voice
                    self._repeat_audio()
                    # voice.play(self.audio, after=lambda e: self._repeat_audio(voice, self.audio))

        if before.channel is not None:
            guild = member.guild.id

            if self.bot_id in [x.id for x in before.channel.members]:
                # see if there are any remaining non-bot members.
                nonbots = len([x for x in before.channel.members if not x.bot])
                if nonbots == 0:
                  existing_vc = [x for x in self.voice_clients
                    if x.channel == before.channel]
                  if len(existing_vc) > 0:
                    await existing_vc[0].disconnect()

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

    def _repeat_audio(self):
        audio = discord.FFmpegPCMAudio(self.audio)
        try: 
          self.voice.play(audio, after=lambda e: self._repeat_audio())
        except Exception as e:
          print('Failed to repeat audio: ', e)


# Add a scheduled job, every ~1h, that uses get_all_channels and the configs to find out which channels
# it should send a picture and quote to.
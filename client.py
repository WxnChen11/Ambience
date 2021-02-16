import discord
import pprint
import logging
import argparse
import shlex
import json
import os
import random
import datetime
import asyncio
import csv

from collections import defaultdict
from os import listdir
from os.path import isfile, join
from threading import Timer

from discord.ext import tasks


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
        self.parser.add_argument(
            "--mode",
            type=str,
            help="mode to run in. One of SOCIAL|FOCUS",
            choices=['', 'SOCIAL', 'FOCUS'],
            default='')

        self.config_file = config_file

        with open(self.config_file) as f:
            config = json.load(f)

        self.latest = config
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
        if self.bot_id not in config[guild_id]:
            config[guild_id][self.bot_id] = {}

        empty_keys = [k for k, v in new_config.items() if not v]
        for k in empty_keys:
            del new_config[k]

        config[guild_id][self.bot_id].update(new_config)
        with open(self.config_file, 'w') as f:
            json.dump(config, f)

        self.latest = config

    def get_config(self, guild_id=None):
        if guild_id is None:
            return self.latest

        guild_id = str(guild_id)
        return self.latest.get(guild_id, {}).get(self.bot_id, None)

    def _get_config(self):
        with open(self.config_file) as f:
            config = json.load(f)

        return config


class AmbienceClient(discord.Client):
    def __init__(self,
                 bot_name,
                 bot_id,
                 media_dir,
                 music_handler=None,
                 visual_handler=None,
                 logging_dir='ambience.log'):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents)
        self.bot_name = bot_name
        self.bot_id = int(bot_id)
        self.prefix = "({0})".format(bot_name)
        self.media_dir = media_dir

        self.pp = pprint.PrettyPrinter(indent=2)
        self._initialize_logging(logging_dir)
        self.music_handler = music_handler
        self.config_client = ConfigClient(
            str(bot_id), "{0}_config.json".format(bot_name.replace(' ', '_')))

        self.audio_dir = os.path.join(media_dir, 'audio')
        self.audio_files = [f for f in listdir(self.audio_dir) if isfile(join(self.audio_dir, f))]

        self.quotes_list = []

        with open(os.path.join(media_dir, 'quotes.txt'),  newline='') as quotesfile:
            reader = csv.reader(quotesfile, delimiter=';')
            for row in reader:
                self.quotes_list.append(row[0] + ' -' + row[1])

        self.images_dir = os.path.join(media_dir, 'images')
        self.image_files = [f for f in listdir(self.images_dir) if isfile(join(self.images_dir, f))]

        config = self.config_client.get_config()
        for _, bot_id_to_config in config.items():
            for _, bot_config in bot_id_to_config.items():
                self._send_picture.start(bot_config['text_channel'])

    async def on_ready(self):
        print('We have logged in as {0.user}.'.format(self))

        config = self.config_client.get_config()
        print('Using config:')
        self.pp.pprint(config)
        print('Logs stored at {0}.'.format(self.logging_dir))

    async def on_message(self, message):
        if message.author == self.user or message.author.guild is None or message.author.bot:
            return

        if message.content.startswith(self.prefix):
            try:
                old_config = self.config_client.get_config(
                    message.author.guild.id)
                args = self.config_client.parse(
                    message.content[len(self.prefix):])

                new_config = vars(args)
                guild_id = message.author.guild.id

                channels = self.get_guild(guild_id).channels

                if new_config['mode'] and (new_config['voice_channel'] or new_config['text_channel']):
                    await message.channel.send(
                        ':x: Cannot update mode at the same time as voice_channel or text_channel.'
                    )
                    return

                # map the names to ids.
                if new_config['voice_channel']:
                    new_config['voice_channel'] = next(
                        (x.id for x in channels if x.name.lower() == new_config['voice_channel'].lower()), 0)

                if new_config['text_channel']:
                    new_config['text_channel'] = next(
                        (x.id for x in channels if x.name.lower() == new_config['text_channel'].lower()), 0)

                self.config_client.update_config(new_config, guild_id)

                await message.channel.send(
                    ':white_check_mark: The config was updated successfully.')
                if 'mode' in new_config:
                    if (new_config['mode'] == 'SOCIAL'):
                        await message.channel.send(
                            ':partying_face: I am now set to social mode. Feel free to chat freely!')
                        await self._mute_all(old_config['voice_channel'], False)
                    # elif (new_config['mode'] == 'QUIET'):
                    #     await message.channel.send(
                    #         ':shushing_face: I am now set to quiet mode. Members are muted by default. Every 30min, there will be a 5 minute break.')
                    elif (new_config['mode'] == 'FOCUS'):
                        await message.channel.send(
                            ':mute: I am now set to focus mode. All members are muted.')
                        await self._mute_all(old_config['voice_channel'])

            except Exception as e:
                print('error when updating config', e)
                await message.channel.send(
                    ':x: The config submitted was invalid, or the update failed: ' +
                    str(e) + '.'
                )
            except SystemExit as e:
                print('error when updating config', e)
                await message.channel.send(
                    ':x: The config submitted was invalid, or the update failed. Are you sending in valid values for enum parameters (mode)?'
                )

    async def on_voice_state_update(self, member, before, after):
        # Assume events are processed more or less synchronously... too lazy to implement this otherwise.
        # Check if we need to join the room, or leave the room.

        if member.bot:
            return

        if after.channel is not None:
            guild = member.guild.id
            config = self.config_client.get_config(guild)
            muted_in_after = False
            if (after.channel.id == config['voice_channel']):
                if not self.bot_id in [x.id for x in after.channel.members]:
                    # see if we have an active connection already.
                    existing_vc = [x for x in self.voice_clients
                                if x.guild and x.guild.id == member.guild.id]

                    if len(existing_vc) > 0 and existing_vc[0].channel != after.channel:
                        await existing_vc[0].move_to(after.channel)
                    else:
                        # play a song
                        voice = await after.channel.connect()
                        self._repeat_audio(voice.session_id)

                # additionally, check mode.
                if (config['mode'] == 'FOCUS'):
                    # server mute.
                    if not after.mute:
                        await member.edit(mute=True)
                    muted_in_after = True

            # Either after is a vc that requires mute, or it's not. This is in the event that it's not.
            if not muted_in_after:
                # unmute.
                if after.mute:
                    await member.edit(mute=False)

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
                                      encoding = 'utf-8',
                                      mode = 'w')
        handler.setFormatter(
            logging.Formatter(
                '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        logger.addHandler(handler)
        self.logging_dir=logging_dir
        self.logger=logger

    def _repeat_audio(self, session_id):
        voice=next(
            (x for x in self.voice_clients if x.session_id == session_id), None)

        if voice is not None:
            random_file=random.choice(self.audio_files)
            audio=discord.FFmpegPCMAudio(
                os.path.join(self.audio_dir, random_file))
            try:
                voice.play(
                    audio, after = lambda e: self._repeat_audio(session_id))
            except Exception as e:
                print('Failed to repeat audio: ', e)

    def _mute_individual(self, guild_id, channel_name, member_id):
        # mute the individual if they are currently active in the channel.
        return

    async def _mute_all(self, channel_id, mute=True):
        # mute all members in the channel except for bots.
        channel = self.get_channel(channel_id)

        if channel is None or channel.members is None:
            return
        for member in channel.members:
            if not member.bot:
                await member.edit(mute=mute)
        return

    @tasks.loop(seconds=5.0)
    async def _send_picture(self, channel_id):
        channel = self.get_channel(channel_id)

        if channel is None:
            return
        
        now = datetime.datetime.now()
        file_name = random.choice(self.image_files)
        await channel.send("It is {0} on {1}. {2}".format(now.strftime("%H:%M:%S"), now.strftime("%m/%d/%Y"), random.choice(self.quotes_list)), file=discord.File(os.path.join(self.images_dir, file_name)))
        return

    @_send_picture.before_loop
    async def _send_picture_before(self):
        now = datetime.datetime.now()
        next_hour = (now + datetime.timedelta(hours=0)).replace(microsecond=0, second=0, minute=32)

        await asyncio.sleep((next_hour - now).total_seconds())

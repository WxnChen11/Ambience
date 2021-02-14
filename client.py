import discord
import pprint
import logging

class AmbienceClient(discord.Client):
  def __init__(self, config, music_handler=None, visual_handler=None, logging_dir='ambience.log'):
    intents = discord.Intents.default()
    intents.members = True

    super().__init__(intents=intents)
    self.pp = pprint.PrettyPrinter(indent=2)
    self.config = config
    self._initialize_logging(logging_dir)
    self.music_handler = music_handler

  async def on_ready(self):
    print('We have logged in as {0.user}.'.format(self))
    print('Using config:')
    self.pp.pprint(self.config)
    print('Logs stored at {0}.'.format(self.logging_dir))

  async def on_message(self, message):
    if message.author == self.user:
      return

    if message.content.startswith('-focus'):
      await message.channel.send('focus mode starting.')

    if message.content == "-give-badge":
      game = discord.Game("with the API")
      await self.change_presence(status=discord.Status.idle, activity=game)

  async def on_voice_state_update(self, member, before, after):
    # Assume events are processed more or less synchronously... too lazy to implement this otherwise.
    # We need to check two things. If before.channel is now empty or only contains the music bot, or
    # After now contains only a single non-music bot.

    before_has_nonbot_member = False
    if before.channel is not None:
      for member in before.channel.members:
        if not member.bot:
          before_has_nonbot_member = True
          break

      if not before_has_nonbot_member:
        # remove all the members (bots).
        for member in before.channel.members:
          await member.move_to(None)

    music_bot_in_after = False
    if after.channel is not None:
      music_bot_name = self.config['channel_config'][after.channel.name]['music bot name']
      for member in after.channel.members:
        if member.name == music_bot_name:
          music_bot_in_after = True
          break

      if not music_bot_in_after:
        # add the bot. to do this, we have to first join the channel ourselves, then type to join.
        join_command = self.config['channel_config'][after.channel.name]['music bot join']
        text_channel_name = self.config['channel_config'][after.channel.name]['chat room name']
        voice_client = await after.channel.connect()

        textchannel = next(x for x in self.get_all_channels() if x.name == text_channel_name) 

        await textchannel.send(join_command)
        await voice_client.disconnect()

  def _initialize_logging(self, logging_dir):
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename=logging_dir, encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)
    self.logging_dir = logging_dir
    self.logger = logger
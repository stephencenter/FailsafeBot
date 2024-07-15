import random
import asyncio
import yt_dlp
import discord
from discord.ext import commands
import helpers
import sound_manager

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

async def vcsound_command(context, update=None):
    if update is not None:
        return "That's Discord only, sorry"

    if context.voice_client is None:
        return "I'm not in a voice channel!"

    user_message = await helpers.get_args_list(context, update)

    # Alert the user if they forgot to provide a sound name
    if not user_message or user_message[0].isspace():
        return random.choice(sound_manager.txt_sound_not_provided)

    # Parse the arguments the user provided for the sound name
    sound_name = user_message[0].lower()
    sound_path = sound_manager.get_sound(sound_name)

    # Alert the user if the sound they requested does not exist
    if sound_path is None:
        return random.choice(sound_manager.txt_sound_not_found)

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))
    context.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

    await sound_manager.increment_playcount(sound_name)

async def vcrandom_command(context, update=None):
    if update is not None:
        return "That's Discord only, sorry!"

    if context.voice_client is None:
        return "I'm not in a voice channel!"

    sound_name, sound_path = sound_manager.get_random_sound()

    if context.voice_client.is_playing():
        context.voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))
    context.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

    await sound_manager.increment_playcount(sound_name)

async def vcstop_command(context, update=None):
    if update is not None:
        return

    try:
        await context.voice_client.stop()
    except (AttributeError, commands.errors.CommandInvokeError):
        pass

async def vcstream_command(context, update=None):
    if update is not None:
        return "That's Discord only, sorry!"

    if context.voice_client is None:
        return "I'm not in a voice channel!"

    try:
        stream_url = (await helpers.get_args_list(context, update))[0]
    except IndexError:
        return "Provide a streamable URL please!"

    if context.voice_client.is_playing():
        context.voice_client.stop()

    player = await YTDLSource.from_url(stream_url, loop=context.bot.loop, stream=True)

    async with context.typing():
        context.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

    await context.send(f'Now playing: {player.title}')

async def vcjoin_command(context, update=None):
    if update is not None:
        return "That's Discord only, sorry!"

    vc_converter = commands.VoiceChannelConverter()
    channel_name = ' '.join(await helpers.get_args_list(context))

    try:
        voice_channel = await vc_converter.convert(context, channel_name)
    except commands.errors.ChannelNotFound:
        return "Couldn't find that channel (note that channel names are case-sensitive)"

    if context.voice_client is not None:
        return await context.voice_client.move_to(voice_channel)

    await voice_channel.connect()

async def vcleave_command(context, update=None):
    if update is not None:
        return

    try:
        await context.voice_client.disconnect()
    except (AttributeError, commands.errors.CommandInvokeError):
        pass

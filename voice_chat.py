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

        if data is None:
            return

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

async def vcsound_command(context, update=None) -> helpers.CommandResponse:
    if update is not None:
        return helpers.CommandResponse("Hey, play that sound in the voice channel.", "That's Discord only, sorry")

    if context.voice_client is None:
        return helpers.CommandResponse("Hey, play that sound in the voice channel.", "I'm not in a voice channel!")

    user_message = await helpers.get_args_list(context, update)

    # Alert the user if they forgot to provide a sound name
    if not user_message or user_message[0].isspace():
        return helpers.CommandResponse("Hey, play that sound in the voice channel.", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    # Parse the arguments the user provided for the sound name
    sound_name = user_message[0].lower()
    sound_path = sound_manager.get_sound(sound_name)

    # Alert the user if the sound they requested does not exist
    if sound_path is None:
        return helpers.CommandResponse(f"Hey, play the sound {sound_name} in the voice channel.", random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))
    context.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

    await sound_manager.increment_playcount(sound_name)

    return helpers.CommandResponse(f"Hey, play the sound {sound_name} in the voice channel.", "Sure, here you go", send_to_chat=False)

async def vcrandom_command(context, update=None) -> helpers.CommandResponse:
    user_message = "Can you play a random sound for me?"

    if update is not None:
        return helpers.CommandResponse(user_message, "That's Discord only, sorry!")

    if context.voice_client is None:
        return helpers.CommandResponse(user_message, "I'm not in a voice channel!")

    sound_name, sound_path = sound_manager.get_random_sound()

    if context.voice_client.is_playing():
        context.voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))
    context.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

    await sound_manager.increment_playcount(sound_name)

    return helpers.CommandResponse(user_message, "Sure, I chose the sound '{sound_name}", send_to_chat=False)

async def vcstop_command(context, update=None) -> helpers.CommandResponse:
    if update is not None:
        return helpers.CommandResponse("Stop making all that noise please.", "That's Discord only, sorry!")

    try:
        await context.voice_client.stop()
    except (AttributeError, commands.errors.CommandInvokeError):
        pass

    return helpers.CommandResponse("Stop making all that noise please.", "If you insist.", send_to_chat=False)

async def vcstream_command(context, update=None) -> helpers.CommandResponse:
    if update is not None:
        return helpers.CommandResponse("Stream this for me please.", "That's Discord only, sorry!")

    if context.voice_client is None:
        return helpers.CommandResponse("Stream this for me please.", "I'm not in a voice channel!")

    try:
        stream_url = (await helpers.get_args_list(context, update))[0]
    except IndexError:
        return helpers.CommandResponse("Stream this for me please.", "Provide a streamable URL please!")

    if context.voice_client.is_playing():
        context.voice_client.stop()

    player = await YTDLSource.from_url(stream_url, loop=context.bot.loop, stream=True)
    if player is None:
        return helpers.CommandResponse("Stream this for me please.", "There was an error streaming from that URL.")

    async with context.typing():
        context.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

    await context.send(f'Now playing: {player.title}')

    return helpers.CommandResponse("Stream this for me please.", "Sure, here you go.")

async def vcjoin_command(context, update=None) -> helpers.CommandResponse:
    if update is not None:
        return helpers.CommandResponse("Join my voice channel please.", "That's Discord only, sorry!")

    target_voice = context.author.voice

    if target_voice is None:
        return helpers.CommandResponse("Join my voice channel please.", "You're not in a voice channel!")

    if context.voice_client is not None:
        await context.voice_client.move_to(target_voice.channel)

    else:
        await target_voice.channel.connect()

    return helpers.CommandResponse("Join my voice channel please.", "If you insist.", send_to_chat=False)

async def vcleave_command(context, update=None) -> helpers.CommandResponse:
    if update is not None:
        return helpers.CommandResponse("Leave the current voice channel please.", "That's Discord only, sorry!")

    try:
        await context.voice_client.disconnect()
    except (AttributeError, commands.errors.CommandInvokeError):
        pass

    return helpers.CommandResponse("Leave the current voice channel please.", "If you insist", send_to_chat=False)

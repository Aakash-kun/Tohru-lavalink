import re

# import nextcord
from nextcord.ext import commands
from nextcord.ext.commands import Context, CommandInvokeError

# import lavalink
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from internal.lavalink_voice_client import LavalinkVoiceClient
from internal.player import CustomPlayer
from internal.load_later_track import LoadLaterTrack
from internal.bot_base import BotBaseBot

URL_REGEX = re.compile(r'https?://(?:www\.)?.+')




class MusicCommands(commands.Cog):
    def __init__(self, bot: BotBaseBot) -> None:
        self.bot = bot
        self.spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=self.bot.config.get("spotify_client_id"), client_secret=self.bot.config.get("spotify_client_secret")))

    async def ensure_voice(self, ctx: Context):
        """Ensures that the bot is in a voice channel,
        the user is in a voice channel and the user and the bot are in the same voice channel.
        """
        if ctx.guild is None:
            try:
                ctx.send('This command can not be used in DMs.')
            except Exception:
                pass

        player: CustomPlayer = self.bot.lavalink.player_manager.create(
            guild_id=ctx.guild.id)

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise CommandInvokeError(
                "You must be in a Voice Channel to use this command.")

        should_connect = ctx.command.name in ('play',)

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError(
                    'I am not connected to a Voice Channel.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:
                raise commands.CommandInvokeError(
                    'I need the `CONNECT` and `SPEAK` permissions to play music.')

            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)

        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError(
                    'You need to be in my voicechannel.')

    async def play_from_url(self, ctx: Context, player: CustomPlayer, query: str):
        """ Play a track from a url. """
        if "open.spotify.com" in query:
            if "track" in query:
                track = self.spotify.track(query)
                query = f"ytsearch:{track['name']} - {track['artists'][0]['name']}"

                results = await self.bot.lavalink.get_tracks(query)

            elif "playlist" in query:
                data = self.spotify.playlist(query)
                tracks = data['tracks']['items']

                for track in tracks:
                    t = track['track']

                    partial_track = LoadLaterTrack(
                        query=f"{t['name']} - {t['artists'][0]['name']}",
                        lavalink=self.bot.lavalink
                    )
                    player.add(requester=ctx.author.id, track=partial_track)

                await ctx.send(f"Added `{len(tracks)}` tracks to the queue.")
                return

            elif "album" in query:
                data = self.spotify.album(query)
                tracks = data['tracks']['items']

                for t in tracks:
                    partial_track = LoadLaterTrack(
                        query=f"{t['name']} - {t['artists'][0]['name']}",
                        lavalink=self.bot.lavalink
                    )
                    player.add(requester=ctx.author.id, track=partial_track)

                await ctx.send(f"Added `{len(tracks)}` tracks to the queue.")
                return

            else:
                raise CommandInvokeError("Unsupported Spotify link.")

        else:
            results = await self.bot.lavalink.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send('Nothing found!')

        if results['loadType'] == 'PLAYLIST_LOADED':
            tracks = results['tracks']

            for track in tracks:
                player.add(requester=ctx.author.id, track=track)
            await ctx.send(f"Added `{len(tracks)}` tracks to the queue.")

        elif results['loadType'] == 'TRACK_LOADED':
            track = results['tracks'][0]
            player.add(track=track, requester=ctx.author.id)
            await ctx.send(f"Added `{track['info']['title']}` to the queue.")

        elif results['loadType'] == 'SEARCH_RESULT':
            track = results['tracks'][0]
            player.add(track=track, requester=ctx.author.id)
            await ctx.send(f"Added `{track['info']['title']}` to the queue.")



    # TODO: before invoke: play cmd, ask the user to accept to privacy policy of data.
    # (recording the songs played to give stats)
    # TODO: after invoke: play cmd, record the info about the song.
    # TODO: play cmd error, check if dm error, send msg explaining.

    @commands.command(aliases=["p", "pl"])
    async def play(self, ctx: Context, *, query: str):
        """ Play a song or a playlist from Youtube, SoundCloud, Bandcamp or Spotify. """
        await self.ensure_voice(ctx)

        player: CustomPlayer = self.bot.lavalink.player_manager.get(
            guild_id=ctx.guild.id)
        # Remove leading and trailing <>. <> may be used to suppress embedding links in Discord.
        query = query.strip('<>')

        if URL_REGEX.match(query):
            await self.play_from_url(ctx, player, query)
        else:
            results = await self.bot.lavalink.get_tracks(f"ytsearch: {query}")

            if not results or not results['tracks']:
                return await ctx.send('Nothing found!')

            track = results['tracks'][0]
            player.add(track=track, requester=ctx.author.id)
            await ctx.send(f'Added `{track["title"]}` to the player.')

        if not player.is_playing:
            await player.play()

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx: Context):
        """ Disconnects the player from the voice channel and clears its queue. """
        await self.ensure_voice(ctx)

        player: CustomPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.queue.clear()
        await player.stop()
        await ctx.voice_client.disconnect(force=True)
        await ctx.send('*⃣ | Disconnected.')

    # TODO: More commands to be added. Leave it to me.


def setup(bot: BotBaseBot):
    """Adds the MusicCommands cog to the bot."""
    bot.add_cog(MusicCommands(bot))

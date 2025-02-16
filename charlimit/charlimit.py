import logging

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red

BaseCog = getattr(commands, "Cog", object)


class Charlimit(BaseCog):  # Charrlimit! Get it?! Charr?! Ah fk... what do you know about humor.
    """Limit the amount of characters / lines per channel"""

    __author__ = ["SharkyTheKing"]
    __version__ = "1.0.0"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=98757087587)

        def_channel = {
            "character_limit": None,
            "line_limit": None,
        }
        def_guild = {"message": False}
        self.config.register_channel(**def_channel)
        self.config.register_guild(**def_guild)
        self.cache = {}
        self.manual = False  # If set to True then requires manual input
        self.log = logging.getLogger("red.cogs.charlimit")

    def format_help_for_context(self, ctx: commands.Context) -> str:
        context = super().format_help_for_context(ctx)
        authors = ", ".join(self.__author__)
        return f"{context}\n\nAuthor: {authors}\nVersion: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        """
        Nothing to delete
        """
        return

    @commands.guild_only()
    @commands.group()
    @checks.mod_or_permissions(manage_messages=True)
    @checks.bot_has_permissions(embed_links=True, manage_messages=True)
    async def charlimit(self, ctx):
        """Manage the character limits"""
        pass

    @charlimit.group(name="set")
    async def set_group(self, ctx):
        """
        Sets the character and line limimts
        """
        pass

    @set_group.command(aliases=["character", "characters"])
    async def char(self, ctx, channel: discord.TextChannel, characters: int):
        """
        Sets the channel's character limit

        If you put 0 for a channel, it'll remove the character limit.
        `example: [p]charlimit set char #general 0`
        """
        if characters == 0:
            await self.config.channel(channel).character_limit.set(None)
            await ctx.send(f"Done, cleared the character limit for {channel.mention}")
            try:
                self.cache[channel.id].pop("characters")
            except KeyError:
                pass
        else:
            await self.config.channel(channel).character_limit.set(characters)
            toggle = characters
            await ctx.send(f"Done, {channel.mention} is now set to {toggle} characters")
            try:
                self.cache[channel.id]["characters"] = characters
            except KeyError:
                self.cache.update({channel.id: {"characters": characters}})

    @set_group.command()
    async def lines(self, ctx, channel: discord.TextChannel, lines: int):
        """
        Sets the channel's line limit

        If you put 0 for a channel, it'll remove the line limit.
        `example: [p]charlimit set lines #general 0`
        """
        if lines == 0:
            await self.config.channel(channel).line_limit.set(None)
            await ctx.send(f"Done, cleared the line limit for {channel.mention}")
            try:
                self.cache[channel.id].pop("lines")
            except KeyError:
                pass
        else:
            await self.config.channel(channel).line_limit.set(lines)
            await ctx.send(f"Done, {channel.mention} is now set to {lines} lines")
            try:
                self.cache[channel.id]["lines"] = lines
            except KeyError:
                self.cache.update({channel.id: {"lines": lines}})

    @charlimit.command()
    async def message(self, ctx, toggle: bool):
        """
        Allows/Disallows the bot to send a message to users if they exceed the limit.

        Default is `False`, to allow type `[p]charlimit message True` othwerise no messages will be sent.
        """
        guild = ctx.guild
        config = self.config.guild(guild).message
        if toggle:
            await config.set(True)
            await ctx.send(
                "The bot will now message the users if they exceed the character limit."
            )
        else:
            await config.set(False)
            await ctx.send("The bot will not message the users.")

    #   The list of channels and their settings
    @charlimit.command()
    async def list(self, ctx):
        """
        The list of the channels in category and character limit
        """
        guild = ctx.guild
        message_conf = await self.config.guild(guild).message()
        count = ""
        lime = ""
        for channel in ctx.guild.channels:
            characters = await self.config.channel(channel).character_limit()
            lines = await self.config.channel(channel).line_limit()
            if characters is not None:
                count += f"{channel.mention}: {characters} characters\n"
            if lines is not None:
                lime += f"\n{channel.mention}: {lines} lines\n"
            e = discord.Embed(color=guild.me.top_role.color)
            e.title = f"{guild}'s Settings"
            e.description = f"{count + lime}"
            e.add_field(name="Exceeding Alert:", value=message_conf)
        return await ctx.send(embed=e)

    @commands.Cog.listener()
    async def on_message(self, message):
        current = message.channel
        reasons = {"send_message": False, "character_count": False, "line_count": False}

        if not isinstance(message.guild, discord.Guild):
            return False

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return False

        if isinstance(
            message.author, discord.Member
        ) and await self.bot.is_automod_immune(message.author):
            return False

        if not self.cache:
            await self.get_cache(guild=message.guild)
        if not self.cache:
            return False  # Stops from continuing on

        try:
            if (
                self.cache[current.id]["characters"]
                and len(message.content) > self.cache[current.id]["characters"]
            ):
                reasons["character_count"] = True
                reasons["send_message"] = True
        except KeyError:
            pass

        try:
            if (
                self.cache[current.id]["lines"]
                and len(message.content.split("\n"))
                > self.cache[current.id]["lines"]
            ):
                reasons["line_count"] = True
                reasons["send_message"] = True
        except KeyError:
            pass

        if all(reason is False for reason in reasons.values()):  # If nothing got hit, do nothing
            return False

        try:
            await self.notify_user(message=message, reasons=reasons)
            await message.delete()
        except discord.Forbidden:
            self.log.debug(f"Forbidden access to delete in {current}")
        except discord.HTTPException as e:
            self.log.debug(f"HTTPException in {current} - {e.status}")

    async def notify_user(self, message: discord.Message, reasons):
        if await self.config.guild(message.guild).message() is False:
            return False
        message_reason = (
            f"Hey there, {message.author.name}.\n\nYour message in {message.channel.mention} has "
            "been deleted due to you:\n"
        )
        if reasons["character_count"] is True:
            chars = self.cache[message.channel.id]["characters"]
            message_reason += f"Exceeding the {chars} character limit.\n"

        if reasons["line_count"] is True:
            lines = self.cache[message.channel.id]["lines"]
            message_reason += f"Exceeding the {lines} line limit."

        if reasons["send_message"] is True:
            try:
                await message.author.send(message_reason)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        await self.on_message(after)

    async def get_cache(self, guild):
        """
        Getting cache info
        """
        if self.manual is True:
            return False

        for channels in guild.text_channels:
            if await self.config.channel(channels).character_limit() is not None:
                try:
                    if self.cache[channels.id]:
                        self.cache[channels.id]["characters"] = await self.config.channel(
                            channels
                        ).character_limit()
                except KeyError:
                    self.cache.update(
                        {
                            channels.id: {
                                "characters": await self.config.channel(channels).character_limit()
                            }
                        }
                    )

            if await self.config.channel(channels).line_limit() is not None:
                try:
                    if self.cache[channels.id]:
                        self.cache[channels.id]["lines"] = await self.config.channel(
                            channels
                        ).line_limit()
                except KeyError:
                    self.cache.update(
                        {channels.id: {"lines": await self.config.channel(channels).line_limit()}}
                    )
        if not self.cache:
            self.manual = True
            self.log.info("No Config. Requires manual input.")
            return False

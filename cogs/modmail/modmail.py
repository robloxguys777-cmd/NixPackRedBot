import discord
from discord.ext import commands

class Modmail(commands.Cog):
    """A lightweight, database-free Modmail system for RedBot."""

    def __init__(self, bot):
        self.bot = bot
        # Format: {user_id: staff_channel_id}
        self.active_threads = {} 
        # Format: {staff_channel_id: user_id}
        self.channel_to_user = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        # Always ignore bots to prevent endless feedback loops
        if message.author.bot:
            return

        # Scenario A: Handle Incoming User Direct Messages (DMs)
        if isinstance(message.channel, discord.DMChannel):
            user_id = message.author.id

            # If a thread already exists, forward the user's text straight to staff
            if user_id in self.active_threads:
                channel_id = self.active_threads[user_id]
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(
                        description=message.content, 
                        color=discord.Color.blue()
                    )
                    embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                    await channel.send(embed=embed)
                    # Handle message attachments/images safely
                    for attachment in message.attachments:
                        await channel.send(attachment.url)
                return

            # If no active thread exists, initialize a new ticket
            # Finds the first server category named "Modmail Tickets"
            category = None
            for guild in self.bot.guilds:
                category = discord.utils.get(guild.categories, name="Modmail Tickets")
                if category:
                    break

            if not category:
                await message.channel.send("❌ Modmail is currently unavailable. Staff has not configured the server category.")
                return

            # Generate the staff-facing chat channel securely
            channel_name = f"ticket-{message.author.name.lower()}"
            staff_channel = await category.guild.create_text_channel(
                name=channel_name, 
                category=category,
                topic=f"Modmail ticket for {message.author} (ID: {user_id})"
            )

            # Map the thread routing parameters into memory
            self.active_threads[user_id] = staff_channel.id
            self.channel_to_user[staff_channel.id] = user_id

            # Alert staff with a clean initialization card
            init_embed = discord.Embed(
                title="📬 New Modmail Ticket",
                description=f"User **{message.author}** has opened a support ticket.",
                color=discord.Color.green()
            )
            init_embed.add_field(name="User ID", value=str(user_id), inline=True)
            init_embed.add_field(name="Account Created", value=message.author.created_at.strftime("%Y-%m-%d"), inline=True)
            await staff_channel.send(embed=init_embed)

            # Forward the user's original message to the new channel
            msg_embed = discord.Embed(description=message.content, color=discord.Color.blue())
            msg_embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            await staff_channel.send(embed=msg_embed)
            
            # Send verification back to the user
            await message.channel.send(f"✅ Your message has been routed to **{category.guild.name}** staff. Please wait for a reply!")

        # Scenario B: Handle Staff Replies in Ticket Channels
        elif isinstance(message.channel, discord.TextChannel):
            if message.channel.id in self.channel_to_user:
                # Skip messages starting with the prefix so staff can talk internally
                if message.content.startswith("-"):
                    return

                user_id = self.channel_to_user[message.channel.id]
                user = self.bot.get_user(user_id)

                if user:
                    try:
                        reply_embed = discord.Embed(
                            description=message.content, 
                            color=discord.Color.orange()
                        )
                        reply_embed.set_author(name=f"Staff Response ({message.guild.name})", icon_url=message.guild.icon.url if message.guild.icon else None)
                        await user.send(embed=reply_embed)
                        # Forward attachments back down to the user
                        for attachment in message.attachments:
                            await user.send(attachment.url)
                        # Add a visual confirmation checkmark for staff visibility
                        await message.add_reaction("✅")
                    except discord.Forbidden:
                        await message.channel.send("❌ Unable to deliver message. The user likely has their Direct Messages disabled.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def close(self, ctx):
        """Closes the current modmail ticket channel."""
        if ctx.channel.id in self.channel_to_user:
            user_id = self.channel_to_user[ctx.channel.id]
            user = self.bot.get_user(user_id)

            if user:
                try:
                    close_embed = discord.Embed(
                        title="🔒 Ticket Closed",
                        description=f"Your modmail conversation in **{ctx.guild.name}** has been closed by staff.",
                        color=discord.Color.red()
                    )
                    await user.send(embed=close_embed)
                except discord.Forbidden:
                    pass # User blocked the bot or disabled DMs

            # Scrub the values out of runtime memory lists
            del self.active_threads[user_id]
            del self.channel_to_user[ctx.channel.id]

            await ctx.channel.send("⏰ Closing and deleting this channel in 5 seconds...")
            await ctx.channel.delete(delay=5.0)
        else:
            await ctx.send("❌ This command can only be executed inside an active modmail ticket channel.")

async def setup(bot):
    await bot.add_cog(Modmail(bot))

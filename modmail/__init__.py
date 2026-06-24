from modmail.modmail import Modmail

async def setup(bot):
    await bot.add_cog(Modmail(bot))

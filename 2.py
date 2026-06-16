import os
import discord
from discord.ext import commands
import requests
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_TOKEN")

# --- CONFIGURATION ---
WG_APP_ID = "02a11c34c34f9a3f73766e3646a1e21a"
CLAN_TAG = "MRLN"                  # Example: "PZ_1"
REGION = "eu"                     # Use "eu", "na", or "asia"

# Setup bot with a prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_clan_id_by_tag(tag):
    """Searches Wargaming API to find the exact clan_id for a given tag."""
    url = f"https://api.worldoftanks.{REGION}/wot/clans/list/?application_id={WG_APP_ID}&search={tag}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "ok" and response["data"]:
            # Loop through search results to find an exact match for the tag
            for clan in response["data"]:
                if clan["tag"].upper() == tag.upper():
                    return clan["clan_id"]
    except Exception as e:
        print(f"Error fetching Clan ID: {e}")
    return None

def get_all_battles(clan_id):
    """Fetches all upcoming battles and province IDs from the WG API using the clan ID."""
    url = f"https://api.worldoftanks.{REGION}/wot/globalmap/clanbattles/?application_id={WG_APP_ID}&clan_id={clan_id}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "ok" and response.get("data"):
            data = response["data"]
            
            # Safely check if data contains a dictionary keyed by clan_id
            if isinstance(data, dict) and str(clan_id) in data:
                battles = data[str(clan_id)]
            elif isinstance(data, list) and len(data) > 0:
                battles = data
            else:
                return []

            if not battles:
                return []
            
            # Return all battles sorted by chronological order (earliest first)
            return sorted(battles, key=lambda x: x["time"])
    except Exception as e:
        print(f"Error fetching battle data: {e}")
    return []


@bot.command(name="allmatches")
async def allmatches(ctx):
    """Command to check all upcoming matches and their respective spawn sides."""
    await ctx.send(f"🔍 Resolving clan ID for `[{CLAN_TAG}]` and fetching all upcoming match layouts...")
    
    # 1. Dynamically get the Clan ID using the tag
    clan_id = get_clan_id_by_tag(CLAN_TAG)
    if not clan_id:
        await ctx.send(f"❌ Could not find a clan with the tag `[{CLAN_TAG}]`. Check your configuration.")
        return

    # 2. Ask API for all upcoming tournament/province details
    all_battles = get_all_battles(clan_id)
    if not all_battles:
        await ctx.send(f"❌ No upcoming Global Map matches found for `[{CLAN_TAG}]`.")
        return
        
    await ctx.send(f"📅 Found **{len(all_battles)}** upcoming battle(s). Processing spawn positions...")

    # 3. Loop through every scheduled battle found
    for index, match in enumerate(all_battles, start=1):
        province = match["province_id"]
        match_type = match["type"]
        
        # Determine the spawn rule based on match type
        if match_type == "defense":
            spawn_side = "🏰 Automatically fixed to default spawn (Defenders)."
        else:
            # Look up the web-scraped placement for tournament/attack rounds
            spawn_side = await scrape_spawn_side(province)
            
        # Build an embed for each match
        embed = discord.Embed(
            title=f"⚔️ Match {index} of {len(all_battles)}: [{CLAN_TAG}]", 
            color=discord.Color.red()
        )
        embed.add_field(name="Province ID", value=f"`{province}`", inline=True)
        embed.add_field(name="Battle Type", value=match_type.capitalize(), inline=True)
        embed.add_field(name="Assigned Spawn Side", value=f"**{spawn_side}**", inline=False)
        embed.set_footer(text=f"Clan ID: {clan_id} | Check the live tree if layout is pending!")
        
        await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"🤖 Bot is logged in as {bot.user.name}")

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_TOKEN missing in environment configuration (.env file).")
    else:
        bot.run(DISCORD_BOT_TOKEN)
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

def get_next_battle(clan_id):
    """Fetches the next battle and province ID from the WG API using the clan ID."""
    url = f"https://api.worldoftanks.{REGION}/wot/globalmap/clanbattles/?application_id={WG_APP_ID}&clan_id={clan_id}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "ok" and response.get("data"):
            data = response["data"]
            
            # Safely check if data contains a dictionary keyed by clan_id (instead of an empty list)
            if isinstance(data, dict) and str(clan_id) in data:
                battles = data[str(clan_id)]
            elif isinstance(data, list) and len(data) > 0:
                battles = data
            else:
                return None

            if not battles:
                return None
            
            # Sort battles by the earliest timestamp
            next_match = sorted(battles, key=lambda x: x["time"])[0]
            
            return {
                "province_id": next_match["province_id"], 
                "time": next_match["time"],
                "type": next_match["type"]
            }
    except Exception as e:
        print(f"Error fetching battle data: {e}")
    return None

async def scrape_spawn_side(province_id):
    """Scrapes the WG portal bracket asynchronously, safely handling missing brackets."""
    bracket_url = f"https://worldoftanks.{REGION}/en/globalmap/battles/tournament/{province_id}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(bracket_url, timeout=15000)
            
            # Use a shorter timeout to quickly check if the bracket even exists
            try:
                await page.wait_for_selector(".tournament-bracket", timeout=5000)
            except Exception:
                return "Bracket not available yet (Matches may still be scheduling or Prime Time is frozen)"
            
            clan_element = page.locator(f"text={CLAN_TAG}").first
            if await clan_element.count() > 0:
                parent_classes = await clan_element.locator("..").get_attribute("class")
                
                if "slot-top" in parent_classes or "team-1" in parent_classes:
                    return "Spawn 1 (Top Side / North-West)"
                else:
                    return "Spawn 2 (Bottom Side / South-East)"
            else:
                return "Unknown (Clan not found in the live tree yet)"
        except Exception as e:
            return f"Error reading bracket page ({type(e).__name__})"
        finally:
            await browser.close()

@bot.command(name="nextmatch")
async def nextmatch(ctx):
    """Command to check the next match details and automatic spawn."""
    await ctx.send(f"🔍 Resolving clan ID for `[{CLAN_TAG}]` and fetching match layout...")
    
    # 1. Dynamically get the Clan ID using the tag
    clan_id = get_clan_id_by_tag(CLAN_TAG)
    if not clan_id:
        await ctx.send(f"❌ Could not find a clan with the tag `[{CLAN_TAG}]`. Check your configuration.")
        return

    # 2. Ask API for the target province ID using the resolved Clan ID
    match_data = get_next_battle(clan_id)
    if not match_data:
        await ctx.send(f"❌ No upcoming Global Map matches found for `[{CLAN_TAG}]`.")
        return
        
    province = match_data["province_id"]
    match_type = match_data["type"]
    
    # 3. Check if it's a regular defense/attack vs province owner
    if match_type == "defense":
        await ctx.send(f"🏰 **Defense Match!**\nProvince: `{province}`\nAs defenders, you are automatically fixed to your default spawn.")
        return
        
    # 4. If it's a tournament matchup, scrape the layout tree asynchronously
    spawn_side = await scrape_spawn_side(province)
    
    # Send a clean breakdown to your Discord channel
    embed = discord.Embed(title=f"⚔️ Next Global Map Match: [{CLAN_TAG}]", color=discord.Color.red())
    embed.add_field(name="Clan ID Found", value=f"`{clan_id}`", inline=True)
    embed.add_field(name="Province ID", value=f"`{province}`", inline=True)
    embed.add_field(name="Battle Type", value=match_type.capitalize(), inline=True)
    embed.add_field(name="Assigned Spawn Side", value=f"**{spawn_side}**", inline=False)
    embed.set_footer(text="Double-check the bracket if the Prime Time freeze just happened!")
    
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"🤖 Bot is logged in as {bot.user.name}")

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_TOKEN missing in environment configuration (.env file).")
    else:
        bot.run(DISCORD_BOT_TOKEN)
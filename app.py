import discord
from discord.ext import commands
import requests
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
DISCORD_BOT_TOKEN = "MTUxNDk2ODE5NTgyNjcxMjY4Nw.G3HDfs.X2Sf5e3bIhNAp26TvtcUvS_qml0Cw4pvVJlq3I"
WG_APP_ID = "02a11c34c34f9a3f73766e3646a1e21a"
CLAN_TAG = "MRLN"        # Example: "PZ_1"
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
        if response.get("status") == "ok" and response["data"][str(clan_id)]:
            battles = response["data"][str(clan_id)]
            # Sort battles by the earliest timestamp
            next_match = sorted(battles, key=lambda x: x["time"])[0]
            return {
                "province_id": next_match["provinces"][0],
                "time": next_match["time"],
                "type": next_match["type"]
            }
    except Exception as e:
        print(f"Error fetching battle data: {e}")
    return None

def scrape_spawn_side(province_id):
    """Scrapes the WG portal bracket to see if the clan is on Top or Bottom."""
    bracket_url = f"https://worldoftanks.{REGION}/en/globalmap/battles/tournament/{province_id}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(bracket_url, timeout=15000)
            page.wait_for_selector(".tournament-bracket", timeout=10000)
            
            clan_element = page.locator(f"text={CLAN_TAG}").first
            if clan_element.count() > 0:
                parent_classes = clan_element.locator("..").get_attribute("class")
                
                if "slot-top" in parent_classes or "team-1" in parent_classes:
                    return "Spawn 1 (Top Side / North-West)"
                else:
                    return "Spawn 2 (Bottom Side / South-East)"
            else:
                return "Unknown (Clan not found in the live tree yet)"
        except Exception as e:
            return f"Error reading bracket page ({e})"
        finally:
            browser.close()

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
        
    # 4. If it's a tournament matchup, scrape the layout tree
    spawn_side = scrape_spawn_side(province)
    
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

bot.run(DISCORD_BOT_TOKEN)
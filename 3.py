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
CLAN_TAG = "MRLN"                  # Target Clan
REGION = "eu"                     # Region ("eu", "na", "asia")
MAPS_DIR = "Maps"                 # Folder containing map images

# List of known maps based on your files (normalized to lowercase for matching)
KNOWN_MAPS = [
    "abbey", "cliff", "el halluf", "ensk", "fisherman's bay", "highway",
    "himmelsdorf", "karelia", "lakeville", "live oaks", "malinovka", "mines",
    "murovanka", "pearl river", "prokhorovka", "redshire", "sand river",
    "serene coast", "steppes", "westfield"
]

# Setup bot with prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_clan_id_by_tag(tag):
    """Searches Wargaming API to find the exact clan_id for a given tag."""
    url = f"https://api.worldoftanks.{REGION}/wot/clans/list/?application_id={WG_APP_ID}&search={tag}"
    try:
        response = requests.get(url).json()
        if response.get("status") == "ok" and response["data"]:
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
            
            if isinstance(data, dict) and str(clan_id) in data:
                battles = data[str(clan_id)]
            elif isinstance(data, list) and len(data) > 0:
                battles = data
            else:
                return []

            if not battles:
                return []
            
            return sorted(battles, key=lambda x: x["time"])
    except Exception as e:
        print(f"Error fetching battle data: {e}")
    return []

async def scrape_battle_details(province_id):
    """Scrapes the WG Global Map tournament page and extracts all visual matchup statistics."""
    bracket_url = f"https://{REGION}.wargaming.net/globalmap/#tournament/{province_id}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        try:
            await page.goto(bracket_url, timeout=30000)
            
            # Wait for structural containers to show up
            try:
                await page.wait_for_selector(".box_part__left, .box_part__right", timeout=15000)
            except Exception:
                return {"error": "Tournament bracket page timed out or hasn't generated yet."}
            
            # Allow dynamic text elements to fully render
            await page.wait_for_timeout(3000)
            
            # 1. Grab Header Details
            page_title = await page.locator(".page_title").first.text_content() if await page.locator(".page_title").count() > 0 else "Unknown Province"
            round_status = await page.locator(".round_step").first.text_content() if await page.locator(".round_step").count() > 0 else "Unknown Round"
            map_name = await page.locator(".list-controls_cell__center").first.text_content() if await page.locator(".list-controls_cell__center").count() > 0 else "Unknown Map"
            
            # 2. Extract Base 1 Details (Left Column)
            left_tag = "N/A"
            left_name = "N/A"
            left_elo = "N/A"
            
            left_column = page.locator(".box_part__left")
            if await left_column.count() > 0:
                tag_el = left_column.locator(".clan-name_tag")
                if await tag_el.count() > 0:
                    left_tag = (await tag_el.first.text_content() or "").strip()
                
                # Retrieve the full name of the clan (stripping tag element out)
                name_el = left_column.locator(".clan-name_text")
                if await name_el.count() > 0:
                    raw_text = await name_el.first.text_content() or ""
                    # Remove the tag prefix to get a clean name
                    left_name = raw_text.replace(left_tag, "").strip() if left_tag != "N/A" else raw_text.strip()
                
                elo_el = left_column.locator(".clan-statistics_help")
                if await elo_el.count() > 0:
                    left_elo = (await elo_el.first.text_content() or "").strip()

            # 3. Extract Base 2 Details (Right Column)
            right_tag = "N/A"
            right_name = "N/A"
            right_elo = "N/A"
            
            right_column = page.locator(".box_part__right")
            if await right_column.count() > 0:
                tag_el = right_column.locator(".clan-name_tag")
                if await tag_el.count() > 0:
                    right_tag = (await tag_el.first.text_content() or "").strip()
                
                name_el = right_column.locator(".clan-name_text")
                if await name_el.count() > 0:
                    raw_text = await name_el.first.text_content() or ""
                    right_name = raw_text.replace(right_tag, "").strip() if right_tag != "N/A" else raw_text.strip()
                
                elo_el = right_column.locator(".clan-statistics_help")
                if await elo_el.count() > 0:
                    right_elo = (await elo_el.first.text_content() or "").strip()

            # 4. Extract Detailed Statistics Comparison Table
            detailed_stats = []
            rows = page.locator("tr.clan-statistics_row")
            row_count = await rows.count()
            
            for i in range(row_count):
                row = rows.nth(i)
                left_val_el = row.locator(".clan-statistics_cell__left")
                heading_el = row.locator(".clan-statistics_cell__heading")
                right_val_el = row.locator(".clan-statistics_cell__right")
                
                left_val = (await left_val_el.text_content() or "").strip() if await left_val_el.count() > 0 else "0"
                heading = (await heading_el.text_content() or "").strip() if await heading_el.count() > 0 else "Metric"
                right_val = (await right_val_el.text_content() or "").strip() if await right_val_el.count() > 0 else "0"
                
                detailed_stats.append((heading, left_val, right_val))
                
            return {
                "province_title": page_title.strip(),
                "round_status": round_status.strip(),
                "map_name": map_name.replace("Map:", "").replace("Карта:", "").strip(),
                "team_left": {"tag": left_tag, "name": left_name, "elo": left_elo},
                "team_right": {"tag": right_tag, "name": right_name, "elo": right_elo},
                "stats": detailed_stats
            }
            
        except Exception as e:
            return {"error": f"Error loading Wargaming dynamic DOM properties: {type(e).__name__}"}
        finally:
            await browser.close()

def find_map_image(scraped_map_name):
    """Finds matching image path inside the Maps directory based on the scraped map name."""
    if not os.path.exists(MAPS_DIR):
        return None
        
    normalized_scraped = scraped_map_name.lower().strip()
    
    # List all files in the Maps folder
    files = os.listdir(MAPS_DIR)
    
    for map_name in KNOWN_MAPS:
        if map_name in normalized_scraped:
            # Look for an image extension matching this map name
            for file in files:
                if file.lower().startswith(map_name):
                    return os.path.join(MAPS_DIR, file)
    return None

@bot.command(name="allmatches")
async def allmatches(ctx):
    """Command to scrape and return complete structural details for all map battles."""
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
        
    await ctx.send(f"📅 Found **{len(all_battles)}** upcoming battle(s). Processing live page datasets...")

    # 3. Loop through every scheduled battle found
    for index, match in enumerate(all_battles, start=1):
        province = match["province_id"]
        match_type = match["type"]
        
        # Determine the layout based on match type
        if match_type == "defense":
            embed = discord.Embed(
                title=f"🏰 Match {index} of {len(all_battles)}: Defensive Layout", 
                color=discord.Color.blue()
            )
            embed.add_field(name="Province ID", value=f"`{province}`", inline=True)
            embed.add_field(name="Battle Type", value="Defense", inline=True)
            embed.add_field(name="Assigned Spawn Side", value="**Spawn 1 (Defenders default spawn)**", inline=False)
            embed.set_footer(text=f"Clan ID: {clan_id} | Defense rules active.")
            await ctx.send(embed=embed)
            continue
        
        # Scrape and gather all details if it's a live tournament / attack matchup
        data = await scrape_battle_details(province)
        
        if "error" in data:
            embed = discord.Embed(
                title=f"⚠️ Match {index} of {len(all_battles)}: Error Reading Layout", 
                color=discord.Color.orange()
            )
            embed.add_field(name="Province ID", value=f"`{province}`", inline=True)
            embed.add_field(name="Battle Type", value=match_type.capitalize(), inline=True)
            embed.add_field(name="Failure Reason", value=data["error"], inline=False)
            embed.set_footer(text=f"Clan ID: {clan_id}")
            await ctx.send(embed=embed)
            continue

        # Extract structured details
        prov_title = data["province_title"]
        round_status = data["round_status"]
        map_name = data["map_name"]
        
        left_clan = data["team_left"]
        right_clan = data["team_right"]
        comparison_stats = data["stats"]

        # Build highly detailed overview embed
        embed = discord.Embed(
            title=f"⚔️ {prov_title}", 
            description=f"**Status**: *{round_status}* | **Map**: `{map_name}`",
            color=discord.Color.red()
        )
        
        # Base 1 / Left Column
        embed.add_field(
            name="🔴 Base 1 (Left Side / Spawn 1)",
            value=f"**Clan**: {left_clan['tag']} {left_clan['name']}\n**Elo Rating**: `{left_clan['elo']}`",
            inline=True
        )
        
        # Base 2 / Right Column
        embed.add_field(
            name="🟢 Base 2 (Right Side / Spawn 2)",
            value=f"**Clan**: {right_clan['tag']} {right_clan['name']}\n**Elo Rating**: `{right_clan['elo']}`",
            inline=True
        )

        # Build comparison statistics block if rows are available
        if comparison_stats:
            stats_block = ""
            for metric, left_v, right_v in comparison_stats:
                stats_block += f"• **{metric}**:\n  [{left_v}] vs. [{right_v}]\n"
            embed.add_field(name="📊 Team Comparison Stats", value=stats_block, inline=False)

        embed.set_footer(text=f"Province ID: {province} | Live Matchup Overview")

        # --- IMAGE ATTACHMENT LOGIC ---
        map_image_path = find_map_image(map_name)
        if map_image_path:
            # Extract filename (e.g. "abbey.png") to pass to the embed attach reference
            filename = os.path.basename(map_image_path)
            discord_file = discord.File(map_image_path, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            await ctx.send(file=discord_file, embed=embed)
        else:
            await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"🤖 Bot is logged in as {bot.user.name}")

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_TOKEN missing in environment configuration (.env file).")
    else:
        bot.run(DISCORD_BOT_TOKEN)
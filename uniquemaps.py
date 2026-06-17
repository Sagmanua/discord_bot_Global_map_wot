import requests

def get_unique_global_map_names(application_id, region="eu"):
    """
    Fetches all available fronts, dynamically extracts their provinces, 
    and returns a unique list of map names.
    """
    base_url = f"https://api.worldoftanks.{region}/wot/globalmap"
    fronts_url = f"{base_url}/fronts/"
    provinces_url = f"{base_url}/provinces/"
    
    unique_maps = set()
    
    # 1. Fetch all active fronts to get their IDs
    print("Fetching active Global Map Fronts...")
    fronts_params = {
        "application_id": application_id,
        "fields": "front_id,front_name"
    }
    
    fronts_response = requests.get(fronts_url, params=fronts_params)
    if fronts_response.status_code != 200:
        print(f"Error fetching fronts: Status code {fronts_response.status_code}")
        return []
        
    fronts_data = fronts_response.json()
    if fronts_data.get("status") == "error":
        print(f"API Error fetching fronts: {fronts_data['error'].get('message')}")
        return []
        
    fronts = fronts_data.get("data", [])
    if not fronts:
        print("No active fronts found on the Global Map right now (Map might be down/season ended).")
        return []

    # 2. Iterate through each front and get its maps
    for front in fronts:
        front_id = front.get("front_id")
        front_name = front.get("front_name")
        print(f"Pulling unique maps from: {front_name} ({front_id})...")
        
        page_number = 1
        while True:
            provinces_params = {
                "application_id": application_id,
                "front_id": front_id,
                "fields": "arena_name",
                "limit": 100,
                "page_no": page_number
            }
            
            response = requests.get(provinces_url, params=provinces_params)
            if response.status_code != 200:
                break
                
            data = response.json()
            if data.get("status") == "error":
                break
                
            provinces = data.get("data", [])
            if not provinces:
                break
                
            for province in provinces:
                map_name = province.get("arena_name")
                if map_name:
                    unique_maps.add(map_name)
            
            # Pagination handling
            meta = data.get("meta", {})
            if page_number * provinces_params["limit"] >= meta.get("total", 0):
                break
            page_number += 1

    return sorted(list(unique_maps))

# --- RUNNING THE SCRIPT ---
if __name__ == "__main__":
    # Insert your actual Wargaming Application ID here
    APP_ID = "02a11c34c34f9a3f73766e3646a1e21a" 
    REGION = "eu" 
    
    if APP_ID == "YOUR_APPLICATION_ID_HERE":
        print("Please replace 'YOUR_APPLICATION_ID_HERE' with your actual WoT API key.")
    else:
        maps_list = get_unique_global_map_names(APP_ID, region=REGION)
        
        print(f"\nFound {len(maps_list)} unique maps across all active fronts:")
        print("-" * 40)
        for name in maps_list:
            print(f"- {name}")
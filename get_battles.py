import requests
import json
import time
import os

def download_replays(format_id=None, page=1, count=50):
    """
    Download replays for a specific user.
    
    Args:
        username (str): The Pokémon Showdown username
        format_id (str, optional): The format ID to filter by (e.g., 'gen9ou')
        page (int): The page number to start from
        count (int): Number of replays to fetch per request
    """
    
    base_url = "https://replay.pokemonshowdown.com/search.json"
    all_replays = []
    
    os.makedirs("replays", exist_ok=True)
    
    while True:
        params = {
            format: format_id,
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break
            
        data = response.json()
        
        if not data:
            print(f"No more replays found after page {page-1}")
            break
            
        print(f"Processing page {page}, found {len(data)} replays")
        
        for replay in data:
            replay_id = replay.get('id')
            if not replay_id:
                continue
                
            replay_url = f"https://replay.pokemonshowdown.com/{replay_id}.log"
            replay_content = requests.get(replay_url).text
            
            # Save to file
            with open(f"replays/{replay_id}.log", "w", encoding="utf-8") as f:
                f.write(replay_content)
                
            all_replays.append(replay_id)
            
        # Avoid hitting rate limits
        time.sleep(1)
        
        page += 1
        
    print(f"Downloaded {len(all_replays)} replays")
    return all_replays

# Example usage
download_replays( format_id="gen9randombattle")
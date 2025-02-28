import asyncio
import websockets
import json
import os
import requests
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

async def connect_to_showdown():
    # Connect to the Pokemon Showdown websocket
    url = "wss://sim3.psim.us/showdown/websocket"
    
    async with websockets.connect(url) as websocket:
        # Initial connection messages
        message = await receive_messages(websocket)
        
        # Extract challenge string and login
        if message and "|challstr|" in message:
            challstr = message.split('|challstr|')[1]
            login_command = await login_to_showdown(challstr)
            
            if login_command:
                await websocket.send(login_command)
                print("Login command sent")
            else:
                print("Login failed")
        
        # Wait for login confirmation
        await receive_messages(websocket)
        
        # Send the move command
        await send_move_command(websocket, 2)
        
        # Wait for response
        await receive_messages(websocket)

async def login_to_showdown(challstr):
    login_url = 'https://play.pokemonshowdown.com/api/login'
    data = {
        'name': 'slattyslattnu',
        'pass': 'dab3st',
        'challstr': challstr
    }
    
    response = requests.post(login_url, data=data)
    
    if response.status_code == 200:
        response_data = json.loads(response.text[1:])  # Remove the ']' prefix
        assertion = response_data.get('assertion')
        if assertion:
            return f'|/trn slattyslattnu,0,{assertion}'
    return None

async def send_move_command(websocket, move_number, battle_id= 'battle-gen9randombattle-2309331601'):
    # Send the command to choose move 2
    await websocket.send(f"{battle_id}|/choose move {move_number}")
    print(f"Sent command: |/choose move {move_number}")

async def receive_messages(websocket, timeout=5):
    try:
        # Set a timeout to avoid waiting indefinitely
        response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        print(f"Received: {response}")
        if "|challstr|" in response:
            challstr = response.split('|challstr|')[1]
            login_command = await login_to_showdown(challstr)
            if login_command:
                await websocket.send(login_command)
                print("Login command sent")
                await receive_messages(websocket)
                await websocket.send(f"|/join battle-gen9randombattle-1740703268")
                await receive_messages(websocket)

            else:
                print("Login failed")
        return response
    except asyncio.TimeoutError:
        print("Timeout waiting for response")
        return None

if __name__ == "__main__":
    asyncio.run(connect_to_showdown())



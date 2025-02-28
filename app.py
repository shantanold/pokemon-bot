import asyncio
import websockets
import aioconsole  # You'll need to: pip install aioconsole
import requests
import json
from langchain_openai import OpenAI
from dotenv import load_dotenv
import os
import re

from context import ContextBuilder
from strategy import BattleStrategy
# Load environment variables
load_dotenv()

class BattleState:
    def __init__(self):
        self.my_team = {}  # Format: {position: {name, hp, max_hp, status, moves}}
        self.opponent_team = {}
        self.active_pokemon = {'self': None, 'opponent': None}
        self.available_moves = []
        self.battle_id = None
        self.turn = 0
        self.weather = None
        self.field_conditions = []
        self.waiting_for_move = False
        self.player_id = None  # To track which player we are (p1 or p2)
        
        # Initialize our strategic components
        self.context_builder = ContextBuilder()
        self.strategy_engine = BattleStrategy(model_name="gpt-3.5-turbo", temperature=0.8)
        
        # Store the last constructed context
        self.current_context = {}
        
        # Track battle history for analysis
        self.battle_history = []
        self.last_decision = None

    def update_from_message(self, message):
        parts = message.split('|')
        if len(parts) < 2:
            return
        
        command = parts[1]
        context_updated = False  # Flag to track if we need to update context
        
        # Process the message based on command type
        if 'start' in message:
            for part in parts:
                if 'p2a' in part:
                    name = part.split(':')[1]
                    print("We are in the start message", name)
                    self.opponent_team[name] = {
                        'name': name,
                        'hp': '100',
                        'revealed': True
                    }
                    self.active_pokemon['opponent'] = name
                    context_updated = True
        
        if command == 'request' and len(parts) >= 3 and parts[2]:
            try:
                request_data = json.loads(parts[2])
                
                # Update our player_id if not already set
                if not self.player_id and 'side' in request_data:
                    self.player_id = request_data['side'].get('id', '')
                    print(f"Player ID set to: {self.player_id}")
                
                # Update our team state
                if 'side' in request_data:
                    self.my_team = {}
                    for pokemon in request_data['side']['pokemon']:
                        self.my_team[pokemon['ident']] = {
                            'name': pokemon['details'],
                            'hp': pokemon['condition'],
                            'moves': pokemon.get('moves', []),
                            'active': pokemon.get('active', False),
                            'stats': pokemon.get('stats', {}),
                            'status': pokemon.get('status', ''),
                            'baseAbility': pokemon.get('baseAbility', '')
                        }
                        
                        # Update active Pokemon
                        if pokemon.get('active', False):
                            pokemon_name = pokemon['details'].split(',')[0]
                            self.active_pokemon['self'] = pokemon_name
                            print(f"Updated active Pokemon to: {pokemon_name}")
                
                # Handle force switch
                if 'forceSwitch' in request_data:
                    self.waiting_for_move = True
                    self.available_moves = []
                    print("\nForce switch required!")
                    context_updated = True
                
                # Handle available moves
                if 'active' in request_data and request_data['active']:
                    active_pokemon = request_data['active'][0]
                    self.available_moves = active_pokemon.get('moves', [])
                    
                    # Track if moves are trapped, disabled, etc.
                    for move in self.available_moves:
                        print(f"Move: {move['move']} - PP: {move['pp']}/{move['maxpp']}")
                        if move.get('disabled'):
                            print(f"  - Disabled: {move['move']}")
                        if move.get('target'):
                            print(f"  - Target type: {move['target']}")
                    
                    self.waiting_for_move = True
                
                # Update context using ContextBuilder
                self.current_context = self.context_builder.construct_context(request_data)
                
                # Print a summary of the context (optional)
                print("\n=== BATTLE CONTEXT UPDATED FROM REQUEST ===")
                self._print_context_summary()
                
            except json.JSONDecodeError as e:
                print(f"Error parsing request data: {e}")

        # Track opponent's moves for future analysis
        elif command == 'move':
            if len(parts) >= 5:
                user = parts[2]
                move = parts[3]
                target = parts[4]
                print(f"\nMove used: {user} used {move} on {target}")
                
                # If opponent used a move, record it for future analysis
                if not user.startswith(self.player_id):
                    opponent_pokemon = user.split(':')[1] if ':' in user else user
                    self.context_builder.record_opponent_move(opponent_pokemon, move)
                    
                    # Also update opponent's active Pokemon if not already set
                    if not self.active_pokemon['opponent']:
                        pokemon_name = opponent_pokemon.split(',')[0]
                        self.active_pokemon['opponent'] = pokemon_name
                        print(f"Updated opponent's active Pokemon to: {pokemon_name}")
                
                context_updated = True
        
        # Handle when a Pokemon is revealed
        elif command == 'poke':
            # Format: |poke|PLAYER|DETAILS|ITEM
            if len(parts) >= 4:
                player = parts[2]
                details = parts[3]
                pokemon_name = details.split(',')[0]
                
                # If it's opponent's Pokemon, add to opponent team
                if not player.startswith(self.player_id):
                    # This is the first time we're seeing this Pokemon
                    if player not in self.opponent_team:
                        self.opponent_team[player] = {
                            'name': details,
                            'revealed': True
                        }
                        print(f"Opponent revealed: {pokemon_name}")
                        context_updated = True
                        
        # Handle when a Pokemon is sent out at the start of battle
        elif command == 'teampreview' or command == 'start':
            # Set player_id if not already set
            if not self.player_id and len(parts) >= 3:
                if 'p1' in parts[2]:
                    self.player_id = 'p1'
                elif 'p2' in parts[2]:
                    self.player_id = 'p2'
                print(f"Player ID set to: {self.player_id}")
                context_updated = True
                
        # Handle switch command (including initial switches at battle start)
        elif command == 'switch':
            # Format: |switch|POKEMON|DETAILS|HP STATUS
            if len(parts) >= 5:
                pokemon_full = parts[2]
                details = parts[3]
                hp_status = parts[4]
                pokemon_name = details.split(',')[0]
                
                if pokemon_full.startswith(self.player_id):
                    self.active_pokemon['self'] = pokemon_name
                    print(f"Switched active Pokemon to: {pokemon_name}")
                else:
                    # This is the opponent's Pokemon
                    self.active_pokemon['opponent'] = pokemon_name
                    
                    # Update opponent team information
                    if pokemon_full not in self.opponent_team:
                        self.opponent_team[pokemon_full] = {
                            'name': details,
                            'hp': hp_status,
                            'revealed': True
                        }
                    else:
                        self.opponent_team[pokemon_full]['hp'] = hp_status
                        
                    print(f"Opponent switched to: {pokemon_name} with HP {hp_status}")
                
                context_updated = True
            
        elif command == '-damage':
            if len(parts) >= 4:
                pokemon = parts[2]
                new_hp = parts[3]
                print(f"Damage dealt to {pokemon}, new HP: {new_hp}")
                
                # Update our team's HP if it's our Pokemon
                if pokemon.startswith(self.player_id):
                    poke_id = pokemon.split(':')[1]
                    if poke_id in self.my_team:
                        self.my_team[poke_id]['hp'] = new_hp
                        print(f"Updated our {poke_id}'s HP to {new_hp}")
                        context_updated = True
                else:
                    # Update opponent's HP
                    for key in self.opponent_team:
                        if key in pokemon:
                            self.opponent_team[key]['hp'] = new_hp
                            print(f"Updated opponent's {key}'s HP to {new_hp}")
                            context_updated = True
        
        elif command == 'turn':
            if len(parts) >= 3:
                old_turn = self.turn
                self.turn = int(parts[2])
                print(f"\nTurn {old_turn} → {self.turn}")
                
                # Every 5 turns, analyze battle trends
                if self.turn % 5 == 0 and self.turn > 0:
                    self._analyze_battle_trends()
                
                context_updated = True

        elif command == '-heal':
            # Format: |-heal|POKEMON|HP STATUS
            if len(parts) >= 4:
                pokemon = parts[2]
                new_hp = parts[3]
                if pokemon.startswith(self.player_id):
                    # Update our Pokemon's HP
                    poke_id = pokemon.split(':')[1]
                    if poke_id in self.my_team:
                        self.my_team[poke_id]['hp'] = new_hp
                        context_updated = True
                else:
                    # Update opponent's HP
                    for key in self.opponent_team:
                        if key in pokemon:
                            self.opponent_team[key]['hp'] = new_hp
                            context_updated = True

        elif command == '-status':
            # Format: |-status|POKEMON|STATUS
            if len(parts) >= 4:
                pokemon = parts[2]
                status = parts[3]
                if pokemon.startswith(self.player_id):
                    poke_id = pokemon.split(':')[1]
                    if poke_id in self.my_team:
                        self.my_team[poke_id]['status'] = status
                        context_updated = True
                else:
                    # Update opponent's status
                    for key in self.opponent_team:
                        if key in pokemon:
                            self.opponent_team[key]['status'] = status
                            context_updated = True

        elif command == 'faint':
            # Format: |faint|POKEMON
            if len(parts) >= 3:
                pokemon = parts[2]
                if pokemon.startswith(self.player_id):
                    poke_id = pokemon.split(':')[1]
                    if poke_id in self.my_team:
                        self.my_team[poke_id]['hp'] = '0 fnt'
                        context_updated = True
                else:
                    # Update opponent's fainted status
                    for key in self.opponent_team:
                        if key in pokemon:
                            self.opponent_team[key]['hp'] = '0 fnt'
                            context_updated = True
                    
        # Handle player identification
        elif command == 'player':
            # Format: |player|PLAYER|USERNAME
            if len(parts) >= 4:
                player_id = parts[2]
                username = parts[3]
                
                # If this is our username, set player_id
                if username.lower() == 'slattyslattnu':
                    self.player_id = player_id
                    print(f"Player ID set to: {self.player_id} from player command")
                    context_updated = True
                
        # Handle when a Pokemon is sent out
        elif command == 'drag' or command == 'replace':
            # Format: |drag|POKEMON|DETAILS|HP STATUS
            if len(parts) >= 4:
                pokemon_full = parts[2]
                details = parts[3]
                pokemon_name = details.split(',')[0]
                
                if pokemon_full.startswith(self.player_id):
                    self.active_pokemon['self'] = pokemon_name
                    print(f"Forced switch to: {pokemon_name}")
                else:
                    self.active_pokemon['opponent'] = pokemon_name
                    print(f"Opponent forced to: {pokemon_name}")
                
                context_updated = True
        
        # Handle weather changes
        elif command == '-weather':
            if len(parts) >= 3:
                self.weather = parts[2]
                print(f"Weather changed to: {self.weather}")
                context_updated = True
        
        # Handle field condition changes
        elif command == '-fieldstart' or command == '-fieldend':
            if len(parts) >= 3:
                field_condition = parts[2]
                if command == '-fieldstart':
                    if field_condition not in self.field_conditions:
                        self.field_conditions.append(field_condition)
                    print(f"Field condition started: {field_condition}")
                else:
                    if field_condition in self.field_conditions:
                        self.field_conditions.remove(field_condition)
                    print(f"Field condition ended: {field_condition}")
                context_updated = True
        
        # Update the context if any battle state has changed
        if context_updated and command != 'request':  # We already update for 'request' commands
            self._update_context_from_battle_state()
        
    def _update_context_from_battle_state(self):
        """Update the context using the current battle state"""
        # Create a simplified request data structure for context updates
        simplified_request = {
            'side': {
                'id': self.player_id or '',  # Use empty string if player_id is None
                'pokemon': []
            },
            'active': [{'moves': self.available_moves}] if self.available_moves else [],
            'turn': self.turn,
            'weather': self.weather or 'none',  # Use 'none' if weather is None
            'field_conditions': self.field_conditions or []  # Use empty list if field_conditions is None
        }
        
        # Add our team to the simplified request
        for pokemon_id, pokemon_data in self.my_team.items():
            if pokemon_data:  # Check if pokemon_data is not None
                pokemon_entry = {
                    'ident': pokemon_id,
                    'details': pokemon_data.get('name', ''),  # Use get with default value
                    'condition': pokemon_data.get('hp', '100'),
                    'active': pokemon_data.get('active', False),
                    'moves': pokemon_data.get('moves', []),
                    'baseAbility': pokemon_data.get('baseAbility', ''),
                    'status': pokemon_data.get('status', '')
                }
                simplified_request['side']['pokemon'].append(pokemon_entry)
        
        # Add opponent information to the context - with null checks
        opponent_data = {
            'team': {}
        }
        
        # Handle opponent's active Pokémon - could be a string or None
        active_opponent = self.active_pokemon.get('opponent', None)
        if active_opponent:
            if isinstance(active_opponent, dict):
                opponent_data['active'] = active_opponent
            else:
                # If it's a string, create a minimal dictionary with the name
                opponent_data['active'] = {
                    'details': active_opponent,
                    'name': active_opponent
                }
        else:
            opponent_data['active'] = None
        
        # Only add opponent team if it exists
        if self.opponent_team:
            opponent_data['team'] = self.opponent_team
        
        simplified_request['opponent'] = opponent_data
        
        try:
            # Update the context using the context builder
            self.current_context = self.context_builder.construct_context(simplified_request)
            
            print("\n=== BATTLE CONTEXT UPDATED (Non-Request) ===")
            self._print_context_summary()
        except Exception as e:
            print(f"Error updating context: {e}")
            print(f"Simplified request: {simplified_request}")

    def _print_context_summary(self):
        """Print a summary of the current context"""
        if not self.current_context:
            print("Nothing available yet")
            return
            
        if "analysis" in self.current_context:
            if "current_matchup" in self.current_context["analysis"]:
                matchup = self.current_context["analysis"]["current_matchup"]
                print(f"Current matchup: {matchup.get('player_pokemon', 'Unknown')} vs {matchup.get('opponent_pokemon', 'Unknown')}")
                print(f"Player has super effective: {matchup.get('player_has_super_effective', False)}")
                print(f"Opponent may have super effective: {matchup.get('opponent_might_have_super_effective', False)}")
            
            if "strategic_options" in self.current_context["analysis"]:
                options = self.current_context["analysis"]["strategic_options"].get("options", [])
                print("\nStrategic options:")
                for option in options:
                    print(f"- {option}")

    def _analyze_battle_trends(self):
        """Analyze battle trends using the strategy engine"""
        if len(self.strategy_engine.get_decision_history()) >= 3:
            print("\n=== BATTLE TREND ANALYSIS ===")
            trend_analysis = self.strategy_engine.analyze_battle_trend()
            print(trend_analysis["analysis"])
            print("===============================")

    def get_battle_state_summary(self):
        """Create a summary of the current battle state for the AI"""
        summary = {
            'my_active': self.active_pokemon['self'],
            'opponent_active': self.active_pokemon['opponent'],
            'my_team': self.my_team,
            'opponent_team': self.opponent_team,
            'available_moves': self.available_moves,
            'weather': self.weather,
            'field_conditions': self.field_conditions,
            'turn': self.turn
        }
        return json.dumps(summary, indent=2)

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

async def handle_user_input(websocket):
    while True:
        # Get input from user without blocking websocket messages
        user_input = await aioconsole.ainput("> ")
        if user_input.lower() == 'quit':
            break
        # Send the message to the websocket
        await websocket.send(user_input)

async def handle_battle_flow(ws, battle_state):
    """Handle the complete battle flow: challenge, join, battle, and cleanup"""
    
    # Send challenge
    opponent = "slattyisnotworking"  # Your opponent's username
    challenge_command = f"|/challenge {opponent}, gen9randombattle"
    await ws.send(challenge_command)
    print(f"Challenge sent to {opponent}")
    
    # The rest of the flow will be handled by the message processing in handle_websocket
    # When the challenge is accepted, we'll extract the battle ID and join the room
    # Then we'll process battle messages and make moves

async def handle_websocket():
    url = "wss://sim3.psim.us/showdown/websocket"
    battle_state = BattleState()
    
    async with websockets.connect(url) as ws:
        input_task = asyncio.create_task(handle_user_input(ws))
        
        while True:
            try:
                message = await ws.recv()
            
                if "|challstr|" in message:
                    # Handle authentication challenge string
                    print("Received challenge string - Attempting login...")
                    challstr = message.split('|challstr|')[1]
                    
                    # Login using the challenge string
                    login_command = await login_to_showdown(challstr)
                    if login_command:
                        await ws.send(login_command)
                        print("Login command sent")
                        
                        # Start the battle flow after successful login
                        if not battle_state.battle_id:
                            await handle_battle_flow(ws, battle_state)
                        else:
                            print("Already in a battle, not sending challenge")
                    else:
                        print("Login failed")
                
                # Handle PM messages with battle links
                elif "|pm|" in message and "accepted the challenge, starting" in message and "battle-gen9randombattle" in message:
                    print("Challenge accepted! Extracting battle ID...")
                    
                    # Extract the battle ID using regex
                    import re
                    battle_match = re.search(r'battle-gen9randombattle-(\d+)', message)
                    
                    if battle_match:
                        battle_id = f"battle-gen9randombattle-{battle_match.group(1)}"
                        battle_state.battle_id = battle_id
                        print(f"Extracted battle ID: {battle_id}")
                        
                        # Explicitly join the battle room
                        join_command = f"|/join {battle_id}"
                        await ws.send(join_command)
                        print(f"Joining battle room: {battle_id}")
                
                # Handle room-specific messages
                elif battle_state.battle_id and message.startswith(f">{battle_state.battle_id}\n"):
                    # This is a message for our battle room
                    # Strip the room prefix and process the actual message content
                    room_message = message.split("\n", 1)[1] if "\n" in message else ""
                    if room_message:
                        battle_state.update_from_message(room_message)
                        
                        # If we need to make a move, get AI recommendation
                        if battle_state.waiting_for_move and battle_state.active_pokemon['opponent']:
                            action_command = await recommend_move(battle_state)
                            if action_command:
                                # Send the command to the specific battle room
                                room_command = f"{battle_state.battle_id}{action_command}"
                                await ws.send(room_command)
                                print(f"AI recommended and used action: {action_command}")
                                battle_state.waiting_for_move = False
                
                # Handle other messages
                else:
                        
                    battle_state.update_from_message(message)
                    
                    # If we need to make a move, get AI recommendation
                    if battle_state.waiting_for_move and battle_state.opponent_team:
                        print("We are abt to recommend, and we have an opponent team", battle_state.opponent_team)
                        action_command = await recommend_move(battle_state)
                        if action_command:
                            # Add battle ID prefix to ensure command is sent to the correct room
                            if battle_state.battle_id:
                                room_command = f"{battle_state.battle_id}{action_command}"
                                await ws.send(room_command)
                            else:
                                await ws.send(action_command)  # Fallback if no battle ID (shouldn't happen)
                            print(f"AI recommended and used action: {action_command}")
                            battle_state.waiting_for_move = False
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break
            
        input_task.cancel()

async def recommend_move(battle_state):
    print("\n=== RECOMMENDING ACTION ===")
    
    # Check if we need to switch
    must_switch = len(battle_state.available_moves) == 0
    
    # Get available switches (exclude fainted Pokémon)
    available_switches = []
    for index, (pos, pokemon) in enumerate(battle_state.my_team.items(), start=1):
        if not pokemon['active'] and 'fnt' not in pokemon['hp']:
            available_switches.append(index)
    
    print(f"Must switch: {must_switch}")
    print(f"Available switches: {available_switches}")
    print(f"Available moves: {[move['move'] for move in battle_state.available_moves]}")
    
    if must_switch and not available_switches:
        print("ERROR: Must switch but no available switches!")
        return None
    
    # Use the BattleStrategy to make a decision based on context
    decision = battle_state.strategy_engine.make_decision(battle_state.current_context)
    
    # Print the decision explanation
    explanation = battle_state.strategy_engine.explain_decision(decision)
    print("\nStrategy Engine Decision:")
    print(explanation)
    
    # Convert the decision to a command format
    action = decision.get("action")
    target = decision.get("target")
    
    command = None
    
    if action == "move":
        # Find the move index in available_moves
        if not must_switch:
            for i, move in enumerate(battle_state.available_moves, 1):
                if move["move"].lower() == target.lower():
                    command = f"|/choose move {i}"
                    print(f"Found matching move: {move['move']} at index {i}")
                    break
            
            # If exact move not found, use the first available move
            if not command and battle_state.available_moves:
                print(f"Warning: Move '{target}' not found in available moves. Using default.")
                command = f"|/choose move 1"
    
    elif action == "switch":
        # Find the Pokemon index in available_switches
        for index, (pos, pokemon) in enumerate(battle_state.my_team.items(), start=1):
            if not pokemon['active'] and 'fnt' not in pokemon['hp']:
                pokemon_name = pokemon['name'].split(',')[0]
                if pokemon_name.lower() == target.lower():
                    if index in available_switches:
                        command = f"|/choose switch {index}"
                        print(f"Found matching Pokemon: {pokemon_name} at index {index}")
                        break
        
        # If target Pokemon not found or not available, use the first available switch
        if not command and available_switches:
            print(f"Warning: Switch target '{target}' not found or not available. Using default.")
            command = f"|/choose switch {available_switches[0]}"
    
    # Default fallback
    if not command:
        if must_switch and available_switches:
            command = f"|/choose switch {available_switches[0]}"
        elif not must_switch and battle_state.available_moves:
            command = f"|/choose move 1"
    
    print(f"Final command to be sent: {command}")
    return command

async def main():
    try:
        await handle_websocket()
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())

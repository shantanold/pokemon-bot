from langchain_chroma import Chroma
from uuid import uuid4
from langchain_openai import OpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders import CSVLoader
import os
import json
from dotenv import load_dotenv
load_dotenv()

with open("gen9randombattle.json") as f:
    rand_bats = json.load(f)

#load meta movesets
json_documents = []
for pokemon_name, pokemon_data in rand_bats.items():
    # Create a document with the Pokemon name and its data
    doc_content = {pokemon_name: pokemon_data}
    json_documents.append(Document(page_content=json.dumps(doc_content)))
#load typing matchups
typing_matchups = CSVLoader("typing_chart.csv")
typing_matchups = typing_matchups.load()
typing_matchups = [Document(page_content=i.page_content) for i in typing_matchups]
#load pokedex information
pokedex_information = CSVLoader("pokedex.csv")
pokedex_information = pokedex_information.load() 
pokedex_information = [Document(page_content=i.page_content) for i in pokedex_information]

class ContextBuilder:
    def __init__(self):
        self.pokedex = Chroma(
            embedding_function=OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY")),
            collection_name = "Pokemon-Information",
        )
        self.meta_db = Chroma(
            embedding_function=OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY")),
            collection_name="Common-Movesets"
        )
        self.typing_matchups = Chroma(
            embedding_function=OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY")),
            collection_name="Typing-Matchups"
        )
        self.meta_db.add_documents(json_documents)
        self.pokedex.add_documents(pokedex_information)
        self.typing_matchups.add_documents(typing_matchups)
        self.context = {}
        self.battle_state = {
            "player": {
                "active": None,
                "team": [],
                "side_conditions": {}
            },
            "opponent": {
                "active": None,
                "team": [],
                "side_conditions": {}
            },
            "weather": None,
            "terrain": None,
            "turn": 0
        }
        self.battle_history = []
        self.revealed_opponent_moves = {}  # Track opponent's revealed moves by Pokemon
        
        # Parse and load the typing chart
        self.type_chart = self._parse_typing_chart("typing_chart.csv")
        
    def _parse_typing_chart(self, csv_path):
        """Parse the typing chart CSV into a dictionary for quick lookups"""
        type_chart = {}
        try:
            with open(csv_path, 'r') as f:
                lines = f.readlines()
                
                # Get the types from the header row
                types = [t.strip() for t in lines[0].split(',')[1:]]
                
                # Parse each row
                for i in range(1, len(lines)):
                    row = lines[i].split(',')
                    attacking_type = row[0].strip()
                    type_chart[attacking_type] = {}
                    
                    # Parse effectiveness values for each defending type
                    for j, defending_type in enumerate(types):
                        if j < len(row) - 1:
                            value = row[j+1].strip()
                            if value:  # Only add if there's a value
                                type_chart[attacking_type][defending_type] = value
            
            return type_chart
        except Exception as e:
            print(f"Error parsing typing chart: {e}")
            return {}
    
    def construct_context(self, parsed_state):
        """Main method to build context from the current game state"""
        # Update the basic context
        context = {}
        context["active"] = parsed_state.get("active", [])
        print(context["active"])
        context["pokemon"] = parsed_state.get("side", {}).get("pokemon", [])
        self.context = context
        
        # Update battle state with more detailed information
        self._update_battle_state(parsed_state)
        
        # Record state in history
        self._record_battle_state()
        
        # Build comprehensive context with analysis
        return self._build_comprehensive_context()
    
    def _update_battle_state(self, parsed_state):
        """Update internal battle state from parsed game state"""
        # Update player's active Pokemon
        if "active" in parsed_state and parsed_state["active"]:
            active_data = parsed_state["active"][0]
            
            # If details is not in the active data, try to find it from the team
            if "details" not in active_data and "side" in parsed_state and "pokemon" in parsed_state["side"]:
                for pokemon in parsed_state["side"]["pokemon"]:
                    if pokemon.get("active", False):
                        active_data["details"] = pokemon["details"]
                        break
            
            self.battle_state["player"]["active"] = active_data
            print(f"Updated player's active Pokemon in battle state: {active_data.get('details', 'Unknown')}")
        
        # Update player's team
        if "side" in parsed_state and "pokemon" in parsed_state["side"]:
            self.battle_state["player"]["team"] = parsed_state["side"]["pokemon"]
            
        # Update side conditions if available
        if "side" in parsed_state and "conditions" in parsed_state["side"]:
            self.battle_state["player"]["side_conditions"] = parsed_state["side"]["conditions"]
            
        # Update opponent's active Pokemon if available
        if "opponent" in parsed_state and "active" in parsed_state["opponent"]:
            self.battle_state["opponent"]["active"] = parsed_state["opponent"]["active"]
            
            # Check if active is a string or a dictionary
            active_opponent = parsed_state["opponent"]["active"]
            if isinstance(active_opponent, dict):
                details = active_opponent.get('details', 'Unknown')
            else:
                # If it's a string, use it directly
                details = active_opponent
                
            print(f"Updated opponent's active Pokemon in battle state: {details}")
            
        # Update opponent's team if available
        if "opponent" in parsed_state and "pokemon" in parsed_state["opponent"]:
            self.battle_state["opponent"]["team"] = parsed_state["opponent"]["pokemon"]
            
        # Update opponent's side conditions if available
        if "opponent" in parsed_state and "conditions" in parsed_state["opponent"]:
            self.battle_state["opponent"]["side_conditions"] = parsed_state["opponent"]["conditions"]
            
        # Update field conditions
        if "weather" in parsed_state:
            self.battle_state["weather"] = parsed_state["weather"]
            
        if "terrain" in parsed_state:
            self.battle_state["terrain"] = parsed_state["terrain"]
            
        if "turn" in parsed_state:
            self.battle_state["turn"] = parsed_state["turn"]
    
    def _record_battle_state(self):
        """Record current battle state in history"""
        # Create a snapshot of the current state
        current_turn = self.battle_state.get("turn", 0)
        
        # Only record if we have active Pokemon information
        if self.battle_state["player"]["active"] or self.battle_state["opponent"]["active"]:
            # Create a simplified snapshot to avoid storing too much data
            snapshot = {
                "turn": current_turn,
                "player_active": self._get_pokemon_snapshot(self.battle_state["player"]["active"]),
                "opponent_active": self._get_pokemon_snapshot(self.battle_state["opponent"]["active"]),
                "weather": self.battle_state["weather"],
                "terrain": self.battle_state["terrain"]
            }
            
            # Add to history
            self.battle_history.append(snapshot)
            
            # Limit history size to prevent memory issues
            if len(self.battle_history) > 20:  # Keep last 20 turns
                self.battle_history = self.battle_history[-20:]
    
    def _get_pokemon_snapshot(self, pokemon_data):
        """Create a simplified snapshot of Pokemon data"""
        if not pokemon_data:
            return None
            
        return {
            "name": pokemon_data.get("details", "").split(",")[0],
            "hp": pokemon_data.get("hp", 100),
            "status": pokemon_data.get("status", None)
        }
    
    def record_opponent_move(self, pokemon_name, move_name):
        """Record a move used by opponent's Pokemon"""
        if pokemon_name not in self.revealed_opponent_moves:
            self.revealed_opponent_moves[pokemon_name] = set()
            
        self.revealed_opponent_moves[pokemon_name].add(move_name)
    
    def _build_comprehensive_context(self):
        """Build comprehensive context with all relevant battle information"""
        comprehensive_context = {
            "battle_state": self.battle_state,
            "battle_history": self._analyze_battle_history(),
            "analysis": {
                "player_team": self._analyze_team(self.battle_state["player"]["team"], is_player=True),
                "opponent_team": self._analyze_team(self.battle_state["opponent"]["team"], is_player=False),
                "current_matchup": self._analyze_current_matchup(),
                "field_effects": self._analyze_field_effects(),
                "strategic_options": self._generate_strategic_options()
            }
        }
        return comprehensive_context
    
    def _analyze_battle_history(self):
        """Analyze battle history for patterns and insights"""
        if not self.battle_history:
            return {"status": "No history available"}
            
        # Extract opponent's Pokemon usage
        opponent_pokemon_usage = {}
        for snapshot in self.battle_history:
            opponent_active = snapshot.get("opponent_active")
            if opponent_active and opponent_active.get("name"):
                pokemon_name = opponent_active.get("name")
                if pokemon_name in opponent_pokemon_usage:
                    opponent_pokemon_usage[pokemon_name] += 1
                else:
                    opponent_pokemon_usage[pokemon_name] = 1
        
        # Analyze HP trends
        hp_trends = []
        for i in range(1, len(self.battle_history)):
            prev = self.battle_history[i-1]
            curr = self.battle_history[i]
            
            player_hp_change = 0
            opponent_hp_change = 0
            
            # Calculate player HP change
            prev_player = prev.get("player_active", {})
            curr_player = curr.get("player_active", {})
            if prev_player and curr_player and prev_player.get("name") == curr_player.get("name"):
                player_hp_change = curr_player.get("hp", 0) - prev_player.get("hp", 0)
            
            # Calculate opponent HP change
            prev_opponent = prev.get("opponent_active", {})
            curr_opponent = curr.get("opponent_active", {})
            if prev_opponent and curr_opponent and prev_opponent.get("name") == curr_opponent.get("name"):
                opponent_hp_change = curr_opponent.get("hp", 0) - prev_opponent.get("hp", 0)
            
            hp_trends.append({
                "turn": curr.get("turn"),
                "player_hp_change": player_hp_change,
                "opponent_hp_change": opponent_hp_change
            })
        
        # Analyze opponent's revealed moves
        revealed_moves_analysis = {}
        for pokemon, moves in self.revealed_opponent_moves.items():
            move_types = set()
            for move in moves:
                # Get move type using similarity search (fallback)
                move_type = "Normal"  # Default
                move_results = self.typing_matchups.similarity_search(
                    f"move {move} type", 
                    k=1
                )
                
                if move_results:
                    move_text = move_results[0].page_content
                    parts = move_text.split(',')
                    if parts:
                        move_types.add(parts[0].strip())
            
            revealed_moves_analysis[pokemon] = {
                "moves": list(moves),
                "move_types": list(move_types)
            }
        
        return {
            "opponent_pokemon_usage": opponent_pokemon_usage,
            "hp_trends": hp_trends,
            "revealed_moves": revealed_moves_analysis,
            "recent_turns": self.battle_history[-3:] if len(self.battle_history) >= 3 else self.battle_history
        }
    
    def _get_pokemon_details(self, pokemon_name):
        """Get detailed information about a Pokemon from databases"""
        # Try to get from meta_db first (for movesets)
        meta_results = self.meta_db.similarity_search(pokemon_name, k=1)
        pokemon_data = {}
        if meta_results:
            try:
                meta_content = meta_results[0].page_content
                meta_json = json.loads(meta_content)
                # Extract the Pokemon data from the document
                if pokemon_name in meta_json:
                    pokemon_data = meta_json[pokemon_name]
                else:
                    # Try to find the first key if exact match not found
                    first_key = list(meta_json.keys())[0]
                    pokemon_data = meta_json[first_key]
            except Exception as e:
                print(f"Error parsing meta data for {pokemon_name}: {e}")
        
        # Get pokedex information
        pokedex_results = self.pokedex.similarity_search(pokemon_name, k=1)
        types = []
        stats = {}
        
        if pokedex_results:
            try:
                pokedex_text = pokedex_results[0].page_content
                # Parse CSV-like content
                pokedex_parts = pokedex_text.split('\n')
                if len(pokedex_parts) >= 4:
                    # Extract types (usually in positions 1 and 2)
                    types = pokedex_parts[10]
                    # Extract stats if available
                    if len(pokedex_parts) > 3:
                        stat_names = ["hp", "attack", "defense", "sp_attack", "sp_defense", "speed"]
                        for i, stat in enumerate(stat_names):
                            if i + 3 < len(pokedex_parts) and pokedex_parts[i + 3].strip():
                                try:
                                    stats[stat] = int(pokedex_parts[i + 3])
                                except ValueError:
                                    stats[stat] = 0
            except Exception as e:
                print(f"Error parsing pokedex data for {pokemon_name}: {e}")
        
        # Get type weaknesses
        weaknesses = self._get_type_weaknesses(types)
        
        # Combine all information
        combined_data = {
            "name": pokemon_name,
            "types": types,
            "stats": stats,
            "abilities": pokemon_data.get("abilities", {}),
            "common_items": pokemon_data.get("items", {}),
            "common_roles": pokemon_data.get("roles", {}),
            "weaknesses": weaknesses
        }
        
        return combined_data
    
    def _get_type_weaknesses(self, types):
        """Get type weaknesses for given Pokemon types"""
        if not types:
            return []
            
        weaknesses = []
        
        # For each of the Pokemon's types, find attacking types that are super effective
        for type_name in types:
            type_name = type_name.strip()
            # Check each attacking type in the type chart
            for attacking_type, defenses in self.type_chart.items():
                # If this attacking type is super effective against the defending type
                if type_name in defenses and defenses[type_name] in ["2", "4"]:
                    weaknesses.append(attacking_type)
        
        return list(set(weaknesses))  # Remove duplicates
    
    def _analyze_team(self, team, is_player=True):
        """Analyze a team's strengths, weaknesses, and coverage"""
        if not team:
            return {"status": "unknown"}
            
        team_analysis = {
            "pokemon": [],
            "team_typing": {},
            "overall_strengths": [],
            "overall_weaknesses": []
        }
        
        type_counts = {}
        team_strengths = set()
        team_weaknesses = set()
        
        for pokemon in team:
            pokemon_name = pokemon.get("details", "").split(",")[0]
            if not pokemon_name:
                continue
                
            # Get detailed Pokemon info
            pokemon_info = self._get_pokemon_details(pokemon_name)
            
            # For player's Pokemon, we know the moves
            if is_player:
                moves_analysis = self._analyze_moves(pokemon.get("moves", []))
            else:
                # For opponent, predict possible movesets
                moves_analysis = self._predict_possible_movesets(pokemon_name)
            
            # Add types to the count
            for type_name in pokemon_info.get("types", []):
                if type_name in type_counts:
                    type_counts[type_name] += 1
                else:
                    type_counts[type_name] = 1
            
            # Add to team analysis
            pokemon_analysis = {
                "name": pokemon_name,
                "details": pokemon_info,
                "current_hp_percent": pokemon.get("hp", 100) / 100 if pokemon.get("hp") else 1.0,
                "status": pokemon.get("status", None),
                "moves": moves_analysis
            }
            
            # Add strengths and weaknesses
            team_strengths.update(moves_analysis.get("strengths", []))
            team_weaknesses.update(pokemon_info.get("weaknesses", []))
            
            team_analysis["pokemon"].append(pokemon_analysis)
        
        team_analysis["team_typing"] = type_counts
        team_analysis["overall_strengths"] = list(team_strengths)
        team_analysis["overall_weaknesses"] = list(team_weaknesses)
        
        return team_analysis
    
    def _analyze_moves(self, moves):
        """Analyze a set of moves for type coverage and effectiveness"""
        if not moves:
            return {"moves": [], "strengths": []}
            
        move_analysis = {
            "moves": [],
            "strengths": []
        }
        
        for move in moves:
            # For now, we'll assume the move type is the same as the move name
            # In a real implementation, you'd have a mapping of moves to their types
            # This is a simplification - you should replace this with actual move type data
            move_type = "Normal"  # Default
            
            # Try to get move type from similarity search (fallback)
            # In a complete implementation, you'd replace this with a direct lookup
            move_results = self.typing_matchups.similarity_search(
                f"move {move} type", 
                k=1
            )
            
            if move_results:
                move_text = move_results[0].page_content
                parts = move_text.split(',')
                if len(parts) >= 1:
                    move_type = parts[0].strip()
            
            move_analysis["moves"].append({
                "name": move,
                "type": move_type
            })
            
            # Find what this move is strong against using the type chart
            if move_type in self.type_chart:
                for defending_type, effectiveness in self.type_chart[move_type].items():
                    if effectiveness in ["2", "4"]:
                        move_analysis["strengths"].append(defending_type)
        
        move_analysis["strengths"] = list(set(move_analysis["strengths"]))  # Remove duplicates
        return move_analysis
    
    def _predict_possible_movesets(self, pokemon_name):
        """Predict possible movesets for opponent's Pokemon"""
        meta_results = self.meta_db.similarity_search(pokemon_name, k=1)
        
        if not meta_results:
            return {"moves": [], "strengths": []}
            
        try:
            meta_content = meta_results[0].page_content
            meta_json = json.loads(meta_content)
            
            # Extract the Pokemon data
            pokemon_data = None
            if pokemon_name in meta_json:
                pokemon_data = meta_json[pokemon_name]
            else:
                # Try to find the first key if exact match not found
                first_key = list(meta_json.keys())[0]
                pokemon_data = meta_json[first_key]
                
            if not pokemon_data:
                return {"moves": [], "strengths": []}
                
            # Extract common moves from roles
            all_moves = set()
            for role_data in pokemon_data.get("roles", {}).values():
                role_moves = role_data.get("moves", {})
                all_moves.update(role_moves.keys())
            
            # Analyze these moves
            return self._analyze_moves(list(all_moves))
            
        except Exception as e:
            print(f"Error predicting movesets for {pokemon_name}: {e}")
            return {"moves": [], "strengths": []}
    
    def _analyze_current_matchup(self):
        """Analyze the current active Pokemon matchup"""
        #print("The battle state is as follows",self.battle_state)
        player_active = self.battle_state["player"]["active"]
        opponent_active = self.battle_state["opponent"]["active"]
        
        print("\n=== ANALYZING CURRENT MATCHUP ===")
        print(f"Player active data: {player_active}")
        print(f"Opponent active data: {opponent_active}")
        
        if not player_active:
            print("Missing player's active Pokémon data")
            return {"status": "incomplete", "reason": "Missing player's active Pokémon data"}
            
        if not opponent_active:
            print("Missing opponent's active Pokémon data")
            return {"status": "incomplete", "reason": "Missing opponent's active Pokémon data"}
        
        # Extract player Pokémon name, handling different possible formats
        player_pokemon = None
        if isinstance(player_active, dict):
            if "details" in player_active:
                player_pokemon = player_active["details"].split(",")[0]
                print(f"Extracted player Pokémon from details: {player_pokemon}")
            elif "name" in player_active:
                player_pokemon = player_active["name"].split(",")[0]
                print(f"Extracted player Pokémon from name: {player_pokemon}")
        elif isinstance(player_active, str):
            player_pokemon = player_active.split(",")[0]
            print(f"Extracted player Pokémon from string: {player_pokemon}")
            
        # Extract opponent Pokémon name, handling different possible formats
        opponent_pokemon = None
        if isinstance(opponent_active, dict):
            if "details" in opponent_active:
                opponent_pokemon = opponent_active["details"].split(",")[0]
                print(f"Extracted opponent Pokémon from details: {opponent_pokemon}")
            elif "name" in opponent_active:
                opponent_pokemon = opponent_active["name"].split(",")[0]
                print(f"Extracted opponent Pokémon from name: {opponent_pokemon}")
        elif isinstance(opponent_active, str):
            opponent_pokemon = opponent_active.split(",")[0]
            print(f"Extracted opponent Pokémon from string: {opponent_pokemon}")
        
        # If we couldn't extract names, return incomplete status
        if not player_pokemon:
            print(f"Could not extract player Pokémon name from active data: {player_active}")
            return {"status": "incomplete", "reason": "Could not extract player Pokémon name"}
            
        if not opponent_pokemon:
            print(f"Could not extract opponent Pokémon name from active data: {opponent_active}")
            return {"status": "incomplete", "reason": "Could not extract opponent Pokémon name"}
            
        print(f"Analyzing matchup: {player_pokemon} vs {opponent_pokemon}")
        
        player_details = self._get_pokemon_details(player_pokemon)
        opponent_details = self._get_pokemon_details(opponent_pokemon)
        #print("The details of the opponent are as follows",opponent_details)
        # Analyze type matchup
        player_moves = []
        if isinstance(player_active, dict) and "moves" in player_active:
            player_moves = player_active["moves"]
        player_move_analysis = self._analyze_moves(player_moves)
        
        # Check if player has super effective moves
        player_has_super_effective = any(
            type_name in player_move_analysis["strengths"] 
            for type_name in opponent_details["types"]
        )
        print("player_move_analysis",player_move_analysis["strengths"])
        # Check if opponent might have super effective moves
        opponent_move_analysis = self._predict_possible_movesets(opponent_pokemon)
        opponent_might_have_super_effective = any(
            type_name in opponent_move_analysis["strengths"] 
            for type_name in player_details["types"]
        )
        
        # Speed comparison
        player_speed = player_details.get("stats", {}).get("speed", 0)
        opponent_speed = opponent_details.get("stats", {}).get("speed", 0)
        
        # HP percentage calculation with safety checks
        player_hp_percent = 1.0
        if isinstance(player_active, dict) and "hp" in player_active:
            try:
                player_hp_percent = player_active["hp"] / 100 if player_active["hp"] else 1.0
            except (TypeError, ZeroDivisionError):
                player_hp_percent = 1.0
                
        opponent_hp_percent = 1.0
        if isinstance(opponent_active, dict) and "hp" in opponent_active:
            try:
                opponent_hp_percent = opponent_active["hp"] / 100 if opponent_active["hp"] else 1.0
            except (TypeError, ZeroDivisionError):
                opponent_hp_percent = 1.0
        
        matchup_result = {
            "player_pokemon": player_pokemon,
            "opponent_pokemon": opponent_pokemon,
            "player_has_super_effective": player_has_super_effective,
            "opponent_might_have_super_effective": opponent_might_have_super_effective,
            "player_faster": player_speed > opponent_speed,
            "speed_comparison": f"{player_speed} vs {opponent_speed}",
            "player_hp_percent": player_hp_percent,
            "opponent_hp_percent": opponent_hp_percent
        }
        
        print(f"Matchup analysis result: {matchup_result}")
        print("=== END MATCHUP ANALYSIS ===\n")
        
        return matchup_result
    
    def _analyze_field_effects(self):
        """Analyze current field effects and their impact"""
        weather = self.battle_state["weather"]
        terrain = self.battle_state["terrain"]
        player_conditions = self.battle_state["player"]["side_conditions"]
        opponent_conditions = self.battle_state["opponent"]["side_conditions"]
        
        weather_effects = {}
        if weather:
            # Define weather effects
            weather_effects = {
                "Rain": {
                    "boosts": ["Water"],
                    "reduces": ["Fire"],
                    "description": "Boosts Water moves, reduces Fire moves"
                },
                "Sun": {
                    "boosts": ["Fire"],
                    "reduces": ["Water"],
                    "description": "Boosts Fire moves, reduces Water moves"
                },
                "Sand": {
                    "boosts": ["Rock"],
                    "reduces": [],
                    "description": "Boosts Rock-type Pokémon's Special Defense"
                },
                "Hail": {
                    "boosts": ["Ice"],
                    "reduces": [],
                    "description": "Damages non-Ice types each turn"
                }
            }.get(weather, {})
        
        terrain_effects = {}
        if terrain:
            # Define terrain effects
            terrain_effects = {
                "Electric": {
                    "boosts": ["Electric"],
                    "prevents": ["Sleep"],
                    "description": "Boosts Electric moves, prevents sleep"
                },
                "Grassy": {
                    "boosts": ["Grass"],
                    "reduces": ["Earthquake"],
                    "description": "Boosts Grass moves, reduces Earthquake damage, heals grounded Pokémon"
                },
                "Misty": {
                    "reduces": ["Dragon"],
                    "prevents": ["Status conditions"],
                    "description": "Reduces Dragon moves, prevents status conditions"
                },
                "Psychic": {
                    "boosts": ["Psychic"],
                    "prevents": ["Priority moves"],
                    "description": "Boosts Psychic moves, prevents priority moves against grounded Pokémon"
                }
            }.get(terrain, {})
        
        return {
            "weather": {
                "name": weather,
                "effects": weather_effects
            },
            "terrain": {
                "name": terrain,
                "effects": terrain_effects
            },
            "player_conditions": player_conditions,
            "opponent_conditions": opponent_conditions
        }
    
    def _generate_strategic_options(self):
        """Generate strategic options based on current battle state"""
        player_active = self.battle_state["player"]["active"]
        opponent_active = self.battle_state["opponent"]["active"]
        
        if not player_active or not opponent_active:
            return {"options": ["Gather more information"]}
            
        player_pokemon = player_active.get("details", "").split(",")[0]
        opponent_pokemon = opponent_active.get("details", "").split(",")[0]
        
        matchup = self._analyze_current_matchup()
        
        strategic_options = []
        
        # Check if we have super effective moves
        if matchup.get("player_has_super_effective", False):
            strategic_options.append("Use super effective move")
        
        # Check if we're at a disadvantage
        if matchup.get("opponent_might_have_super_effective", False):
            strategic_options.append("Consider switching to resist opponent's moves")
        
        # Check HP percentages
        player_hp = matchup.get("player_hp_percent", 1)
        opponent_hp = matchup.get("opponent_hp_percent", 1)
        
        if player_hp < 0.3:
            strategic_options.append("Low HP - consider healing or switching")
        
        if opponent_hp < 0.3:
            strategic_options.append("Opponent low HP - focus on finishing")
        
        # Speed considerations
        if matchup.get("player_faster", False):
            strategic_options.append("Speed advantage - consider priority attacks")
        else:
            strategic_options.append("Speed disadvantage - consider priority moves or defensive play")
        
        # Field effect considerations
        field_effects = self._analyze_field_effects()
        weather = field_effects.get("weather", {}).get("name")
        terrain = field_effects.get("terrain", {}).get("name")
        
        if weather:
            weather_effects = field_effects.get("weather", {}).get("effects", {})
            boosted_types = weather_effects.get("boosts", [])
            reduced_types = weather_effects.get("reduces", [])
            
            # Check if we have moves that are boosted by weather
            player_moves = player_active.get("moves", [])
            move_analysis = self._analyze_moves(player_moves)
            
            for move in move_analysis.get("moves", []):
                if move.get("type") in boosted_types:
                    strategic_options.append(f"Use {move.get('name')} - boosted by {weather}")
        
        return {
            "options": strategic_options,
            "explanation": "Strategic options based on current battle state"
        }
    
    def get_counter_types(self, pokemon_name):
        """Get counter types for a specific Pokemon"""
        pokemon_details = self._get_pokemon_details(pokemon_name)
        types = pokemon_details.get("types", [])
        
        counter_suggestions = []
        for type_name in types:
            # Search for matchups where this type is weak
            matchups = self.typing_matchups.similarity_search(
                f"moves that are super effective against {type_name}", 
                k=2
            )
            counter_suggestions.extend([match.page_content for match in matchups])
            
        return {
            "pokemon": pokemon_name,
            "types": types,
            "weaknesses": pokemon_details.get("weaknesses", []),
            "suggested_counters": counter_suggestions
        }
    
    def suggest_switch(self, opponent_pokemon):
        """Suggest which Pokemon to switch to against opponent's active"""
        if not self.battle_state["player"]["team"]:
            return {"suggestion": "No team data available"}
            
        opponent_details = self._get_pokemon_details(opponent_pokemon)
        opponent_types = opponent_details.get("types", [])
        opponent_moves = self._predict_possible_movesets(opponent_pokemon)
        
        best_switches = []
        
        for pokemon in self.battle_state["player"]["team"]:
            if pokemon.get("active", False):
                continue  # Skip currently active Pokemon
                
            pokemon_name = pokemon.get("details", "").split(",")[0]
            pokemon_details = self._get_pokemon_details(pokemon_name)
            
            # Check if this Pokemon resists opponent's types
            resists_count = 0
            for opponent_type in opponent_types:
                if opponent_type not in pokemon_details.get("weaknesses", []):
                    resists_count += 1
            
            # Check if this Pokemon has super effective moves
            pokemon_moves = self._analyze_moves(pokemon.get("moves", []))
            super_effective_count = 0
            for opponent_type in opponent_types:
                if opponent_type in pokemon_moves.get("strengths", []):
                    super_effective_count += 1
            
            # Calculate a simple score
            score = resists_count + super_effective_count
            
            best_switches.append({
                "pokemon": pokemon_name,
                "score": score,
                "resists_opponent_types": resists_count > 0,
                "has_super_effective": super_effective_count > 0
            })
        
        # Sort by score
        best_switches.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "opponent": opponent_pokemon,
            "opponent_types": opponent_types,
            "switch_options": best_switches[:3]  # Top 3 options
        }
    
    def suggest_best_move(self):
        """Suggest the best move for the current matchup"""
        player_active = self.battle_state["player"]["active"]
        opponent_active = self.battle_state["opponent"]["active"]
        
        if not player_active or not opponent_active:
            return {"suggestion": "Insufficient data"}
            
        player_pokemon = player_active.get("details", "").split(",")[0]
        opponent_pokemon = opponent_active.get("details", "").split(",")[0]
        
        opponent_details = self._get_pokemon_details(opponent_pokemon)
        opponent_types = opponent_details.get("types", [])
        
        player_moves = player_active.get("moves", [])
        move_ratings = []
        
        for move in player_moves:
            # Get move type (same approach as in _analyze_moves)
            move_type = "Normal"  # Default
            move_results = self.typing_matchups.similarity_search(
                f"move {move} type", 
                k=1
            )
            
            if move_results:
                move_text = move_results[0].page_content
                parts = move_text.split(',')
                if len(parts) >= 1:
                    move_type = parts[0].strip()
            
            # Check effectiveness against opponent types using the type chart
            effectiveness_score = 0
            for opponent_type in opponent_types:
                opponent_type = opponent_type.strip()
                if move_type in self.type_chart and opponent_type in self.type_chart[move_type]:
                    effectiveness = self.type_chart[move_type][opponent_type]
                    if effectiveness == "2":
                        effectiveness_score += 2  # Super effective
                    elif effectiveness == "4":
                        effectiveness_score += 4  # Double super effective
                    elif effectiveness == "0.5":
                        effectiveness_score -= 1  # Not very effective
                    elif effectiveness == "0.25":
                        effectiveness_score -= 2  # Double not very effective
                    elif effectiveness == "0":
                        effectiveness_score -= 5  # No effect
            
            # Consider field effects
            field_effects = self._analyze_field_effects()
            weather = field_effects.get("weather", {}).get("name")
            terrain = field_effects.get("terrain", {}).get("name")
            
            weather_bonus = 0
            if weather:
                weather_effects = field_effects.get("weather", {}).get("effects", {})
                if move_type in weather_effects.get("boosts", []):
                    weather_bonus = 1
                elif move_type in weather_effects.get("reduces", []):
                    weather_bonus = -1
            
            terrain_bonus = 0
            if terrain:
                terrain_effects = field_effects.get("terrain", {}).get("effects", {})
                if move_type in terrain_effects.get("boosts", []):
                    terrain_bonus = 1
                elif move_type in terrain_effects.get("reduces", []):
                    terrain_bonus = -1
            
            # Calculate final score
            final_score = effectiveness_score + weather_bonus + terrain_bonus
            
            move_ratings.append({
                "move": move,
                "type": move_type,
                "effectiveness_score": effectiveness_score,
                "weather_bonus": weather_bonus,
                "terrain_bonus": terrain_bonus,
                "final_score": final_score
            })
        
        # Sort by final score
        move_ratings.sort(key=lambda x: x["final_score"], reverse=True)
        
        return {
            "player_pokemon": player_pokemon,
            "opponent_pokemon": opponent_pokemon,
            "opponent_types": opponent_types,
            "move_ratings": move_ratings,
            "best_move": move_ratings[0]["move"] if move_ratings else None
        }
        
    def should_switch(self):
        """Determine if the player should switch Pokemon"""
        player_active = self.battle_state["player"]["active"]
        opponent_active = self.battle_state["opponent"]["active"]
        
        if not player_active or not opponent_active:
            return {"should_switch": False, "reason": "Insufficient data"}
            
        player_pokemon = player_active.get("details", "").split(",")[0]
        opponent_pokemon = opponent_active.get("details", "").split(",")[0]
        
        # Get matchup analysis
        matchup = self._analyze_current_matchup()
        
        # Check if opponent has super effective moves
        if matchup.get("opponent_might_have_super_effective", False):
            # Check if we're at a significant HP disadvantage
            if matchup.get("player_hp_percent", 1.0) < 0.5:
                return {
                    "should_switch": True, 
                    "reason": f"Disadvantageous matchup against {opponent_pokemon} and low HP"
                }
        
        # Check if player has no effective moves
        move_suggestion = self.suggest_best_move()
        best_move_score = 0
        if move_suggestion.get("move_ratings"):
            best_move_score = move_suggestion["move_ratings"][0].get("final_score", 0)
            
        if best_move_score < 0:
            return {
                "should_switch": True,
                "reason": f"No effective moves against {opponent_pokemon}"
            }
        
        # Check if player is at very low HP
        if matchup.get("player_hp_percent", 1.0) < 0.25:
            return {
                "should_switch": True,
                "reason": "Very low HP, risk of being knocked out"
            }
        
        # Check if player has a status condition that severely limits effectiveness
        if player_active.get("status") in ["slp", "frz", "par"]:
            return {
                "should_switch": True,
                "reason": f"Hindering status condition: {player_active.get('status')}"
            }
        
        return {"should_switch": False, "reason": "Current matchup is favorable or neutral"}
    
    def analyze_opponent_team(self):
        """Analyze opponent's team composition and potential threats"""
        opponent_team = self.battle_state["opponent"]["team"]
        
        if not opponent_team:
            return {"status": "No opponent team data available"}
        
        # Analyze each revealed Pokemon
        revealed_pokemon = []
        for pokemon in opponent_team:
            pokemon_name = pokemon.get("details", "").split(",")[0]
            if not pokemon_name:
                continue
                
            # Get Pokemon details
            pokemon_details = self._get_pokemon_details(pokemon_name)
            
            # Get revealed moves if any
            revealed_moves = []
            if pokemon_name in self.revealed_opponent_moves:
                revealed_moves = list(self.revealed_opponent_moves[pokemon_name])
            
            # Predict potential moves based on common movesets
            predicted_moves = self._predict_possible_movesets(pokemon_name)
            
            # Determine potential threat level to our team
            threat_level = self._calculate_threat_level(pokemon_details)
            
            revealed_pokemon.append({
                "name": pokemon_name,
                "types": pokemon_details.get("types", []),
                "revealed_moves": revealed_moves,
                "predicted_moves": predicted_moves.get("moves", []),
                "threat_level": threat_level
            })
        
        # Analyze team type coverage
        type_coverage = {}
        for pokemon in revealed_pokemon:
            for type_name in pokemon.get("types", []):
                if type_name in type_coverage:
                    type_coverage[type_name] += 1
                else:
                    type_coverage[type_name] = 1
        
        # Sort threats by level
        revealed_pokemon.sort(key=lambda x: x["threat_level"], reverse=True)
        
        return {
            "revealed_pokemon": revealed_pokemon,
            "type_coverage": type_coverage,
            "top_threats": revealed_pokemon[:2] if len(revealed_pokemon) >= 2 else revealed_pokemon
        }
    
    def _calculate_threat_level(self, pokemon_details):
        """Calculate threat level of an opponent's Pokemon to our team"""
        player_team = self.battle_state["player"]["team"]
        
        if not player_team or not pokemon_details:
            return 0
        
        threat_score = 0
        opponent_types = pokemon_details.get("types", [])
        
        # Check how many of our Pokemon are weak to this Pokemon's types
        for player_pokemon in player_team:
            player_name = player_pokemon.get("details", "").split(",")[0]
            player_details = self._get_pokemon_details(player_name)
            
            # Check if player Pokemon is weak to opponent's types
            for opponent_type in opponent_types:
                if opponent_type in player_details.get("weaknesses", []):
                    threat_score += 1
        
        # Consider base stats as a factor
        stats = pokemon_details.get("stats", {})
        base_stat_total = sum(stats.values())
        
        # Normalize base stat total to a 0-3 scale
        stat_factor = min(3, max(0, base_stat_total / 200))
        
        # Combine factors
        total_threat = threat_score + stat_factor
        
        return total_threat
    
    def predict_opponent_switch(self):
        """Predict if opponent might switch and to which Pokemon"""
        opponent_active = self.battle_state["opponent"]["active"]
        opponent_team = self.battle_state["opponent"]["team"]
        player_active = self.battle_state["player"]["active"]
        
        if not opponent_active or not player_active or not opponent_team:
            return {"prediction": "Insufficient data"}
        
        opponent_pokemon = opponent_active.get("details", "").split(",")[0]
        player_pokemon = player_active.get("details", "").split(",")[0]
        
        # Get matchup analysis
        matchup = self._analyze_current_matchup()
        
        # Check if we have super effective moves against opponent
        if matchup.get("player_has_super_effective", False):
            switch_probability = 0.7  # 70% chance they might switch
        else:
            switch_probability = 0.3  # 30% chance they might switch
        
        # Check opponent's HP
        opponent_hp = matchup.get("opponent_hp_percent", 1.0)
        if opponent_hp < 0.3:
            switch_probability += 0.2  # More likely to switch at low HP
        
        # Check if opponent has a bad status condition
        if opponent_active.get("status") in ["slp", "frz", "par"]:
            switch_probability += 0.2  # More likely to switch with bad status
        
        # Cap probability at 0.9 (90%)
        switch_probability = min(0.9, switch_probability)
        
        # Predict which Pokemon they might switch to
        potential_switches = []
        
        player_details = self._get_pokemon_details(player_pokemon)
        player_types = player_details.get("types", [])
        
        for pokemon in opponent_team:
            if pokemon.get("active", False):
                continue  # Skip currently active Pokemon
                
            pokemon_name = pokemon.get("details", "").split(",")[0]
            pokemon_details = self._get_pokemon_details(pokemon_name)
            
            # Check if this Pokemon resists player's types
            resistance_score = 0
            for player_type in player_types:
                if player_type not in pokemon_details.get("weaknesses", []):
                    resistance_score += 1
            
            potential_switches.append({
                "pokemon": pokemon_name,
                "resistance_score": resistance_score,
                "types": pokemon_details.get("types", [])
            })
        
        # Sort by resistance score
        potential_switches.sort(key=lambda x: x["resistance_score"], reverse=True)
        
        return {
            "current_opponent": opponent_pokemon,
            "switch_probability": switch_probability,
            "potential_switches": potential_switches[:2] if potential_switches else []
        }
    
    def analyze_team_coverage(self):
        """Analyze team's type coverage and identify gaps"""
        player_team = self.battle_state["player"]["team"]
        
        if not player_team:
            return {"status": "No team data available"}
        
        # Get all Pokemon types
        all_types = [
            "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", 
            "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", 
            "Dragon", "Dark", "Steel", "Fairy"
        ]
        
        # Initialize coverage map
        coverage = {type_name: 0 for type_name in all_types}
        
        # Analyze each Pokemon's move coverage
        for pokemon in player_team:
            pokemon_name = pokemon.get("details", "").split(",")[0]
            moves = pokemon.get("moves", [])
            
            move_analysis = self._analyze_moves(moves)
            
            # Add coverage from this Pokemon's moves
            for type_name in move_analysis.get("strengths", []):
                if type_name in coverage:
                    coverage[type_name] += 1
        
        # Identify gaps in coverage
        gaps = []
        for type_name, count in coverage.items():
            if count == 0:
                gaps.append(type_name)
            
        # Calculate overall coverage percentage
        covered_types = sum(1 for count in coverage.values() if count > 0)
        coverage_percentage = (covered_types / len(all_types)) * 100
        
        return {
            "type_coverage": coverage,
            "coverage_percentage": coverage_percentage,
            "gaps": gaps
        }
    
    def get_move_description(self, move_name):
        """Get detailed description of a move"""
        # Get move type (same approach as in _analyze_moves)
        move_type = "Normal"  # Default
        move_results = self.typing_matchups.similarity_search(
            f"move {move_name} type", 
            k=1
        )
        
        if move_results:
            move_text = move_results[0].page_content
            parts = move_text.split(',')
            if len(parts) >= 1:
                move_type = parts[0].strip()
        
        # Get effectiveness against all types using the type chart
        effectiveness = {}
        all_types = [
            "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", 
            "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", 
            "Dragon", "Dark", "Steel", "Fairy"
        ]
        
        if move_type in self.type_chart:
            for defending_type in all_types:
                if defending_type in self.type_chart[move_type]:
                    effectiveness[defending_type] = self.type_chart[move_type][defending_type]
                else:
                    effectiveness[defending_type] = "1"  # Default to neutral if not specified
        
        return {
            "move": move_name,
            "type": move_type,
            "effectiveness": effectiveness
        }
    
    def get_decision(self):
        """Get the final decision for the current turn"""
        # Check if we should switch
        switch_analysis = self.should_switch()
        
        if switch_analysis.get("should_switch", False):
            # Find the best Pokemon to switch to
            opponent_active = self.battle_state["opponent"]["active"]
            if opponent_active:
                opponent_name = opponent_active.get("details", "").split(",")[0]
                switch_suggestion = self.suggest_switch(opponent_name)
                
                # Get the target Pokemon name, ensuring it's a string
                target_pokemon = None
                if switch_suggestion.get("switch_options"):
                    target_pokemon = switch_suggestion["switch_options"][0].get("pokemon", "")
                
                # If no valid target found, use the first available Pokemon from the team
                if not target_pokemon and self.battle_state["player"]["team"]:
                    for pokemon in self.battle_state["player"]["team"]:
                        if not pokemon.get("active", False) and "fnt" not in pokemon.get("hp", ""):
                            target_pokemon = pokemon.get("details", "").split(",")[0]
                            break
                
                # Ensure target is a string
                if not target_pokemon:
                    target_pokemon = "default"
                
                return {
                    "action": "switch",
                    "target": target_pokemon,
                    "reason": switch_analysis.get("reason", "Strategic switch"),
                    "confidence": 0.8
                }
        
        # If not switching, find the best move
        move_suggestion = self.suggest_best_move()
        
        if move_suggestion.get("best_move"):
            # Ensure best_move is a string
            best_move = move_suggestion.get("best_move", "")
            if not isinstance(best_move, str):
                best_move = str(best_move)
            
            return {
                "action": "move",
                "target": best_move,
                "reason": f"Best move against {move_suggestion.get('opponent_pokemon', 'opponent')}",
                "confidence": 0.9
            }
        
        # Fallback - ensure we return a valid move string
        default_move = ""
        if self.battle_state["player"]["active"] and self.battle_state["player"]["active"].get("moves"):
            if isinstance(self.battle_state["player"]["active"]["moves"][0], dict):
                default_move = self.battle_state["player"]["active"]["moves"][0].get("move", "")
            elif isinstance(self.battle_state["player"]["active"]["moves"][0], str):
                default_move = self.battle_state["player"]["active"]["moves"][0]
        
        if not default_move:
            default_move = "default"
        
        return {
            "action": "move",
            "target": default_move,
            "reason": "Default action",
            "confidence": 0.5
        }
  




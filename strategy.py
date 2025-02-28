import json
from typing import Dict, List, Any, Tuple, Optional
import os
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BattleStrategy:
    """
    A decision-making agent for Pokemon battles that uses LangChain and OpenAI
    to make strategic decisions based on context from ContextBuilder.
    """
    
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.8):
        """Initialize the strategy agent with LLM capabilities"""
        self.last_decision = None
        self.decision_history = []
        
        # Initialize the language model
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Set up output parser for structured decisions
        self.output_parser = self._create_output_parser()
        
        # Create the prompt template
        self.prompt = self._create_prompt_template()
        
    def _create_output_parser(self):
        """Create a structured output parser for decision responses"""
        action_schema = ResponseSchema(
            name="action",
            description="The action to take: 'move' or 'switch'",
            type="string"
        )
        
        target_schema = ResponseSchema(
            name="target",
            description="If action is 'move', this is the move name. If action is 'switch', this is the Pokemon to switch to.",
            type="string"
        )
        
        reason_schema = ResponseSchema(
            name="reason",
            description="A detailed explanation of why this decision was made",
            type="string"
        )
        
        confidence_schema = ResponseSchema(
            name="confidence",
            description="A confidence score between 0.0 and 1.0 for this decision",
            type="number"
        )
        
        return StructuredOutputParser.from_response_schemas([
            action_schema, target_schema, reason_schema, confidence_schema
        ])
    
    def _create_prompt_template(self):
        """Create the prompt template for decision making"""
        template = """
        You are a Pokemon battle expert AI assistant. Your task is to analyze the current battle state and make the optimal strategic decision.

        # Battle Context
        {battle_context}

        # Current Battle State
        Player's Active Pokemon: {player_active}
        Opponent's Active Pokemon: {opponent_active}
        Player's Team: {player_team}
        Opponent's Team: {opponent_team}
        Weather: {weather}
        Terrain: {terrain}
        Turn: {turn}

        # Analysis
        Current Matchup Analysis: {matchup_analysis}
        Field Effects Analysis: {field_effects}
        Strategic Options: {strategic_options}

        Based on this information, decide whether to use a move or switch to another Pokemon.
        Consider type matchups, effectiveness, current HP, status conditions, individual stats
        like speed and defense, secondary move effects, potential opponent moves, and field effects.

        {format_instructions}
        """
        
        return ChatPromptTemplate.from_template(template)
    
    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a strategic decision based on the provided battle context using LLM
        
        Args:
            context: The comprehensive battle context from ContextBuilder
            
        Returns:
            A decision dictionary with action, target/move, reason, and confidence
        """
        # Extract key information from context
        battle_state = context.get("battle_state", {})
        analysis = context.get("analysis", {})
        print("LINE 109 strategy.py")
        # Format the context for the prompt
        formatted_context = self._format_context_for_prompt(context)
        print("LINE 112 strategy.py")

        # Get format instructions
        format_instructions = self.output_parser.get_format_instructions()
        print("LINE 115 strategy.py")
        #print(self.prompt)
        # Create the prompt with all the information
        try:
            messages = self.prompt.format_messages(
                battle_context=json.dumps(context),
                player_active=self._format_pokemon(battle_state.get("player", {}).get("active")),
                opponent_active=self._format_pokemon(battle_state.get("opponent", {}).get("active")),
                player_team=self._format_team(battle_state.get("player", {}).get("team", [])),
                opponent_team=self._format_team(battle_state.get("opponent", {}).get("team", [])),
                weather=str(battle_state.get("weather", "None")),
                terrain=str(battle_state.get("terrain", "None")),
                turn=str(battle_state.get("turn", 0)),
                matchup_analysis=json.dumps(analysis.get("current_matchup", {}), indent=2),
                field_effects=json.dumps(analysis.get("field_effects", {}), indent=2),
                strategic_options=json.dumps(analysis.get("strategic_options", {}), indent=2),
                format_instructions=format_instructions
            )
        except Exception as e:
            print(f"Error formatting context: {e}")
            fallback_decision = self._generate_fallback_decision(battle_state)
            self._record_decision(fallback_decision)
            return fallback_decision
        
        # Get the response from the LLM
        llm_response = self.llm.invoke(messages)
        
            # Parse the structured output
        decision = self.output_parser.parse(llm_response.content)
            
            # Ensure confidence is a float between 0 and 1
        decision["confidence"] = float(decision.get("confidence", 0.5))
        decision["confidence"] = max(0.0, min(1.0, decision["confidence"]))
        
        # Record the decision
        self._record_decision(decision)
        
        return decision
            
        # except Exception as e:
        #     # Fallback in case of parsing error
        #     print(f"Error parsing LLM response: {e}")
 
    
    def _format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format the context in a concise way for the prompt"""
        # Extract only the most relevant information to keep the prompt size manageable
        relevant_context = {
            "battle_state": {
                "player_active": self._extract_pokemon_summary(context.get("battle_state", {}).get("player", {}).get("active")),
                "opponent_active": self._extract_pokemon_summary(context.get("battle_state", {}).get("opponent", {}).get("active")),
                "weather": context.get("battle_state", {}).get("weather"),
                "terrain": context.get("battle_state", {}).get("terrain"),
                "turn": context.get("battle_state", {}).get("turn")
            },
            "analysis": {
                "current_matchup": context.get("analysis", {}).get("current_matchup"),
                "field_effects": context.get("analysis", {}).get("field_effects"),
                "strategic_options": context.get("analysis", {}).get("strategic_options")
            }
        }
        
        return json.dumps(relevant_context, indent=2)
    
    def _extract_pokemon_summary(self, pokemon: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a summary of a Pokemon for the prompt"""
        if not pokemon:
            return {}
            
        return {
            "name": pokemon.get("details", "").split(",")[0] if pokemon.get("details") else "Unknown",
            "hp": pokemon.get("hp", 100),
            "status": pokemon.get("status"),
            "moves": pokemon.get("moves", [])
        }
    
    def _format_pokemon(self, pokemon: Dict[str, Any]) -> str:
        # print("LINE 221 strategy.py",pokemon)
        """Format a Pokemon's information as a string"""
        if not pokemon:
            return "None"
            
        # Handle case where pokemon is a string instead of a dictionary
        if isinstance(pokemon, str):
            return f"{pokemon} (Details unknown)"
        
        name = pokemon.get("details", "").split(",")[0] if pokemon.get("details") else "Unknown"
        print("LINE 231 strategy.py",name)
        hp = pokemon.get("hp", 100)
        print("LINE 233 strategy.py",hp)
        status = pokemon.get("status", "None")
        print("LINE 235 strategy.py",status)
        print("LINE 236 strategy.py",pokemon.get("moves"))
        moves = pokemon.get("moves", [])
        
        print(f"{name} (HP: {hp}%, Status: {status}, Moves: {moves})")
        return f"{name} (HP: {hp}%, Status: {status}, Moves: {moves})"
    
    def _format_team(self, team: List[Dict[str, Any]]) -> str:
        """Format a team's information as a string"""
        if not team:
            return "No team data"
            
        team_info = []
        for pokemon in team:
            name = pokemon.get("details", "").split(",")[0] if pokemon.get("details") else "Unknown"
            hp = pokemon.get("hp", 100)
            status = pokemon.get("status", "None")
            team_info.append(f"{name} (HP: {hp}%, Status: {status})")
            
        return " | ".join(team_info)
    
    def _generate_fallback_decision(self, battle_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a fallback decision when LLM parsing fails"""
        player_active = battle_state.get("player", {}).get("active")
        
        if not player_active:
            return {
                "action": "move",
                "target": "struggle",
                "reason": "Fallback decision due to error in LLM response parsing",
                "confidence": 0.3
            }
            
        # Get the first available move
        moves = player_active.get("moves", [])
        first_move = moves[0] if moves else "struggle"
        
        return {
            "action": "move",
            "target": first_move,
            "reason": "Fallback decision due to error in LLM response parsing",
            "confidence": 0.3
        }
    
    def _record_decision(self, decision: Dict[str, Any]) -> None:
        """Record the decision for history tracking"""
        self.last_decision = decision
        self.decision_history.append(decision)
        
        # Limit history size
        if len(self.decision_history) > 20:
            self.decision_history = self.decision_history[-20:]
    
    def get_decision_history(self) -> List[Dict[str, Any]]:
        """Get the history of decisions made"""
        return self.decision_history
    
    def explain_decision(self, decision: Dict[str, Any] = None) -> str:
        """Provide a detailed explanation of a decision"""
        if decision is None:
            if self.last_decision is None:
                return "No decision has been made yet."
            decision = self.last_decision
            
        action = decision.get("action", "unknown")
        target = decision.get("target", "unknown")
        reason = decision.get("reason", "No reason provided")
        confidence = decision.get("confidence", 0.0)
        
        if action == "move":
            return f"Decision: Use move '{target}'\nReason: {reason}\nConfidence: {confidence:.2f}"
        elif action == "switch":
            return f"Decision: Switch to '{target}'\nReason: {reason}\nConfidence: {confidence:.2f}"
        else:
            return f"Decision: {action} {target}\nReason: {reason}\nConfidence: {confidence:.2f}"
    
    def analyze_battle_trend(self) -> Dict[str, Any]:
        """Analyze the trend of the battle based on decision history"""
        if len(self.decision_history) < 3:
            return {"status": "Not enough history for trend analysis"}
            
        # Use LLM to analyze the battle trend
        trend_prompt = ChatPromptTemplate.from_template("""
        You are a Pokemon battle expert AI assistant. Analyze the following battle decision history and identify trends, patterns, and strategic insights.

        Decision History:
        {decision_history}

        Based on this history, provide:
        1. Overall battle trend (who seems to be winning)
        2. Strategic patterns observed
        3. Recommendations for adjusting strategy

        Provide your analysis in a structured format.
        """)
        
        prompt_value = trend_prompt.format_messages(
            decision_history=json.dumps(self.decision_history, indent=2)
        )
        
        trend_analysis = self.llm.invoke(prompt_value)
        
        return {
            "analysis": trend_analysis.content,
            "decisions_analyzed": len(self.decision_history)
        }

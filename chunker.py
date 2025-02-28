from langchain_core.documents import Document
import pypokedex
import pandas as pd
def pokemon_strategy_transcript_chunker(documents, min_chunk_size=300, max_chunk_size=1500):
    """Custom chunker for Pokémon strategy transcripts"""
    chunks = []
    
    # Key topic indicators in competitive Pokémon discussions
    topic_indicators = [
        "lead matchup", "wind condition", "win condition", "risk versus reward", 
        "team building", "prediction", "outplay", "competitive analysis",
        "meta game", "offense versus", "stall versus"
    ]
    
    # Pokémon battle indicators
    battle_indicators = [
        "let's break down this battle", "let's take a look at", 
        "in this battle", "versus", " vs ", "lead off with"
    ]
    
    for doc in documents:
        text = doc.page_content
        current_text = ""
        current_metadata = doc.metadata.copy()
        
        # Split initially by paragraphs (transcript segments)
        paragraphs = text.split("\n\n")
        
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # Check if this paragraph indicates a new topic
            new_topic = False
            current_topic = ""
            
            for indicator in topic_indicators:
                if indicator in paragraph.lower():
                    new_topic = True
                    current_topic = indicator
                    break
                    
            # Check if this is discussing a specific battle
            battle_discussion = False
            for indicator in battle_indicators:
                if indicator in paragraph.lower():
                    battle_discussion = True
                    break
            
            # If we're starting a new topic and have enough text, create a chunk
            if (new_topic or i == len(paragraphs)-1) and current_text and len(current_text) >= min_chunk_size:
                if current_topic:
                    current_metadata["topic"] = current_topic
                
                chunks.append(Document(page_content=current_text, metadata=current_metadata))
                current_text = paragraph
                current_metadata = doc.metadata.copy()
            # If we're in a battle discussion, try to keep it together
            elif battle_discussion and current_text and "battle" not in current_metadata.get("topic", ""):
                if len(current_text) >= min_chunk_size:
                    chunks.append(Document(page_content=current_text, metadata=current_metadata))
                current_text = paragraph
                current_metadata = doc.metadata.copy()
                current_metadata["topic"] = "battle_analysis"
            # If adding this paragraph would exceed max size, create a chunk
            elif len(current_text) + len(paragraph) > max_chunk_size and len(current_text) >= min_chunk_size:
                chunks.append(Document(page_content=current_text, metadata=current_metadata))
                current_text = paragraph
                current_metadata = doc.metadata.copy()
            else:
                if current_text:
                    current_text += "\n\n" + paragraph
                else:
                    current_text = paragraph
                    
            # Extract Pokemon names mentioned for metadata
            pokemon_mentioned = extract_pokemon_names(paragraph)
            if pokemon_mentioned:
                if "pokemon_mentioned" not in current_metadata:
                    current_metadata["pokemon_mentioned"] = []
                current_metadata["pokemon_mentioned"].extend(pokemon_mentioned)
        
        # Don't forget the last chunk
        if current_text and len(current_text) >= min_chunk_size:
            chunks.append(Document(page_content=current_text, metadata=current_metadata))
    
    return chunks

def extract_pokemon_names(text):
    """Extract Pokemon names from text using a simple heuristic approach"""
    # This is a simplified version - in practice, you might want to use a more comprehensive list
    common_pokemon = pd.read_csv("pokedex.csv")["name"].tolist()
    found_pokemon = []
    for pokemon in common_pokemon:
        if pokemon.lower() in text.lower():
            found_pokemon.append(pokemon)
    
    return found_pokemon
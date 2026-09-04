import google.generativeai as genai
import json
import os
from pydantic import BaseModel
from typing import Optional

# Ensure you have set GEMINI_API_KEY environment variable.
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "MOCK_KEY_FOR_LOCAL_TESTING"))
model = genai.GenerativeModel('gemini-2.5-flash')

def update_search_context(current_context, new_message: str) -> dict:
    """
    Calls the LLM to act as a search query rewriter.
    """
    prompt = f"""
    You are an intelligent visual memory search assistant.
    The user originally searched for: "{current_context.original_intent}"
    Current updated query (if any): "{current_context.updated_query}"
    Current clues:
    - Topic: {current_context.topic_clues}
    - Content: {current_context.content_clues}
    - Visual: {current_context.visual_clues}
    
    The user has sent a follow-up refinement message: "{new_message}"
    
    Update the clues and generate a single, highly effective search query that combines the original intent and the new refinement. 
    Ensure the query is descriptive and captures both text and visual concepts.
    
    Return ONLY a raw JSON object with exactly these fields (use null if not applicable):
    - "topic_clues"
    - "visual_clues"
    - "content_clues"
    - "updated_query"
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"LLM Error: {e}")
        # Fallback if LLM fails
        return {
            "topic_clues": current_context.topic_clues,
            "visual_clues": current_context.visual_clues,
            "content_clues": current_context.content_clues,
            "updated_query": f"{current_context.updated_query} {new_message}".strip()
        }

"""AI Analyzer service for text extraction and classification using Gemini."""
import json
from typing import Optional

import google.generativeai as genai

from app.config import get_settings
from app.models.enums import MemoryType

settings = get_settings()

# Configure Gemini
genai.configure(api_key=settings.google_api_key)

# System prompt for memory extraction
EXTRACTION_PROMPT = """You are a memory extraction system. Analyze the input text and extract atomic pieces of information.

For each piece of information, determine:
1. **content**: A concise, self-contained statement (include subject if omitted)
2. **memory_type**: One of:
   - "fact": Stable, objective information (name, skills, preferences)
   - "state": Temporary, current conditions (mood, health, workload)
   - "episode": Past events or experiences
3. **tags**: Relevant classification tags (e.g., ["health", "work", "preference"])
4. **importance**: 1-5 scale (5=critical, 1=trivial)
5. **confidence**: 0.0-1.0 how certain you are about this extraction

Rules:
- Extract only meaningful, reusable information
- Skip pure greetings, acknowledgments, or trivial chat
- Normalize dates to absolute format when possible
- Add "ユーザー" as subject if omitted
- Combine related statements into one atomic fact

Output as JSON array:
```json
[
  {
    "content": "...",
    "memory_type": "fact|state|episode",
    "tags": ["tag1", "tag2"],
    "importance": 3,
    "confidence": 0.8
  }
]
```

If no extractable information, return empty array: []
"""


async def extract_memories(text: str, source: Optional[str] = None) -> list[dict]:
    """Extract structured memories from raw text.
    
    Args:
        text: Raw input text to analyze
        source: Optional source identifier
        
    Returns:
        List of extracted memory dictionaries
    """
    model = genai.GenerativeModel(settings.llm_model)
    
    prompt = f"{EXTRACTION_PROMPT}\n\n---\nInput text:\n{text}"
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    
    try:
        # Parse JSON response
        memories = json.loads(response.text)
        
        # Validate and normalize
        validated = []
        for mem in memories:
            if not mem.get("content"):
                continue
                
            validated.append({
                "content": mem["content"],
                "memory_type": MemoryType(mem.get("memory_type", "fact")),
                "tags": mem.get("tags", []),
                "importance": min(5, max(1, mem.get("importance", 3))),
                "confidence": min(1.0, max(0.0, mem.get("confidence", 0.7))),
                "source": source,
            })
        
        return validated
        
    except (json.JSONDecodeError, ValueError) as e:
        # Log error and return empty list
        print(f"Error parsing AI response: {e}")
        return []


async def synthesize_context(
    query: str,
    memories: list[dict],
    app_context: Optional[dict] = None,
) -> dict:
    """Synthesize context from retrieved memories for RAG.
    
    Args:
        query: User's current query/question
        memories: List of retrieved memories
        app_context: Optional application state
        
    Returns:
        Synthesized context with summary and bullets
    """
    model = genai.GenerativeModel(settings.llm_model)
    
    # Format memories for context
    memory_text = "\n".join([
        f"- [{m.get('memory_type', 'unknown')}] {m.get('content', '')}"
        for m in memories
    ])
    
    context_text = ""
    if app_context:
        context_text = f"\nApplication State: {json.dumps(app_context)}"
    
    prompt = f"""Based on the user's query and their stored memories, synthesize a helpful context summary.

User Query: {query}
{context_text}

Relevant Memories:
{memory_text}

Provide:
1. A concise summary paragraph
2. Key bullet points for the AI to consider

Output as JSON:
```json
{{
  "summary": "...",
  "bullets": ["point 1", "point 2", ...]
}}
```
"""
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {
            "summary": "Unable to synthesize context.",
            "bullets": [],
        }

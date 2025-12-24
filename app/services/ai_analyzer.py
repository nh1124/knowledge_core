"""AI Analyzer service for text extraction and classification using Gemini."""
import json
from typing import Optional

import google.generativeai as genai

from app.config import get_settings
from app.models.enums import MemoryType
from app.logging_config import get_logger

logger = get_logger("ai_analyzer")

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

SYNTHESIS_PROMPT = """You are a context synthesizer. Based on the user's query and their stored memories, synthesize a helpful context summary.

Provide:
1. A concise summary paragraph
2. Key bullet points for the AI to consider

Output as JSON:
{
  "summary": "...",
  "bullets": ["point 1", "point 2", ...]
}
"""


async def extract_memories(text: str, source: Optional[str] = None, api_key: Optional[str] = None) -> list[dict]:
    """Extract structured memories from raw text."""
    logger.debug(f"Extracting memories from text (length: {len(text)})")
    
    # Use user-provided key or fallback to system key
    effective_api_key = api_key or settings.google_api_key
    if not effective_api_key:
        logger.error("No Gemini API key available (per-user or system)")
        return []
        
    # Configure for this call (thread-safeish for simple scripts, but better to use specific client if possible)
    # genai.configure is global, but GenerativeModel can take a client or we can just hope for the best in this simple setup
    # Actually, a better way with google-generativeai is to use a specific api_key for the model if possible
    # But genai.configure is the standard way. For concurrency, we might need to be careful.
    # However, the library is mostly stateless in terms of calls once configured.
    genai.configure(api_key=effective_api_key)
    
    model = genai.GenerativeModel(
        model_name=settings.llm_model,
        system_instruction=EXTRACTION_PROMPT
    )
    
    response = model.generate_content(
        f"Input text:\n{text}",
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
        logger.error(f"Error parsing AI response: {e}")
        return []


async def synthesize_context(
    query: str,
    memories: list[dict],
    app_context: Optional[dict] = None,
    api_key: Optional[str] = None,
) -> dict:
    """Synthesize context from retrieved memories for RAG."""
    logger.debug(f"Synthesizing context for query with {len(memories)} memories")
    
    effective_api_key = api_key or settings.google_api_key
    if not effective_api_key:
        logger.error("No Gemini API key available for context synthesis")
        return {"summary": "Gemini API key not configured.", "bullets": []}
        
    genai.configure(api_key=effective_api_key)

    model = genai.GenerativeModel(
        model_name=settings.llm_model,
        system_instruction=SYNTHESIS_PROMPT
    )
    
    # Format memories for context
    memory_text = "\n".join([
        f"- [{m.get('memory_type', 'unknown')}] {m.get('content', '')}"
        for m in memories
    ])
    
    context_text = ""
    if app_context:
        context_text = f"\nApplication State: {json.dumps(app_context)}"
    
    prompt = f"""User Query: {query}
{context_text}

Relevant Memories:
{memory_text}
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

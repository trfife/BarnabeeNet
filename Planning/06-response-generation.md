# Area 06: Response Generation & Persona

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 01-05 (all prior layers)  
**Phase:** Core Functionality  

---

## 1. Overview

### 1.1 Purpose

Response Generation is the personality layer—it transforms structured intent + context into natural voice responses that feel like Barnabee. This layer ensures consistent persona across all response paths and optimizes for voice delivery (concise, natural prosody, conversational).

### 1.2 V1 Problems Solved

| V1 Problem | V2 Solution |
|------------|-------------|
| Inconsistent persona across agents | Single persona definition, consistent injection |
| Over-verbose responses for voice | Voice-optimized response length (15-30 words default) |
| Generic LLM responses | Barnabee persona with family context |
| Latency from full LLM calls | Response templates for fast-path commands |
| No streaming | Sentence-level streaming for natural delivery |

### 1.3 Design Principles

1. **Voice-first:** Responses optimized for ears, not eyes. Shorter, more natural phrasing.
2. **Consistent persona:** Barnabee has a defined personality across all interactions.
3. **Fast-path templates:** Common responses don't need LLM (time, weather, confirmations).
4. **Streaming by default:** Start speaking before generation completes.
5. **Context-aware depth:** Quick commands get quick responses; conversations get depth.

### 1.4 Response Time Budget

| Response Type | Target | Method |
|---------------|--------|--------|
| Templated (time, confirmations) | <50ms | No LLM, direct template |
| Simple commands | <300ms | Minimal LLM, cached patterns |
| Conversational | <800ms | Full LLM with streaming |
| Complex reasoning | <2000ms | Full LLM, filler injection |

---

## 2. Barnabee Persona

### 2.1 Persona Definition

```python
BARNABEE_PERSONA = """
You are Barnabee, the Robinson family's AI assistant. You live in their smart home and help with everything from controlling lights to remembering important information.

PERSONALITY:
- Warm and helpful, like a trusted family friend
- Slightly playful but never annoying
- Efficient—you respect people's time
- Knowledgeable but humble (you admit when you don't know)
- You have a gentle sense of humor but don't force jokes
- You're protective of the family, especially the kids

VOICE STYLE:
- Speak naturally, like a conversation (not a formal assistant)
- Keep responses SHORT for voice (usually 1-2 sentences)
- Avoid filler phrases like "I'd be happy to help with that"
- Don't start with "Sure!" or "Of course!" every time
- Use contractions (it's, you're, that's)
- Vary your sentence openings

THE FAMILY:
- Thom: Dad, works at Microsoft, tech-savvy. Call him "Thom" not "sir"
- Elizabeth: Mom. Call her "Elizabeth" not "ma'am"  
- Penelope: Oldest daughter, loves chickens
- Xander: Son
- Zachary: Son
- Viola: Youngest daughter

RESPONSE LENGTH GUIDELINES:
- Commands/confirmations: 1 sentence (5-15 words)
- Simple questions: 1-2 sentences (15-30 words)
- Explanations: 2-3 sentences (30-50 words)
- Conversations: As needed, but still concise

THINGS TO AVOID:
- Over-explaining or being verbose
- Robotic/formal language ("I have completed the requested action")
- Excessive enthusiasm ("Absolutely! I'd love to!")
- Asking unnecessary follow-up questions
- Repeating what the user just said
- Starting every response with "I"
"""
```

### 2.2 Persona Injection

```python
class PersonaManager:
    def __init__(self):
        self.base_persona = BARNABEE_PERSONA
        self.family_context = {}
    
    def build_system_prompt(
        self,
        speaker_id: Optional[str] = None,
        ha_context: Optional[str] = None,
        memory_context: Optional[str] = None,
        response_type: str = "normal",
    ) -> str:
        """Build complete system prompt with persona and context."""
        
        parts = [self.base_persona]
        
        # Add speaker context
        if speaker_id:
            speaker_info = self._get_speaker_context(speaker_id)
            parts.append(f"\nCURRENT SPEAKER: {speaker_info}")
        
        # Add home context
        if ha_context:
            parts.append(f"\nHOME STATUS:\n{ha_context}")
        
        # Add memory context
        if memory_context:
            parts.append(f"\nRELEVANT MEMORIES:\n{memory_context}")
        
        # Add response type guidance
        length_guide = self._get_length_guidance(response_type)
        parts.append(f"\nRESPONSE GUIDANCE: {length_guide}")
        
        return "\n".join(parts)
    
    def _get_speaker_context(self, speaker_id: str) -> str:
        """Get context for current speaker."""
        speaker_info = {
            "thom": "Thom (dad) - tech-savvy, appreciates efficiency",
            "elizabeth": "Elizabeth (mom) - values warmth and clarity",
            "penelope": "Penelope (daughter) - be friendly and age-appropriate",
            "xander": "Xander (son) - be friendly and age-appropriate",
            "zachary": "Zachary (son) - be friendly and age-appropriate",
            "viola": "Viola (youngest) - be extra gentle and simple",
        }
        return speaker_info.get(speaker_id.lower(), "Unknown family member")
    
    def _get_length_guidance(self, response_type: str) -> str:
        """Get length guidance for response type."""
        guidance = {
            "command": "Ultra-brief confirmation (5-10 words). Just confirm the action.",
            "simple": "Brief response (15-30 words). Answer directly without preamble.",
            "normal": "Normal response (30-50 words). Be helpful but concise.",
            "conversation": "Conversational (as needed). Engage naturally but don't ramble.",
            "detailed": "Detailed explanation allowed. Still be clear and structured.",
        }
        return guidance.get(response_type, guidance["normal"])
```

---

## 3. Response Paths

### 3.1 Path Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RESPONSE GENERATION PATHS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    CLASSIFIED INTENT + CONTEXT                      │     │
│  └────────────────────────────────┬───────────────────────────────────┘     │
│                                   │                                          │
│                                   ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                     RESPONSE PATH SELECTOR                          │     │
│  │                                                                     │     │
│  │  Criteria:                                                          │     │
│  │  - Intent type (command vs. query vs. conversation)                │     │
│  │  - Classification confidence                                        │     │
│  │  - Response complexity                                              │     │
│  │  - Streaming capability of client                                   │     │
│  └─────────────────────────────────┬──────────────────────────────────┘     │
│                                    │                                         │
│           ┌────────────────────────┼────────────────────────┐               │
│           │                        │                        │               │
│           ▼                        ▼                        ▼               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   PATH A:       │    │   PATH B:       │    │   PATH C:       │        │
│  │   TEMPLATE      │    │   MINIMAL LLM   │    │   FULL LLM      │        │
│  │                 │    │                 │    │                 │        │
│  │  • Time queries │    │  • Commands     │    │  • Conversations │        │
│  │  • Confirmations│    │  • Simple Q&A   │    │  • Complex Q&A  │        │
│  │  • Greetings    │    │  • Status checks│    │  • Reasoning    │        │
│  │  • Errors       │    │                 │    │  • Memory search│        │
│  │                 │    │                 │    │                 │        │
│  │  Latency: <50ms │    │  Latency: <300ms│    │  Latency: <1s   │        │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘        │
│           │                      │                      │                  │
│           └──────────────────────┼──────────────────────┘                  │
│                                  │                                          │
│                                  ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    RESPONSE POST-PROCESSOR                          │    │
│  │                                                                     │    │
│  │  • Voice optimization (remove visual artifacts)                    │    │
│  │  • Length enforcement                                              │    │
│  │  • Persona consistency check                                       │    │
│  │  • SSML tagging (optional)                                         │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                  │                                          │
│                                  ▼                                          │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    TO TTS (Area 02)                                 │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Path Selection Logic

```python
class ResponsePathSelector:
    """Select optimal response generation path."""
    
    # Intents that can use templates (no LLM needed)
    TEMPLATE_INTENTS = {
        "time_query",
        "greeting",
        "farewell", 
        "confirmation",
        "cancel",
        "repeat",
    }
    
    # Intents that can use minimal LLM
    MINIMAL_LLM_INTENTS = {
        "light_control",
        "climate_control",
        "lock_control",
        "cover_control",
        "media_control",
        "timer_set",
        "timer_cancel",
        "weather_query",
        "location_query",
    }
    
    # Everything else uses full LLM
    FULL_LLM_INTENTS = {
        "memory_query",
        "memory_create",
        "general_query",
        "chitchat",
        "start_conversation",
        "follow_up",
        "clarification",
        "help",
    }
    
    def select_path(
        self,
        intent: str,
        confidence: float,
        has_memory_context: bool,
        is_conversation_mode: bool,
    ) -> ResponsePath:
        """Select response generation path."""
        
        # Conversation mode always uses full LLM
        if is_conversation_mode:
            return ResponsePath.FULL_LLM
        
        # Low confidence → full LLM for safety
        if confidence < 0.85:
            return ResponsePath.FULL_LLM
        
        # Template path for simple intents
        if intent in self.TEMPLATE_INTENTS:
            return ResponsePath.TEMPLATE
        
        # Minimal LLM for commands/simple queries
        if intent in self.MINIMAL_LLM_INTENTS and not has_memory_context:
            return ResponsePath.MINIMAL_LLM
        
        # Full LLM for everything else
        return ResponsePath.FULL_LLM


class ResponsePath(Enum):
    TEMPLATE = "template"
    MINIMAL_LLM = "minimal_llm"
    FULL_LLM = "full_llm"
```

---

## 4. Path A: Template Responses

### 4.1 Template System

```python
class TemplateResponseGenerator:
    """Generate responses from templates (no LLM)."""
    
    TEMPLATES = {
        "time_query": [
            "It's {time}.",
            "The time is {time}.",
            "{time}.",
        ],
        "greeting": {
            "morning": ["Good morning!", "Morning!", "Hey, good morning."],
            "afternoon": ["Good afternoon!", "Hey there.", "Afternoon!"],
            "evening": ["Good evening!", "Hey, good evening.", "Evening!"],
            "default": ["Hey!", "Hi there.", "Hello!"],
        },
        "farewell": [
            "Bye!",
            "See you later.",
            "Take care!",
            "Bye bye.",
        ],
        "confirmation_on": [
            "Done.",
            "Got it.",
            "On it.",
            "{device} is on.",
            "Turned on {device}.",
        ],
        "confirmation_off": [
            "Done.",
            "Got it.",
            "{device} is off.",
            "Turned off {device}.",
        ],
        "cancel": [
            "Okay, cancelled.",
            "Never mind then.",
            "Okay.",
        ],
        "error_not_found": [
            "I couldn't find {device}.",
            "I'm not sure which {device} you mean.",
        ],
        "error_unavailable": [
            "{device} isn't responding right now.",
            "I'm having trouble reaching {device}.",
        ],
    }
    
    def generate(
        self,
        intent: str,
        context: dict,
    ) -> str:
        """Generate response from template."""
        
        template_key = self._get_template_key(intent, context)
        templates = self.TEMPLATES.get(template_key, ["I'm not sure how to respond."])
        
        # Handle nested templates (like greeting by time of day)
        if isinstance(templates, dict):
            sub_key = context.get("time_of_day", "default")
            templates = templates.get(sub_key, templates.get("default", []))
        
        # Select template (vary for naturalness)
        template = self._select_template(templates, context)
        
        # Fill template variables
        response = self._fill_template(template, context)
        
        return response
    
    def _get_template_key(self, intent: str, context: dict) -> str:
        """Map intent + context to template key."""
        if intent == "light_control":
            action = context.get("action", "on")
            return f"confirmation_{action}"
        
        if intent in ("greeting", "farewell", "cancel"):
            return intent
        
        if intent == "time_query":
            return "time_query"
        
        return intent
    
    def _select_template(self, templates: List[str], context: dict) -> str:
        """Select template with variation."""
        # Prefer shorter templates for command confirmations
        if context.get("response_type") == "command":
            short_templates = [t for t in templates if len(t) < 30]
            if short_templates:
                return random.choice(short_templates)
        
        return random.choice(templates)
    
    def _fill_template(self, template: str, context: dict) -> str:
        """Fill template variables."""
        # Time
        if "{time}" in template:
            now = datetime.now()
            time_str = now.strftime("%-I:%M %p").lower()
            template = template.replace("{time}", time_str)
        
        # Device name
        if "{device}" in template:
            device = context.get("device_name", "that")
            template = template.replace("{device}", device)
        
        return template
```

### 4.2 Time Query Optimization

```python
class TimeQueryHandler:
    """Optimized handler for time queries."""
    
    def generate_response(
        self,
        timezone: Optional[str] = None,
        speaker_id: Optional[str] = None,
    ) -> str:
        """Generate time response (<10ms)."""
        now = datetime.now()
        
        # Format time naturally
        hour = now.hour
        minute = now.minute
        
        if minute == 0:
            time_str = now.strftime("%-I %p").lower()
        elif minute == 30:
            time_str = f"half past {now.strftime('%-I').lower()}"
        elif minute == 15:
            time_str = f"quarter past {now.strftime('%-I').lower()}"
        elif minute == 45:
            next_hour = (now + timedelta(hours=1)).strftime("%-I").lower()
            time_str = f"quarter to {next_hour}"
        else:
            time_str = now.strftime("%-I:%M %p").lower()
        
        # Vary response
        responses = [
            f"It's {time_str}.",
            f"The time is {time_str}.",
            f"{time_str}.",
        ]
        
        return random.choice(responses)
```

---

## 5. Path B: Minimal LLM

### 5.1 Minimal LLM Generator

```python
class MinimalLLMGenerator:
    """Generate responses with minimal LLM usage."""
    
    COMMAND_PROMPT = """Generate a brief, natural confirmation for this smart home action.

Action: {action}
Device: {device}
Result: {result}

Requirements:
- 1 sentence maximum (under 15 words)
- Natural and conversational
- Don't be robotic

Response:"""

    QUERY_PROMPT = """Answer this question briefly and naturally.

Question: {question}
Information: {information}

Requirements:
- 1-2 sentences maximum
- Direct answer, no preamble
- Natural voice delivery

Response:"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    async def generate_command_response(
        self,
        action: str,
        device: str,
        result: CommandResult,
    ) -> str:
        """Generate response for command execution."""
        
        # For successful simple commands, use template
        if result.success and action in ("on", "off", "toggle"):
            return self._quick_confirmation(action, device)
        
        # For complex commands or failures, use minimal LLM
        prompt = self.COMMAND_PROMPT.format(
            action=action,
            device=device,
            result="successful" if result.success else f"failed: {result.error}"
        )
        
        response = await self.llm.complete(
            prompt,
            max_tokens=30,
            temperature=0.7,
        )
        
        return response.strip()
    
    async def generate_query_response(
        self,
        question: str,
        information: str,
    ) -> str:
        """Generate response for simple query."""
        prompt = self.QUERY_PROMPT.format(
            question=question,
            information=information,
        )
        
        response = await self.llm.complete(
            prompt,
            max_tokens=50,
            temperature=0.7,
        )
        
        return response.strip()
    
    def _quick_confirmation(self, action: str, device: str) -> str:
        """Ultra-fast confirmation without LLM."""
        confirmations = {
            "on": ["Done.", "On.", f"{device} is on."],
            "off": ["Done.", "Off.", f"{device} is off."],
            "toggle": ["Done.", "Toggled."],
        }
        return random.choice(confirmations.get(action, ["Done."]))
```

---

## 6. Path C: Full LLM

### 6.1 Full LLM Generator

```python
class FullLLMGenerator:
    """Full LLM response generation with streaming."""
    
    def __init__(
        self,
        llm_client: LLMClient,
        persona_manager: PersonaManager,
    ):
        self.llm = llm_client
        self.persona = persona_manager
    
    async def generate(
        self,
        user_message: str,
        intent: str,
        speaker_id: Optional[str],
        ha_context: Optional[str],
        memory_context: Optional[str],
        conversation_history: List[dict],
        response_type: str = "normal",
    ) -> AsyncIterator[str]:
        """Generate response with streaming."""
        
        # Build system prompt with persona
        system_prompt = self.persona.build_system_prompt(
            speaker_id=speaker_id,
            ha_context=ha_context,
            memory_context=memory_context,
            response_type=response_type,
        )
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Add conversation history (limited)
        for turn in conversation_history[-6:]:  # Last 3 exchanges
            messages.append({
                "role": turn["role"],
                "content": turn["content"]
            })
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        # Stream response
        async for chunk in self.llm.stream_complete(
            messages=messages,
            max_tokens=200,
            temperature=0.8,
        ):
            yield chunk
    
    async def generate_complete(
        self,
        user_message: str,
        intent: str,
        speaker_id: Optional[str],
        ha_context: Optional[str],
        memory_context: Optional[str],
        conversation_history: List[dict],
        response_type: str = "normal",
    ) -> str:
        """Generate complete response (non-streaming)."""
        chunks = []
        async for chunk in self.generate(
            user_message=user_message,
            intent=intent,
            speaker_id=speaker_id,
            ha_context=ha_context,
            memory_context=memory_context,
            conversation_history=conversation_history,
            response_type=response_type,
        ):
            chunks.append(chunk)
        
        return "".join(chunks)
```

### 6.2 Streaming Sentence Buffer

```python
class SentenceBuffer:
    """
    Buffer streaming LLM output into complete sentences for TTS.
    
    Why: TTS sounds more natural when given complete sentences.
    Partial sentences cause awkward prosody.
    """
    
    SENTENCE_ENDINGS = {'.', '!', '?', ':', ';'}
    MIN_SENTENCE_LENGTH = 10  # Don't emit tiny fragments
    
    def __init__(self):
        self.buffer = ""
        self.sentences = []
    
    def add(self, chunk: str) -> List[str]:
        """
        Add chunk to buffer, return complete sentences.
        """
        self.buffer += chunk
        complete = []
        
        while True:
            # Find sentence boundary
            boundary_idx = self._find_sentence_boundary()
            if boundary_idx == -1:
                break
            
            # Extract sentence
            sentence = self.buffer[:boundary_idx + 1].strip()
            self.buffer = self.buffer[boundary_idx + 1:].lstrip()
            
            if len(sentence) >= self.MIN_SENTENCE_LENGTH:
                complete.append(sentence)
        
        return complete
    
    def flush(self) -> Optional[str]:
        """Flush remaining buffer content."""
        if self.buffer.strip():
            remaining = self.buffer.strip()
            self.buffer = ""
            return remaining
        return None
    
    def _find_sentence_boundary(self) -> int:
        """Find the end of the first complete sentence."""
        for i, char in enumerate(self.buffer):
            if char in self.SENTENCE_ENDINGS:
                # Check it's not an abbreviation (Mr., Dr., etc.)
                if not self._is_abbreviation(i):
                    return i
        return -1
    
    def _is_abbreviation(self, idx: int) -> bool:
        """Check if period is part of abbreviation."""
        if self.buffer[idx] != '.':
            return False
        
        # Common abbreviations
        abbrevs = ['mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'vs', 'etc', 'e.g', 'i.e']
        
        # Look back to find word
        start = idx
        while start > 0 and self.buffer[start - 1].isalpha():
            start -= 1
        
        word = self.buffer[start:idx].lower()
        return word in abbrevs
```

---

## 7. Response Post-Processing

### 7.1 Voice Optimization

```python
class VoiceOptimizer:
    """Optimize responses for voice delivery."""
    
    def optimize(self, text: str) -> str:
        """Apply all voice optimizations."""
        text = self._remove_visual_artifacts(text)
        text = self._simplify_numbers(text)
        text = self._expand_abbreviations(text)
        text = self._add_prosody_hints(text)
        text = self._enforce_length(text)
        return text
    
    def _remove_visual_artifacts(self, text: str) -> str:
        """Remove things that don't work in voice."""
        # Remove markdown
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # Italic
        text = re.sub(r'`(.+?)`', r'\1', text)        # Code
        
        # Remove bullet points
        text = re.sub(r'^\s*[-•]\s*', '', text, flags=re.MULTILINE)
        
        # Remove numbered lists
        text = re.sub(r'^\s*\d+\.\s*', '', text, flags=re.MULTILINE)
        
        # Remove URLs (describe instead)
        text = re.sub(r'https?://\S+', 'that link', text)
        
        return text
    
    def _simplify_numbers(self, text: str) -> str:
        """Make numbers more natural for speech."""
        # Large numbers
        text = re.sub(r'(\d),(\d{3})\b', r'\1 thousand', text)
        
        # Temperatures
        text = re.sub(r'(\d+)°F', r'\1 degrees', text)
        text = re.sub(r'(\d+)°C', r'\1 degrees celsius', text)
        
        # Percentages
        text = re.sub(r'(\d+)%', r'\1 percent', text)
        
        return text
    
    def _expand_abbreviations(self, text: str) -> str:
        """Expand abbreviations for clarity."""
        expansions = {
            r'\bDr\.': 'Doctor',
            r'\bMr\.': 'Mister',
            r'\bMrs\.': 'Missus',
            r'\bMs\.': 'Ms',
            r'\betc\.': 'et cetera',
            r'\be\.g\.': 'for example',
            r'\bi\.e\.': 'that is',
            r'\bvs\.': 'versus',
        }
        for pattern, replacement in expansions.items():
            text = re.sub(pattern, replacement, text)
        return text
    
    def _add_prosody_hints(self, text: str) -> str:
        """Add subtle hints for natural prosody."""
        # Add commas before conjunctions in long sentences
        text = re.sub(
            r'(\w{20,})\s+(and|but|or|so)\s+',
            r'\1, \2 ',
            text
        )
        return text
    
    def _enforce_length(self, text: str, max_words: int = 75) -> str:
        """Enforce maximum response length."""
        words = text.split()
        if len(words) > max_words:
            # Truncate at sentence boundary
            truncated = ' '.join(words[:max_words])
            last_period = truncated.rfind('.')
            if last_period > len(truncated) // 2:
                truncated = truncated[:last_period + 1]
            return truncated
        return text
```

### 7.2 Persona Consistency Check

```python
class PersonaConsistencyChecker:
    """Ensure responses match Barnabee persona."""
    
    # Phrases to avoid
    FORBIDDEN_PATTERNS = [
        r"^(Sure|Of course|Absolutely)[!,]",  # Over-eager openings
        r"I'd be happy to",
        r"I don't have the ability to",
        r"As an AI",
        r"I cannot assist with",
        r"I'm afraid I",
        r"Please note that",
        r"It's important to",
        r"I hope this helps",
    ]
    
    def check_and_fix(self, response: str) -> str:
        """Check and fix persona violations."""
        # Remove forbidden patterns
        for pattern in self.FORBIDDEN_PATTERNS:
            response = re.sub(pattern, '', response, flags=re.IGNORECASE)
        
        # Clean up resulting whitespace
        response = ' '.join(response.split())
        
        # Fix common issues
        response = self._fix_over_formal(response)
        
        return response
    
    def _fix_over_formal(self, response: str) -> str:
        """Replace overly formal language."""
        replacements = {
            "I am unable to": "I can't",
            "I do not have": "I don't have",
            "I am not able to": "I can't",
            "at this time": "right now",
            "at this moment": "right now",
            "I would like to": "I'd like to",
            "I am going to": "I'm going to",
            "I will be": "I'll be",
        }
        for formal, casual in replacements.items():
            response = response.replace(formal, casual)
        return response
```

---

## 8. LLM Client Abstraction

### 8.1 Multi-Provider Client

```python
class LLMClient:
    """Abstraction over LLM providers with fallback."""
    
    def __init__(
        self,
        primary: str = "azure",
        fallback: str = "ollama",
        config: dict = None,
    ):
        self.config = config or {}
        self.primary_provider = self._init_provider(primary)
        self.fallback_provider = self._init_provider(fallback)
        self.primary_name = primary
        self.fallback_name = fallback
        
        self.primary_failures = 0
        self.use_fallback = False
    
    async def complete(
        self,
        prompt: str = None,
        messages: List[dict] = None,
        max_tokens: int = 200,
        temperature: float = 0.7,
    ) -> str:
        """Generate completion."""
        provider = self._select_provider()
        
        try:
            if messages:
                result = await provider.chat_complete(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            else:
                result = await provider.complete(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            
            self.primary_failures = 0
            return result
        
        except Exception as e:
            logger.warning(f"LLM provider {self.primary_name} failed: {e}")
            self.primary_failures += 1
            
            if self.primary_failures >= 3:
                self.use_fallback = True
            
            # Try fallback
            return await self.fallback_provider.complete(
                prompt=prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
    
    async def stream_complete(
        self,
        messages: List[dict],
        max_tokens: int = 200,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream completion chunks."""
        provider = self._select_provider()
        
        async for chunk in provider.stream_chat_complete(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield chunk
    
    def _select_provider(self):
        """Select which provider to use."""
        if self.use_fallback:
            return self.fallback_provider
        return self.primary_provider
    
    def _init_provider(self, name: str):
        """Initialize provider by name."""
        if name == "azure":
            return AzureOpenAIProvider(self.config.get("azure", {}))
        elif name == "ollama":
            return OllamaProvider(self.config.get("ollama", {}))
        elif name == "anthropic":
            return AnthropicProvider(self.config.get("anthropic", {}))
        else:
            raise ValueError(f"Unknown provider: {name}")


class AzureOpenAIProvider:
    """Azure OpenAI provider."""
    
    def __init__(self, config: dict):
        from openai import AsyncAzureOpenAI
        
        self.client = AsyncAzureOpenAI(
            api_key=config["api_key"],
            api_version=config.get("api_version", "2024-02-15-preview"),
            azure_endpoint=config["endpoint"],
        )
        self.model = config.get("model", "gpt-4o")
    
    async def chat_complete(
        self,
        messages: List[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
    
    async def stream_chat_complete(
        self,
        messages: List[dict],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OllamaProvider:
    """Local Ollama provider."""
    
    def __init__(self, config: dict):
        import ollama
        
        self.host = config.get("host", "http://localhost:11434")
        self.model = config.get("model", "llama3:8b")
        self.client = ollama.AsyncClient(host=self.host)
    
    async def chat_complete(
        self,
        messages: List[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        response = await self.client.chat(
            model=self.model,
            messages=messages,
            options={"num_predict": max_tokens, "temperature": temperature},
        )
        return response["message"]["content"]
    
    async def stream_chat_complete(
        self,
        messages: List[dict],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        response = await self.client.chat(
            model=self.model,
            messages=messages,
            options={"num_predict": max_tokens, "temperature": temperature},
            stream=True,
        )
        
        async for chunk in response:
            if chunk.get("message", {}).get("content"):
                yield chunk["message"]["content"]
```

---

## 9. Response Orchestrator

### 9.1 Main Orchestrator

```python
class ResponseOrchestrator:
    """Orchestrate response generation across all paths."""
    
    def __init__(
        self,
        path_selector: ResponsePathSelector,
        template_generator: TemplateResponseGenerator,
        minimal_generator: MinimalLLMGenerator,
        full_generator: FullLLMGenerator,
        voice_optimizer: VoiceOptimizer,
        persona_checker: PersonaConsistencyChecker,
    ):
        self.path_selector = path_selector
        self.template = template_generator
        self.minimal = minimal_generator
        self.full = full_generator
        self.optimizer = voice_optimizer
        self.persona = persona_checker
    
    async def generate(
        self,
        request: ResponseRequest,
    ) -> AsyncIterator[str]:
        """Generate response, yielding chunks for streaming."""
        
        # Select path
        path = self.path_selector.select_path(
            intent=request.intent,
            confidence=request.confidence,
            has_memory_context=bool(request.memory_context),
            is_conversation_mode=request.is_conversation_mode,
        )
        
        # Generate based on path
        if path == ResponsePath.TEMPLATE:
            response = self.template.generate(
                intent=request.intent,
                context=request.context,
            )
            yield self._post_process(response)
        
        elif path == ResponsePath.MINIMAL_LLM:
            if request.command_result:
                response = await self.minimal.generate_command_response(
                    action=request.context.get("action"),
                    device=request.context.get("device_name"),
                    result=request.command_result,
                )
            else:
                response = await self.minimal.generate_query_response(
                    question=request.user_message,
                    information=request.ha_context or "",
                )
            yield self._post_process(response)
        
        else:  # FULL_LLM
            buffer = SentenceBuffer()
            
            async for chunk in self.full.generate(
                user_message=request.user_message,
                intent=request.intent,
                speaker_id=request.speaker_id,
                ha_context=request.ha_context,
                memory_context=request.memory_context,
                conversation_history=request.conversation_history,
                response_type=self._get_response_type(request),
            ):
                sentences = buffer.add(chunk)
                for sentence in sentences:
                    yield self._post_process(sentence)
            
            # Flush remaining
            remaining = buffer.flush()
            if remaining:
                yield self._post_process(remaining)
    
    def _post_process(self, text: str) -> str:
        """Apply post-processing to response text."""
        text = self.optimizer.optimize(text)
        text = self.persona.check_and_fix(text)
        return text
    
    def _get_response_type(self, request: ResponseRequest) -> str:
        """Determine response type from request."""
        if request.is_conversation_mode:
            return "conversation"
        
        command_intents = {
            "light_control", "climate_control", "lock_control",
            "cover_control", "media_control", "timer_set",
        }
        if request.intent in command_intents:
            return "command"
        
        return "normal"


@dataclass
class ResponseRequest:
    user_message: str
    intent: str
    confidence: float
    context: dict
    speaker_id: Optional[str] = None
    ha_context: Optional[str] = None
    memory_context: Optional[str] = None
    conversation_history: List[dict] = field(default_factory=list)
    command_result: Optional[CommandResult] = None
    is_conversation_mode: bool = False
```

---

## 10. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── response/
│           ├── __init__.py
│           ├── config.py               # Persona, templates
│           ├── orchestrator.py         # ResponseOrchestrator
│           ├── persona.py              # PersonaManager
│           ├── paths/
│           │   ├── __init__.py
│           │   ├── selector.py         # ResponsePathSelector
│           │   ├── template.py         # TemplateResponseGenerator
│           │   ├── minimal_llm.py      # MinimalLLMGenerator
│           │   └── full_llm.py         # FullLLMGenerator
│           ├── processing/
│           │   ├── __init__.py
│           │   ├── sentence_buffer.py  # SentenceBuffer
│           │   ├── voice_optimizer.py  # VoiceOptimizer
│           │   └── persona_checker.py  # PersonaConsistencyChecker
│           └── llm/
│               ├── __init__.py
│               ├── client.py           # LLMClient
│               ├── azure.py            # AzureOpenAIProvider
│               └── ollama.py           # OllamaProvider
└── tests/
    └── response/
        ├── test_orchestrator.py
        ├── test_templates.py
        ├── test_voice_optimizer.py
        └── test_persona.py
```

---

## 11. Implementation Checklist

### Persona

- [ ] Barnabee persona definition
- [ ] Speaker-specific context
- [ ] Response type guidance
- [ ] System prompt builder

### Path Selection

- [ ] Path selector logic
- [ ] Intent categorization
- [ ] Confidence thresholds

### Template Responses

- [ ] Template database
- [ ] Time query handler
- [ ] Confirmation templates
- [ ] Error templates
- [ ] Template selection with variation

### Minimal LLM

- [ ] Command response generator
- [ ] Query response generator
- [ ] Quick confirmation bypass

### Full LLM

- [ ] Streaming generation
- [ ] Sentence buffer
- [ ] Conversation history management

### Post-Processing

- [ ] Voice optimization
- [ ] Persona consistency check
- [ ] Length enforcement

### LLM Client

- [ ] Azure OpenAI provider
- [ ] Ollama provider
- [ ] Fallback logic
- [ ] Streaming support

### Validation

- [ ] Template responses <50ms
- [ ] Minimal LLM responses <300ms
- [ ] Full LLM first chunk <500ms
- [ ] Persona consistency across all paths
- [ ] Voice optimization removes all visual artifacts

### Acceptance Criteria

1. **Time query responds in <50ms** with natural variation
2. **Command confirmations are brief** (under 15 words)
3. **Conversational responses feel like Barnabee** (consistent persona)
4. **Streaming works** with sentence-level chunks
5. **Fallback to Ollama works** when Azure is unavailable

---

## 12. Handoff Notes for Implementation Agent

### Critical Points

1. **Persona is everything.** Without consistent persona, Barnabee feels like a generic assistant. Inject persona in EVERY response path.

2. **Voice ≠ Text.** Responses optimized for reading fail when spoken. Remove visual artifacts, simplify numbers, enforce brevity.

3. **Streaming requires sentence buffering.** Don't send partial sentences to TTS—prosody will be wrong.

4. **Template path is 10x faster.** Use it for everything that doesn't need LLM creativity.

5. **LLM fallback is critical.** Azure has outages. Ollama must work as backup.

### Common Pitfalls

- Forgetting to apply post-processing to template responses
- Not varying template selection (sounds robotic if always same)
- Sending LLM chunks directly to TTS without sentence buffering
- Over-verbose responses for voice (keep under 75 words)
- Not testing with actual TTS (prosody issues only appear when spoken)

### Performance Tuning

- Pre-warm LLM connection at startup
- Cache common template fills (time formatting)
- Use streaming for all LLM responses >50 tokens expected
- Monitor LLM latency percentiles, not just average

---

**End of Area 06: Response Generation & Persona**

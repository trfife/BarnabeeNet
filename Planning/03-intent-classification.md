# Area 03: Intent Classification & NLU

**Version:** 2.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer)  
**Phase:** Backbone  

---

## 1. Overview

### 1.1 Purpose

Intent Classification & NLU transforms natural language into structured actions. This is the "brain" that decides what Barnabee should do with user input.

### 1.2 Core Design Principle: Never Say "I Don't Know"

**Critical:** The NLU system should NEVER respond with:
- "I don't know what you mean"
- "I couldn't find that device"
- "Please be more specific"

Instead, the system should:
1. **Always make an intelligent attempt** using all available context
2. **Use the LLM as an intelligent safety net** when fast paths fail
3. **Execute the most likely interpretation** and offer to correct if wrong
4. **Learn from corrections** to improve future accuracy

The LLM has access to all HA entities, user location, recent commands, and can make intelligent guesses. Use it.

### 1.2 V1 Problems Solved

| V1 Problem | V2 Solution |
|------------|-------------|
| 378 brittle regex patterns | Embedding-based classification |
| Bimodal latency (50ms OR 2500ms) | Consistent <100ms classification |
| "barnabee what time is it" fails | Preprocessing normalizes input |
| Patterns don't generalize | Embeddings handle natural variation |
| LLM fallback for everything unclear | Staged fallback preserves latency |

### 1.3 Design Principles

1. **Embedding-first:** Vector similarity handles natural language variation better than regex.
2. **Three-stage cascade:** Fast path → local classifier → LLM fallback. Stop early when confident.
3. **Separation of concerns:** Classification is separate from execution. This layer only determines *what* to do.
4. **Continuous learning:** Every LLM fallback becomes training data for local classifier.
5. **Entity resolution is critical:** "the office lights" must map to correct HA entities.

### 1.4 Latency Budget

| Stage | Budget | Cumulative |
|-------|--------|------------|
| Preprocessing | 5ms | 5ms |
| Embedding generation | 15ms | 20ms |
| Fast pattern match | 5ms | 25ms |
| Embedding similarity | 20ms | 45ms |
| Local classifier (if needed) | 50ms | 95ms |
| LLM fallback (if needed) | 400ms | 495ms |

**Target:** 95% of requests classified in <50ms. LLM fallback only for genuinely ambiguous queries.

---

## 2. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Embedding model | all-MiniLM-L6-v2 | 384-dim, 14ms inference, good accuracy |
| Embedding inference | sentence-transformers | Standard, well-optimized |
| Vector similarity | sqlite-vss | Already in data layer |
| Local classifier | Fine-tuned DistilBERT | Small, fast, trainable |
| LLM fallback | Azure OpenAI GPT-4o | High accuracy for edge cases |
| Entity matching | Fuzzy + semantic | Handles typos and variations |

### 2.1 Why all-MiniLM-L6-v2

Per MTEB leaderboard benchmarks:

| Model | Dimensions | Speed | Accuracy (STS) |
|-------|------------|-------|----------------|
| all-MiniLM-L6-v2 | 384 | 14ms | 82.4 |
| all-mpnet-base-v2 | 768 | 35ms | 83.4 |
| text-embedding-ada-002 | 1536 | 50ms+ (API) | 84.2 |

MiniLM achieves 98% of ada-002 accuracy at 3.5x speed and zero API cost. For intent classification (not semantic search), this is the optimal tradeoff.

### 2.2 Why Not Just LLM?

| Approach | Latency | Cost | Accuracy |
|----------|---------|------|----------|
| Always LLM | 400-800ms | $$$ | 98% |
| Embedding + LLM fallback | 50ms (P95) | $ | 96% |
| Regex only (V1) | 5ms | $0 | 70% |

Per Voiceflow's production data: embedding classification with LLM fallback achieves 95%+ accuracy at 3-5x cost reduction vs. always-LLM.

---

## 3. Architecture

### 3.1 Classification Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INTENT CLASSIFICATION PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT                                                                       │
│  ═════                                                                       │
│  "barnabee what time is it please"                                          │
│                     │                                                        │
│                     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 0: PREPROCESSING (5ms)                                        │   │
│  │                                                                       │   │
│  │  1. Lowercase                                                         │   │
│  │  2. Remove wake word ("barnabee")                                     │   │
│  │  3. Remove politeness ("please", "thanks", "can you")                │   │
│  │  4. Normalize whitespace                                              │   │
│  │  5. Expand contractions ("what's" → "what is")                       │   │
│  │                                                                       │   │
│  │  Result: "what time is it"                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 1: FAST PATTERN MATCH (5ms)                                   │   │
│  │                                                                       │   │
│  │  High-confidence exact/near-exact matches only                       │   │
│  │  ~50 core patterns for most common commands                          │   │
│  │                                                                       │   │
│  │  "what time is it" → time_query (confidence: 0.99)                   │   │
│  │                                                                       │   │
│  │  If confidence > 0.95: RETURN IMMEDIATELY                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼ (if not matched)                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 2: EMBEDDING SIMILARITY (20ms)                                │   │
│  │                                                                       │   │
│  │  1. Generate embedding for normalized input                          │   │
│  │  2. Compare against intent exemplar embeddings                       │   │
│  │  3. Return top match with similarity score                           │   │
│  │                                                                       │   │
│  │  If similarity > 0.85: RETURN                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼ (if not confident)                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 3: LOCAL CLASSIFIER (50ms)                                    │   │
│  │                                                                       │   │
│  │  Fine-tuned DistilBERT on labeled utterances                         │   │
│  │  Trained on: golden dataset + LLM fallback examples                  │   │
│  │                                                                       │   │
│  │  If confidence > 0.80: RETURN                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼ (if still not confident)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STAGE 4: LLM FALLBACK (400ms)                                       │   │
│  │                                                                       │   │
│  │  Azure GPT-4o with structured output                                 │   │
│  │  Includes: intent taxonomy, examples, context                        │   │
│  │                                                                       │   │
│  │  Result logged for future training                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ENTITY EXTRACTION (parallel with classification)                    │   │
│  │                                                                       │   │
│  │  Extract: device names, locations, times, durations, names          │   │
│  │  Resolve: map to HA entities, calendar events, people               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                     │                                                        │
│                     ▼                                                        │
│  OUTPUT                                                                      │
│  ══════                                                                      │
│  ClassificationResult(                                                       │
│      intent="time_query",                                                   │
│      confidence=0.99,                                                       │
│      stage="fast_pattern",                                                  │
│      entities={},                                                           │
│      raw_text="barnabee what time is it please",                           │
│      normalized_text="what time is it"                                     │
│  )                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

```python
@dataclass
class ClassificationResult:
    intent: str                      # e.g., "light_control"
    confidence: float                # 0.0 to 1.0
    stage: str                       # "fast_pattern", "embedding", "local_classifier", "llm"
    entities: Dict[str, Any]         # Extracted entities
    raw_text: str                    # Original input
    normalized_text: str             # After preprocessing
    latency_ms: float               # Classification time
    
    # For multi-intent (future)
    secondary_intents: List[Tuple[str, float]] = field(default_factory=list)


@dataclass  
class ExtractedEntities:
    devices: List[str]               # HA entity IDs
    locations: List[str]             # Area names
    times: List[datetime]            # Parsed times
    durations: List[timedelta]       # Parsed durations
    people: List[str]                # Person names/IDs
    raw_slots: Dict[str, str]        # Unparsed slot values
```

---

## 4. Intent Taxonomy

### 4.1 Intent Hierarchy

```
ROOT
├── home_control
│   ├── light_control           # "turn on the lights"
│   ├── climate_control         # "set temperature to 72"
│   ├── lock_control            # "lock the front door"
│   ├── cover_control           # "close the blinds"
│   ├── media_control           # "pause the music"
│   └── scene_activation        # "activate movie mode"
│
├── information
│   ├── time_query              # "what time is it"
│   ├── weather_query           # "what's the weather"
│   ├── calendar_query          # "what's on my calendar"
│   ├── email_query             # "any important emails"
│   ├── location_query          # "where is thom"
│   └── general_query           # "what's the capital of france"
│
├── tasks
│   ├── timer_set               # "set a timer for 10 minutes"
│   ├── timer_query             # "how much time left"
│   ├── timer_cancel            # "cancel the timer"
│   ├── reminder_set            # "remind me to call mom"
│   ├── todo_add                # "add milk to shopping list"
│   └── todo_query              # "what's on my todo list"
│
├── memory
│   ├── memory_create           # "remember that..."
│   ├── memory_query            # "what did I say about..."
│   ├── memory_delete           # "forget that"
│   └── memory_search           # "find memories about..."
│
├── mode_control
│   ├── start_conversation      # "let's talk about..."
│   ├── end_conversation        # "thanks, that's all"
│   ├── start_notes             # "start taking notes"
│   ├── end_notes               # "stop taking notes"
│   ├── start_journal           # "journal mode"
│   └── start_ambient           # "listen in"
│
├── conversation
│   ├── greeting                # "hi barnabee"
│   ├── farewell                # "goodbye"
│   ├── follow_up               # "what about..." (needs context)
│   ├── clarification           # "I meant the other one"
│   ├── confirmation            # "yes" / "no"
│   └── chitchat                # "how are you"
│
└── system
    ├── help                    # "what can you do"
    ├── repeat                  # "say that again"
    ├── cancel                  # "never mind"
    └── unknown                 # Fallback
```

**Extended Intents:** Finance intents (balance, spending, budget, goals, bills, transactions) are defined in `19-personal-finance.md` - restricted to super user only.

### 4.2 Intent Definitions

```python
INTENT_DEFINITIONS = {
    "light_control": {
        "description": "Turn lights on, off, dim, or change color",
        "required_entities": ["device"],
        "optional_entities": ["brightness", "color", "location"],
        "exemplars": [
            "turn on the lights",
            "turn off the kitchen light",
            "dim the bedroom lights to 50%",
            "make the living room lights blue",
            "lights on in the office",
        ],
        "action_type": "ha_service_call",
    },
    "time_query": {
        "description": "Ask for current time",
        "required_entities": [],
        "optional_entities": ["timezone"],
        "exemplars": [
            "what time is it",
            "what's the time",
            "current time",
            "time",
        ],
        "action_type": "instant_response",
    },
    "timer_set": {
        "description": "Set a countdown timer",
        "required_entities": ["duration"],
        "optional_entities": ["label"],
        "exemplars": [
            "set a timer for 10 minutes",
            "timer 5 minutes",
            "start a 30 second timer",
            "10 minute timer for pasta",
        ],
        "action_type": "create_timer",
    },
    # ... etc for all intents
}
```

---

## 5. Preprocessing

### 5.1 Normalization Pipeline

```python
import re
from typing import Tuple

class TextPreprocessor:
    WAKE_WORDS = ["barnabee", "barnaby", "hey barnabee", "ok barnabee"]
    
    POLITENESS_PATTERNS = [
        r"\bplease\b",
        r"\bthanks?\b",
        r"\bthank you\b",
        r"^can you\s+",
        r"^could you\s+",
        r"^would you\s+",
        r"^i'd like you to\s+",
        r"^i want you to\s+",
    ]
    
    CONTRACTIONS = {
        "what's": "what is",
        "where's": "where is",
        "who's": "who is",
        "how's": "how is",
        "it's": "it is",
        "that's": "that is",
        "there's": "there is",
        "he's": "he is",
        "she's": "she is",
        "let's": "let us",
        "i'm": "i am",
        "you're": "you are",
        "we're": "we are",
        "they're": "they are",
        "i've": "i have",
        "you've": "you have",
        "we've": "we have",
        "they've": "they have",
        "i'll": "i will",
        "you'll": "you will",
        "he'll": "he will",
        "she'll": "she will",
        "we'll": "we will",
        "they'll": "they will",
        "i'd": "i would",
        "you'd": "you would",
        "he'd": "he would",
        "she'd": "she would",
        "we'd": "we would",
        "they'd": "they would",
        "isn't": "is not",
        "aren't": "are not",
        "wasn't": "was not",
        "weren't": "were not",
        "haven't": "have not",
        "hasn't": "has not",
        "hadn't": "had not",
        "won't": "will not",
        "wouldn't": "would not",
        "don't": "do not",
        "doesn't": "does not",
        "didn't": "did not",
        "can't": "cannot",
        "couldn't": "could not",
        "shouldn't": "should not",
        "mightn't": "might not",
        "mustn't": "must not",
    }
    
    def preprocess(self, text: str) -> Tuple[str, dict]:
        """
        Normalize input text for classification.
        
        Returns: (normalized_text, metadata)
        """
        metadata = {"original": text, "transformations": []}
        
        # Lowercase
        result = text.lower().strip()
        
        # Remove wake word
        for wake in self.WAKE_WORDS:
            if result.startswith(wake):
                result = result[len(wake):].strip()
                result = result.lstrip(",").strip()  # Remove trailing comma
                metadata["transformations"].append(f"removed_wake_word:{wake}")
                break
        
        # Expand contractions
        for contraction, expansion in self.CONTRACTIONS.items():
            if contraction in result:
                result = result.replace(contraction, expansion)
                metadata["transformations"].append(f"expanded:{contraction}")
        
        # Remove politeness
        for pattern in self.POLITENESS_PATTERNS:
            result, count = re.subn(pattern, "", result, flags=re.IGNORECASE)
            if count > 0:
                metadata["transformations"].append(f"removed_politeness:{pattern}")
        
        # Normalize whitespace
        result = " ".join(result.split())
        
        return result, metadata
```

### 5.2 Preprocessing Tests

```python
def test_preprocessing():
    p = TextPreprocessor()
    
    cases = [
        ("barnabee what time is it please", "what time is it"),
        ("Hey Barnabee, turn on the lights", "turn on the lights"),
        ("Can you tell me the weather?", "tell me the weather"),
        ("What's the temperature", "what is the temperature"),
        ("TURN OFF THE LIGHTS", "turn off the lights"),
        ("  set   a  timer  ", "set a timer"),
    ]
    
    for input_text, expected in cases:
        result, _ = p.preprocess(input_text)
        assert result == expected, f"Expected '{expected}', got '{result}'"
```

---

## 6. Stage 1: Fast Pattern Matching

### 6.1 Pattern Database

Limited to ~50 high-confidence patterns for most common commands. These are NOT the 378 V1 patterns—these are carefully curated exact matches.

```python
FAST_PATTERNS = {
    # Time queries
    "time_query": [
        "what time is it",
        "what is the time",
        "current time",
        "time",
    ],
    
    # Weather queries  
    "weather_query": [
        "what is the weather",
        "weather",
        "what is the forecast",
        "is it going to rain",
        "temperature outside",
    ],
    
    # Basic light control
    "light_control": [
        "turn on the lights",
        "turn off the lights",
        "lights on",
        "lights off",
    ],
    
    # Timer
    "timer_query": [
        "how much time is left",
        "timer status",
        "how long on the timer",
    ],
    "timer_cancel": [
        "cancel the timer",
        "stop the timer",
        "cancel timer",
    ],
    
    # System
    "cancel": [
        "never mind",
        "cancel",
        "forget it",
        "stop",
    ],
    "repeat": [
        "say that again",
        "repeat that",
        "what did you say",
    ],
    
    # Greeting/farewell
    "greeting": [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
    ],
    "farewell": [
        "goodbye",
        "bye",
        "see you",
        "thanks that is all",
        "that is all",
    ],
}

class FastPatternMatcher:
    def __init__(self):
        # Build reverse index: normalized_text -> intent
        self.patterns = {}
        for intent, texts in FAST_PATTERNS.items():
            for text in texts:
                self.patterns[text] = intent
    
    def match(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Exact match against pattern database.
        
        Returns: (intent, confidence) or None
        """
        if text in self.patterns:
            return (self.patterns[text], 0.99)
        
        # Try fuzzy match for minor typos (Levenshtein distance ≤ 1)
        for pattern, intent in self.patterns.items():
            if self._levenshtein(text, pattern) <= 1:
                return (intent, 0.95)
        
        return None
    
    def _levenshtein(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance."""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        
        return prev_row[-1]
```

---

## 7. Stage 2: Embedding Similarity

### 7.1 Intent Exemplar Database

Each intent has multiple exemplar utterances with pre-computed embeddings.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingClassifier:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.intent_embeddings: Dict[str, np.ndarray] = {}
        self.intent_exemplars: Dict[str, List[str]] = {}
    
    def load_exemplars(self, intent_definitions: dict):
        """Load and embed all intent exemplars."""
        for intent, definition in intent_definitions.items():
            exemplars = definition.get("exemplars", [])
            if exemplars:
                self.intent_exemplars[intent] = exemplars
                # Compute centroid embedding for intent
                embeddings = self.model.encode(exemplars)
                self.intent_embeddings[intent] = np.mean(embeddings, axis=0)
    
    def classify(self, text: str) -> Tuple[str, float]:
        """
        Classify text by embedding similarity.
        
        Returns: (intent, confidence)
        """
        # Generate embedding for input
        query_embedding = self.model.encode(text)
        
        # Compare against all intent centroids
        best_intent = None
        best_similarity = -1
        
        for intent, intent_embedding in self.intent_embeddings.items():
            similarity = self._cosine_similarity(query_embedding, intent_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_intent = intent
        
        return (best_intent, best_similarity)
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### 7.2 Exemplar Expansion

Generate additional exemplars via paraphrasing for better coverage:

```python
INTENT_EXEMPLARS_EXPANDED = {
    "light_control": [
        # Original
        "turn on the lights",
        "turn off the lights",
        # Variations - location
        "turn on the kitchen lights",
        "turn off the bedroom light",
        "turn on the office light",
        "turn on lights in the living room",
        # Variations - phrasing
        "switch on the lights",
        "switch off the lights",
        "lights on",
        "lights off",
        "kill the lights",
        "hit the lights",
        # Variations - dimming
        "dim the lights",
        "dim the lights to 50 percent",
        "brighten the lights",
        "set lights to 75 percent",
        # Variations - color
        "make the lights blue",
        "change light color to red",
        "set lights to warm white",
    ],
    "timer_set": [
        # Original
        "set a timer for 10 minutes",
        # Variations - duration formats
        "set a timer for 5 minutes",
        "timer for 30 seconds",
        "start a 2 hour timer",
        "10 minute timer",
        "timer 15 minutes",
        # Variations - with labels
        "set a timer for pasta 10 minutes",
        "10 minute timer for eggs",
        "timer for laundry 45 minutes",
        # Variations - phrasing
        "start a timer for 10 minutes",
        "create a 10 minute timer",
        "count down 10 minutes",
    ],
    # ... etc
}
```

### 7.3 Embedding Caching

Pre-compute and cache embeddings at startup:

```python
class CachedEmbeddingClassifier(EmbeddingClassifier):
    def __init__(self, model_name: str, cache_path: Path):
        super().__init__(model_name)
        self.cache_path = cache_path
    
    def load_or_compute_embeddings(self, intent_definitions: dict):
        """Load cached embeddings or compute and cache."""
        cache_file = self.cache_path / "intent_embeddings.npz"
        
        if cache_file.exists():
            # Load from cache
            data = np.load(cache_file, allow_pickle=True)
            self.intent_embeddings = data["embeddings"].item()
            self.intent_exemplars = data["exemplars"].item()
        else:
            # Compute embeddings
            self.load_exemplars(intent_definitions)
            
            # Save to cache
            np.savez(
                cache_file,
                embeddings=self.intent_embeddings,
                exemplars=self.intent_exemplars
            )
```

---

## 8. Stage 3: Local Classifier

### 8.1 Model Architecture

Fine-tuned DistilBERT for multi-class classification.

```python
from transformers import (
    DistilBertForSequenceClassification,
    DistilBertTokenizer,
    Trainer,
    TrainingArguments,
)
import torch

class LocalIntentClassifier:
    def __init__(self, model_path: str, device: str = "cuda"):
        self.device = device
        self.tokenizer = DistilBertTokenizer.from_pretrained(model_path)
        self.model = DistilBertForSequenceClassification.from_pretrained(model_path)
        self.model.to(device)
        self.model.eval()
        
        # Load label mapping
        self.id_to_label = self.model.config.id2label
        self.label_to_id = self.model.config.label2id
    
    @torch.no_grad()
    def classify(self, text: str) -> Tuple[str, float]:
        """
        Classify text using fine-tuned model.
        
        Returns: (intent, confidence)
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=128,
            padding=True
        ).to(self.device)
        
        outputs = self.model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)
        
        confidence, predicted_id = torch.max(probs, dim=-1)
        intent = self.id_to_label[predicted_id.item()]
        
        return (intent, confidence.item())
```

### 8.2 Training Pipeline

```python
from datasets import Dataset
import pandas as pd

def train_local_classifier(
    training_data: List[Dict[str, str]],
    output_dir: str,
    base_model: str = "distilbert-base-uncased"
):
    """
    Train local classifier on labeled utterances.
    
    training_data: List of {"text": "...", "intent": "..."}
    """
    # Create dataset
    df = pd.DataFrame(training_data)
    
    # Create label mapping
    labels = sorted(df["intent"].unique())
    label_to_id = {label: i for i, label in enumerate(labels)}
    id_to_label = {i: label for label, i in label_to_id.items()}
    
    df["label"] = df["intent"].map(label_to_id)
    
    dataset = Dataset.from_pandas(df)
    
    # Split
    split = dataset.train_test_split(test_size=0.1)
    
    # Tokenize
    tokenizer = DistilBertTokenizer.from_pretrained(base_model)
    
    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=128,
            padding="max_length"
        )
    
    tokenized = split.map(tokenize, batched=True)
    
    # Load model
    model = DistilBertForSequenceClassification.from_pretrained(
        base_model,
        num_labels=len(labels),
        id2label=id_to_label,
        label2id=label_to_id
    )
    
    # Training arguments
    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=10,
        per_device_train_batch_size=32,
        per_device_eval_batch_size=32,
        learning_rate=2e-5,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["test"],
        compute_metrics=compute_metrics,
    )
    
    # Train
    trainer.train()
    
    # Save
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)


def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=-1)
    accuracy = (predictions == labels).mean()
    return {"accuracy": accuracy}
```

### 8.3 Training Data Sources

| Source | Volume | Quality |
|--------|--------|---------|
| Intent exemplars | ~500 | High (curated) |
| LLM fallback logs | Growing | Medium (needs review) |
| Synthetic paraphrases | ~2000 | Medium |
| User corrections | Growing | High |

---

## 9. Stage 4: LLM Fallback

### 9.1 Prompt Template

```python
LLM_CLASSIFICATION_PROMPT = """You are an intent classifier for a home assistant named Barnabee.

Given a user utterance, classify it into exactly ONE of the following intents:

HOME CONTROL:
- light_control: Turn lights on/off, dim, change color
- climate_control: Adjust temperature, HVAC settings
- lock_control: Lock/unlock doors
- cover_control: Open/close blinds, garage doors
- media_control: Play/pause/skip music, control TV
- scene_activation: Activate predefined scenes

INFORMATION:
- time_query: Current time
- weather_query: Weather and forecast
- calendar_query: Calendar and schedule
- email_query: Email status
- location_query: Where someone is
- general_query: General knowledge questions

TASKS:
- timer_set: Create a timer
- timer_query: Check timer status
- timer_cancel: Cancel a timer
- reminder_set: Set a reminder
- todo_add: Add to a list
- todo_query: Check lists

MEMORY:
- memory_create: Remember something
- memory_query: Recall something
- memory_delete: Forget something

MODE:
- start_conversation: Begin extended conversation
- end_conversation: End conversation
- start_notes: Begin meeting transcription
- end_notes: Stop transcription
- start_journal: Begin journal mode

CONVERSATION:
- greeting: Hello/hi
- farewell: Goodbye/bye
- follow_up: Continuation needing context
- clarification: Correcting misunderstanding
- confirmation: Yes/no response
- chitchat: Small talk

SYSTEM:
- help: Ask what Barnabee can do
- repeat: Ask to repeat
- cancel: Cancel current action
- unknown: Cannot determine intent

Respond with ONLY a JSON object:
{
  "intent": "<intent_name>",
  "confidence": <0.0-1.0>,
  "entities": {
    "device": "<device name if mentioned>",
    "location": "<location if mentioned>",
    "duration": "<duration if mentioned>",
    "time": "<time if mentioned>"
  },
  "reasoning": "<brief explanation>"
}

User utterance: "{utterance}"
"""

class LLMClassifier:
    def __init__(self, client: AzureOpenAI, model: str = "gpt-4o"):
        self.client = client
        self.model = model
    
    async def classify(self, text: str) -> Tuple[str, float, Dict]:
        """
        Classify using LLM with structured output.
        
        Returns: (intent, confidence, entities)
        """
        prompt = LLM_CLASSIFICATION_PROMPT.format(utterance=text)
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0,
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return (
            result["intent"],
            result["confidence"],
            result.get("entities", {})
        )
```

### 9.2 Fallback Logging

Every LLM fallback is logged for future training:

```python
async def log_llm_fallback(
    db: Database,
    utterance: str,
    result: ClassificationResult
):
    """Log LLM classification for future training."""
    await db.execute(
        """
        INSERT INTO training_examples 
        (utterance, correct_intent, original_intent, confidence, source)
        VALUES (?, ?, ?, ?, 'llm_fallback')
        """,
        [
            utterance,
            result.intent,
            None,  # No original intent (that's why we fell back)
            result.confidence,
        ]
    )
```

### 9.3 Intelligent Entity Resolution Fallback

When the fast entity resolver can't find a match, the LLM is used to make an intelligent guess. **The system should NEVER respond with "I don't know" or "I can't find that device"** - it should always make its best attempt.

```python
class IntelligentEntityResolver:
    """
    LLM-powered entity resolution when fast matching fails.
    
    Design Principle: NEVER say "I don't know" or "entity not found".
    Always make an intelligent attempt with full context.
    """
    
    def __init__(
        self,
        fast_resolver: 'FastEntityResolver',
        llm_client: 'LLMClient',
        ha_client: 'HAClient',
        signal_collector: 'SignalCollector',
    ):
        self.fast_resolver = fast_resolver
        self.llm = llm_client
        self.ha_client = ha_client
        self.signals = signal_collector
    
    async def resolve(
        self,
        entity_text: str,
        intent: str,
        device_area: Optional[str] = None,
        recent_commands: Optional[List[dict]] = None,
    ) -> 'ResolvedEntity':
        """
        Resolve entity text to HA entity ID.
        
        Always returns a result - never gives up.
        """
        
        # Try fast path first
        fast_result = await self.fast_resolver.resolve(entity_text)
        if fast_result and fast_result.confidence > 0.85:
            return fast_result
        
        # Fast path failed - use LLM with full context
        return await self._llm_resolve(
            entity_text=entity_text,
            intent=intent,
            device_area=device_area,
            recent_commands=recent_commands or [],
            fast_candidates=fast_result.candidates if fast_result else [],
        )
    
    async def _llm_resolve(
        self,
        entity_text: str,
        intent: str,
        device_area: Optional[str],
        recent_commands: List[dict],
        fast_candidates: List[dict],
    ) -> 'ResolvedEntity':
        """
        Use LLM to intelligently resolve ambiguous entity reference.
        """
        
        # Get all relevant HA entities
        all_entities = await self.ha_client.get_entities_for_intent(intent)
        
        # Filter by area if we know where the user is
        if device_area:
            area_entities = [e for e in all_entities if e.area == device_area]
            # But keep all entities available as context
        else:
            area_entities = []
        
        prompt = f"""You are Barnabee's entity resolver. The user said something that references a smart home device, but the exact match wasn't found.

User's device reference: "{entity_text}"
Detected intent: {intent}
User's current area: {device_area or "unknown"}

{self._format_area_entities(area_entities)}

All available entities for this intent type:
{self._format_all_entities(all_entities)}

{self._format_recent_commands(recent_commands)}

{self._format_fast_candidates(fast_candidates)}

Your job is to determine which entity the user MOST LIKELY means.

Consider:
1. Phonetic similarity (they might have said "liv room" meaning "living room")
2. Common abbreviations and nicknames
3. Context from the user's current location
4. What they've controlled recently
5. Logical groupings (e.g., "the lights" in the kitchen probably means kitchen lights)

You MUST pick the most likely entity. Do NOT say you can't find it.
If truly ambiguous between 2-3 options, pick the most likely AND suggest alternatives.

Respond with JSON:
{{
  "entity_id": "the most likely entity ID",
  "friendly_name": "human readable name",
  "confidence": 0.0-1.0,
  "reasoning": "why you chose this",
  "alternatives": ["other.entity_id", "if.ambiguous"],
  "suggested_alias": "if the user's phrase should become an alias"
}}"""

        response = await self.llm.complete(
            prompt,
            response_format={"type": "json_object"},
            max_tokens=300,
            temperature=0,
        )
        
        result = json.loads(response)
        
        # Verify the entity actually exists
        entity = await self.ha_client.get_entity(result["entity_id"])
        if not entity:
            # LLM hallucinated - fall back to first fast candidate or most likely by area
            result["entity_id"] = fast_candidates[0]["entity_id"] if fast_candidates else \
                                  area_entities[0].entity_id if area_entities else \
                                  all_entities[0].entity_id
            result["confidence"] = 0.5
            result["reasoning"] = "Fallback selection"
        
        # Log for self-improvement
        await self.signals.record_llm_entity_resolution(
            original_text=entity_text,
            resolved_entity=result["entity_id"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            suggested_alias=result.get("suggested_alias"),
        )
        
        return ResolvedEntity(
            entity_id=result["entity_id"],
            friendly_name=result["friendly_name"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            alternatives=result.get("alternatives", []),
            suggested_alias=result.get("suggested_alias"),
            resolution_method="llm",
        )
    
    def _format_area_entities(self, entities: List) -> str:
        if not entities:
            return ""
        return f"""Entities in user's current area:
{chr(10).join(f'  - {e.entity_id}: {e.friendly_name}' for e in entities)}
"""
    
    def _format_all_entities(self, entities: List) -> str:
        # Group by area for readability
        by_area = {}
        for e in entities:
            area = e.area or "Unknown Area"
            by_area.setdefault(area, []).append(e)
        
        lines = []
        for area, area_entities in by_area.items():
            lines.append(f"  {area}:")
            for e in area_entities[:5]:  # Limit per area
                lines.append(f"    - {e.entity_id}: {e.friendly_name}")
            if len(area_entities) > 5:
                lines.append(f"    - ... and {len(area_entities) - 5} more")
        
        return chr(10).join(lines)
    
    def _format_recent_commands(self, commands: List[dict]) -> str:
        if not commands:
            return ""
        return f"""Recent commands from this user:
{chr(10).join(f'  - {c["entity_id"]}: {c["action"]} ({c["ago"]})' for c in commands[:5])}
"""
    
    def _format_fast_candidates(self, candidates: List[dict]) -> str:
        if not candidates:
            return "No close matches found by fast resolver."
        return f"""Close matches from fast resolver (but below confidence threshold):
{chr(10).join(f'  - {c["entity_id"]}: {c["score"]:.2f}' for c in candidates[:3])}
"""


@dataclass
class ResolvedEntity:
    entity_id: str
    friendly_name: str
    confidence: float
    reasoning: str
    alternatives: List[str]
    suggested_alias: Optional[str]
    resolution_method: str  # "fast", "llm", "cache"
```

### 9.4 Graceful Execution with Fallback

The command executor should never fail with "entity not found". It should always make an attempt and offer corrections.

```python
class GracefulCommandExecutor:
    """
    Execute commands gracefully - never fail with 'not found'.
    
    Design Principle: Always try to do something helpful.
    """
    
    async def execute(
        self,
        classification: ClassificationResult,
        context: 'ExecutionContext',
    ) -> ExecutionResult:
        """
        Execute a classified command.
        
        Never returns "I don't know" or "I can't find that".
        """
        
        # Get the primary device entity
        device_entity = classification.get_entity("device")
        
        if device_entity and device_entity.entity_id:
            # Entity was resolved - execute
            result = await self._execute_on_entity(
                entity_id=device_entity.entity_id,
                intent=classification.intent,
            )
            
            return ExecutionResult(
                success=True,
                response=self._format_success_response(result),
            )
        
        elif device_entity and device_entity.raw_value:
            # Entity text exists but wasn't resolved - use intelligent resolver
            resolved = await self.intelligent_resolver.resolve(
                entity_text=device_entity.raw_value,
                intent=classification.intent,
                device_area=context.device_area,
                recent_commands=context.recent_commands,
            )
            
            # Execute on resolved entity
            result = await self._execute_on_entity(
                entity_id=resolved.entity_id,
                intent=classification.intent,
            )
            
            # Build response that mentions what we did
            response = self._format_resolved_response(result, resolved)
            
            return ExecutionResult(
                success=True,
                response=response,
                resolved_entity=resolved,
            )
        
        else:
            # No entity specified - use context to guess
            guessed_entity = await self._guess_entity_from_context(
                intent=classification.intent,
                context=context,
            )
            
            result = await self._execute_on_entity(
                entity_id=guessed_entity.entity_id,
                intent=classification.intent,
            )
            
            response = self._format_guessed_response(result, guessed_entity)
            
            return ExecutionResult(
                success=True,
                response=response,
                guessed_entity=guessed_entity,
            )
    
    def _format_success_response(self, result: HACommandResult) -> str:
        """Simple success response."""
        return "Done."
    
    def _format_resolved_response(
        self, 
        result: HACommandResult, 
        resolved: ResolvedEntity
    ) -> str:
        """Response when we had to resolve an ambiguous reference."""
        base = f"I've turned {result.new_state} the {resolved.friendly_name}."
        
        if resolved.alternatives:
            base += f" Did you mean a different one?"
        
        return base
    
    def _format_guessed_response(
        self,
        result: HACommandResult,
        guessed: 'GuessedEntity',
    ) -> str:
        """Response when we guessed based on context."""
        return f"I've turned {result.new_state} the {guessed.friendly_name}. " \
               f"Let me know if you meant a different one."
    
    async def _guess_entity_from_context(
        self,
        intent: str,
        context: 'ExecutionContext',
    ) -> 'GuessedEntity':
        """
        When no entity is specified, guess based on context.
        
        e.g., "turn on the lights" in the kitchen → kitchen lights
        """
        
        # Get entities in user's current area
        area_entities = await self.ha_client.get_entities_by_area(
            area=context.device_area,
            domain=self._intent_to_domain(intent),
        )
        
        if area_entities:
            # Pick the "main" entity for this area (usually the one without a suffix)
            main_entity = self._find_main_entity(area_entities)
            return GuessedEntity(
                entity_id=main_entity.entity_id,
                friendly_name=main_entity.friendly_name,
                reason=f"Main {self._intent_to_domain(intent)} in {context.device_area}",
            )
        
        # No area-specific entity - get most recently used
        recent = await self.ha_client.get_recently_used_entity(
            domain=self._intent_to_domain(intent),
        )
        
        if recent:
            return GuessedEntity(
                entity_id=recent.entity_id,
                friendly_name=recent.friendly_name,
                reason="Most recently used",
            )
        
        # Last resort - get any entity of the right type
        any_entity = await self.ha_client.get_any_entity(
            domain=self._intent_to_domain(intent),
        )
        
        return GuessedEntity(
            entity_id=any_entity.entity_id,
            friendly_name=any_entity.friendly_name,
            reason="Default entity",
        )
```

---

## 10. Entity Extraction & Resolution

### 10.1 Entity Types

| Entity Type | Examples | Resolution Target |
|-------------|----------|-------------------|
| device | "kitchen lights", "the thermostat" | HA entity_id |
| location | "office", "upstairs", "the bedroom" | HA area |
| duration | "10 minutes", "half an hour" | timedelta |
| time | "3pm", "tomorrow morning" | datetime |
| brightness | "50 percent", "dim", "bright" | 0-100 |
| color | "blue", "warm white", "red" | RGB or color temp |
| person | "thom", "elizabeth", "the kids" | person entity |

### 10.2 Entity Extraction

```python
import re
from dateutil import parser as date_parser
from datetime import timedelta

class EntityExtractor:
    DURATION_PATTERNS = [
        (r"(\d+)\s*hours?", lambda m: timedelta(hours=int(m.group(1)))),
        (r"(\d+)\s*minutes?", lambda m: timedelta(minutes=int(m.group(1)))),
        (r"(\d+)\s*seconds?", lambda m: timedelta(seconds=int(m.group(1)))),
        (r"half\s*(?:an?\s*)?hour", lambda m: timedelta(minutes=30)),
        (r"quarter\s*(?:of\s*an?\s*)?hour", lambda m: timedelta(minutes=15)),
    ]
    
    BRIGHTNESS_PATTERNS = [
        (r"(\d+)\s*(?:percent|%)", lambda m: int(m.group(1))),
        (r"\bdim\b", lambda m: 30),
        (r"\bbright\b", lambda m: 100),
        (r"\bmedium\b", lambda m: 50),
    ]
    
    COLOR_MAP = {
        "red": "#FF0000",
        "green": "#00FF00",
        "blue": "#0000FF",
        "warm white": {"color_temp": 2700},
        "cool white": {"color_temp": 6500},
        "daylight": {"color_temp": 5000},
    }
    
    def extract(self, text: str, intent: str) -> ExtractedEntities:
        """Extract entities from text based on intent."""
        entities = ExtractedEntities(
            devices=[],
            locations=[],
            times=[],
            durations=[],
            people=[],
            raw_slots={},
        )
        
        # Duration
        for pattern, converter in self.DURATION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                entities.durations.append(converter(match))
                break
        
        # Brightness
        for pattern, converter in self.BRIGHTNESS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                entities.raw_slots["brightness"] = converter(match)
                break
        
        # Color
        for color, value in self.COLOR_MAP.items():
            if color in text.lower():
                entities.raw_slots["color"] = value
                break
        
        # Time (using dateutil for natural language parsing)
        try:
            parsed_time = date_parser.parse(text, fuzzy=True)
            entities.times.append(parsed_time)
        except:
            pass  # No time found
        
        return entities
```

### 10.3 Entity Resolution (HA Mapping)

```python
from rapidfuzz import fuzz, process

class HAEntityResolver:
    def __init__(self, ha_cache: HAEntityCache):
        self.ha_cache = ha_cache
    
    async def resolve_device(
        self, 
        device_text: str, 
        domain: Optional[str] = None,
        location: Optional[str] = None
    ) -> List[str]:
        """
        Resolve natural language device reference to HA entity IDs.
        
        Returns: List of matching entity_ids
        """
        # Get candidate entities
        candidates = await self.ha_cache.get_entities(domain=domain, area=location)
        
        if not candidates:
            return []
        
        # Build searchable names
        searchable = []
        for entity in candidates:
            names = [
                entity.entity_id,
                entity.friendly_name,
                *entity.aliases,
            ]
            for name in names:
                if name:
                    searchable.append((name.lower(), entity.entity_id))
        
        # Exact match first
        device_lower = device_text.lower()
        for name, entity_id in searchable:
            if name == device_lower:
                return [entity_id]
        
        # Fuzzy match
        matches = process.extract(
            device_lower,
            [s[0] for s in searchable],
            scorer=fuzz.ratio,
            limit=5
        )
        
        # Filter by threshold
        results = []
        for match_text, score, _ in matches:
            if score >= 80:
                # Find corresponding entity_id
                for name, entity_id in searchable:
                    if name == match_text:
                        results.append(entity_id)
                        break
        
        return results
    
    async def resolve_location(self, location_text: str) -> Optional[str]:
        """Resolve location text to HA area."""
        areas = await self.ha_cache.get_areas()
        
        location_lower = location_text.lower()
        
        # Exact match
        for area in areas:
            if area.lower() == location_lower:
                return area
        
        # Fuzzy match
        match = process.extractOne(
            location_lower,
            areas,
            scorer=fuzz.ratio
        )
        
        if match and match[1] >= 80:
            return match[0]
        
        return None
```

### 10.4 Combined Resolution

```python
async def resolve_entities(
    text: str,
    intent: str,
    extracted: ExtractedEntities,
    ha_resolver: HAEntityResolver
) -> ExtractedEntities:
    """
    Resolve extracted entities to HA entities.
    """
    # Determine domain from intent
    domain_map = {
        "light_control": "light",
        "climate_control": "climate",
        "lock_control": "lock",
        "cover_control": "cover",
        "media_control": "media_player",
    }
    domain = domain_map.get(intent)
    
    # Resolve location first (for scoping device search)
    location = None
    if extracted.locations:
        location = await ha_resolver.resolve_location(extracted.locations[0])
    else:
        # Try to extract location from text
        location = await extract_location_from_text(text, ha_resolver)
    
    # Resolve devices
    if extracted.devices:
        device_ids = []
        for device in extracted.devices:
            ids = await ha_resolver.resolve_device(device, domain, location)
            device_ids.extend(ids)
        extracted.devices = device_ids
    else:
        # No explicit device - try to extract from text
        device_ids = await extract_devices_from_text(text, domain, location, ha_resolver)
        extracted.devices = device_ids
    
    # If still no devices but we have location+domain, get all in area
    if not extracted.devices and location and domain:
        entities = await ha_resolver.ha_cache.get_entities(domain=domain, area=location)
        extracted.devices = [e.entity_id for e in entities]
    
    return extracted


async def extract_devices_from_text(
    text: str,
    domain: Optional[str],
    location: Optional[str],
    resolver: HAEntityResolver
) -> List[str]:
    """Extract device references from free text."""
    # Common device words to search for
    device_words = {
        "light": ["light", "lights", "lamp", "lamps"],
        "climate": ["thermostat", "ac", "heater", "hvac"],
        "lock": ["lock", "door lock"],
        "cover": ["blinds", "shades", "curtains", "garage"],
        "media_player": ["tv", "speaker", "roku", "chromecast"],
    }
    
    # Check for device words in text
    for word_list in (device_words.get(domain, []) if domain else sum(device_words.values(), [])):
        if word_list in text.lower():
            # Found device word, resolve with context
            return await resolver.resolve_device(word_list, domain, location)
    
    return []
```

---

## 11. Orchestrator

### 11.1 Main Classification Pipeline

```python
class IntentClassifier:
    def __init__(
        self,
        preprocessor: TextPreprocessor,
        fast_matcher: FastPatternMatcher,
        embedding_classifier: EmbeddingClassifier,
        local_classifier: LocalIntentClassifier,
        llm_classifier: LLMClassifier,
        entity_extractor: EntityExtractor,
        ha_resolver: HAEntityResolver,
        db: Database,
    ):
        self.preprocessor = preprocessor
        self.fast_matcher = fast_matcher
        self.embedding_classifier = embedding_classifier
        self.local_classifier = local_classifier
        self.llm_classifier = llm_classifier
        self.entity_extractor = entity_extractor
        self.ha_resolver = ha_resolver
        self.db = db
        
        # Confidence thresholds
        self.FAST_THRESHOLD = 0.95
        self.EMBEDDING_THRESHOLD = 0.85
        self.LOCAL_THRESHOLD = 0.80
    
    async def classify(self, text: str) -> ClassificationResult:
        """
        Run full classification pipeline.
        """
        start_time = time.perf_counter()
        
        # Stage 0: Preprocessing
        normalized, metadata = self.preprocessor.preprocess(text)
        
        # Stage 1: Fast pattern match
        fast_result = self.fast_matcher.match(normalized)
        if fast_result and fast_result[1] >= self.FAST_THRESHOLD:
            intent, confidence = fast_result
            entities = await self._extract_and_resolve(normalized, intent)
            return ClassificationResult(
                intent=intent,
                confidence=confidence,
                stage="fast_pattern",
                entities=entities,
                raw_text=text,
                normalized_text=normalized,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Stage 2: Embedding similarity
        embed_intent, embed_conf = self.embedding_classifier.classify(normalized)
        if embed_conf >= self.EMBEDDING_THRESHOLD:
            entities = await self._extract_and_resolve(normalized, embed_intent)
            return ClassificationResult(
                intent=embed_intent,
                confidence=embed_conf,
                stage="embedding",
                entities=entities,
                raw_text=text,
                normalized_text=normalized,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Stage 3: Local classifier
        local_intent, local_conf = self.local_classifier.classify(normalized)
        if local_conf >= self.LOCAL_THRESHOLD:
            entities = await self._extract_and_resolve(normalized, local_intent)
            return ClassificationResult(
                intent=local_intent,
                confidence=local_conf,
                stage="local_classifier",
                entities=entities,
                raw_text=text,
                normalized_text=normalized,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Stage 4: LLM fallback
        llm_intent, llm_conf, llm_entities = await self.llm_classifier.classify(normalized)
        
        # Log for future training
        await self._log_llm_fallback(text, normalized, llm_intent, llm_conf)
        
        # Resolve LLM-extracted entities
        entities = await self._merge_and_resolve_entities(normalized, llm_intent, llm_entities)
        
        return ClassificationResult(
            intent=llm_intent,
            confidence=llm_conf,
            stage="llm",
            entities=entities,
            raw_text=text,
            normalized_text=normalized,
            latency_ms=(time.perf_counter() - start_time) * 1000,
        )
    
    async def _extract_and_resolve(self, text: str, intent: str) -> Dict:
        """Extract and resolve entities."""
        extracted = self.entity_extractor.extract(text, intent)
        resolved = await resolve_entities(text, intent, extracted, self.ha_resolver)
        return asdict(resolved)
    
    async def _log_llm_fallback(
        self, 
        raw_text: str, 
        normalized: str, 
        intent: str, 
        confidence: float
    ):
        """Log LLM fallback for training data."""
        await log_llm_fallback(
            self.db,
            normalized,
            ClassificationResult(
                intent=intent,
                confidence=confidence,
                stage="llm",
                entities={},
                raw_text=raw_text,
                normalized_text=normalized,
                latency_ms=0,
            )
        )
```

---

## 12. Continuous Learning

### 12.1 Correction Detection

```python
CORRECTION_PATTERNS = [
    r"no,?\s*i\s*(?:meant|said|want)",
    r"not\s+that\s+one",
    r"wrong\s+(?:one|thing|device)",
    r"the\s+other\s+(?:one|light|room)",
    r"i\s+didn'?t\s+(?:mean|say|want)",
]

async def detect_correction(
    current_text: str,
    previous_result: ClassificationResult
) -> Optional[CorrectionEvent]:
    """Detect if user is correcting a misclassification."""
    for pattern in CORRECTION_PATTERNS:
        if re.search(pattern, current_text.lower()):
            return CorrectionEvent(
                original_text=previous_result.raw_text,
                original_intent=previous_result.intent,
                correction_text=current_text,
                timestamp=datetime.utcnow(),
            )
    return None
```

### 12.2 Training Data Management

```python
async def get_training_data(db: Database) -> List[Dict[str, str]]:
    """Get all approved training examples."""
    # Get curated exemplars
    curated = []
    for intent, definition in INTENT_DEFINITIONS.items():
        for exemplar in definition.get("exemplars", []):
            curated.append({"text": exemplar, "intent": intent})
    
    # Get LLM fallbacks (high confidence only)
    llm_examples = await db.fetch(
        """
        SELECT utterance, correct_intent
        FROM training_examples
        WHERE source = 'llm_fallback' AND confidence > 0.9
        AND included_in_training = 0
        """
    )
    
    # Get user corrections
    corrections = await db.fetch(
        """
        SELECT utterance, correct_intent
        FROM training_examples
        WHERE source = 'user_correction'
        AND included_in_training = 0
        """
    )
    
    all_data = curated + [
        {"text": ex["utterance"], "intent": ex["correct_intent"]}
        for ex in llm_examples + corrections
    ]
    
    return all_data
```

### 12.3 Retraining Pipeline

```python
async def retrain_local_classifier(db: Database, output_dir: str):
    """Retrain local classifier with new data."""
    # Get training data
    training_data = await get_training_data(db)
    
    if len(training_data) < 100:
        logger.warning("Not enough training data for retraining")
        return
    
    # Train
    train_local_classifier(training_data, output_dir)
    
    # Mark examples as included
    await db.execute(
        "UPDATE training_examples SET included_in_training = 1 WHERE included_in_training = 0"
    )
    
    # Evaluate on golden dataset
    accuracy = await evaluate_on_golden_dataset(output_dir)
    
    if accuracy < 0.90:
        logger.error(f"Retrained model accuracy too low: {accuracy}")
        # Don't deploy
        return
    
    logger.info(f"Retrained model accuracy: {accuracy}, ready for deployment")
```

---

## 13. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── nlu/
│           ├── __init__.py
│           ├── config.py              # Thresholds, model paths
│           ├── classifier.py          # IntentClassifier orchestrator
│           ├── preprocessing.py       # TextPreprocessor
│           ├── stages/
│           │   ├── __init__.py
│           │   ├── fast_patterns.py   # FastPatternMatcher
│           │   ├── embedding.py       # EmbeddingClassifier
│           │   ├── local_model.py     # LocalIntentClassifier
│           │   └── llm_fallback.py    # LLMClassifier
│           ├── entities/
│           │   ├── __init__.py
│           │   ├── extractor.py       # EntityExtractor
│           │   └── resolver.py        # HAEntityResolver
│           ├── training/
│           │   ├── __init__.py
│           │   ├── data.py            # Training data management
│           │   ├── train.py           # Training pipeline
│           │   └── evaluate.py        # Evaluation on golden dataset
│           └── intents/
│               ├── __init__.py
│               └── definitions.py     # INTENT_DEFINITIONS, exemplars
├── models/
│   ├── embedding_cache/              # Cached intent embeddings
│   └── local_classifier/             # Fine-tuned DistilBERT
├── data/
│   └── golden_dataset.json           # Curated test cases
└── scripts/
    ├── train_classifier.py
    ├── evaluate_classifier.py
    └── expand_exemplars.py
```

---

## 14. Implementation Checklist

### Preprocessing

- [ ] Wake word removal
- [ ] Contraction expansion
- [ ] Politeness removal
- [ ] Whitespace normalization
- [ ] Unit tests for all transformations

### Fast Pattern Matching

- [ ] Core pattern database (~50 patterns)
- [ ] Exact match lookup
- [ ] Levenshtein fuzzy match (distance ≤ 1)

### Embedding Classification

- [ ] all-MiniLM-L6-v2 model loading
- [ ] Intent exemplar database
- [ ] Embedding caching
- [ ] Cosine similarity classification

### Local Classifier

- [ ] DistilBERT fine-tuning pipeline
- [ ] Initial training on exemplars
- [ ] Model serving with CUDA

### LLM Fallback

- [ ] Structured output prompt
- [ ] Azure OpenAI integration
- [ ] Fallback logging for training

### Entity Extraction

- [ ] Duration parsing
- [ ] Time parsing (dateutil)
- [ ] Brightness/color extraction
- [ ] Device name extraction

### Entity Resolution

- [ ] HA entity cache integration
- [ ] Fuzzy matching with rapidfuzz
- [ ] Location resolution
- [ ] Domain-scoped device resolution

### Continuous Learning

- [ ] Correction detection
- [ ] Training data management
- [ ] Retraining pipeline
- [ ] Golden dataset evaluation

### Validation

- [ ] Classification accuracy >95% on golden dataset
- [ ] Stage 1+2 latency <50ms
- [ ] LLM fallback rate <10%
- [ ] Entity resolution accuracy >98%

### Acceptance Criteria

1. **95%+ accuracy** on 200+ golden dataset utterances
2. **<50ms classification** for 90%+ of requests
3. **<10% LLM fallback rate** in normal operation
4. **Entity resolution works** for all common device references

---

## 15. Handoff Notes for Implementation Agent

### Critical Points

1. **Preprocessing is crucial.** Without wake word removal, "barnabee what time" ≠ "what time" and classification fails.

2. **Embedding model must be GPU-loaded at startup.** First inference is slow (500ms+). Warm it up.

3. **Don't skip stages.** The cascade is designed for consistent latency. Running embedding + local in parallel wastes GPU.

4. **Entity resolution is as important as classification.** "Turn on the lights" is useless without knowing WHICH lights.

5. **Log everything for LLM fallback.** This is your training data flywheel.

6. **Golden dataset is your ground truth.** Never deploy a model that regresses on it.

### Common Pitfalls

- Forgetting to normalize case before embedding (model expects lowercase)
- Not handling empty entity resolution (return helpful error, not crash)
- Training local classifier on too few examples (<100 per intent)
- Not re-caching embeddings after adding exemplars
- Fuzzy matching with too low threshold (false positives on "light" vs "night")

### Performance Tuning

- Batch embedding generation at startup (all exemplars at once)
- Use CUDA for DistilBERT inference
- Cache entity resolution results (same "kitchen lights" text = same result)
- Pre-compute area→entities mapping at HA cache load

---

**End of Area 03: Intent Classification & NLU**

# Area 05: Memory System

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer), Area 03 (Intent Classification)  
**Phase:** Data  

---

## 1. Overview

### 1.1 Purpose

The Memory System provides persistent, searchable knowledge that makes Barnabee useful over time. Unlike V1's profile system (which over-injected irrelevant facts), V2 memories are contextually retrieved, relevance-scored, and intentionally created.

### 1.2 V1 Problems Solved

| V1 Problem | V2 Solution |
|------------|-------------|
| Profile facts always injected (chickens in every response) | Contextual retrieval based on query relevance |
| No memory from conversations | Automatic extraction with user confirmation |
| No way to forget | Soft delete with super user recovery |
| Single-tier (all or nothing) | Three tiers: active, soft-deleted, operational logs |
| No search ("what did I say about...") | Hybrid vector + FTS search with progressive narrowing |

### 1.3 Design Principles

1. **Intentional memory only:** Memories come from explicit requests, meaningful conversations, meetings, or journals—never from ambient listening or transient commands.

2. **Relevance over volume:** Inject 3-5 highly relevant memories, not 50 tangentially related ones.

3. **Progressive narrowing:** Search returns batches of 3, user refines conversationally.

4. **Soft delete by default:** "Forget that" moves to recoverable tier, not permanent deletion.

5. **Transparency:** Users can ask "what do you remember about X" and get a clear answer.

---

## 2. Memory Architecture

### 2.1 Three-Tier Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MEMORY TIERS                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TIER 1: ACTIVE MEMORY                                                       │
│  ═══════════════════════                                                     │
│  │ Visibility: User-facing                                                  │
│  │ Searchable: Yes                                                          │
│  │ Auto-injected: Yes (when relevant)                                       │
│  │ Deletable: Yes (moves to Tier 2)                                         │
│  │                                                                          │
│  │ Sources:                                                                 │
│  │   ✓ "Barnabee, remember that..." (explicit)                             │
│  │   ✓ Extracted from conversations (with confirmation)                    │
│  │   ✓ Meeting summaries and decisions                                     │
│  │   ✓ Journal entries                                                     │
│  │   ✓ Migration from V1 profiles                                          │
│  │                                                                          │
│  │ NOT from:                                                                │
│  │   ✗ Ambient mode listening                                              │
│  │   ✗ Command-mode transactions ("turn on lights")                        │
│  │   ✗ Failed/cancelled requests                                           │
│  │                                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 2: SOFT-DELETED MEMORY                                                 │
│  ═══════════════════════════════                                             │
│  │ Visibility: Hidden from user                                             │
│  │ Searchable: Super user only                                              │
│  │ Auto-injected: Never                                                     │
│  │                                                                          │
│  │ Purpose:                                                                 │
│  │   • Recovery ("I didn't mean to delete that")                           │
│  │   • Safety verification                                                 │
│  │   • Debugging                                                           │
│  │                                                                          │
│  │ Retention: Indefinite (until hard delete)                               │
│  │                                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 3: OPERATIONAL LOGS                                                    │
│  ═══════════════════════════                                                 │
│  │ Visibility: Admin dashboard only                                         │
│  │ Searchable: Super user only                                              │
│  │ Auto-injected: Never                                                     │
│  │                                                                          │
│  │ Contents:                                                                │
│  │   • Every request/response                                              │
│  │   • Classification decisions                                            │
│  │   • Memory operations (create, delete, access)                          │
│  │   • System events                                                       │
│  │                                                                          │
│  │ Retention: 90 days (auto-purge)                                         │
│  │                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Memory Types

| Type | Description | Example |
|------|-------------|---------|
| fact | Objective information | "Thom works at Microsoft" |
| preference | Subjective preference | "Penelope loves chicken-themed gifts" |
| decision | Agreed-upon choice | "We decided to go with the blue tile" |
| event | Something that happened | "Visited Grandma on March 15th" |
| person | Information about a person | "John from Contoso - sales director" |
| project | Project-related info | "Kitchen renovation budget is $50k" |
| meeting | Meeting summary | "Azure migration planning - Mar 18" |
| journal | Personal reflection | "Feeling good about the interview" |

### 2.3 Memory Sources

| Source | Trigger | Confirmation Required |
|--------|---------|----------------------|
| explicit | "Remember that..." | No |
| extracted | End of conversation | Yes ("Should I remember anything?") |
| meeting | Meeting ends | No (automatic) |
| journal | Journal entry saved | No (automatic) |
| migration | V1 import | No (one-time) |

---

## 3. Memory Creation

### 3.1 Explicit Memory Creation

```python
class ExplicitMemoryCreator:
    """Handle "Barnabee, remember that..." requests."""
    
    REMEMBER_PATTERNS = [
        r"remember\s+that\s+(.+)",
        r"don'?t\s+forget\s+(?:that\s+)?(.+)",
        r"keep\s+in\s+mind\s+(?:that\s+)?(.+)",
        r"note\s+that\s+(.+)",
        r"make\s+a\s+note\s+(?:that\s+)?(.+)",
    ]
    
    def __init__(self, memory_repo: MemoryRepository, llm_client: LLMClient):
        self.memory_repo = memory_repo
        self.llm = llm_client
    
    async def create_from_utterance(
        self,
        utterance: str,
        speaker_id: str,
        conversation_id: Optional[str] = None,
    ) -> Memory:
        """Create memory from explicit request."""
        
        # Extract the memory content
        content = self._extract_content(utterance)
        
        # Classify memory type
        memory_type = await self._classify_type(content)
        
        # Generate summary (shorter than content)
        summary = await self._generate_summary(content)
        
        # Extract keywords
        keywords = await self._extract_keywords(content)
        
        # Create memory
        memory = await self.memory_repo.create(
            summary=summary,
            content=content,
            memory_type=memory_type,
            source_type="explicit",
            source_id=conversation_id,
            source_speaker=speaker_id,
            owner=speaker_id,
            keywords=keywords,
        )
        
        # Generate and store embedding
        await self._generate_embedding(memory)
        
        return memory
    
    def _extract_content(self, utterance: str) -> str:
        """Extract memory content from utterance."""
        for pattern in self.REMEMBER_PATTERNS:
            match = re.search(pattern, utterance, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return utterance
    
    async def _classify_type(self, content: str) -> str:
        """Classify memory type using LLM."""
        prompt = f"""Classify this memory into exactly one category:
- fact: Objective information
- preference: Subjective like/dislike
- decision: A choice that was made
- event: Something that happened
- person: Information about a person
- project: Project-related information

Memory: "{content}"

Respond with just the category name."""

        response = await self.llm.complete(prompt, max_tokens=10)
        memory_type = response.strip().lower()
        
        if memory_type not in ["fact", "preference", "decision", "event", "person", "project"]:
            return "fact"  # Default
        
        return memory_type
    
    async def _generate_summary(self, content: str) -> str:
        """Generate concise summary if content is long."""
        if len(content) < 100:
            return content
        
        prompt = f"""Summarize this in one sentence (max 100 characters):
"{content}"

Summary:"""

        return (await self.llm.complete(prompt, max_tokens=50)).strip()
    
    async def _extract_keywords(self, content: str) -> List[str]:
        """Extract searchable keywords."""
        prompt = f"""Extract 3-5 important keywords from this text. 
Return as comma-separated list, lowercase.

Text: "{content}"

Keywords:"""

        response = await self.llm.complete(prompt, max_tokens=50)
        keywords = [k.strip().lower() for k in response.split(",")]
        return keywords[:5]
```

### 3.2 Conversation Memory Extraction

```python
class ConversationMemoryExtractor:
    """Extract memories from completed conversations."""
    
    EXTRACTION_PROMPT = """Analyze this conversation and extract any information worth remembering long-term.

Focus on:
- Facts about people, places, or things
- Preferences expressed
- Decisions made
- Events mentioned
- Project details

Ignore:
- Transient commands (turn on lights)
- Small talk
- Questions without answers
- Temporary information

Conversation:
{conversation}

For each memory worth saving, provide:
1. A one-sentence summary
2. The full content
3. Type (fact/preference/decision/event/person/project)
4. Keywords (3-5)

If nothing is worth remembering, respond with "NONE".

Format as JSON array:
[{{"summary": "...", "content": "...", "type": "...", "keywords": ["...", "..."]}}]
"""
    
    def __init__(
        self,
        memory_repo: MemoryRepository,
        llm_client: LLMClient,
    ):
        self.memory_repo = memory_repo
        self.llm = llm_client
    
    async def extract_from_conversation(
        self,
        conversation: Conversation,
        turns: List[ConversationTurn],
    ) -> List[dict]:
        """
        Extract potential memories from a conversation.
        Returns list of proposed memories for user confirmation.
        """
        # Format conversation for LLM
        conversation_text = self._format_conversation(turns)
        
        # Skip if too short
        if len(turns) < 4:
            return []
        
        # Extract via LLM
        prompt = self.EXTRACTION_PROMPT.format(conversation=conversation_text)
        response = await self.llm.complete(prompt, max_tokens=500)
        
        if "NONE" in response:
            return []
        
        # Parse response
        try:
            proposals = json.loads(response)
        except json.JSONDecodeError:
            return []
        
        # Validate and enrich
        validated = []
        for proposal in proposals:
            if self._validate_proposal(proposal):
                proposal["conversation_id"] = conversation.id
                proposal["speaker_id"] = conversation.speaker_id
                validated.append(proposal)
        
        return validated
    
    async def confirm_and_create(
        self,
        proposals: List[dict],
        confirmed_indices: List[int],
    ) -> List[Memory]:
        """Create memories from confirmed proposals."""
        memories = []
        
        for idx in confirmed_indices:
            if 0 <= idx < len(proposals):
                proposal = proposals[idx]
                memory = await self.memory_repo.create(
                    summary=proposal["summary"],
                    content=proposal["content"],
                    memory_type=proposal["type"],
                    source_type="extracted",
                    source_id=proposal.get("conversation_id"),
                    source_speaker=proposal.get("speaker_id"),
                    owner=proposal.get("speaker_id"),
                    keywords=proposal.get("keywords", []),
                )
                memories.append(memory)
        
        return memories
    
    def _format_conversation(self, turns: List[ConversationTurn]) -> str:
        """Format turns for LLM prompt."""
        lines = []
        for turn in turns:
            role = "User" if turn.role == "user" else "Barnabee"
            lines.append(f"{role}: {turn.content}")
        return "\n".join(lines)
    
    def _validate_proposal(self, proposal: dict) -> bool:
        """Validate extracted proposal has required fields."""
        required = ["summary", "content", "type"]
        return all(k in proposal for k in required)
```

### 3.3 Confirmation Flow

```
End of Conversation
        │
        ▼
┌───────────────────┐
│ Extract Proposals │
│ (LLM analysis)    │
└────────┬──────────┘
         │
         ▼
    ┌────────────┐
    │ Any found? │
    └─────┬──────┘
          │
    ┌─────┴─────┐
    No          Yes
    │           │
    ▼           ▼
 [Silent]  ┌───────────────────────────────────────┐
           │ "Should I remember anything from our  │
           │  conversation? I noticed:             │
           │  1. [Summary 1]                       │
           │  2. [Summary 2]                       │
           │  Say 'yes', 'no', or the numbers     │
           │  you'd like me to remember."         │
           └──────────────────┬────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ User Response     │
                    └────────┬──────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
        "yes"            "1, 2"              "no"
           │                 │                 │
           ▼                 ▼                 ▼
    [Create All]    [Create Selected]    [Create None]
           │                 │                 │
           └─────────────────┴─────────────────┘
                             │
                             ▼
                    [Conversation Ends]
```

---

## 4. Memory Retrieval

### 4.1 Retrieval Strategy

```python
@dataclass
class RetrievalResult:
    memories: List[Memory]
    total_found: int
    search_method: str  # "vector", "fts", "hybrid", "keyword"
    query_embedding: Optional[List[float]] = None


class MemoryRetriever:
    """Retrieve relevant memories for context injection or search."""
    
    def __init__(
        self,
        memory_repo: MemoryRepository,
        embedding_service: EmbeddingService,
        db: Database,
    ):
        self.memory_repo = memory_repo
        self.embedding = embedding_service
        self.db = db
        
        # Retrieval settings
        self.MAX_CONTEXT_MEMORIES = 5
        self.MAX_SEARCH_RESULTS = 20
        self.VECTOR_WEIGHT = 0.6
        self.FTS_WEIGHT = 0.4
        self.MIN_RELEVANCE = 0.5
    
    async def retrieve_for_context(
        self,
        query: str,
        intent: str,
        speaker_id: str,
        limit: int = 5,
    ) -> List[Memory]:
        """
        Retrieve memories for LLM context injection.
        
        Strategy:
        1. Generate query embedding
        2. Hybrid search (vector + FTS)
        3. Filter by speaker visibility
        4. Re-rank by relevance
        5. Return top N
        """
        # Skip for intents that don't benefit from memory
        if intent in ["timer_set", "timer_query", "time_query", "cancel"]:
            return []
        
        # Generate embedding
        query_embedding = await self.embedding.embed(query)
        
        # Hybrid search
        results = await self._hybrid_search(
            query_text=query,
            query_embedding=query_embedding,
            owner=speaker_id,
            limit=limit * 2,  # Get more for re-ranking
        )
        
        # Re-rank with LLM (optional, for high-quality retrieval)
        if len(results) > limit:
            results = await self._rerank(query, results, limit)
        
        # Update access tracking
        for memory in results:
            await self.memory_repo.record_access(memory.id)
        
        return results[:limit]
    
    async def search(
        self,
        query: str,
        owner: str,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> RetrievalResult:
        """
        Search memories for explicit user query.
        Returns more results than context retrieval.
        """
        query_embedding = await self.embedding.embed(query)
        
        memories = await self._hybrid_search(
            query_text=query,
            query_embedding=query_embedding,
            owner=owner,
            memory_type=memory_type,
            limit=limit,
        )
        
        # Count total matches (for pagination info)
        total = await self._count_matches(query, owner, memory_type)
        
        return RetrievalResult(
            memories=memories,
            total_found=total,
            search_method="hybrid",
            query_embedding=query_embedding,
        )
    
    async def _hybrid_search(
        self,
        query_text: str,
        query_embedding: List[float],
        owner: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Memory]:
        """
        Combine vector similarity and full-text search.
        
        Per Pinecone research: hybrid search improves recall 15-20% over vector-only.
        """
        # Vector search
        vector_results = await self._vector_search(
            query_embedding, owner, limit * 2
        )
        
        # FTS search
        fts_results = await self._fts_search(
            query_text, owner, limit * 2
        )
        
        # Merge and score
        scores: Dict[str, float] = {}
        memory_map: Dict[str, Memory] = {}
        
        for memory, similarity in vector_results:
            scores[memory.id] = similarity * self.VECTOR_WEIGHT
            memory_map[memory.id] = memory
        
        for memory, bm25_score in fts_results:
            # Normalize BM25 (typically negative, lower = better match)
            normalized = 1.0 - (bm25_score / -25) if bm25_score < 0 else 0
            scores[memory.id] = scores.get(memory.id, 0) + normalized * self.FTS_WEIGHT
            memory_map[memory.id] = memory
        
        # Sort by combined score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Filter by minimum relevance
        results = [
            memory_map[mid] for mid, score in ranked 
            if score >= self.MIN_RELEVANCE and mid in memory_map
        ]
        
        # Filter by type if specified
        if memory_type:
            results = [m for m in results if m.memory_type == memory_type]
        
        return results[:limit]
    
    async def _vector_search(
        self,
        embedding: List[float],
        owner: str,
        limit: int,
    ) -> List[Tuple[Memory, float]]:
        """Search by embedding similarity."""
        results = await self.db.fetchall(
            """
            SELECT m.*, (1 - vss.distance) as similarity
            FROM memory_embeddings AS vss
            JOIN memory_embedding_map AS map ON map.embedding_rowid = vss.rowid
            JOIN memories AS m ON m.id = map.memory_id
            WHERE vss_search(vss.embedding, ?)
            AND m.status = 'active'
            AND (m.owner = ? OR m.visibility = 'family' OR m.visibility = 'all')
            ORDER BY similarity DESC
            LIMIT ?
            """,
            [json.dumps(embedding), owner, limit]
        )
        
        return [(self._row_to_memory(r), r["similarity"]) for r in results]
    
    async def _fts_search(
        self,
        query: str,
        owner: str,
        limit: int,
    ) -> List[Tuple[Memory, float]]:
        """Search by full-text match."""
        # Escape FTS special characters
        escaped = self._escape_fts_query(query)
        
        results = await self.db.fetchall(
            """
            SELECT m.*, bm25(memories_fts) as score
            FROM memories_fts AS fts
            JOIN memories AS m ON m.rowid = fts.rowid
            WHERE memories_fts MATCH ?
            AND m.status = 'active'
            AND (m.owner = ? OR m.visibility = 'family' OR m.visibility = 'all')
            ORDER BY score
            LIMIT ?
            """,
            [escaped, owner, limit]
        )
        
        return [(self._row_to_memory(r), r["score"]) for r in results]
    
    async def _rerank(
        self,
        query: str,
        memories: List[Memory],
        limit: int,
    ) -> List[Memory]:
        """Re-rank results using LLM for better relevance."""
        if len(memories) <= limit:
            return memories
        
        # Format for LLM
        memory_list = "\n".join([
            f"{i+1}. {m.summary}" for i, m in enumerate(memories)
        ])
        
        prompt = f"""Given this query: "{query}"

Rank these memories by relevance (most relevant first).
Return only the numbers in order, comma-separated.

Memories:
{memory_list}

Ranking:"""

        response = await self.llm.complete(prompt, max_tokens=50)
        
        # Parse ranking
        try:
            indices = [int(x.strip()) - 1 for x in response.split(",")]
            reranked = [memories[i] for i in indices if 0 <= i < len(memories)]
            return reranked[:limit]
        except:
            return memories[:limit]
    
    def _escape_fts_query(self, query: str) -> str:
        """Escape FTS5 special characters."""
        # FTS5 special: AND OR NOT ( ) " *
        special = ['AND', 'OR', 'NOT', '(', ')', '"', '*']
        escaped = query
        for char in ['(', ')', '"', '*']:
            escaped = escaped.replace(char, f'"{char}"')
        return escaped
```

### 4.2 Progressive Narrowing

```python
class ProgressiveMemorySearch:
    """
    Multi-turn memory search with conversational refinement.
    
    "What was that recipe from last week?"
    → Returns top 3, asks if more needed
    → "Not those, tell me more"
    → Returns next 3
    → "It was the second one"
    → Returns full content
    """
    
    def __init__(self, retriever: MemoryRetriever):
        self.retriever = retriever
        self.active_searches: Dict[str, SearchSession] = {}
        self.BATCH_SIZE = 3
    
    async def start_search(
        self,
        session_id: str,
        query: str,
        owner: str,
    ) -> SearchResponse:
        """Start a new search session."""
        # Get all results
        result = await self.retriever.search(
            query=query,
            owner=owner,
            limit=20,
        )
        
        # Create session
        session = SearchSession(
            query=query,
            owner=owner,
            all_results=result.memories,
            current_index=0,
            total_found=result.total_found,
        )
        self.active_searches[session_id] = session
        
        # Return first batch
        return self._format_batch(session)
    
    async def continue_search(
        self,
        session_id: str,
        user_response: str,
    ) -> SearchResponse:
        """Handle user response to search results."""
        session = self.active_searches.get(session_id)
        if not session:
            return SearchResponse(
                error="No active search. Please start a new search."
            )
        
        # Check for selection
        selection = self._parse_selection(user_response, session)
        if selection is not None:
            # User selected a specific memory
            memory = session.all_results[selection]
            del self.active_searches[session_id]
            return SearchResponse(
                selected_memory=memory,
                message=f"Here's what I have: {memory.content}"
            )
        
        # Check for "more" request
        if self._is_more_request(user_response):
            session.current_index += self.BATCH_SIZE
            if session.current_index >= len(session.all_results):
                return SearchResponse(
                    message="That's all I found for that search.",
                    complete=True
                )
            return self._format_batch(session)
        
        # Check for "none of those" / cancel
        if self._is_cancel(user_response):
            del self.active_searches[session_id]
            return SearchResponse(
                message="Okay, let me know if you want to search for something else.",
                complete=True
            )
        
        # Unclear response
        return SearchResponse(
            message="Would you like to hear more options, or is it one of the ones I mentioned? You can say 'more' or tell me which number.",
            awaiting_clarification=True
        )
    
    def _format_batch(self, session: SearchSession) -> SearchResponse:
        """Format current batch of results."""
        start = session.current_index
        end = min(start + self.BATCH_SIZE, len(session.all_results))
        batch = session.all_results[start:end]
        
        if not batch:
            return SearchResponse(
                message="I couldn't find any memories matching that.",
                complete=True
            )
        
        lines = [f"I found {session.total_found} memories. Here are the top matches:"]
        for i, memory in enumerate(batch, start=1):
            date = memory.created_at.strftime("%B %d")
            lines.append(f"{i}. {date} - {memory.summary}")
        
        if end < len(session.all_results):
            lines.append("\nIs it one of these, or would you like to hear more?")
        else:
            lines.append("\nIs it one of these?")
        
        return SearchResponse(
            message="\n".join(lines),
            batch=batch,
            has_more=end < len(session.all_results),
        )
    
    def _parse_selection(self, response: str, session: SearchSession) -> Optional[int]:
        """Parse user's selection from response."""
        response_lower = response.lower().strip()
        
        # Number selection: "1", "the first one", "number 2"
        number_patterns = [
            r'^(\d+)$',
            r'(?:number|the)\s*(\d+)',
            r'(?:first|1st)',
            r'(?:second|2nd)',
            r'(?:third|3rd)',
        ]
        
        for pattern in number_patterns[:2]:
            match = re.search(pattern, response_lower)
            if match:
                num = int(match.group(1))
                idx = session.current_index + num - 1
                if 0 <= idx < len(session.all_results):
                    return idx
        
        # Ordinal words
        ordinals = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2}
        for word, offset in ordinals.items():
            if word in response_lower:
                idx = session.current_index + offset
                if 0 <= idx < len(session.all_results):
                    return idx
        
        return None
    
    def _is_more_request(self, response: str) -> bool:
        """Check if user wants more results."""
        more_patterns = [
            r'\bmore\b', r'\bnext\b', r'\bother', r'\belse\b',
            r'not\s+(?:those|these|them)', r'none\s+of\s+(?:those|these)',
            r'keep\s+going', r'continue'
        ]
        return any(re.search(p, response.lower()) for p in more_patterns)
    
    def _is_cancel(self, response: str) -> bool:
        """Check if user wants to cancel search."""
        cancel_patterns = [
            r'\bcancel\b', r'\bstop\b', r'\bnevermind\b', r'\bnever\s*mind\b',
            r'\bforget\s*it\b', r'\bthat\'?s\s*(?:ok|fine|all)\b'
        ]
        return any(re.search(p, response.lower()) for p in cancel_patterns)


@dataclass
class SearchSession:
    query: str
    owner: str
    all_results: List[Memory]
    current_index: int
    total_found: int


@dataclass
class SearchResponse:
    message: str = ""
    batch: List[Memory] = field(default_factory=list)
    selected_memory: Optional[Memory] = None
    has_more: bool = False
    complete: bool = False
    awaiting_clarification: bool = False
    error: Optional[str] = None
```

---

## 5. Memory Deletion

### 5.1 Soft Delete

```python
class MemoryDeleter:
    """Handle memory deletion requests."""
    
    DELETE_PATTERNS = [
        r"forget\s+(?:that|about\s+)?(.+)",
        r"delete\s+(?:the\s+)?memory\s+(?:about\s+)?(.+)",
        r"remove\s+(?:the\s+)?memory\s+(?:about\s+)?(.+)",
        r"don'?t\s+remember\s+(.+)",
    ]
    
    def __init__(self, memory_repo: MemoryRepository, retriever: MemoryRetriever):
        self.memory_repo = memory_repo
        self.retriever = retriever
    
    async def delete_by_reference(
        self,
        utterance: str,
        speaker_id: str,
        recent_memory_id: Optional[str] = None,
    ) -> DeleteResult:
        """
        Delete memory referenced in utterance.
        
        Handles:
        - "Forget that" (most recent memory mentioned)
        - "Forget what I just told you" (last created memory)
        - "Forget about the blue tile" (search and confirm)
        """
        # Check for "that" / "what I just said" references
        if self._is_immediate_reference(utterance):
            if recent_memory_id:
                return await self._soft_delete(recent_memory_id, speaker_id)
            else:
                return DeleteResult(
                    success=False,
                    message="I'm not sure which memory you mean. Can you be more specific?"
                )
        
        # Extract search query
        query = self._extract_query(utterance)
        if not query:
            return DeleteResult(
                success=False,
                message="I'm not sure what you want me to forget."
            )
        
        # Search for matching memories
        results = await self.retriever.search(
            query=query,
            owner=speaker_id,
            limit=5,
        )
        
        if not results.memories:
            return DeleteResult(
                success=False,
                message=f"I don't have any memories about '{query}'."
            )
        
        if len(results.memories) == 1:
            # Single match - confirm and delete
            memory = results.memories[0]
            return DeleteResult(
                success=True,
                awaiting_confirmation=True,
                memory=memory,
                message=f"Do you want me to forget: '{memory.summary}'?"
            )
        
        # Multiple matches - need clarification
        return DeleteResult(
            success=False,
            candidates=results.memories,
            message=self._format_candidates(results.memories)
        )
    
    async def confirm_delete(
        self,
        memory_id: str,
        speaker_id: str,
    ) -> DeleteResult:
        """Confirm and execute soft delete."""
        return await self._soft_delete(memory_id, speaker_id)
    
    async def _soft_delete(
        self,
        memory_id: str,
        speaker_id: str,
    ) -> DeleteResult:
        """Execute soft delete."""
        success = await self.memory_repo.soft_delete(memory_id, speaker_id)
        
        if success:
            return DeleteResult(
                success=True,
                message="Done, I've forgotten that."
            )
        
        return DeleteResult(
            success=False,
            message="I couldn't delete that memory."
        )
    
    def _is_immediate_reference(self, utterance: str) -> bool:
        """Check for references to most recent memory."""
        patterns = [
            r'\bthat\b',
            r'what\s+i\s+just\s+(?:said|told)',
            r'the\s+last\s+(?:one|thing|memory)',
        ]
        return any(re.search(p, utterance.lower()) for p in patterns)
    
    def _extract_query(self, utterance: str) -> Optional[str]:
        """Extract search query from delete request."""
        for pattern in self.DELETE_PATTERNS:
            match = re.search(pattern, utterance, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _format_candidates(self, memories: List[Memory]) -> str:
        """Format multiple candidates for clarification."""
        lines = ["I found a few memories that might match. Which one?"]
        for i, m in enumerate(memories, 1):
            lines.append(f"{i}. {m.summary}")
        return "\n".join(lines)


@dataclass
class DeleteResult:
    success: bool
    message: str = ""
    awaiting_confirmation: bool = False
    memory: Optional[Memory] = None
    candidates: List[Memory] = field(default_factory=list)
```

### 5.2 Super User Recovery

```python
class SuperUserMemoryAccess:
    """Admin-only memory operations."""
    
    def __init__(self, memory_repo: MemoryRepository, db: Database):
        self.memory_repo = memory_repo
        self.db = db
    
    async def search_deleted(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Memory]:
        """Search soft-deleted memories."""
        results = await self.db.fetchall(
            """
            SELECT * FROM memories
            WHERE status = 'deleted'
            AND (summary LIKE ? OR content LIKE ?)
            ORDER BY deleted_at DESC
            LIMIT ?
            """,
            [f"%{query}%", f"%{query}%", limit]
        )
        return [self._row_to_memory(r) for r in results]
    
    async def restore_memory(self, memory_id: str) -> bool:
        """Restore soft-deleted memory to active."""
        result = await self.db.execute(
            """
            UPDATE memories
            SET status = 'active', deleted_at = NULL, deleted_by = NULL
            WHERE id = ? AND status = 'deleted'
            """,
            [memory_id]
        )
        return result.rowcount > 0
    
    async def hard_delete(self, memory_id: str) -> bool:
        """Permanently delete memory. No recovery."""
        # Delete embedding first
        await self.db.execute(
            "DELETE FROM memory_embedding_map WHERE memory_id = ?",
            [memory_id]
        )
        
        # Delete memory
        result = await self.db.execute(
            "DELETE FROM memories WHERE id = ?",
            [memory_id]
        )
        return result.rowcount > 0
    
    async def search_all_tiers(
        self,
        query: str,
        limit: int = 50,
    ) -> Dict[str, List]:
        """Search across all tiers (active, deleted, logs)."""
        # Active memories
        active = await self.db.fetchall(
            """
            SELECT * FROM memories
            WHERE status = 'active'
            AND (summary LIKE ? OR content LIKE ?)
            LIMIT ?
            """,
            [f"%{query}%", f"%{query}%", limit]
        )
        
        # Deleted memories
        deleted = await self.db.fetchall(
            """
            SELECT * FROM memories
            WHERE status = 'deleted'
            AND (summary LIKE ? OR content LIKE ?)
            LIMIT ?
            """,
            [f"%{query}%", f"%{query}%", limit]
        )
        
        # Operational logs
        logs = await self.db.fetchall(
            """
            SELECT * FROM operational_logs
            WHERE content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [f"%{query}%", limit]
        )
        
        return {
            "active": [self._row_to_memory(r) for r in active],
            "deleted": [self._row_to_memory(r) for r in deleted],
            "logs": logs,
        }
```

---

## 6. Context Injection

### 6.1 Memory Context for LLM

```python
class MemoryContextBuilder:
    """Build memory context for LLM prompts."""
    
    MAX_TOKENS = 300  # Token budget for memory context
    
    def __init__(self, retriever: MemoryRetriever):
        self.retriever = retriever
    
    async def build_context(
        self,
        query: str,
        intent: str,
        speaker_id: str,
    ) -> str:
        """
        Build memory context string for LLM injection.
        
        Returns formatted string, empty if no relevant memories.
        """
        # Get relevant memories
        memories = await self.retriever.retrieve_for_context(
            query=query,
            intent=intent,
            speaker_id=speaker_id,
            limit=5,
        )
        
        if not memories:
            return ""
        
        # Format naturally (not "According to my memory...")
        lines = ["Relevant background:"]
        for memory in memories:
            lines.append(f"- {memory.summary}")
        
        return "\n".join(lines)
    
    def format_for_response(
        self,
        memories: List[Memory],
        query: str,
    ) -> str:
        """
        Format memories for voice response.
        
        Used when user explicitly asks about memories.
        """
        if not memories:
            return f"I don't have any memories about that."
        
        if len(memories) == 1:
            return memories[0].content
        
        # Multiple memories - summarize
        lines = [f"I remember {len(memories)} things about that:"]
        for i, m in enumerate(memories[:3], 1):
            lines.append(f"{i}. {m.summary}")
        
        if len(memories) > 3:
            lines.append(f"...and {len(memories) - 3} more.")
        
        return " ".join(lines)
```

---

## 7. Embedding Management

### 7.1 Embedding Service

```python
class EmbeddingService:
    """Generate and manage embeddings."""
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        use_gpu: bool = True,
    ):
        from sentence_transformers import SentenceTransformer
        
        device = "cuda" if use_gpu else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = self.model.get_sentence_embedding_dimension()
    
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        # Run in executor to not block async loop
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.model.encode(text, convert_to_numpy=True)
        )
        return embedding.tolist()
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.encode(texts, convert_to_numpy=True)
        )
        return embeddings.tolist()


class MemoryEmbeddingManager:
    """Manage memory embeddings in sqlite-vss."""
    
    def __init__(
        self,
        db: Database,
        embedding_service: EmbeddingService,
    ):
        self.db = db
        self.embedding = embedding_service
    
    async def generate_and_store(self, memory: Memory) -> None:
        """Generate and store embedding for memory."""
        # Combine summary and content for richer embedding
        text = f"{memory.summary}. {memory.content}"
        
        embedding = await self.embedding.embed(text)
        
        # Insert into vss table
        cursor = await self.db.execute(
            "INSERT INTO memory_embeddings(embedding) VALUES (?)",
            [json.dumps(embedding)]
        )
        embedding_rowid = cursor.lastrowid
        
        # Map to memory
        await self.db.execute(
            """
            INSERT OR REPLACE INTO memory_embedding_map(memory_id, embedding_rowid, model)
            VALUES (?, ?, ?)
            """,
            [memory.id, embedding_rowid, "all-MiniLM-L6-v2"]
        )
    
    async def backfill_embeddings(self) -> int:
        """Generate embeddings for memories that don't have them."""
        # Find memories without embeddings
        memories = await self.db.fetchall(
            """
            SELECT m.* FROM memories m
            LEFT JOIN memory_embedding_map map ON m.id = map.memory_id
            WHERE map.memory_id IS NULL AND m.status = 'active'
            """
        )
        
        for row in memories:
            memory = self._row_to_memory(row)
            await self.generate_and_store(memory)
        
        return len(memories)
    
    async def update_embedding(self, memory_id: str, new_content: str) -> None:
        """Update embedding when memory content changes."""
        memory = await self.db.fetchone(
            "SELECT * FROM memories WHERE id = ?",
            [memory_id]
        )
        
        if memory:
            # Delete old embedding
            map_row = await self.db.fetchone(
                "SELECT embedding_rowid FROM memory_embedding_map WHERE memory_id = ?",
                [memory_id]
            )
            if map_row:
                await self.db.execute(
                    "DELETE FROM memory_embeddings WHERE rowid = ?",
                    [map_row["embedding_rowid"]]
                )
                await self.db.execute(
                    "DELETE FROM memory_embedding_map WHERE memory_id = ?",
                    [memory_id]
                )
            
            # Generate new embedding
            await self.generate_and_store(self._row_to_memory(memory))
```

---

## 8. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── memory/
│           ├── __init__.py
│           ├── config.py               # Settings, thresholds
│           ├── models.py               # Memory dataclass, results
│           ├── repository.py           # MemoryRepository (CRUD)
│           ├── creation/
│           │   ├── __init__.py
│           │   ├── explicit.py         # ExplicitMemoryCreator
│           │   └── extraction.py       # ConversationMemoryExtractor
│           ├── retrieval/
│           │   ├── __init__.py
│           │   ├── retriever.py        # MemoryRetriever
│           │   ├── progressive.py      # ProgressiveMemorySearch
│           │   └── context.py          # MemoryContextBuilder
│           ├── deletion/
│           │   ├── __init__.py
│           │   ├── deleter.py          # MemoryDeleter
│           │   └── super_user.py       # SuperUserMemoryAccess
│           └── embedding/
│               ├── __init__.py
│               ├── service.py          # EmbeddingService
│               └── manager.py          # MemoryEmbeddingManager
└── tests/
    └── memory/
        ├── test_creation.py
        ├── test_retrieval.py
        ├── test_deletion.py
        └── test_embedding.py
```

---

## 9. Implementation Checklist

### Memory Creation

- [ ] Explicit memory creation from "remember that..."
- [ ] Memory type classification
- [ ] Keyword extraction
- [ ] Summary generation
- [ ] Conversation memory extraction
- [ ] User confirmation flow

### Memory Retrieval

- [ ] Hybrid search (vector + FTS)
- [ ] Relevance scoring
- [ ] Context injection builder
- [ ] Progressive narrowing search
- [ ] Search session management

### Memory Deletion

- [ ] Soft delete implementation
- [ ] Delete by reference ("forget that")
- [ ] Delete by search
- [ ] Confirmation flow
- [ ] Super user restore
- [ ] Hard delete (admin only)

### Embedding Management

- [ ] EmbeddingService with MiniLM
- [ ] Embedding storage in sqlite-vss
- [ ] Backfill for existing memories
- [ ] Update on content change

### Validation

- [ ] Retrieval latency <100ms
- [ ] Search accuracy (relevant in top 3)
- [ ] Progressive narrowing UX
- [ ] Soft delete recoverable
- [ ] Embeddings generated for all memories

### Acceptance Criteria

1. **"Remember that..." creates searchable memory** with embedding
2. **"What did I say about X" returns relevant memories** in ranked order
3. **Progressive narrowing** works conversationally (batches of 3)
4. **"Forget that" soft deletes** and is recoverable by super user
5. **Context injection adds relevant memories** to LLM prompts without over-injection

---

## 10. Handoff Notes for Implementation Agent

### Critical Points

1. **Embeddings are essential.** Without embeddings, search is just keyword matching. Hybrid search is the right approach.

2. **Confirmation before extraction.** Don't silently create memories from conversations. Ask first.

3. **Soft delete is the default.** Hard delete is super user only. Users change their minds.

4. **Progressive narrowing is a UX feature.** Don't dump 20 results. Show 3, ask if more needed.

5. **Context injection must be relevant.** Irrelevant memories (chickens in every response) was V1's failure.

### Common Pitfalls

- Forgetting to generate embedding when creating memory
- Not escaping FTS5 special characters in search queries
- Injecting too many memories (token budget overflow)
- Not handling empty search results gracefully
- Blocking async loop with synchronous embedding generation

### Performance Tuning

- Batch embedding generation for backfill
- Cache frequent query embeddings
- Pre-compute keyword index for fast filtering
- Use covering indexes for common query patterns

---

**End of Area 05: Memory System**

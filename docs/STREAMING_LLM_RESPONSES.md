# Streaming LLM Responses - Explanation

## What is Streaming?

Streaming LLM responses means receiving the response **incrementally** as the model generates it, rather than waiting for the complete response. This is similar to how ChatGPT shows text appearing word-by-word.

## Current Implementation

Currently, BarnabeeNet uses **non-streaming** LLM calls:
1. Send full request to OpenRouter
2. Wait for complete response
3. Return entire response at once
4. Then synthesize TTS

## How Streaming Would Work

With streaming enabled:

1. **Send request with `stream=True`** to OpenRouter
2. **Receive chunks** as they're generated (via Server-Sent Events or streaming JSON)
3. **Begin TTS synthesis** on first chunk (speculative execution)
4. **Update dashboard** in real-time as text appears
5. **Complete response** when model finishes

## Benefits

### 1. Reduced Perceived Latency
- **Current**: User waits 1-3 seconds for complete response
- **Streaming**: User sees response starting in 200-500ms
- **Impact**: Feels 500-1500ms faster even though total time is similar

### 2. Progressive TTS
- Can start speaking while still generating text
- User hears response sooner
- Better for long responses

### 3. Real-time Dashboard Updates
- Dashboard shows response as it's generated
- Better UX for debugging
- Users can see what model is "thinking"

## Implementation Approach

### Option 1: WebSocket Streaming (Recommended)
```python
# Client connects via WebSocket
# Server streams chunks as they arrive
async def stream_llm_response(websocket, messages):
    async for chunk in llm_client.chat_stream(messages):
        await websocket.send_json({
            "type": "chunk",
            "text": chunk.text,
            "done": chunk.finished
        })
```

### Option 2: Server-Sent Events (SSE)
```python
# Client uses EventSource
# Server sends SSE events
async def stream_llm_response(request):
    async def generate():
        async for chunk in llm_client.chat_stream(messages):
            yield f"data: {json.dumps(chunk)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Option 3: HTTP Streaming
```python
# Client uses streaming HTTP response
# Server sends chunks via HTTP chunked transfer
async def stream_llm_response(request):
    async def generate():
        async for chunk in llm_client.chat_stream(messages):
            yield chunk.text.encode()
    return StreamingResponse(generate(), media_type="text/plain")
```

## OpenRouter Streaming Support

OpenRouter supports streaming via the `stream` parameter:

```python
payload = {
    "model": "anthropic/claude-3.5-sonnet",
    "messages": messages,
    "stream": True  # Enable streaming
}

response = await client.post("/chat/completions", json=payload, stream=True)

async for line in response.aiter_lines():
    if line.startswith("data: "):
        data = json.loads(line[6:])
        if data.get("choices"):
            delta = data["choices"][0].get("delta", {})
            if "content" in delta:
                yield delta["content"]  # Stream this chunk
```

## Integration Points

1. **OpenRouterClient**: Add `chat_stream()` method
2. **InteractionAgent**: Support streaming mode
3. **Voice Pipeline**: Begin TTS on first chunk
4. **Dashboard**: Show streaming responses in real-time
5. **WebSocket**: Stream chunks to connected clients

## Trade-offs

### Pros
- Much better perceived latency
- Better UX (feels more responsive)
- Enables progressive TTS
- Real-time feedback

### Cons
- More complex implementation
- Requires WebSocket/SSE infrastructure
- TTS needs to handle partial text
- Error handling more complex

## When to Use

- **Use streaming for**: Interaction Agent (conversations), long responses
- **Don't use streaming for**: Meta Agent (fast routing), Action Agent (quick commands)

## Current Status

**Not implemented yet** - This is a future enhancement. The infrastructure exists (WebSocket support, SSE support for self-improvement), but LLM streaming is not yet integrated.

## Next Steps

1. Add `chat_stream()` to OpenRouterClient
2. Add streaming support to InteractionAgent
3. Integrate with WebSocket endpoint
4. Update dashboard to show streaming responses
5. Implement progressive TTS (optional)

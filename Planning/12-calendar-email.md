# Area 12: Calendar & Email Integration

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer), Area 06 (Response Generation)  
**Phase:** Extended Functionality  

---

## 1. Overview

### 1.1 Purpose

This specification defines the integration with Gmail for email access and Google Calendar for scheduling. These integrations enable Barnabee to answer questions like "What's on my calendar today?", "Did I get a response from the contractor?", and "Schedule a meeting with Elizabeth for Saturday."

### 1.2 Scope

| Capability | In Scope | Out of Scope (V2) |
|------------|----------|-------------------|
| Read calendar events | ✓ | |
| Create calendar events | ✓ | |
| Read email subjects/senders | ✓ | |
| Read email bodies | ✓ | |
| Send email | | ✓ (security risk for voice) |
| Multiple accounts | | ✓ (Thom + Elizabeth only) |
| Shared calendars | ✓ | |

### 1.3 Design Principles

1. **Read-heavy, write-cautious:** Reading is low-risk; creating events requires confirmation
2. **Privacy-first caching:** Cache metadata (subjects, senders) longer than bodies
3. **Offline-capable:** Basic queries work with cached data during API outages
4. **Minimal permissions:** Request only scopes actually needed

---

## 2. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Auth | Google OAuth 2.0 + refresh tokens | Standard, well-documented |
| Calendar API | Google Calendar API v3 | Direct, full-featured |
| Email API | Gmail API v1 | Better than IMAP for OAuth |
| Token Storage | SQLite (encrypted) | Single data store, encrypted at rest |
| Sync | Background ARQ worker | Non-blocking, scheduled |

### 2.1 Required OAuth Scopes

```python
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",      # Read events
    "https://www.googleapis.com/auth/calendar.events",        # Create/modify events
    "https://www.googleapis.com/auth/gmail.readonly",         # Read emails
    "https://www.googleapis.com/auth/gmail.labels",           # Check labels (inbox, etc.)
]

# NOT requesting:
# - gmail.send (security risk for voice commands)
# - gmail.modify (no need to mark read/delete)
# - calendar.settings (no need)
```

---

## 3. Architecture

### 3.1 Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CALENDAR & EMAIL INTEGRATION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         GOOGLE OAUTH FLOW                               │ │
│  │                                                                         │ │
│  │  Dashboard ──▶ /auth/google/start ──▶ Google Consent ──▶ /auth/callback│ │
│  │                                                                         │ │
│  │  Tokens stored encrypted in SQLite:                                    │ │
│  │  - access_token (1 hour TTL)                                           │ │
│  │  - refresh_token (long-lived, encrypted)                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         SYNC WORKERS (ARQ)                              │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐              ┌─────────────────┐                  │ │
│  │  │  Calendar Sync  │              │   Email Sync    │                  │ │
│  │  │                 │              │                 │                  │ │
│  │  │  Every 5 min:   │              │  Every 2 min:   │                  │ │
│  │  │  - Next 14 days │              │  - Last 100     │                  │ │
│  │  │  - Past 7 days  │              │  - Inbox only   │                  │ │
│  │  │                 │              │  - Headers first│                  │ │
│  │  └────────┬────────┘              └────────┬────────┘                  │ │
│  │           │                                │                           │ │
│  │           └────────────┬───────────────────┘                           │ │
│  │                        ▼                                               │ │
│  │              ┌─────────────────┐                                       │ │
│  │              │   SQLite Cache  │                                       │ │
│  │              │                 │                                       │ │
│  │              │  calendar_events│                                       │ │
│  │              │  email_headers  │                                       │ │
│  │              │  email_bodies   │                                       │ │
│  │              └────────┬────────┘                                       │ │
│  │                       │                                                │ │
│  └───────────────────────┼────────────────────────────────────────────────┘ │
│                          │                                                  │
│                          ▼                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      QUERY LAYER                                        │ │
│  │                                                                         │ │
│  │  "What's on my calendar today?"                                        │ │
│  │       │                                                                 │ │
│  │       ▼                                                                 │ │
│  │  CalendarRepository.get_events_for_day(date)                           │ │
│  │       │                                                                 │ │
│  │       ▼                                                                 │ │
│  │  Return from cache (< 5 min old) OR fetch + cache                      │ │
│  │                                                                         │ │
│  │  "Did John reply about the quote?"                                     │ │
│  │       │                                                                 │ │
│  │       ▼                                                                 │ │
│  │  EmailRepository.search(sender="john", subject_contains="quote")       │ │
│  │       │                                                                 │ │
│  │       ▼                                                                 │ │
│  │  Search cached headers, lazy-load bodies if needed                     │ │
│  │                                                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Database Schema (Addition to Area 01)

```sql
-- =============================================================================
-- GOOGLE AUTH TOKENS
-- =============================================================================

CREATE TABLE google_tokens (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    user_id TEXT NOT NULL UNIQUE,              -- 'thom', 'elizabeth'
    email TEXT NOT NULL,                        -- Google account email
    access_token_encrypted BLOB NOT NULL,       -- AES-256-GCM encrypted
    refresh_token_encrypted BLOB NOT NULL,      -- AES-256-GCM encrypted
    token_expiry TEXT NOT NULL,                 -- ISO datetime
    scopes TEXT NOT NULL,                       -- JSON array of granted scopes
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =============================================================================
-- CALENDAR EVENTS CACHE
-- =============================================================================

CREATE TABLE calendar_events (
    id TEXT PRIMARY KEY,                        -- Google event ID
    user_id TEXT NOT NULL,
    calendar_id TEXT NOT NULL,                  -- 'primary' or calendar email
    
    -- Event details
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    start_time TEXT NOT NULL,                   -- ISO datetime
    end_time TEXT NOT NULL,
    all_day INTEGER NOT NULL DEFAULT 0,
    
    -- Attendees (JSON array)
    attendees TEXT DEFAULT '[]',
    
    -- Recurrence
    recurring INTEGER NOT NULL DEFAULT 0,
    recurrence_rule TEXT,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'confirmed',   -- confirmed, tentative, cancelled
    
    -- Sync metadata
    etag TEXT,                                  -- For conditional fetches
    synced_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(id, user_id)
);

CREATE INDEX idx_calendar_events_user_time ON calendar_events(user_id, start_time);
CREATE INDEX idx_calendar_events_synced ON calendar_events(synced_at);

-- Full-text search for calendar
CREATE VIRTUAL TABLE calendar_events_fts USING fts5(
    title,
    description,
    location,
    content='calendar_events',
    content_rowid='rowid'
);

-- =============================================================================
-- EMAIL HEADERS CACHE
-- =============================================================================

CREATE TABLE email_headers (
    id TEXT PRIMARY KEY,                        -- Gmail message ID
    user_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    
    -- Header fields
    subject TEXT,
    from_address TEXT NOT NULL,
    from_name TEXT,
    to_addresses TEXT NOT NULL,                 -- JSON array
    cc_addresses TEXT DEFAULT '[]',
    date TEXT NOT NULL,                         -- ISO datetime
    
    -- Labels/folders
    labels TEXT NOT NULL DEFAULT '[]',          -- JSON array: ['INBOX', 'UNREAD', etc.]
    
    -- Flags
    is_unread INTEGER NOT NULL DEFAULT 1,
    has_attachments INTEGER NOT NULL DEFAULT 0,
    
    -- Snippet (first ~100 chars)
    snippet TEXT,
    
    -- Sync metadata
    synced_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    UNIQUE(id, user_id)
);

CREATE INDEX idx_email_headers_user_date ON email_headers(user_id, date DESC);
CREATE INDEX idx_email_headers_from ON email_headers(from_address);
CREATE INDEX idx_email_headers_unread ON email_headers(user_id, is_unread);

-- Full-text search for email
CREATE VIRTUAL TABLE email_headers_fts USING fts5(
    subject,
    from_name,
    snippet,
    content='email_headers',
    content_rowid='rowid'
);

-- =============================================================================
-- EMAIL BODIES (Lazy-loaded, shorter retention)
-- =============================================================================

CREATE TABLE email_bodies (
    message_id TEXT PRIMARY KEY REFERENCES email_headers(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    body_text TEXT,                             -- Plain text version
    body_html TEXT,                             -- HTML version (optional)
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Cleanup old bodies (keep headers longer)
-- DELETE FROM email_bodies WHERE fetched_at < datetime('now', '-7 days');
```

---

## 4. OAuth Setup Flow

### 4.1 Google Cloud Console Setup (One-Time)

1. Create project in Google Cloud Console
2. Enable Calendar API and Gmail API
3. Configure OAuth consent screen (Internal or External)
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URI: `https://barnabee.local/auth/google/callback`

### 4.2 Dashboard OAuth Flow

```python
# src/barnabee/auth/google.py
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [f"{settings.BASE_URL}/auth/google/callback"],
    }
}

@router.get("/auth/google/start")
async def start_google_auth(user_id: str = Depends(get_current_user)):
    """Initiate OAuth flow from dashboard."""
    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{settings.BASE_URL}/auth/google/callback"
    )
    
    auth_url, state = flow.authorization_url(
        access_type="offline",        # Get refresh token
        include_granted_scopes="true", # Incremental auth
        prompt="consent",              # Always show consent (ensures refresh token)
        state=user_id,                 # Pass user ID through state
    )
    
    return RedirectResponse(auth_url)


@router.get("/auth/google/callback")
async def google_auth_callback(code: str, state: str):
    """Handle OAuth callback, store tokens."""
    user_id = state
    
    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=GOOGLE_SCOPES,
        redirect_uri=f"{settings.BASE_URL}/auth/google/callback"
    )
    
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # Get user's email for display
    service = build("oauth2", "v2", credentials=credentials)
    user_info = service.userinfo().get().execute()
    
    # Encrypt and store tokens
    await store_google_tokens(
        user_id=user_id,
        email=user_info["email"],
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        expiry=credentials.expiry,
        scopes=credentials.scopes,
    )
    
    return RedirectResponse("/dashboard/settings?google=connected")
```

### 4.3 Token Refresh

```python
async def get_google_credentials(user_id: str) -> Credentials:
    """Get valid credentials, refreshing if needed."""
    tokens = await get_google_tokens(user_id)
    if not tokens:
        raise GoogleNotConnectedError(user_id)
    
    credentials = Credentials(
        token=decrypt(tokens.access_token_encrypted),
        refresh_token=decrypt(tokens.refresh_token_encrypted),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=json.loads(tokens.scopes),
    )
    
    if credentials.expired:
        credentials.refresh(Request())
        await update_google_tokens(
            user_id=user_id,
            access_token=credentials.token,
            expiry=credentials.expiry,
        )
    
    return credentials
```

---

## 5. Sync Workers

### 5.1 Calendar Sync

```python
# src/barnabee/workers/calendar_sync.py
from googleapiclient.discovery import build

async def sync_calendar(ctx, user_id: str):
    """Sync calendar events for a user."""
    credentials = await get_google_credentials(user_id)
    service = build("calendar", "v3", credentials=credentials)
    
    # Time range: 7 days past to 14 days future
    time_min = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
    time_max = (datetime.utcnow() + timedelta(days=14)).isoformat() + "Z"
    
    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=250,
        singleEvents=True,          # Expand recurring events
        orderBy="startTime",
    ).execute()
    
    events = events_result.get("items", [])
    
    for event in events:
        await upsert_calendar_event(user_id, event)
    
    logger.info("calendar_sync_complete", user_id=user_id, event_count=len(events))


# Schedule: every 5 minutes
class WorkerSettings:
    functions = [sync_calendar, sync_email_headers]
    cron_jobs = [
        cron(sync_calendar, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(sync_email_headers, minute={1, 3, 5, 7, 9, ...}),  # Every 2 min
    ]
```

### 5.2 Email Sync

```python
async def sync_email_headers(ctx, user_id: str):
    """Sync recent email headers for a user."""
    credentials = await get_google_credentials(user_id)
    service = build("gmail", "v1", credentials=credentials)
    
    # Fetch last 100 inbox messages
    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        maxResults=100,
    ).execute()
    
    messages = results.get("messages", [])
    
    for msg_ref in messages:
        # Check if we already have this message
        existing = await get_email_header(user_id, msg_ref["id"])
        if existing:
            continue
        
        # Fetch headers only (not body)
        msg = service.users().messages().get(
            userId="me",
            id=msg_ref["id"],
            format="metadata",
            metadataHeaders=["From", "To", "Cc", "Subject", "Date"],
        ).execute()
        
        await upsert_email_header(user_id, msg)
    
    logger.info("email_sync_complete", user_id=user_id, message_count=len(messages))


async def fetch_email_body(user_id: str, message_id: str) -> str:
    """Lazy-fetch email body when needed for queries."""
    # Check cache first
    cached = await get_email_body(user_id, message_id)
    if cached:
        return cached.body_text
    
    credentials = await get_google_credentials(user_id)
    service = build("gmail", "v1", credentials=credentials)
    
    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()
    
    body_text = extract_body_text(msg)
    await store_email_body(user_id, message_id, body_text)
    
    return body_text
```

---

## 6. Query Interfaces

### 6.1 Calendar Queries

```python
# src/barnabee/repositories/calendar.py

class CalendarRepository:
    async def get_events_for_day(
        self, 
        user_id: str, 
        date: date
    ) -> list[CalendarEvent]:
        """Get all events for a specific day."""
        start = datetime.combine(date, time.min).isoformat()
        end = datetime.combine(date, time.max).isoformat()
        
        return await self.db.fetch_all("""
            SELECT * FROM calendar_events
            WHERE user_id = ? AND start_time >= ? AND start_time < ?
            AND status != 'cancelled'
            ORDER BY start_time
        """, user_id, start, end)
    
    async def get_events_in_range(
        self,
        user_id: str,
        start: datetime,
        end: datetime
    ) -> list[CalendarEvent]:
        """Get events within a time range."""
        return await self.db.fetch_all("""
            SELECT * FROM calendar_events
            WHERE user_id = ? AND start_time >= ? AND end_time <= ?
            AND status != 'cancelled'
            ORDER BY start_time
        """, user_id, start.isoformat(), end.isoformat())
    
    async def search_events(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> list[CalendarEvent]:
        """Full-text search calendar events."""
        return await self.db.fetch_all("""
            SELECT e.* FROM calendar_events e
            JOIN calendar_events_fts fts ON e.rowid = fts.rowid
            WHERE fts MATCH ? AND e.user_id = ?
            ORDER BY e.start_time DESC
            LIMIT ?
        """, query, user_id, limit)
    
    async def get_next_event(self, user_id: str) -> Optional[CalendarEvent]:
        """Get the next upcoming event."""
        now = datetime.utcnow().isoformat()
        return await self.db.fetch_one("""
            SELECT * FROM calendar_events
            WHERE user_id = ? AND start_time > ? AND status != 'cancelled'
            ORDER BY start_time
            LIMIT 1
        """, user_id, now)
```

### 6.2 Email Queries

```python
class EmailRepository:
    async def get_recent_emails(
        self,
        user_id: str,
        limit: int = 20,
        unread_only: bool = False
    ) -> list[EmailHeader]:
        """Get recent emails."""
        query = """
            SELECT * FROM email_headers
            WHERE user_id = ?
        """
        if unread_only:
            query += " AND is_unread = 1"
        query += " ORDER BY date DESC LIMIT ?"
        
        return await self.db.fetch_all(query, user_id, limit)
    
    async def search_emails(
        self,
        user_id: str,
        sender: Optional[str] = None,
        subject_contains: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 10
    ) -> list[EmailHeader]:
        """Search emails with multiple filters."""
        conditions = ["user_id = ?"]
        params = [user_id]
        
        if sender:
            conditions.append("(from_address LIKE ? OR from_name LIKE ?)")
            params.extend([f"%{sender}%", f"%{sender}%"])
        
        if subject_contains:
            conditions.append("subject LIKE ?")
            params.append(f"%{subject_contains}%")
        
        if query:
            # Use FTS for general search
            return await self.db.fetch_all("""
                SELECT e.* FROM email_headers e
                JOIN email_headers_fts fts ON e.rowid = fts.rowid
                WHERE fts MATCH ? AND e.user_id = ?
                ORDER BY e.date DESC
                LIMIT ?
            """, query, user_id, limit)
        
        sql = f"""
            SELECT * FROM email_headers
            WHERE {' AND '.join(conditions)}
            ORDER BY date DESC
            LIMIT ?
        """
        params.append(limit)
        
        return await self.db.fetch_all(sql, *params)
    
    async def get_email_with_body(
        self,
        user_id: str,
        message_id: str
    ) -> EmailWithBody:
        """Get email with body (lazy-fetches if needed)."""
        header = await self.get_by_id(user_id, message_id)
        if not header:
            raise EmailNotFoundError(message_id)
        
        body = await fetch_email_body(user_id, message_id)
        
        return EmailWithBody(**header.dict(), body=body)
```

---

## 7. Event Creation (Voice Commands)

### 7.1 Calendar Event Creation

```python
async def create_calendar_event(
    user_id: str,
    title: str,
    start_time: datetime,
    end_time: datetime,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[list[str]] = None,
) -> CalendarEvent:
    """Create a new calendar event."""
    credentials = await get_google_credentials(user_id)
    service = build("calendar", "v3", credentials=credentials)
    
    event_body = {
        "summary": title,
        "start": {"dateTime": start_time.isoformat(), "timeZone": "America/New_York"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "America/New_York"},
    }
    
    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location
    if attendees:
        event_body["attendees"] = [{"email": a} for a in attendees]
    
    created = service.events().insert(
        calendarId="primary",
        body=event_body,
    ).execute()
    
    # Cache locally
    await upsert_calendar_event(user_id, created)
    
    return CalendarEvent.from_google(created)
```

### 7.2 Voice Command Confirmation Flow

```python
# Event creation requires confirmation to prevent mistakes

async def handle_calendar_create_intent(
    session: Session,
    parsed: ParsedCalendarIntent
) -> Response:
    """Handle calendar creation with confirmation."""
    
    # Parse natural language to event details
    event_details = await parse_event_from_utterance(parsed.utterance)
    
    # Store pending event in session
    session.pending_action = PendingAction(
        type="calendar_create",
        data=event_details,
        expires_at=datetime.utcnow() + timedelta(seconds=30),
    )
    
    # Ask for confirmation
    return Response(
        text=f"I'll add '{event_details.title}' on {format_date(event_details.start_time)} "
             f"at {format_time(event_details.start_time)}. Sound right?",
        expects_confirmation=True,
    )


async def handle_confirmation(session: Session, confirmed: bool) -> Response:
    """Handle yes/no confirmation."""
    if not session.pending_action:
        return Response(text="I'm not sure what you're confirming.")
    
    if session.pending_action.type == "calendar_create":
        if confirmed:
            event = await create_calendar_event(
                session.user_id,
                **session.pending_action.data
            )
            return Response(text=f"Done! I've added it to your calendar.")
        else:
            return Response(text="Okay, I won't add that.")
    
    session.pending_action = None
```

---

## 8. Context Injection for Response Generation

### 8.1 Calendar Context

```python
async def get_calendar_context(user_id: str) -> str:
    """Get calendar context for response generation."""
    repo = CalendarRepository()
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    today_events = await repo.get_events_for_day(user_id, today)
    tomorrow_events = await repo.get_events_for_day(user_id, tomorrow)
    next_event = await repo.get_next_event(user_id)
    
    context_parts = []
    
    if today_events:
        context_parts.append(f"Today's events: {format_events_brief(today_events)}")
    else:
        context_parts.append("No events scheduled for today.")
    
    if tomorrow_events:
        context_parts.append(f"Tomorrow: {format_events_brief(tomorrow_events)}")
    
    if next_event and next_event.start_time.date() > tomorrow:
        context_parts.append(f"Next event: {format_event_brief(next_event)}")
    
    return "\n".join(context_parts)
```

### 8.2 Email Context

```python
async def get_email_context(user_id: str) -> str:
    """Get email context for response generation."""
    repo = EmailRepository()
    
    unread = await repo.get_recent_emails(user_id, limit=5, unread_only=True)
    
    if not unread:
        return "No unread emails."
    
    context_parts = [f"You have {len(unread)} unread emails:"]
    for email in unread[:3]:  # Top 3 only
        context_parts.append(f"- From {email.from_name or email.from_address}: {email.subject}")
    
    if len(unread) > 3:
        context_parts.append(f"  ...and {len(unread) - 3} more")
    
    return "\n".join(context_parts)
```

---

## 9. Error Handling

### 9.1 Token Expiration

```python
class GoogleTokenExpiredError(Exception):
    """Raised when refresh token is revoked or expired."""
    pass

async def handle_google_api_error(user_id: str, error: Exception):
    """Handle Google API errors gracefully."""
    if "invalid_grant" in str(error):
        # Refresh token revoked - user needs to re-authenticate
        await mark_google_disconnected(user_id)
        raise GoogleTokenExpiredError(
            "Your Google connection has expired. "
            "Please reconnect in the dashboard."
        )
    
    if "quota" in str(error).lower():
        # Rate limited - back off
        logger.warning("google_quota_exceeded", user_id=user_id)
        raise GoogleQuotaExceededError("Try again in a few minutes.")
    
    # Unknown error - log and re-raise
    logger.error("google_api_error", user_id=user_id, error=str(error))
    raise
```

### 9.2 Offline Fallback

```python
async def get_calendar_events_with_fallback(
    user_id: str,
    date: date
) -> tuple[list[CalendarEvent], bool]:
    """Get events, falling back to cache if API unavailable."""
    try:
        # Try fresh fetch
        await sync_calendar_for_date(user_id, date)
        events = await CalendarRepository().get_events_for_day(user_id, date)
        return events, True  # is_fresh=True
    except Exception as e:
        logger.warning("calendar_fetch_failed", user_id=user_id, error=str(e))
        
        # Fall back to cached data
        events = await CalendarRepository().get_events_for_day(user_id, date)
        return events, False  # is_fresh=False
```

---

## 10. Implementation Checklist

### OAuth Setup
- [ ] Google Cloud project created
- [ ] OAuth consent screen configured
- [ ] OAuth credentials created
- [ ] Redirect URI configured

### Database
- [ ] Schema migration added for calendar/email tables
- [ ] FTS triggers created
- [ ] Token encryption key generated

### Auth Flow
- [ ] Dashboard OAuth initiation endpoint
- [ ] OAuth callback handler
- [ ] Token refresh logic
- [ ] Token encryption/decryption

### Sync Workers
- [ ] Calendar sync worker
- [ ] Email header sync worker
- [ ] Email body lazy-fetch
- [ ] Worker scheduling configured

### Repositories
- [ ] CalendarRepository with all queries
- [ ] EmailRepository with all queries
- [ ] Context injection functions

### Voice Integration
- [ ] Calendar query intents
- [ ] Email query intents
- [ ] Event creation with confirmation

---

## 11. Acceptance Criteria

1. **OAuth flow completes:** Dashboard → Google → callback → tokens stored
2. **Calendar sync:** Events appear within 5 minutes of creation in Google
3. **Email sync:** New emails indexed within 2 minutes
4. **Voice queries work:** "What's on my calendar today?" returns correct events
5. **Event creation works:** "Schedule a meeting" → confirmation → event created
6. **Offline resilience:** Cached data returned when Google API unavailable

---

**End of Area 12: Calendar & Email Integration**

# Area 21: Enhanced User Profile System

**Version:** 1.0
**Status:** Implementation Ready
**Dependencies:** Areas 01, 05, 06, 07, 09
**Phase:** Extended Functionality

## Overview

Enhanced user profile system capturing preferences, interests, communication styles, relationships, and behavioral patterns for personalized interactions.

## Data Model

Tables:
- user_profiles: Core profile (nickname, pronouns, birthday, communication_style, formality, etc.)
- user_interests: Extracted or explicit interests with confidence scores
- user_relationships: Family relationships with mutual consent requirement
- user_important_dates: Birthdays, anniversaries for reminders
- user_usage_patterns: Behavioral analysis (intents, active hours, devices)
- profile_extraction_queue: Pending extractions needing confirmation

## Collection Methods

1. Explicit (Onboarding): Nickname, pronouns, birthday, communication style
2. Conversation Extraction: Interests, relationships, preferences from speech
3. Behavioral Analysis: Nightly worker analyzes usage patterns

## Personalization

- Include nickname, pronouns in responses
- Adjust length based on communication_style
- Apply formality level
- Avoid topics_to_avoid
- Reference interests contextually
- Proactive suggestions based on dates and patterns

## Privacy

- Extraction settings (opt-out available)
- Relationship mutual consent required
- Data export and deletion available

## Dashboard

- Profile view/edit page
- Interest management
- Extraction queue confirmation
- Privacy settings

## API Endpoints

- GET/PUT /api/profile/me
- GET/POST/DELETE /api/profile/me/interests
- GET/POST /api/profile/me/extraction-queue
- GET/PUT /api/profile/me/privacy
- GET /api/profile/me/export

## Acceptance Criteria

1. Profiles persist
2. Extractions queue for confirmation
3. Personalization applies to responses
4. Privacy settings respected
5. Dashboard functional
6. Relationships require consent

End of Area 21
FAULT FALSE,
    UNIQUE(user_id, related_user_id)
);

CREATE TABLE user_important_dates (
    id INTEGER PRIMARY KEY,
    user_id TEXT REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    date_type TEXT NOT NULL,
    date_value DATE NOT NULL,
    recurring BOOLEAN DEFAULT TRUE,
    label TEXT,
    remind_days_before INTEGER DEFAULT 1
);

CREATE TABLE user_usage_patterns (
    user_id TEXT PRIMARY KEY,
    intent_usage JSON DEFAULT '{}',
    most_used_intents JSON DEFAULT '[]',
    hourly_activity JSON DEFAULT '{}',
    typical_active_hours JSON DEFAULT '[]',
    preferred_device_id TEXT,
    device_usage JSON DEFAULT '{}'
);

CREATE TABLE profile_extraction_queue (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    extraction_type TEXT NOT NULL,
    extracted_value TEXT NOT NULL,
    source_utterance TEXT,
    confidence REAL,
    status TEXT DEFAULT 'pending'
);
```

---

## 3. Profile Collection

### 3.1 Explicit (Onboarding)

| Field | Voice Prompt |
|-------|--------------|
| Nickname | "What would you like me to call you?" |
| Pronouns | "What pronouns should I use?" |
| Birthday | "When is your birthday?" |
| Style | "Do you prefer brief or detailed answers?" |

### 3.2 Conversation Extraction

Detect patterns like:
- "I love/like/enjoy [X]" → interest
- "My wife/husband [name]" → relationship
- "Don't mention [X]" → topic to avoid

Low-confidence extractions go to confirmation queue.

### 3.3 Behavioral Analysis

Nightly worker analyzes:
- Most used intents
- Typical active hours
- Preferred device
- Conversation patterns

---

## 4. Personalization

### 4.1 Response Personalization

Include in LLM prompt:
- Use nickname when addressing user
- Adjust response length based on communication_style
- Apply formality level
- Avoid topics in topics_to_avoid
- Reference interests when relevant

### 4.2 Proactive Suggestions

Based on:
- Upcoming important dates
- Time of day + interests
- Usage patterns

---

## 5. Privacy Controls

### 5.1 Settings

- allow_interest_extraction (default: true)
- allow_relationship_extraction (default: true)
- allow_behavior_analysis (default: true)
- share_calendar_with_family (default: false)

### 5.2 Relationship Consent

Both users must agree for relationship data sharing.

### 5.3 Data Rights

- Export: Download all profile data as JSON
- Delete: Remove all profile data

---

## 6. Dashboard

### 6.1 Profile Page

- View/edit basic information
- Manage interests
- Review extraction queue
- Set communication preferences
- Privacy settings

### 6.2 API Endpoints

```
GET    /api/profile/me
PUT    /api/profile/me
GET    /api/profile/me/interests
POST   /api/profile/me/interests
DELETE /api/profile/me/interests/{id}
GET    /api/profile/me/extraction-queue
POST   /api/profile/me/extraction-queue/{id}/confirm
POST   /api/profile/me/extraction-queue/{id}/reject
GET    /api/profile/me/privacy
PUT    /api/profile/me/privacy
GET    /api/profile/me/export
```

---

## 7. Checklist

- [ ] Create all profile tables
- [ ] Onboarding flow
- [ ] Conversation extraction
- [ ] Extraction queue
- [ ] Behavior analysis worker
- [ ] Response personalization
- [ ] Proactive suggestions
- [ ] Privacy settings
- [ ] Data export/delete
- [ ] Dashboard profile page

---

## 8. Acceptance Criteria

1. Profiles persist and are queryable
2. Extractions appear in queue for confirmation
3. Responses reflect communication style
4. Privacy settings are respected
5. Users can edit profiles via dashboard
6. Relationships require mutual consent
7. Data can be exported/deleted

---

## 9. Handoff Notes

### Critical Points

1. Privacy by default - extractions are opt-out
2. Don't over-extract - high confidence only
3. Personalization should be subtle
4. Interests decay over time (90 days)
5. Behavioral analysis runs nightly

### Integration Points

- Response generation: personalization prompt
- Memory system: profile informs relevance
- Meeting scribe: speaker links to profile
- Notifications: date reminders

---

**End of Area 21: Enhanced User Profile System**

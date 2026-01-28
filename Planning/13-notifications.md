# Area 13: Notifications & Delivery

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer), Area 04 (Home Assistant)  
**Phase:** Extended Functionality  

---

## 1. Overview

### 1.1 Purpose

This specification defines how Barnabee delivers notifications and long-form content to family members. The primary channel is Home Assistant notifications (mobile push), with SMS via Azure Communication Services as a secondary channel for critical alerts and content delivery.

### 1.2 Notification Channels

| Channel | Use Case | Latency | Cost |
|---------|----------|---------|------|
| Home Assistant Mobile | Standard notifications, alerts | <2s | Free |
| Azure Communication Services SMS | Critical alerts, long content delivery | <5s | ~$0.0075/msg |
| Voice (Barnabee speakers) | Immediate household alerts | <500ms | Free |

### 1.3 Design Principles

1. **HA-first:** Home Assistant notifications are free, fast, and already integrated
2. **SMS for overflow:** Long content that doesn't fit voice gets texted
3. **User preference respected:** Each family member controls their notification preferences
4. **Rate limiting:** Prevent notification spam (max 10/hour unless critical)
5. **Quiet hours:** Respect DND schedules (except critical alerts)

---

## 2. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Primary Notifications | Home Assistant notify service | Already integrated, free |
| SMS | Azure Communication Services | Enterprise-grade, good pricing |
| Notification Queue | ARQ (Redis) | Async delivery, retry logic |
| Preferences | SQLite | Part of core data layer |

### 2.1 Why Azure Communication Services for SMS

| Provider | Cost/SMS | API Quality | Already Used |
|----------|----------|-------------|--------------|
| Twilio | $0.0079 | Excellent | No |
| Azure Comm Services | $0.0075 | Good | Yes (Azure ecosystem) |
| AWS SNS | $0.00645 | Basic | No |

Azure is marginally cheaper and you're already in the Azure ecosystem for OpenAI. One fewer vendor relationship.

---

## 3. Architecture

### 3.1 Notification Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NOTIFICATION SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      NOTIFICATION TRIGGERS                              │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │   Timer     │  │  Calendar   │  │   Alert     │  │   Long      │   │ │
│  │  │  Complete   │  │  Reminder   │  │  (Security) │  │  Response   │   │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │ │
│  │         │                │                │                │          │ │
│  │         └────────────────┴────────┬───────┴────────────────┘          │ │
│  │                                   │                                    │ │
│  └───────────────────────────────────┼────────────────────────────────────┘ │
│                                      │                                      │
│                                      ▼                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      NOTIFICATION ROUTER                                │ │
│  │                                                                         │ │
│  │  1. Check user preferences (quiet hours, channels)                     │ │
│  │  2. Check rate limits (unless critical)                                │ │
│  │  3. Select channel based on content type:                              │ │
│  │     - Short alerts → HA Mobile Push                                    │ │
│  │     - Long content → SMS                                               │ │
│  │     - Immediate household → Voice broadcast                            │ │
│  │  4. Queue for delivery                                                 │ │
│  │                                                                         │ │
│  └───────────────────────────────────┬────────────────────────────────────┘ │
│                                      │                                      │
│              ┌───────────────────────┼───────────────────────┐              │
│              │                       │                       │              │
│              ▼                       ▼                       ▼              │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐   │
│  │   HA Mobile Push    │ │   Azure SMS         │ │   Voice Broadcast   │   │
│  │                     │ │                     │ │                     │   │
│  │  notify.mobile_app_ │ │  ACS REST API       │ │  TTS → Speakers     │   │
│  │  thom / elizabeth   │ │                     │ │  (via HA media)     │   │
│  └─────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Database Schema (Addition to Area 01)

```sql
-- =============================================================================
-- NOTIFICATION PREFERENCES
-- =============================================================================

CREATE TABLE notification_preferences (
    user_id TEXT PRIMARY KEY,                   -- 'thom', 'elizabeth', etc.
    
    -- Channel preferences
    ha_mobile_enabled INTEGER NOT NULL DEFAULT 1,
    sms_enabled INTEGER NOT NULL DEFAULT 1,
    voice_broadcast_enabled INTEGER NOT NULL DEFAULT 1,
    
    -- Phone number for SMS (E.164 format)
    phone_number TEXT,
    
    -- Quiet hours (local time, 24h format)
    quiet_hours_start TEXT DEFAULT '22:00',     -- 10 PM
    quiet_hours_end TEXT DEFAULT '07:00',       -- 7 AM
    quiet_hours_enabled INTEGER NOT NULL DEFAULT 1,
    
    -- Rate limiting
    max_notifications_per_hour INTEGER NOT NULL DEFAULT 10,
    
    -- Override for critical notifications
    critical_override_quiet_hours INTEGER NOT NULL DEFAULT 1,
    
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =============================================================================
-- NOTIFICATION LOG
-- =============================================================================

CREATE TABLE notification_log (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Target
    user_id TEXT NOT NULL,
    
    -- Content
    title TEXT,
    message TEXT NOT NULL,
    notification_type TEXT NOT NULL,            -- alert, reminder, content, timer
    priority TEXT NOT NULL DEFAULT 'normal',    -- low, normal, high, critical
    
    -- Delivery
    channel TEXT NOT NULL,                      -- ha_mobile, sms, voice
    status TEXT NOT NULL DEFAULT 'pending',     -- pending, sent, failed, rate_limited
    
    -- Tracking
    sent_at TEXT,
    error_message TEXT,
    
    -- Source tracking
    source_type TEXT,                           -- timer, calendar, memory, alert
    source_id TEXT                              -- Reference to originating entity
);

CREATE INDEX idx_notification_log_user_created ON notification_log(user_id, created_at DESC);
CREATE INDEX idx_notification_log_status ON notification_log(status);
```

---

## 4. Home Assistant Integration

### 4.1 HA Notification Service

```python
# src/barnabee/notifications/ha_notify.py

async def send_ha_notification(
    user_id: str,
    title: str,
    message: str,
    data: Optional[dict] = None,
) -> bool:
    """Send notification via Home Assistant mobile app."""
    
    # Map user to HA service
    service_map = {
        "thom": "notify.mobile_app_thoms_iphone",
        "elizabeth": "notify.mobile_app_elizabeths_iphone",
    }
    
    service = service_map.get(user_id)
    if not service:
        logger.warning("no_ha_service_for_user", user_id=user_id)
        return False
    
    payload = {
        "title": title,
        "message": message,
    }
    
    if data:
        payload["data"] = data
    
    # Call HA service via WebSocket
    await ha_client.call_service(
        domain="notify",
        service=service.split(".")[1],
        service_data=payload,
    )
    
    return True


async def send_actionable_notification(
    user_id: str,
    title: str,
    message: str,
    actions: list[dict],
) -> bool:
    """Send notification with action buttons."""
    
    # iOS actionable notification format
    data = {
        "actions": [
            {
                "action": action["id"],
                "title": action["title"],
                "destructive": action.get("destructive", False),
            }
            for action in actions
        ]
    }
    
    return await send_ha_notification(user_id, title, message, data)
```

### 4.2 HA Event Listener for Actions

```python
# Handle notification action responses from HA

async def handle_ha_notification_action(event: dict):
    """Handle user response to actionable notification."""
    action_id = event.get("action")
    user_id = event.get("user_id")
    
    if action_id == "CONFIRM_CALENDAR_EVENT":
        await process_pending_calendar_event(user_id)
    elif action_id == "DISMISS":
        await clear_pending_action(user_id)
    # etc.
```

---

## 5. Azure Communication Services SMS

### 5.1 Configuration

```python
# config/settings.py

class AzureCommSettings(BaseSettings):
    connection_string: str = Field(..., env="AZURE_COMM_CONNECTION_STRING")
    sender_phone: str = Field(..., env="AZURE_COMM_SENDER_PHONE")  # E.164 format
    
    class Config:
        env_prefix = "AZURE_COMM_"
```

### 5.2 SMS Client

```python
# src/barnabee/notifications/sms.py

from azure.communication.sms import SmsClient

class AzureSMSClient:
    def __init__(self, settings: AzureCommSettings):
        self.client = SmsClient.from_connection_string(settings.connection_string)
        self.sender = settings.sender_phone
    
    async def send_sms(
        self,
        to_phone: str,
        message: str,
    ) -> SMSResult:
        """Send SMS via Azure Communication Services."""
        
        # Azure SDK is sync, run in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.send(
                from_=self.sender,
                to=to_phone,
                message=message,
            )
        )
        
        result = response[0]
        
        if result.successful:
            logger.info("sms_sent", to=to_phone, message_id=result.message_id)
            return SMSResult(success=True, message_id=result.message_id)
        else:
            logger.error("sms_failed", to=to_phone, error=result.error_message)
            return SMSResult(success=False, error=result.error_message)


async def send_long_content_via_sms(
    user_id: str,
    content: str,
    intro: str = "Here's what you asked for:",
) -> bool:
    """Send long content via SMS when it doesn't fit voice."""
    prefs = await get_notification_preferences(user_id)
    
    if not prefs.sms_enabled or not prefs.phone_number:
        logger.warning("sms_not_configured", user_id=user_id)
        return False
    
    # SMS character limit is 1600 for concatenated messages
    # Keep under 1000 to be safe
    if len(content) > 1000:
        content = content[:997] + "..."
    
    message = f"{intro}\n\n{content}"
    
    client = AzureSMSClient(settings.azure_comm)
    result = await client.send_sms(prefs.phone_number, message)
    
    return result.success
```

---

## 6. Notification Router

### 6.1 Core Router Logic

```python
# src/barnabee/notifications/router.py

from enum import Enum
from dataclasses import dataclass

class NotificationPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationChannel(Enum):
    HA_MOBILE = "ha_mobile"
    SMS = "sms"
    VOICE = "voice"

@dataclass
class Notification:
    user_id: str
    title: Optional[str]
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    notification_type: str = "alert"
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    preferred_channel: Optional[NotificationChannel] = None


class NotificationRouter:
    def __init__(self, db, ha_client, sms_client):
        self.db = db
        self.ha_client = ha_client
        self.sms_client = sms_client
    
    async def send(self, notification: Notification) -> bool:
        """Route and send a notification."""
        
        # 1. Get user preferences
        prefs = await self.get_preferences(notification.user_id)
        
        # 2. Check quiet hours (unless critical)
        if notification.priority != NotificationPriority.CRITICAL:
            if self.is_quiet_hours(prefs):
                logger.info("notification_quiet_hours", user_id=notification.user_id)
                return False
        
        # 3. Check rate limits (unless critical)
        if notification.priority != NotificationPriority.CRITICAL:
            if await self.is_rate_limited(notification.user_id, prefs):
                await self.log_notification(notification, "rate_limited")
                logger.info("notification_rate_limited", user_id=notification.user_id)
                return False
        
        # 4. Select channel
        channel = self.select_channel(notification, prefs)
        
        # 5. Send via selected channel
        success = await self.deliver(notification, channel)
        
        # 6. Log result
        await self.log_notification(
            notification, 
            "sent" if success else "failed",
            channel=channel.value,
        )
        
        return success
    
    def select_channel(
        self, 
        notification: Notification, 
        prefs: NotificationPreferences
    ) -> NotificationChannel:
        """Select the best channel for this notification."""
        
        # Explicit preference
        if notification.preferred_channel:
            return notification.preferred_channel
        
        # Long content → SMS
        if len(notification.message) > 200:
            if prefs.sms_enabled and prefs.phone_number:
                return NotificationChannel.SMS
        
        # Critical security → Voice broadcast (if home)
        if notification.priority == NotificationPriority.CRITICAL:
            if notification.notification_type == "security":
                return NotificationChannel.VOICE
        
        # Default → HA Mobile
        return NotificationChannel.HA_MOBILE
    
    async def deliver(
        self, 
        notification: Notification, 
        channel: NotificationChannel
    ) -> bool:
        """Deliver notification via selected channel."""
        
        if channel == NotificationChannel.HA_MOBILE:
            return await send_ha_notification(
                notification.user_id,
                notification.title or "Barnabee",
                notification.message,
            )
        
        elif channel == NotificationChannel.SMS:
            prefs = await self.get_preferences(notification.user_id)
            return await self.sms_client.send_sms(
                prefs.phone_number,
                notification.message,
            )
        
        elif channel == NotificationChannel.VOICE:
            return await self.broadcast_voice(notification)
        
        return False
    
    async def broadcast_voice(self, notification: Notification) -> bool:
        """Broadcast notification via household speakers."""
        # Use HA media_player service to play TTS on speakers
        # TODO: Integrate with Pipecat for Barnabee's voice
        pass
    
    def is_quiet_hours(self, prefs: NotificationPreferences) -> bool:
        """Check if current time is within quiet hours."""
        if not prefs.quiet_hours_enabled:
            return False
        
        now = datetime.now().time()
        start = datetime.strptime(prefs.quiet_hours_start, "%H:%M").time()
        end = datetime.strptime(prefs.quiet_hours_end, "%H:%M").time()
        
        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if start > end:
            return now >= start or now < end
        else:
            return start <= now < end
    
    async def is_rate_limited(
        self, 
        user_id: str, 
        prefs: NotificationPreferences
    ) -> bool:
        """Check if user has exceeded notification rate limit."""
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        count = await self.db.fetch_val("""
            SELECT COUNT(*) FROM notification_log
            WHERE user_id = ? AND created_at > ? AND status = 'sent'
        """, user_id, one_hour_ago.isoformat())
        
        return count >= prefs.max_notifications_per_hour
```

---

## 7. Long Content Delivery

### 7.1 When Voice Response is Too Long

```python
# src/barnabee/response/delivery.py

MAX_VOICE_RESPONSE_LENGTH = 200  # characters
MAX_VOICE_RESPONSE_DURATION = 15  # seconds (approximate)

async def deliver_response(
    session: Session,
    response: str,
) -> DeliveryResult:
    """Deliver response via appropriate channel."""
    
    # Short enough for voice
    if len(response) <= MAX_VOICE_RESPONSE_LENGTH:
        return DeliveryResult(
            channel="voice",
            spoken=response,
            sent_separately=None,
        )
    
    # Too long - split into voice summary + SMS full content
    summary = await generate_voice_summary(response)
    
    # Send full content via SMS
    sms_sent = await send_long_content_via_sms(
        session.user_id,
        response,
        intro="Here's the full response you asked for:",
    )
    
    if sms_sent:
        spoken = f"{summary} I've texted you the full details."
    else:
        # SMS failed - give voice summary only
        spoken = f"{summary} There's more detail I couldn't fit in."
    
    return DeliveryResult(
        channel="voice+sms",
        spoken=spoken,
        sent_separately=response if sms_sent else None,
    )


async def generate_voice_summary(long_response: str) -> str:
    """Generate a voice-friendly summary of long content."""
    
    # Use LLM to summarize
    summary = await llm.complete(
        system="Summarize the following in 1-2 short sentences for voice delivery. "
               "Be concise and conversational.",
        user=long_response,
        max_tokens=100,
    )
    
    return summary.strip()
```

---

## 8. Notification Types

### 8.1 Timer Notifications

```python
async def notify_timer_complete(user_id: str, timer_name: str):
    """Notify user that a timer has completed."""
    
    # Voice broadcast if user is home
    if await is_user_home(user_id):
        await notify_router.send(Notification(
            user_id=user_id,
            title="Timer Complete",
            message=f"Your {timer_name} timer is done.",
            priority=NotificationPriority.HIGH,
            notification_type="timer",
            preferred_channel=NotificationChannel.VOICE,
        ))
    
    # Also send push notification
    await notify_router.send(Notification(
        user_id=user_id,
        title="Timer Complete",
        message=f"Your {timer_name} timer is done.",
        priority=NotificationPriority.NORMAL,
        notification_type="timer",
        preferred_channel=NotificationChannel.HA_MOBILE,
    ))
```

### 8.2 Calendar Reminders

```python
async def notify_calendar_reminder(user_id: str, event: CalendarEvent, minutes_before: int):
    """Send calendar event reminder."""
    
    message = f"{event.title} starts in {minutes_before} minutes"
    if event.location:
        message += f" at {event.location}"
    
    await notify_router.send(Notification(
        user_id=user_id,
        title="Calendar Reminder",
        message=message,
        priority=NotificationPriority.NORMAL,
        notification_type="reminder",
        source_type="calendar",
        source_id=event.id,
    ))
```

### 8.3 Security Alerts

```python
async def notify_security_alert(alert_type: str, details: str):
    """Send security alert to all family members."""
    
    for user_id in ["thom", "elizabeth"]:
        await notify_router.send(Notification(
            user_id=user_id,
            title="Security Alert",
            message=f"{alert_type}: {details}",
            priority=NotificationPriority.CRITICAL,
            notification_type="security",
        ))
```

---

## 9. Dashboard Integration

### 9.1 Notification Preferences UI

```typescript
// Dashboard settings for notification preferences
interface NotificationPreferences {
  ha_mobile_enabled: boolean;
  sms_enabled: boolean;
  phone_number: string | null;
  voice_broadcast_enabled: boolean;
  quiet_hours_start: string;  // "22:00"
  quiet_hours_end: string;    // "07:00"
  quiet_hours_enabled: boolean;
  max_notifications_per_hour: number;
  critical_override_quiet_hours: boolean;
}

// API endpoints
// GET /api/notifications/preferences/{user_id}
// PUT /api/notifications/preferences/{user_id}
// GET /api/notifications/history/{user_id}?limit=50
```

---

## 10. Implementation Checklist

### Infrastructure
- [ ] Azure Communication Services account created
- [ ] Phone number provisioned
- [ ] Connection string configured

### Database
- [ ] notification_preferences table created
- [ ] notification_log table created
- [ ] Indexes created

### HA Integration
- [ ] notify services mapped per user
- [ ] Notification action handler implemented
- [ ] Voice broadcast via media_player working

### SMS Integration
- [ ] Azure SMS client implemented
- [ ] Long content delivery working
- [ ] Error handling and retries

### Router
- [ ] Quiet hours logic implemented
- [ ] Rate limiting working
- [ ] Channel selection logic complete
- [ ] Logging for all notifications

### Dashboard
- [ ] Preferences API endpoints
- [ ] Preferences UI in dashboard
- [ ] Notification history view

---

## 11. Acceptance Criteria

1. **HA push works:** Notification appears on mobile within 2 seconds
2. **SMS works:** Message delivered within 5 seconds
3. **Quiet hours respected:** No notifications during quiet hours (except critical)
4. **Rate limiting works:** 11th notification in an hour is blocked
5. **Long content flows to SMS:** >200 char response triggers SMS delivery
6. **Critical overrides all:** Security alerts always delivered

---

**End of Area 13: Notifications & Delivery**

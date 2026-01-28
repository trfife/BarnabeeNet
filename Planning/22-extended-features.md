# Area 22: Extended Features

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 01, 03, 04, 06, 09, 13, 21  
**Phase:** Extended Functionality  

---

## Overview

This specification covers additional household features that enhance BarnabeeNet's utility as a comprehensive home assistant. These features build on the core infrastructure and integrate with existing systems.

### Features Covered

1. Shopping Lists
2. Recipe Assistance
3. Package Tracking
4. Smart Appliance Control
5. Intercom/Announce
6. Language Learning
7. Guest Mode
8. Routines/Automations
9. Kids Mode
10. Morning/Evening Briefings
11. Habit Tracking
12. Home Inventory
13. Home Maintenance
14. Pet Care
15. Travel Assistant
16. Entertainment Recommendations
17. Garden/Plant Care
18. Energy Monitoring

---

## 1. Shopping Lists

### Purpose
Dedicated shopping list management beyond basic todos, with store organization and smart suggestions.

### Data Model

```sql
CREATE TABLE shopping_lists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,              -- "Groceries", "Costco", "Hardware"
    store TEXT,                      -- Optional store association
    owner_id TEXT,
    shared BOOLEAN DEFAULT TRUE,     -- Visible to all family
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE shopping_items (
    id TEXT PRIMARY KEY,
    list_id TEXT REFERENCES shopping_lists(id) ON DELETE CASCADE,
    item_name TEXT NOT NULL,
    quantity TEXT,                   -- "2", "1 lb", "bunch"
    category TEXT,                   -- "produce", "dairy", "frozen"
    added_by TEXT,
    checked BOOLEAN DEFAULT FALSE,
    checked_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE shopping_history (
    id TEXT PRIMARY KEY,
    item_name TEXT NOT NULL,
    typical_quantity TEXT,
    purchase_frequency_days INTEGER,
    last_purchased DATE,
    usual_store TEXT
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `shopping.add` | "Add milk to the grocery list" |
| `shopping.add_multiple` | "Add bread, eggs, and butter" |
| `shopping.remove` | "Remove milk from the list" |
| `shopping.query` | "What's on my shopping list?" |
| `shopping.clear` | "Clear the grocery list" |
| `shopping.check` | "Check off the milk" |
| `shopping.suggest` | "What do we usually buy at Costco?" |

### Smart Features

- **Category organization**: Auto-sort by store aisle
- **Quantity inference**: "Add eggs" → "Add eggs (1 dozen)"
- **Purchase history**: Learn typical quantities
- **Restock suggestions**: "You usually buy coffee every 2 weeks"
- **Recipe integration**: "Add ingredients for lasagna"

---

## 2. Recipe Assistance

### Purpose
Cooking help including recipe search, step-by-step guidance, measurement conversions, and timers.

### Data Model

```sql
CREATE TABLE saved_recipes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT,                     -- URL or "personal"
    ingredients JSON,                -- [{item, quantity, unit}]
    instructions JSON,               -- [{step, time_minutes}]
    prep_time_minutes INTEGER,
    cook_time_minutes INTEGER,
    servings INTEGER,
    tags JSON,                       -- ["vegetarian", "quick", "kid-friendly"]
    rating INTEGER,
    notes TEXT,
    last_made DATE,
    times_made INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE meal_plan (
    id TEXT PRIMARY KEY,
    date DATE NOT NULL,
    meal_type TEXT,                  -- "breakfast", "lunch", "dinner"
    recipe_id TEXT REFERENCES saved_recipes(id),
    notes TEXT
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `recipe.search` | "Find me a chicken recipe" |
| `recipe.start` | "Start the lasagna recipe" |
| `recipe.next_step` | "What's next?" / "Next step" |
| `recipe.repeat` | "Repeat that step" |
| `recipe.timer` | "Set a timer for this step" |
| `recipe.convert` | "How many tablespoons in a cup?" |
| `recipe.substitute` | "What can I use instead of buttermilk?" |
| `recipe.scale` | "Scale this recipe for 8 people" |
| `recipe.add_to_list` | "Add these ingredients to my list" |

### Guided Cooking Mode

```python
class GuidedCooking:
    """Step-by-step recipe guidance."""
    
    def __init__(self, recipe_id: str):
        self.recipe = load_recipe(recipe_id)
        self.current_step = 0
        self.active_timers = []
    
    async def start(self) -> str:
        return f"Let's make {self.recipe.name}. " \
               f"It takes about {self.recipe.total_time} minutes. " \
               f"First, {self.recipe.instructions[0].text}"
    
    async def next_step(self) -> str:
        self.current_step += 1
        if self.current_step >= len(self.recipe.instructions):
            return "That's the last step! Enjoy your meal."
        
        step = self.recipe.instructions[self.current_step]
        response = step.text
        
        if step.time_minutes:
            response += f" This takes about {step.time_minutes} minutes. "
            response += "Want me to set a timer?"
        
        return response
```

### Measurement Conversions

Built-in conversion support:
- Volume: cups ↔ tablespoons ↔ teaspoons ↔ ml ↔ liters
- Weight: pounds ↔ ounces ↔ grams ↔ kg
- Temperature: Fahrenheit ↔ Celsius
- Common substitutions database

---

## 3. Package Tracking

### Purpose
Track deliveries from major carriers with voice status updates.

### Data Model

```sql
CREATE TABLE packages (
    id TEXT PRIMARY KEY,
    tracking_number TEXT NOT NULL,
    carrier TEXT NOT NULL,           -- "ups", "fedex", "usps", "amazon"
    description TEXT,                -- "Amazon order" or custom
    status TEXT,                     -- "in_transit", "out_for_delivery", "delivered"
    estimated_delivery DATE,
    actual_delivery TIMESTAMP,
    last_location TEXT,
    last_update TIMESTAMP,
    notify_on_delivery BOOLEAN DEFAULT TRUE,
    added_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE package_events (
    id TEXT PRIMARY KEY,
    package_id TEXT REFERENCES packages(id) ON DELETE CASCADE,
    event_time TIMESTAMP,
    status TEXT,
    location TEXT,
    description TEXT
);
```

### Integration Options

1. **Email parsing**: Auto-detect tracking numbers from order confirmations
2. **Manual entry**: "Track package 1Z999AA10123456784"
3. **Carrier APIs**: Direct integration where available

### Voice Commands

| Intent | Examples |
|--------|----------|
| `package.track` | "Track package [number]" |
| `package.status` | "Where's my Amazon package?" |
| `package.list` | "What packages am I expecting?" |
| `package.arriving` | "Any deliveries today?" |
| `package.delete` | "Stop tracking the FedEx package" |

### Notifications

- Out for delivery alert
- Delivered notification
- Delay alerts
- Daily summary: "You have 2 packages arriving today"

---

## 4. Smart Appliance Control

### Purpose
Control and monitor smart appliances beyond basic Home Assistant entities.

### Supported Appliances

| Appliance | Capabilities |
|-----------|--------------|
| Washer/Dryer | Start, status, cycle complete notifications |
| Robot Vacuum | Start, stop, dock, locate, schedule |
| Dishwasher | Status, cycle complete |
| Oven/Range | Preheat, timer, temperature |
| Coffee Maker | Brew, schedule |
| Air Purifier | Mode, fan speed, filter status |

### Voice Commands

| Intent | Examples |
|--------|----------|
| `appliance.vacuum.start` | "Start the robot vacuum" |
| `appliance.vacuum.dock` | "Send Roomba home" |
| `appliance.vacuum.locate` | "Where's the vacuum?" |
| `appliance.laundry.status` | "Is the laundry done?" |
| `appliance.laundry.notify` | "Tell me when the dryer is done" |
| `appliance.coffee.brew` | "Start the coffee maker" |
| `appliance.oven.preheat` | "Preheat the oven to 375" |

### Notifications

- Cycle complete (washer, dryer, dishwasher)
- Robot vacuum stuck or needs attention
- Filter replacement reminders
- Door left open alerts

### Integration

Primarily through Home Assistant entities with enhanced semantic understanding:
- "The laundry" → washer OR dryer based on context
- "Start cleaning" → robot vacuum
- "Is the wash done?" → washer status

---

## 5. Intercom / Announce

### Purpose
Broadcast messages to specific devices or all devices in the home.

### Voice Commands

| Intent | Examples |
|--------|----------|
| `intercom.announce_all` | "Announce dinner is ready" |
| `intercom.announce_room` | "Tell the kids room to come downstairs" |
| `intercom.announce_person` | "Tell Elizabeth I'm leaving" |
| `intercom.call` | "Call the living room" (two-way) |

### Implementation

```python
class IntercomService:
    """Broadcast and two-way intercom."""
    
    async def announce(
        self,
        message: str,
        targets: list[str] = None,  # Device IDs or "all"
        voice: str = "barnabee",
        urgent: bool = False,
    ):
        """Broadcast a message to target devices."""
        
        if targets is None or "all" in targets:
            devices = await self.get_all_speaker_devices()
        else:
            devices = await self.resolve_targets(targets)
        
        # Generate TTS audio
        audio = await self.tts.synthesize(message, voice=voice)
        
        # Play on all targets
        for device in devices:
            if urgent:
                # Interrupt current audio
                await device.play_urgent(audio)
            else:
                # Queue after current audio
                await device.play(audio)
    
    async def resolve_targets(self, targets: list[str]) -> list[Device]:
        """Resolve room names, person names to devices."""
        devices = []
        
        for target in targets:
            # Check if it's a room
            room_devices = await self.get_devices_in_room(target)
            if room_devices:
                devices.extend(room_devices)
                continue
            
            # Check if it's a person
            person_device = await self.get_person_primary_device(target)
            if person_device:
                devices.append(person_device)
        
        return devices
```

### Features

- **TTS synthesis**: Message spoken in Barnabee's voice
- **Room targeting**: "Announce to the kitchen"
- **Person targeting**: Uses device location or sends to phone
- **Two-way intercom**: "Call the garage" opens audio channel
- **Urgent mode**: Interrupts current audio

---

## 6. Language Learning

### Purpose
Help family members learn new languages through conversation practice, vocabulary, and translation.

### Data Model

```sql
CREATE TABLE language_profiles (
    user_id TEXT PRIMARY KEY,
    target_language TEXT NOT NULL,   -- "spanish", "french", "mandarin"
    proficiency_level TEXT,          -- "beginner", "intermediate", "advanced"
    daily_goal_minutes INTEGER DEFAULT 10,
    streak_days INTEGER DEFAULT 0,
    last_practice DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vocabulary (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    language TEXT NOT NULL,
    example_sentence TEXT,
    audio_url TEXT,
    times_practiced INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    last_practiced TIMESTAMP,
    next_review TIMESTAMP,           -- Spaced repetition
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE practice_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    language TEXT,
    duration_minutes INTEGER,
    words_practiced INTEGER,
    accuracy REAL,
    session_type TEXT,               -- "vocabulary", "conversation", "translation"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `language.translate` | "How do you say 'hello' in Spanish?" |
| `language.practice` | "Let's practice Spanish" |
| `language.word` | "What does 'gato' mean?" |
| `language.pronounce` | "How do you pronounce 'croissant'?" |
| `language.quiz` | "Quiz me on my Spanish vocabulary" |
| `language.conversation` | "Have a conversation with me in French" |
| `language.set_goal` | "I want to learn Spanish" |

### Practice Modes

```python
class LanguagePractice:
    """Interactive language learning."""
    
    async def vocabulary_quiz(self, user_id: str) -> str:
        """Spaced repetition vocabulary practice."""
        
        # Get words due for review
        words = await self.get_due_vocabulary(user_id)
        
        if not words:
            return "Great job! No words due for review right now."
        
        word = words[0]
        
        # Randomly choose direction
        if random.choice([True, False]):
            return f"What's the Spanish word for '{word.translation}'?"
        else:
            return f"What does '{word.word}' mean?"
    
    async def conversation_mode(
        self,
        user_id: str,
        language: str,
    ) -> str:
        """Practice conversation in target language."""
        
        profile = await self.get_profile(user_id)
        
        system_prompt = f"""
        You are a friendly language tutor helping someone practice {language}.
        Their level is {profile.proficiency_level}.
        
        - Speak primarily in {language}
        - Keep sentences appropriate for their level
        - Gently correct mistakes
        - Occasionally ask questions to keep them engaged
        - If they struggle, offer hints or switch to English briefly
        """
        
        return await self.llm.chat(system_prompt, conversation_history)
```

### Features

- **Translation**: Quick translations to/from learning language
- **Pronunciation**: TTS in target language
- **Vocabulary building**: Add words, spaced repetition review
- **Conversation practice**: LLM-powered chat in target language
- **Progress tracking**: Streaks, accuracy, time spent
- **Level adaptation**: Difficulty adjusts to proficiency

---

## 7. Guest Mode

### Purpose
Limited access for visitors - basic functionality without personal data access.

### Access Levels

| Feature | Super User | Family | Guest |
|---------|------------|--------|-------|
| Lights/Climate | Yes | Yes | Yes |
| Media control | Yes | Yes | Yes |
| Time/Weather | Yes | Yes | Yes |
| Timers | Yes | Yes | Yes |
| Calendar | Yes | Own | No |
| Memories | All | Own | No |
| Finance | Yes | No | No |
| Shopping lists | Yes | Yes | View only |
| Intercom | Yes | Yes | No |
| Settings | Yes | Limited | No |

### Activation

```python
class GuestMode:
    """Manage guest access."""
    
    async def enable_guest_mode(
        self,
        duration_hours: int = 24,
        devices: list[str] = None,
    ):
        """Enable guest mode on specified devices."""
        
        expiry = datetime.utcnow() + timedelta(hours=duration_hours)
        
        guest_session = {
            "id": generate_id(),
            "enabled_at": datetime.utcnow(),
            "expires_at": expiry,
            "devices": devices or ["all"],
        }
        
        await self.store_guest_session(guest_session)
        
        return f"Guest mode enabled for {duration_hours} hours."
    
    def is_guest_allowed(self, intent: str) -> bool:
        """Check if intent is allowed for guests."""
        
        GUEST_ALLOWED = {
            "light_control", "climate_control", "media_control",
            "time_query", "weather_query", "timer_set", "timer_query",
            "general_query", "greeting", "farewell", "help",
        }
        
        return intent in GUEST_ALLOWED
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `guest.enable` | "Enable guest mode" |
| `guest.disable` | "Disable guest mode" |
| `guest.status` | "Is guest mode on?" |
| `guest.extend` | "Extend guest mode for 2 hours" |

### Features

- **Time-limited**: Auto-expires after set duration
- **Device-specific**: Can limit to certain rooms
- **No personal data**: Memories, calendar, finance blocked
- **Basic control**: Lights, media, timers work
- **Audit logging**: Track guest interactions

---

## 8. Routines / Automations

### Purpose
Multi-action sequences triggered by voice, time, or events.

### Data Model

```sql
CREATE TABLE routines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,              -- "Good Morning", "Movie Time"
    trigger_type TEXT,               -- "voice", "time", "event", "location"
    trigger_config JSON,             -- Trigger-specific config
    actions JSON,                    -- [{action_type, params, delay_seconds}]
    enabled BOOLEAN DEFAULT TRUE,
    owner_id TEXT,
    last_run TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE routine_runs (
    id TEXT PRIMARY KEY,
    routine_id TEXT REFERENCES routines(id),
    triggered_by TEXT,               -- "voice", "schedule", "event"
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,                     -- "success", "partial", "failed"
    actions_completed INTEGER,
    error_message TEXT
);
```

### Trigger Types

| Type | Config Example |
|------|----------------|
| Voice | `{"phrase": "good morning"}` |
| Time | `{"time": "07:00", "days": ["mon","tue","wed","thu","fri"]}` |
| Event | `{"entity": "person.thom", "state": "home"}` |
| Location | `{"person": "thom", "zone": "home", "enter": true}` |

### Action Types

| Action | Parameters |
|--------|------------|
| `ha_service` | `{service, entity_id, data}` |
| `speak` | `{message, device}` |
| `notify` | `{message, channel}` |
| `wait` | `{seconds}` |
| `condition` | `{if, then, else}` |
| `briefing` | `{include: [weather, calendar, news]}` |

### Voice Commands

| Intent | Examples |
|--------|----------|
| `routine.run` | "Good morning" / "Start movie time" |
| `routine.create` | "Create a bedtime routine" |
| `routine.list` | "What routines do I have?" |
| `routine.edit` | "Edit my morning routine" |
| `routine.delete` | "Delete the movie routine" |
| `routine.enable` | "Enable the good morning routine" |

### Example Routines

**Good Morning:**
```json
{
  "name": "Good Morning",
  "trigger_type": "voice",
  "trigger_config": {"phrases": ["good morning", "wake up routine"]},
  "actions": [
    {"action": "ha_service", "service": "light.turn_on", "entity": "bedroom_lights", "data": {"brightness": 50}},
    {"action": "wait", "seconds": 2},
    {"action": "briefing", "include": ["weather", "calendar"]},
    {"action": "ha_service", "service": "switch.turn_on", "entity": "coffee_maker"}
  ]
}
```

**Movie Time:**
```json
{
  "name": "Movie Time",
  "trigger_type": "voice",
  "trigger_config": {"phrases": ["movie time", "start movie mode"]},
  "actions": [
    {"action": "ha_service", "service": "light.turn_off", "entity": "living_room_lights"},
    {"action": "ha_service", "service": "cover.close", "entity": "living_room_blinds"},
    {"action": "ha_service", "service": "media_player.turn_on", "entity": "tv"},
    {"action": "speak", "message": "Enjoy your movie!"}
  ]
}
```

---

## 9. Kids Mode

### Purpose
Age-appropriate interactions with parental controls and educational features.

### Data Model

```sql
CREATE TABLE kid_profiles (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    age INTEGER,
    grade_level INTEGER,
    content_level TEXT,              -- "young_child", "child", "preteen", "teen"
    daily_screen_limit_minutes INTEGER,
    allowed_hours_start TIME,
    allowed_hours_end TIME,
    homework_help_enabled BOOLEAN DEFAULT TRUE,
    parent_id TEXT,                  -- Super user who manages this profile
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE kid_activity_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    activity_type TEXT,              -- "question", "game", "homework", "story"
    content TEXT,
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Features

**Content Filtering:**
- Age-appropriate responses
- No adult topics
- Simplified language for younger kids
- Educational focus

**Educational Features:**
- Homework help (math, spelling, science)
- Fun facts
- Educational games (trivia, word games)
- Story time

**Parental Controls:**
- Usage time limits
- Active hours restrictions
- Activity logging (for parents to review)
- Topic restrictions

### Voice Commands

| Intent | Examples |
|--------|----------|
| `kids.homework` | "Help me with my math homework" |
| `kids.spell` | "How do you spell 'necessary'?" |
| `kids.fact` | "Tell me a fun fact" |
| `kids.story` | "Tell me a story" |
| `kids.game` | "Let's play a word game" |
| `kids.joke` | "Tell me a kid-friendly joke" |

### Example Interaction

```
Kid: "Barnabee, what's 7 times 8?"
Barnabee: "7 times 8 is 56! Here's a trick to remember: 
          5, 6, 7, 8... 56 equals 7 times 8!"

Kid: "Help me with my spelling homework"
Barnabee: "Sure! Give me a word and I'll help you spell it, 
          or I can quiz you on your spelling list."
```

---

## 10. Morning/Evening Briefings

### Purpose
Personalized daily summaries delivered proactively or on-demand.

### Data Model

```sql
CREATE TABLE briefing_preferences (
    user_id TEXT PRIMARY KEY,
    morning_enabled BOOLEAN DEFAULT TRUE,
    morning_time TIME DEFAULT '07:00',
    evening_enabled BOOLEAN DEFAULT FALSE,
    evening_time TIME DEFAULT '18:00',
    include_weather BOOLEAN DEFAULT TRUE,
    include_calendar BOOLEAN DEFAULT TRUE,
    include_reminders BOOLEAN DEFAULT TRUE,
    include_news BOOLEAN DEFAULT FALSE,
    include_commute BOOLEAN DEFAULT FALSE,
    include_birthdays BOOLEAN DEFAULT TRUE,
    include_packages BOOLEAN DEFAULT TRUE,
    custom_greeting TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Briefing Content

**Morning:**
- Personalized greeting with name
- Weather summary and clothing suggestion
- Calendar events for the day
- Reminders due today
- Birthdays/important dates
- Package deliveries expected
- Commute conditions (if enabled)

**Evening:**
- Day summary
- Tomorrow's calendar preview
- Reminders for tomorrow
- Unfinished todos

### Voice Commands

| Intent | Examples |
|--------|----------|
| `briefing.morning` | "Good morning" / "What's my day look like?" |
| `briefing.evening` | "Evening briefing" / "What's tomorrow?" |
| `briefing.custom` | "Give me a quick update" |
| `briefing.configure` | "Change my morning briefing" |

### Example Briefing

```
"Good morning, Thom! It's Tuesday, January 27th. 

Currently 45 degrees and cloudy—you'll want a jacket today. 
High of 52 expected.

You have 3 events today: a team standup at 9, lunch with Mike at noon, 
and Penelope's soccer practice at 4.

Quick reminder: you wanted to call the dentist today.

Oh, and your Amazon package should arrive this afternoon.

Have a great day!"
```

---

## 11. Habit Tracking

### Purpose
Track daily habits like medications, exercise, water intake, and custom habits.

### Data Model

```sql
CREATE TABLE habits (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,              -- "Take vitamins", "Drink water"
    frequency TEXT,                  -- "daily", "weekdays", "weekly"
    target_count INTEGER DEFAULT 1,  -- Times per period
    reminder_time TIME,
    reminder_enabled BOOLEAN DEFAULT TRUE,
    streak_current INTEGER DEFAULT 0,
    streak_best INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE habit_logs (
    id TEXT PRIMARY KEY,
    habit_id TEXT REFERENCES habits(id) ON DELETE CASCADE,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    count INTEGER DEFAULT 1,
    notes TEXT
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `habit.log` | "I took my vitamins" / "Log my workout" |
| `habit.query` | "Did I take my vitamins today?" |
| `habit.streak` | "What's my meditation streak?" |
| `habit.create` | "Create a habit to drink 8 glasses of water" |
| `habit.list` | "What habits am I tracking?" |
| `habit.remind` | "Remind me to take vitamins at 8am" |

### Features

- **Quick logging**: "Log [habit]" marks it complete
- **Query status**: "Did I [habit] today?"
- **Streaks**: Track consecutive days
- **Reminders**: Time-based prompts
- **Progress reports**: Weekly/monthly summaries
- **Medications**: Special handling with dose tracking

### Example Interactions

```
Thom: "Did I take my vitamins today?"
Barnabee: "Not yet! You usually take them around 8am."

Thom: "I took my vitamins"
Barnabee: "Got it! That's 12 days in a row—nice streak!"

Barnabee (8am): "Good morning! Time for your vitamins."
```

---

## 12. Home Inventory

### Purpose
Track where things are stored and what supplies you have.

### Data Model

```sql
CREATE TABLE inventory_locations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,              -- "Garage shelf", "Kitchen pantry"
    parent_id TEXT,                  -- For nested locations
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE inventory_items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,                   -- "holiday", "tools", "office", "kitchen"
    location_id TEXT REFERENCES inventory_locations(id),
    quantity INTEGER,
    unit TEXT,                       -- "boxes", "rolls", "items"
    low_stock_threshold INTEGER,
    notes TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    photo_url TEXT
);

CREATE TABLE inventory_log (
    id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES inventory_items(id),
    action TEXT,                     -- "added", "removed", "moved", "updated"
    quantity_change INTEGER,
    new_location_id TEXT,
    notes TEXT,
    logged_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `inventory.find` | "Where are the Christmas decorations?" |
| `inventory.add` | "Add AA batteries to garage inventory" |
| `inventory.update` | "I used 4 AA batteries" |
| `inventory.check` | "Do we have any light bulbs?" |
| `inventory.low_stock` | "What's running low?" |
| `inventory.move` | "I moved the camping gear to the basement" |

### Features

- **Location tracking**: "Where did I put...?"
- **Quantity management**: Track counts and usage
- **Low stock alerts**: "You're down to 2 AA batteries"
- **Categories**: Holiday, tools, cleaning, office, etc.
- **Search**: Find items by name or category
- **Movement logging**: Track when items are relocated

### Example Interactions

```
Thom: "Where did I put the Christmas decorations?"
Barnabee: "The Christmas decorations are in the garage, 
          on the top shelf by the window. You put them 
          there last January."

Thom: "Do we have any AA batteries?"
Barnabee: "Yes, you have about 8 AA batteries in the 
          kitchen utility drawer."

Thom: "I used 4 batteries"
Barnabee: "Got it. You're down to 4 AA batteries now. 
          Want me to add them to your shopping list?"
```

---

## 13. Home Maintenance

### Purpose
Track maintenance schedules for home systems, vehicles, and appliances with proactive reminders.

### Data Model

```sql
CREATE TABLE maintenance_items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,                   -- "hvac", "vehicle", "appliance", "home"
    location TEXT,                   -- "furnace", "car", "refrigerator"
    interval_days INTEGER,
    interval_type TEXT,              -- "days", "months", "miles", "hours"
    last_service DATE,
    next_service DATE,
    service_provider TEXT,
    estimated_cost INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE maintenance_log (
    id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES maintenance_items(id),
    service_date DATE NOT NULL,
    service_type TEXT,               -- "routine", "repair", "inspection"
    cost_cents INTEGER,
    provider TEXT,
    notes TEXT,
    receipt_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE warranties (
    id TEXT PRIMARY KEY,
    item_name TEXT NOT NULL,
    purchase_date DATE,
    warranty_expires DATE,
    coverage_type TEXT,
    provider TEXT,
    policy_number TEXT,
    notes TEXT,
    document_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `maintenance.due` | "What maintenance is due?" |
| `maintenance.log` | "I changed the furnace filter" |
| `maintenance.schedule` | "When do I need an oil change?" |
| `maintenance.warranty` | "Is the dishwasher still under warranty?" |
| `maintenance.add` | "Add oil change every 5000 miles" |

### Tracked Items

**HVAC:**
- Furnace filter (every 1-3 months)
- AC service (annual)
- Duct cleaning (every 3-5 years)

**Vehicle:**
- Oil change (mileage or time-based)
- Tire rotation
- Brake inspection
- Registration renewal

**Appliances:**
- Refrigerator coils
- Dryer vent cleaning
- Water heater flush
- Garbage disposal care

**Home:**
- Smoke detector batteries
- Gutter cleaning
- Roof inspection
- Pest control

### Example Interactions

```
Barnabee (proactive): "Heads up—your furnace filter is due 
for replacement. It's been about 90 days."

Thom: "I changed the furnace filter"
Barnabee: "Got it! I'll remind you again in 3 months."

Thom: "Is the dishwasher still under warranty?"
Barnabee: "Yes, your Bosch dishwasher warranty runs until 
March 2027. You have about 14 months left."
```

---

## 14. Pet Care

### Purpose
Manage pet feeding schedules, medications, vet appointments, and care tasks.

### Data Model

```sql
CREATE TABLE pets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    species TEXT,                    -- "dog", "cat", "fish", etc.
    breed TEXT,
    birthday DATE,
    weight REAL,
    microchip_id TEXT,
    vet_name TEXT,
    vet_phone TEXT,
    notes TEXT,
    photo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pet_feeding (
    id TEXT PRIMARY KEY,
    pet_id TEXT REFERENCES pets(id),
    feeding_time TIME NOT NULL,
    food_type TEXT,
    amount TEXT,
    notes TEXT,
    enabled BOOLEAN DEFAULT TRUE
);

CREATE TABLE pet_feeding_log (
    id TEXT PRIMARY KEY,
    pet_id TEXT REFERENCES pets(id),
    fed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fed_by TEXT,
    amount TEXT,
    notes TEXT
);

CREATE TABLE pet_medications (
    id TEXT PRIMARY KEY,
    pet_id TEXT REFERENCES pets(id),
    medication_name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    start_date DATE,
    end_date DATE,
    reminder_time TIME,
    notes TEXT
);

CREATE TABLE pet_appointments (
    id TEXT PRIMARY KEY,
    pet_id TEXT REFERENCES pets(id),
    appointment_type TEXT,           -- "checkup", "vaccination", "grooming"
    provider TEXT,
    scheduled_at TIMESTAMP,
    notes TEXT,
    reminder_sent BOOLEAN DEFAULT FALSE
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `pet.feed` | "I fed the dog" / "Log Luna's breakfast" |
| `pet.fed_query` | "Did anyone feed the cat?" |
| `pet.medication` | "I gave Luna her heartworm pill" |
| `pet.appointment` | "When is Luna's next vet appointment?" |
| `pet.schedule` | "Schedule a vet checkup for Luna" |
| `pet.info` | "How old is Luna?" / "What's Luna's microchip number?" |

### Features

- **Feeding coordination**: Track who fed the pet to avoid double-feeding
- **Medication reminders**: Time-based alerts for pet meds
- **Vet appointment reminders**: Upcoming visit alerts
- **Vaccination tracking**: Know when boosters are due
- **Weight tracking**: Monitor pet health over time

### Example Interactions

```
Elizabeth: "Did anyone feed the dog?"
Barnabee: "Thom fed Luna about 2 hours ago, at 7:15 AM."

Barnabee (6pm): "It's time for Luna's evening meal."

Thom: "When is Luna's next vet appointment?"
Barnabee: "Luna has a checkup with Dr. Wilson on February 
15th at 2:30 PM. That's in 3 weeks."

Barnabee (proactive): "Luna's heartworm medication is due 
today. She gets one chewable with her morning meal."
```

---

## 15. Travel Assistant

### Purpose
Track flights, manage packing lists, and organize trip itineraries.

### Data Model

```sql
CREATE TABLE trips (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    destination TEXT,
    start_date DATE,
    end_date DATE,
    travelers JSON,                  -- ["thom", "elizabeth"]
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE flights (
    id TEXT PRIMARY KEY,
    trip_id TEXT REFERENCES trips(id),
    airline TEXT NOT NULL,
    flight_number TEXT NOT NULL,
    departure_airport TEXT,
    arrival_airport TEXT,
    departure_time TIMESTAMP,
    arrival_time TIMESTAMP,
    confirmation_code TEXT,
    seat_assignments JSON,
    status TEXT,                     -- "scheduled", "delayed", "cancelled"
    last_status_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE packing_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,              -- "Beach vacation", "Business trip"
    items JSON,                      -- [{item, category, quantity}]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE packing_lists (
    id TEXT PRIMARY KEY,
    trip_id TEXT REFERENCES trips(id),
    template_id TEXT,
    items JSON,                      -- [{item, packed, category}]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trip_itinerary (
    id TEXT PRIMARY KEY,
    trip_id TEXT REFERENCES trips(id),
    date DATE,
    time TIME,
    activity TEXT,
    location TEXT,
    confirmation TEXT,
    notes TEXT
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `travel.flight_status` | "What's the status of my flight?" |
| `travel.add_flight` | "Add flight AA123 on February 10th" |
| `travel.packing` | "Start a packing list for Hawaii" |
| `travel.pack_item` | "Add sunscreen to my packing list" |
| `travel.packed` | "I packed the sunscreen" |
| `travel.checklist` | "What haven't I packed yet?" |
| `travel.itinerary` | "What's planned for Tuesday in Hawaii?" |

### Features

- **Flight tracking**: Real-time status via FlightAware or airline APIs
- **Delay alerts**: Proactive notifications for flight changes
- **Packing templates**: Reusable lists for trip types
- **Pack tracking**: Check off items as you pack
- **Itinerary management**: Day-by-day activity planning
- **Time zone awareness**: "What time is it in Hawaii?"

### Example Interactions

```
Thom: "What's the status of my flight tomorrow?"
Barnabee: "Your flight AA1234 to Honolulu is on time. 
Departure at 8:45 AM from DFW, arriving at 1:30 PM 
local time. Don't forget—Hawaii is 4 hours behind."

Barnabee (proactive): "Heads up—your flight to Hawaii has 
been delayed by 45 minutes. New departure is 9:30 AM."

Thom: "Start a packing list for Hawaii"
Barnabee: "I've created a packing list based on your beach 
vacation template. You have 24 items. Want me to read them?"

Thom: "What haven't I packed yet?"
Barnabee: "You still need to pack: phone charger, sunglasses, 
and your snorkel gear."
```

---

## 16. Entertainment Recommendations

### Purpose
Suggest movies, shows, and content based on preferences and streaming services.

### Data Model

```sql
CREATE TABLE entertainment_profiles (
    user_id TEXT PRIMARY KEY,
    favorite_genres JSON,            -- ["comedy", "sci-fi", "documentary"]
    disliked_genres JSON,
    streaming_services JSON,         -- ["netflix", "hulu", "disney+"]
    movie_vs_tv_preference TEXT,     -- "movies", "tv", "both"
    typical_watch_length INTEGER,    -- minutes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE watch_history (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT NOT NULL,
    content_type TEXT,               -- "movie", "tv_show"
    genre TEXT,
    rating INTEGER,                  -- 1-5 stars
    watched_at TIMESTAMP,
    finished BOOLEAN DEFAULT TRUE,
    notes TEXT
);

CREATE TABLE watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT NOT NULL,
    content_type TEXT,
    streaming_service TEXT,
    recommended_by TEXT,             -- "barnabee", "friend", "self"
    priority INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `entertainment.recommend` | "What should I watch?" |
| `entertainment.recommend_specific` | "Recommend a comedy movie" |
| `entertainment.family` | "What can we watch as a family?" |
| `entertainment.similar` | "Something like Breaking Bad" |
| `entertainment.watchlist_add` | "Add Dune to my watchlist" |
| `entertainment.watchlist` | "What's on my watchlist?" |
| `entertainment.rate` | "I loved that movie" / "Rate it 4 stars" |
| `entertainment.where` | "Where can I watch Oppenheimer?" |

### Features

- **Personalized recommendations**: Based on watch history and ratings
- **Family mode**: Suggest age-appropriate content for group watching
- **Streaming service awareness**: Know what's available where
- **Similar content**: "If you liked X, try Y"
- **Watchlist management**: Track what you want to watch
- **New release alerts**: Notify about anticipated content

### Example Interactions

```
Thom: "What should I watch tonight?"
Barnabee: "Based on your recent viewing, I'd suggest 'Silo' 
on Apple TV+—it's a sci-fi thriller with great reviews. 
Or if you want something lighter, 'Ted Lasso' is always 
a good choice. Both are on services you have."

Elizabeth: "What can we watch as a family?"
Barnabee: "For family movie night, how about 'Elemental' on 
Disney+? It's rated PG and has great reviews. Or 'Nimona' 
on Netflix—Penelope might really enjoy that one."

Thom: "Where can I watch Oppenheimer?"
Barnabee: "Oppenheimer is available on Peacock, which you 
don't have, or you can rent it on Amazon for $5.99."
```

---

## 17. Garden & Plant Care

### Purpose
Track plant watering schedules, care requirements, and garden tasks with weather-based adjustments.

### Data Model

```sql
CREATE TABLE plants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,              -- "Tomatoes" or "Living room ficus"
    plant_type TEXT,                 -- "vegetable", "houseplant", "flower"
    location TEXT,                   -- "backyard garden", "kitchen window"
    indoor BOOLEAN DEFAULT FALSE,
    watering_frequency_days INTEGER,
    sunlight_needs TEXT,             -- "full", "partial", "shade"
    last_watered DATE,
    next_water DATE,
    notes TEXT,
    photo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE plant_care_log (
    id TEXT PRIMARY KEY,
    plant_id TEXT REFERENCES plants(id),
    care_type TEXT,                  -- "water", "fertilize", "prune", "harvest"
    care_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE garden_tasks (
    id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    task_type TEXT,                  -- "planting", "harvesting", "maintenance"
    due_date DATE,
    recurring BOOLEAN DEFAULT FALSE,
    recurrence_pattern TEXT,
    completed BOOLEAN DEFAULT FALSE,
    notes TEXT
);
```

### Voice Commands

| Intent | Examples |
|--------|----------|
| `garden.water` | "I watered the tomatoes" |
| `garden.needs_water` | "What plants need watering?" |
| `garden.care` | "How do I care for my fiddle leaf fig?" |
| `garden.plant` | "When should I plant tomatoes?" |
| `garden.harvest` | "When will the tomatoes be ready?" |
| `garden.add` | "Add a new plant—basil on the kitchen windowsill" |

### Weather Integration

- Skip watering reminders if rain is forecast
- Adjust schedules based on temperature
- Frost warnings for outdoor plants
- Heat advisories for extra watering

### Example Interactions

```
Barnabee (morning): "Good morning! Your indoor plants need 
watering today: the fiddle leaf fig and the pothos."

Thom: "I watered the fiddle leaf fig"
Barnabee: "Got it! I'll remind you again in about 10 days."

Thom: "What plants need watering?"
Barnabee: "The tomatoes in the backyard could use water, 
but it's supposed to rain tomorrow, so you might wait. 
The basil on the windowsill is due today."

Barnabee (alert): "Frost warning tonight—low of 28°F. You 
might want to cover the tomatoes or bring in any sensitive 
outdoor plants."
```

---

## 18. Energy Monitoring

### Purpose
Track home energy usage, solar production, and provide optimization suggestions.

### Data Model

```sql
CREATE TABLE energy_readings (
    id TEXT PRIMARY KEY,
    reading_type TEXT,               -- "consumption", "solar_production"
    reading_time TIMESTAMP,
    value_kwh REAL,
    source TEXT                      -- "smart_meter", "solar_inverter", "manual"
);

CREATE TABLE energy_daily (
    date DATE PRIMARY KEY,
    consumption_kwh REAL,
    solar_production_kwh REAL,
    net_kwh REAL,                    -- Negative = exported to grid
    peak_hour_usage_kwh REAL,
    cost_estimate_cents INTEGER
);

CREATE TABLE energy_goals (
    id TEXT PRIMARY KEY,
    goal_type TEXT,                  -- "reduce_consumption", "increase_solar"
    target_value REAL,
    target_unit TEXT,
    period TEXT,                     -- "daily", "monthly"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Integration

- **Smart meter**: Via Home Assistant utility_meter or Sense
- **Solar inverter**: Enphase, SolarEdge, Tesla APIs
- **Time-of-use rates**: Know peak vs off-peak pricing

### Voice Commands

| Intent | Examples |
|--------|----------|
| `energy.usage` | "How much energy did we use today?" |
| `energy.solar` | "How much solar did we produce?" |
| `energy.compare` | "How does this month compare to last month?" |
| `energy.peak` | "When do we use the most energy?" |
| `energy.cost` | "What's our estimated electric bill?" |
| `energy.tips` | "How can we reduce energy usage?" |

### Features

- **Real-time monitoring**: Current usage and production
- **Historical comparison**: Day, week, month trends
- **Peak usage alerts**: Warn during high-rate periods
- **Solar tracking**: Production vs consumption
- **Cost estimation**: Based on utility rates
- **Efficiency tips**: Suggestions based on usage patterns

### Example Interactions

```
Thom: "How much solar did we produce today?"
Barnabee: "Your solar panels produced 42 kilowatt-hours today—
that's above average for January! You used 38 kWh, so you 
actually exported 4 kWh back to the grid."

Thom: "What's our estimated electric bill this month?"
Barnabee: "Based on usage so far, you're looking at about $85 
for January. That's down from $110 last month—nice job! 
Your solar offset about $45 of that."

Barnabee (alert): "Heads up—we're entering peak rate hours. 
The AC is running and the dryer is going. You might save 
a few dollars by waiting on the laundry until 9 PM."

Thom: "How can we reduce energy usage?"
Barnabee: "Looking at your patterns, your biggest opportunities 
are: running the dishwasher during off-peak hours instead of 
dinner time, and the upstairs AC seems to run a lot more than 
downstairs—might be worth checking the insulation up there."
```

---

## Intent Taxonomy Additions

Add to `03-intent-classification.md`:

```
├── shopping
│   ├── add                    # "add milk to the list"
│   ├── remove                 # "remove eggs"
│   ├── query                  # "what's on my list"
│   ├── clear                  # "clear the list"
│   └── suggest                # "what do we need"
│
├── recipe
│   ├── search                 # "find a recipe"
│   ├── start                  # "start the recipe"
│   ├── next_step              # "next step"
│   ├── convert                # "tablespoons in a cup"
│   └── add_ingredients        # "add to shopping list"
│
├── package
│   ├── track                  # "track package"
│   ├── status                 # "where's my package"
│   └── list                   # "what packages"
│
├── appliance
│   ├── vacuum_control         # "start the vacuum"
│   ├── laundry_status         # "is the laundry done"
│   └── oven_control           # "preheat oven"
│
├── intercom
│   ├── announce               # "announce dinner"
│   └── call                   # "call the garage"
│
├── language
│   ├── translate              # "how do you say"
│   ├── practice               # "practice Spanish"
│   └── quiz                   # "quiz me"
│
├── routine
│   ├── run                    # "good morning"
│   ├── create                 # "create routine"
│   └── list                   # "what routines"
│
├── kids
│   ├── homework               # "help with homework"
│   ├── story                  # "tell me a story"
│   └── game                   # "let's play"
│
├── briefing
│   ├── morning                # "morning briefing"
│   └── evening                # "evening briefing"
│
├── habit
│   ├── log                    # "I took my vitamins"
│   ├── query                  # "did I exercise"
│   └── streak                 # "what's my streak"
│
├── inventory
│   ├── find                   # "where are the"
│   ├── add                    # "add to inventory"
│   ├── check                  # "do we have"
│   └── low_stock              # "what's running low"
│
├── maintenance
│   ├── due                    # "what maintenance is due"
│   ├── log                    # "I changed the filter"
│   └── warranty               # "is it under warranty"
│
├── pet
│   ├── feed                   # "I fed the dog"
│   ├── fed_query              # "did anyone feed the cat"
│   ├── medication             # "I gave Luna her pill"
│   └── appointment            # "when is the vet"
│
├── travel
│   ├── flight_status          # "status of my flight"
│   ├── packing                # "start a packing list"
│   ├── packed                 # "I packed the sunscreen"
│   └── itinerary              # "what's planned Tuesday"
│
├── entertainment
│   ├── recommend              # "what should I watch"
│   ├── family                 # "family movie night"
│   ├── watchlist              # "add to watchlist"
│   └── where                  # "where can I watch"
│
├── garden
│   ├── water                  # "I watered the tomatoes"
│   ├── needs_water            # "what needs watering"
│   └── care                   # "how do I care for"
│
├── energy
│   ├── usage                  # "how much energy today"
│   ├── solar                  # "solar production"
│   ├── cost                   # "estimated bill"
│   └── tips                   # "reduce energy usage"
│
└── guest
    ├── enable                 # "enable guest mode"
    └── disable                # "disable guest mode"
```

---

## Implementation Checklist

### Shopping Lists
- [ ] Database tables
- [ ] Voice commands
- [ ] Category organization
- [ ] Recipe integration
- [ ] Dashboard page

### Recipe Assistance
- [ ] Recipe storage
- [ ] Guided cooking mode
- [ ] Measurement conversions
- [ ] Step timers
- [ ] Shopping list integration

### Package Tracking
- [ ] Carrier integrations (or email parsing)
- [ ] Voice commands
- [ ] Delivery notifications
- [ ] Dashboard view

### Smart Appliances
- [ ] HA entity mapping
- [ ] Voice commands
- [ ] Cycle notifications
- [ ] Status queries

### Intercom
- [ ] Announce to all
- [ ] Room targeting
- [ ] Person targeting
- [ ] Two-way calls

### Language Learning
- [ ] Profile setup
- [ ] Vocabulary storage
- [ ] Translation
- [ ] Practice modes
- [ ] Progress tracking

### Guest Mode
- [ ] Access control
- [ ] Time limits
- [ ] Device targeting
- [ ] Audit logging

### Routines
- [ ] Routine storage
- [ ] Trigger types
- [ ] Action execution
- [ ] Voice creation
- [ ] Dashboard editor

### Kids Mode
- [ ] Kid profiles
- [ ] Content filtering
- [ ] Educational features
- [ ] Parental controls
- [ ] Activity logging

### Briefings
- [ ] Preference storage
- [ ] Content assembly
- [ ] Morning trigger
- [ ] Evening trigger
- [ ] Customization

### Habit Tracking
- [ ] Habit storage
- [ ] Quick logging
- [ ] Streak tracking
- [ ] Reminders
- [ ] Progress reports

### Home Inventory
- [ ] Location hierarchy
- [ ] Item tracking
- [ ] Quantity management
- [ ] Low stock alerts
- [ ] Search

### Home Maintenance
- [ ] Maintenance item tracking
- [ ] Service logging
- [ ] Warranty database
- [ ] Proactive reminders
- [ ] Vehicle maintenance

### Pet Care
- [ ] Pet profiles
- [ ] Feeding schedules and logging
- [ ] Medication tracking
- [ ] Vet appointments
- [ ] Family coordination (who fed)

### Travel Assistant
- [ ] Flight tracking integration
- [ ] Packing list templates
- [ ] Pack status tracking
- [ ] Itinerary management
- [ ] Delay notifications

### Entertainment
- [ ] User preference profiles
- [ ] Watch history
- [ ] Recommendation engine
- [ ] Streaming service awareness
- [ ] Watchlist management

### Garden/Plants
- [ ] Plant database
- [ ] Watering schedules
- [ ] Weather integration
- [ ] Care logging
- [ ] Frost/heat alerts

### Energy Monitoring
- [ ] Smart meter integration
- [ ] Solar inverter integration
- [ ] Usage tracking
- [ ] Cost estimation
- [ ] Peak usage alerts

---

## Acceptance Criteria

1. **Shopping lists** work with voice add/remove/query
2. **Recipes** can be followed step-by-step with voice
3. **Packages** show status via voice query
4. **Appliances** notify when cycles complete
5. **Announcements** reach target devices
6. **Language practice** tracks progress and adapts
7. **Guest mode** restricts access appropriately
8. **Routines** execute multi-step sequences
9. **Kids mode** filters content and tracks usage
10. **Briefings** deliver personalized summaries
11. **Habits** track streaks and send reminders
12. **Inventory** answers "where is" questions
13. **Maintenance** tracks service schedules and warranties
14. **Pets** manage feeding, vet visits, and medications
15. **Travel** tracks flights and manages packing
16. **Entertainment** recommends what to watch
17. **Garden** provides plant care reminders
18. **Energy** monitors usage and solar production

---

**End of Area 22: Extended Features**

# BarnabeeNet Capability Roadmap

**Last Updated:** January 2026  
**Status:** Planning Reference  
**Purpose:** Prioritized list of all potential capabilities, ordered by ease of development and usefulness

---

## Scoring System

| Ease | Description | Typical Effort |
|------|-------------|----------------|
| ⭐⭐⭐ | Easy | Pattern matching only, no external APIs, 1-2 days |
| ⭐⭐ | Medium | Needs LLM or simple API integration, 1-2 weeks |
| ⭐ | Hard | Complex integration, new infrastructure, 3+ weeks |

| Usefulness | Description | Usage Frequency |
|------------|-------------|-----------------|
| 🔥🔥🔥 | High | Daily use, especially by kids |
| 🔥🔥 | Medium | Weekly use, quality of life |
| 🔥 | Low | Occasional, nice to have |

---

## Already Implemented ✅

| Capability | Description |
|------------|-------------|
| Spelling | "spell dinosaur" → D I N O S A U R |
| Time/Date | "what time is it?" |
| Math | "what's 5 + 3?" |
| Greetings | "hello", "good morning" |
| Timers with actions | "set a pizza timer for 10 minutes" |
| Delayed actions | "in 5 minutes turn off the light" |
| Entity state queries | "is the office light on?" |
| Area queries | "how many lights are on downstairs?" |
| Battery status | "what batteries need changing?" |
| Temperature queries | "what's the temperature?" |
| Climate/thermostat | "what's the thermostat set to?" |
| Security queries | "are all the doors locked?" |
| Presence queries | "who's home?" |
| Media status | "what's playing?" |
| Cover/blind status | "are the blinds open?" |
| Last changed | "when was the door last opened?" |
| Brightness queries | "how bright is the light?" |
| Device control | "turn on the kitchen lights" |

---

## Tier 1: Easy + High Value (Do First)

These can be done in 1-2 days and provide high daily value.

### 1.1 Random Choices / Decisions
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥

Kids love these for games, decisions, and fairness.

| Command | Response |
|---------|----------|
| "flip a coin" | "Heads!" or "Tails!" |
| "roll a dice" | "You rolled a 4!" |
| "roll a d20" | "You rolled a 17!" |
| "pick a number between 1 and 10" | "I pick... 7!" |
| "pick someone to go first" | Randomly selects from present family members |
| "who should do the dishes?" | Randomly picks a kid |
| "yes or no" | "Yes!" or "No!" |
| "magic 8 ball" | Random fortune response |

**Implementation:** Add to InstantAgent with random.choice()

---

### 1.2 Jokes
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Response |
|---------|----------|
| "tell me a joke" | Random from joke database |
| "tell me a dad joke" | Filtered to dad jokes |
| "tell me a knock knock joke" | Interactive knock-knock |
| "tell me a riddle" | Riddle with answer on request |

**Implementation:** JSON file with categorized jokes, InstantAgent handler

---

### 1.3 Unit Conversions
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥

Essential for cooking and homework.

| Command | Response |
|---------|----------|
| "how many cups in a liter?" | "About 4.2 cups" |
| "convert 100 fahrenheit to celsius" | "That's about 38 degrees Celsius" |
| "how many ounces in a pound?" | "16 ounces" |
| "how many inches in a foot?" | "12 inches" |
| "how many feet in a mile?" | "5,280 feet" |

**Implementation:** Regex patterns + conversion functions in InstantAgent

---

### 1.4 Countdown to Events
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Response |
|---------|----------|
| "how many days until Christmas?" | "47 days until Christmas!" |
| "how many days until my birthday?" | Uses family profiles for birthdays |
| "how long until summer?" | Based on calendar |
| "countdown to vacation" | If event in calendar |

**Implementation:** Date calculations, integrate with family profiles for birthdays

---

### 1.5 Animal Sounds
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥 (young kids)

| Command | Response |
|---------|----------|
| "what does a cow say?" | "Moo!" (or play sound) |
| "what sound does an elephant make?" | Describes or plays sound |

**Implementation:** Text responses or audio files, InstantAgent

---

### 1.6 Counting & Number Help
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥 (young kids)

| Command | Response |
|---------|----------|
| "count to 10" | "1, 2, 3, 4, 5, 6, 7, 8, 9, 10!" |
| "what comes after 7?" | "8!" |
| "count by 2s to 20" | "2, 4, 6, 8, 10, 12, 14, 16, 18, 20!" |
| "count backwards from 10" | "10, 9, 8, 7, 6, 5, 4, 3, 2, 1, blastoff!" |

**Implementation:** Simple InstantAgent patterns

---

### 1.7 World Clock / Time Zones
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "what time is it in Tokyo?" | "It's 2:30 AM in Tokyo" |
| "what time is it in London?" | "It's 10:30 PM in London" |

**Implementation:** pytz + InstantAgent patterns

---

### 1.8 Undo / Cancel Last Action
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Action |
|---------|--------|
| "undo that" | Reverses last device action |
| "never mind" | Cancels pending confirmation |
| "cancel" | Stops current action |

**Implementation:** Track last action in session, ActionAgent handler

---

### 1.9 Say That Again / Repeat
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Action |
|---------|--------|
| "say that again" | Repeats last response |
| "repeat that" | Repeats last response |
| "what did you say?" | Repeats last response |
| "speak slower" | Adjusts TTS rate |

**Implementation:** Cache last response, TTS rate parameter

---

### 1.10 Simple Definitions
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Response |
|---------|----------|
| "what does 'ephemeral' mean?" | Dictionary definition |
| "define 'hypothesis'" | Definition appropriate to speaker age |

**Implementation:** Can use LLM (InteractionAgent) or free dictionary API

---

## Tier 2: Easy + Medium Value

### 2.1 Translation
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "how do you say hello in Spanish?" | "Hola!" |
| "translate 'thank you' to French" | "Merci!" |

**Implementation:** LLM-based (InteractionAgent handles naturally)

---

### 2.2 Fun Facts
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "tell me a fun fact" | Random interesting fact |
| "tell me a fact about space" | Category-filtered fact |

**Implementation:** JSON database of facts, InstantAgent

---

### 2.3 Story Generation
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥 (kids)

| Command | Response |
|---------|----------|
| "tell me a story about a dragon" | Short generated story |
| "tell me a bedtime story" | Calming story |

**Implementation:** LLM-based, age-appropriate based on speaker

---

### 2.4 Math Practice / Problems
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥 (kids)

| Command | Response |
|---------|----------|
| "give me a math problem" | Age-appropriate problem |
| "give me a multiplication problem" | e.g., "What's 7 times 8?" |
| "what's the answer?" | Reveals answer after attempt |

**Implementation:** Generate problems based on speaker's age profile

---

### 2.5 Trivia Questions
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "ask me a trivia question" | Random trivia |
| "let's play trivia" | Interactive game mode |

**Implementation:** Trivia database, track score in session

---

### 2.6 Would You Rather
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥 (kids)

| Command | Response |
|---------|----------|
| "would you rather" | Presents choice |
| "give me a would you rather" | Random scenario |

**Implementation:** JSON database of scenarios

---

### 2.7 Sunrise / Sunset Times
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "when does the sun set?" | "Sunset is at 5:47 PM today" |
| "when is sunrise?" | "Sunrise is at 7:12 AM" |

**Implementation:** HA sun integration or astral library

---

### 2.8 Moon Phase
**Ease:** ⭐⭐ | **Usefulness:** 🔥

| Command | Response |
|---------|----------|
| "what phase is the moon?" | "Tonight is a waxing gibbous" |

**Implementation:** Astronomy library or HA integration

---

### 2.9 Compliments / Encouragement
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥 (kids)

| Command | Response |
|---------|----------|
| "give me a compliment" | Random encouraging phrase |
| "I'm feeling down" | Supportive response |
| "motivate me" | Motivational quote |

**Implementation:** JSON database of compliments/quotes

---

### 2.10 Sleep Timer
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "stop playing music in 30 minutes" | Sets timer to pause media |
| "sleep timer 1 hour" | Stops media after duration |

**Implementation:** Extension of timer system with media control action

---

## Tier 3: Medium Difficulty + High Value

### 3.1 Weather Integration
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Response |
|---------|----------|
| "what's the weather?" | Current conditions |
| "will it rain today?" | Precipitation forecast |
| "what's the forecast for tomorrow?" | Tomorrow's weather |
| "do I need an umbrella?" | Based on forecast |
| "is it going to snow?" | Precipitation type |

**Implementation:** HA weather integration or weather API

---

### 3.2 Phone Finder (Phase 1)
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Response |
|---------|----------|
| "find Xander's phone" | Triggers alarm on phone |
| "where is Penelope's phone?" | Last known location |
| "is Oliver's phone charged?" | Battery level |

**Implementation:** HA Companion App integration (see Phone Finder doc)

---

### 3.3 Chore Tracking / Star System
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥🔥 (family)

| Command | Response |
|---------|----------|
| "Xander finished his homework" | "+1 star for Xander!" |
| "how many stars does Viola have?" | "Viola has 12 stars this week" |
| "whose turn to do dishes?" | Rotation tracker |
| "what chores are left today?" | Family chore list |

**Implementation:** Memory storage for chore/star tracking

---

### 3.4 Homework Timer / Pomodoro
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥 (kids)

| Command | Response |
|---------|----------|
| "start homework time" | 25-min focus timer |
| "start a pomodoro" | Pomodoro with breaks |
| "how long have I been studying?" | Session tracking |

**Implementation:** Extension of timer system with DND integration

---

### 3.5 Calendar Integration
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Response |
|---------|----------|
| "what's on my calendar today?" | Today's events |
| "when is the next appointment?" | Next scheduled event |
| "add dentist Tuesday at 3pm" | Creates event |
| "what's happening this weekend?" | Weekend overview |

**Implementation:** HA calendar integration or Google Calendar API

---

### 3.6 Shopping List
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥🔥

| Command | Response |
|---------|----------|
| "add milk to the shopping list" | Adds item |
| "what's on my shopping list?" | Reads list |
| "clear the shopping list" | Empties list |

**Implementation:** HA shopping list or Todoist/custom list

---

### 3.7 Bedtime Countdown
**Ease:** ⭐⭐⭐ | **Usefulness:** 🔥🔥🔥 (kids)

| Command | Response |
|---------|----------|
| "how long until bedtime?" | Based on family profile |
| "bedtime in 15 minutes" | Starts countdown + announcements |

**Implementation:** Family profile bedtimes + announcement timer

---

### 3.8 Recipe Help
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "how do I make pancakes?" | LLM recipe |
| "what can I substitute for eggs?" | LLM substitution |
| "convert this recipe for 8 people" | Scaling help |

**Implementation:** LLM-based (InteractionAgent)

---

### 3.9 Air Quality / Pollen
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "what's the air quality?" | AQI reading |
| "is pollen high today?" | Pollen count |
| "should I run outside today?" | Considers AQI + weather |

**Implementation:** Weather API with AQI data

---

### 3.10 Sports Scores
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "did the Panthers win?" | Latest game result |
| "what's the score of the game?" | Live score if playing |

**Implementation:** Sports API integration

---

## Tier 4: Medium Difficulty + Medium Value

### 4.1 Confirmation Read-back
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "set alarm for 7am" | "I'll set an alarm for 7am, is that right?" |
| (high-risk actions) | Confirms before executing |

**Implementation:** Confirmation flow in ActionAgent

---

### 4.2 Follow-up Mode
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Description |
|---------|-------------|
| (continues listening) | After response, listens for ~5 seconds without wake word |

**Implementation:** Modify wake word detection state machine

---

### 4.3 Quick Notes / Voice Memos
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "note: call the dentist" | Saves note |
| "remind me to buy eggs" | Creates reminder |
| "what are my notes?" | Lists recent notes |

**Implementation:** Memory storage + recall

---

### 4.4 Traffic / Commute
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "how long to get to work?" | Drive time estimate |
| "what's traffic like?" | Traffic conditions |

**Implementation:** HA waze integration or Google Maps API

---

### 4.5 Package Tracking
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "do I have any packages coming?" | Delivery status |
| "when will my package arrive?" | Estimated delivery |

**Implementation:** HA package tracking integrations

---

### 4.6 Guest WiFi
**Ease:** ⭐⭐ | **Usefulness:** 🔥

| Command | Response |
|---------|----------|
| "what's the wifi password?" | Guest network credentials |
| "create a guest wifi password" | Generates temporary password |

**Implementation:** Router API integration

---

### 4.7 Appliance Notifications
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "tell me when the dryer is done" | Proactive notification |
| "is the washing machine done?" | Checks sensor |

**Implementation:** HA integration with smart plugs/appliances

---

### 4.8 Energy Usage
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥

| Command | Response |
|---------|----------|
| "how much energy are we using?" | Current power draw |
| "what's our electricity bill this month?" | Usage estimate |

**Implementation:** HA energy integration

---

### 4.9 Printer Status
**Ease:** ⭐⭐ | **Usefulness:** 🔥

| Command | Response |
|---------|----------|
| "is the printer ready?" | Printer status |
| "how much ink is left?" | Ink levels |

**Implementation:** HA printer integration

---

### 4.10 Pet Reminders
**Ease:** ⭐⭐ | **Usefulness:** 🔥🔥 (if pets)

| Command | Response |
|---------|----------|
| "did anyone feed the dog?" | Checks/logs feeding |
| "log that I fed the cat" | Records feeding time |

**Implementation:** Memory-based tracking

---

## Tier 5: Hard + High Value

### 5.1 Find My Phone (Custom App - Phase 3)
**Ease:** ⭐ | **Usefulness:** 🔥🔥🔥

Custom BarnabeeNet mobile app for reliable phone finding with:
- Foreground service for reliability
- Custom TTS voice
- Battery monitoring
- Silent mode bypass

**Implementation:** Flutter app (see Phone Finder doc)

---

### 5.2 Full Calendar Management
**Ease:** ⭐ | **Usefulness:** 🔥🔥🔥

Complete family calendar with:
- Conflict detection
- Shared visibility
- Transportation coordination
- Event creation/modification

**Implementation:** Deep calendar API integration

---

### 5.3 Spatial Awareness / Multi-Room
**Ease:** ⭐ | **Usefulness:** 🔥🔥🔥

| Capability | Description |
|------------|-------------|
| Conversation handoff | Continue conversation across rooms |
| Notification routing | Deliver alerts to correct room |
| Privacy zones | Respect room-specific rules |

**Implementation:** Room graph model (documented in Features doc)

---

### 5.4 Proactive Intelligence
**Ease:** ⭐ | **Usefulness:** 🔥🔥🔥

| Capability | Description |
|------------|-------------|
| Pattern learning | "You usually turn on lights at 6pm" |
| Automation suggestions | "Should I automate this?" |
| Predictive actions | Pre-warm house before arrival |

**Implementation:** ML-based pattern detection

---

### 5.5 Age-Appropriate Response Adaptation
**Ease:** ⭐ | **Usefulness:** 🔥🔥🔥

Automatically adjust vocabulary, complexity, and content based on who's listening.

**Implementation:** Speaker ID + profile-based response templating

---

## Tier 6: Hard + Medium Value

### 6.1 Voice Training
**Ease:** ⭐ | **Usefulness:** 🔥🔥

Improve speaker recognition for specific voices.

---

### 6.2 Pronunciation Correction
**Ease:** ⭐ | **Usefulness:** 🔥🔥

"That's not how you say my name" → learns correct pronunciation.

---

### 6.3 AR Glasses Integration
**Ease:** ⭐ | **Usefulness:** 🔥🔥

Visual notifications, status overlays, navigation.

---

### 6.4 Wearable Gestures
**Ease:** ⭐ | **Usefulness:** 🔥🔥

Watch-based control: double-tap, crown twist, etc.

---

### 6.5 Meeting Proxy Mode
**Ease:** ⭐ | **Usefulness:** 🔥🔥

Attend meetings on your behalf with voice synthesis.

---

### 6.6 Email Integration
**Ease:** ⭐ | **Usefulness:** 🔥🔥

Read and summarize emails, send quick replies.

---

## Tier 7: Novel / Differentiating Features

These are unique to BarnabeeNet and not available in commercial assistants.

| Feature | Description | Difficulty |
|---------|-------------|------------|
| Family digest | "What happened at home today?" - aggregated summary | ⭐ |
| Conflict resolution | Mediate temperature/music preferences fairly | ⭐⭐ |
| Chore accountability | "Who took out the trash last?" with history | ⭐⭐ |
| Homework verification | Track study time and completion | ⭐⭐ |
| Explanation caching | Remember how concepts were explained to each child | ⭐ |
| Preference negotiation | "Elizabeth wants 72°, Thom wants 68° - setting to 70°" | ⭐⭐ |
| Device intent logging | "Why did the lights turn on?" - explain automations | ⭐⭐ |
| Parental override | Parent can authorize restricted actions for child | ⭐⭐ |
| Guest arrival prediction | "Your guests should arrive in 15 minutes" | ⭐ |
| Room-appropriate volume | Auto-adjust based on room size and ambient noise | ⭐ |
| Predictive preheating | Start oven when cooking plans mentioned | ⭐ |

---

## Implementation Priority Recommendation

### Sprint 1 (Next 2 weeks)
1. Random choices (flip coin, roll dice, pick number)
2. Jokes database
3. Unit conversions
4. Countdown to events
5. Counting help
6. Undo last action
7. Say that again / repeat

### Sprint 2
1. World clock
2. Fun facts
3. Math practice
4. Weather integration
5. Compliments/encouragement
6. Sleep timer

### Sprint 3
1. Phone finder (Phase 1 - HA Companion)
2. Chore tracking basics
3. Homework timer
4. Bedtime countdown
5. Shopping list

### Sprint 4+
1. Calendar integration
2. Recipe help
3. Phone finder Phase 2 evaluation
4. Novel features based on family feedback

---

## Notes

- **Whisper mode** is marked as difficult because detecting whispered speech requires audio analysis that current STT doesn't handle well
- **Follow-up mode** requires modifying the wake word detection pipeline
- Many "hard" features could become "medium" if good APIs exist
- Kid-focused features should be prioritized as they're the primary users alongside parents
- All features should respect the per-listener adaptation system once implemented

---

*This document should be updated as features are implemented or priorities change.*

# Area 09: Dashboard & Admin

**Version:** 2.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 01, 08 (Data Layer, Self-Improvement)  
**Phase:** Extended Functionality  

---

## 1. Overview

### 1.1 Purpose

The Dashboard provides full visibility into Barnabee's operations and control over system configuration. It is purpose-built for quick access to what you need: testing commands, managing memories, reviewing logs, tuning intents, controlling self-improvement, and configuring the system.

### 1.2 Design Principles

1. **Purpose-built pages:** Each page serves a specific function. Get what you need immediately.
2. **Full logging:** Every operation is visible and searchable.
3. **Local-first:** Dashboard runs on home network only. No cloud dependency.
4. **Responsive:** Optimized for desktop, phone, and Samsung Fold 6 (inner and outer screens).
5. **Complete control:** All configuration through UI, no .env file editing.

### 1.3 Access Levels

| Role | Capabilities |
|------|--------------|
| Super User (Thom) | Full access: all pages, all features |
| Family Member | Personal memories, chat test, limited config |
| Guest | None (no dashboard access) |

---

## 2. Dashboard Pages

### 2.1 Navigation Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DASHBOARD NAVIGATION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  HOME   │ │  CHAT   │ │ MEMORY  │ │ INTENTS │ │ IMPROVE │ │ CONFIG  │   │
│  │         │ │  TEST   │ │  LOGS   │ │         │ │         │ │         │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                                                                              │
│  + LOGS (full system logging - accessible from header icon)                  │
│                                                                              │
│  7 Pages Total:                                                              │
│  1. Home      - Health at a glance, today's stats, recent activity          │
│  2. Chat Test - Test commands without voice, debug classification flow       │
│  3. Memory    - All memory operations, search, edit, audit trail            │
│  4. Intents   - Classification management, training examples, accuracy       │
│  5. Improve   - Self-improvement control, user suggestions, history          │
│  6. Config    - All settings, credentials, thresholds                        │
│  7. Logs      - Full system logging, search, filter, export                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Page Purposes

| Page | Purpose | Key Actions |
|------|---------|-------------|
| **Home** | Health at a glance | View status, today's stats, active alerts, recent activity |
| **Chat Test** | Test commands without voice | Type commands, see full classification flow, debug issues |
| **Memory Logs** | All memory operations | Search, browse, edit, delete, view audit trail |
| **Intents** | Classification management | View intents, add training examples, see accuracy |
| **Improve** | Self-improvement control | Review pending, approve/reject, add your suggestions |
| **Config** | All settings | HA connection, LLM providers, thresholds, credentials |
| **Logs** | Full system logging | Filter by level/component/time, search, export |

---

## 3. Responsive Design

### 3.1 Target Devices

| Device | Screen Width | Layout |
|--------|--------------|--------|
| Fold 6 Outer | 344px | Single column, bottom nav, essential info |
| Phone | 375-428px | Single column, bottom nav |
| Fold 6 Inner | 884px | Two column, nav rail, medium detail |
| Tablet | 768-1024px | Two column, collapsible sidebar |
| Desktop | 1200px+ | Full sidebar, multi-column, full detail |

### 3.2 Responsive Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RESPONSIVE BREAKPOINTS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FOLD 6 OUTER (344px)          FOLD 6 INNER (884px)       DESKTOP (1200px+) │
│  ───────────────────          ─────────────────────       ───────────────── │
│                                                                              │
│  ┌───────────────┐            ┌──────────────────┐       ┌─────────────────┐│
│  │ ≡ Barnabee    │            │ ≡ Barnabee       │       │ ☰ Home Chat ... ││
│  ├───────────────┤            ├──────────────────┤       ├─────┬───────────┤│
│  │               │            │      │           │       │     │           ││
│  │  Single       │            │ Nav  │  Content  │       │ Nav │  Content  ││
│  │  Column       │            │ Rail │  Area     │       │     │  Area     ││
│  │  Stack        │            │      │           │       │     │           ││
│  │               │            │      │           │       │     │           ││
│  │               │            │      │           │       │     │           ││
│  │               │            │      │           │       │     │           ││
│  ├───────────────┤            │      │           │       │     │           ││
│  │ [Nav Icons]   │            │      │           │       │     │           ││
│  └───────────────┘            └──────────────────┘       └─────┴───────────┘│
│                                                                              │
│  • Bottom nav               • Collapsed sidebar          • Full sidebar      │
│  • Full-width cards         • 2-column where useful      • Multi-column     │
│  • Swipe gestures           • Tap + keyboard             • Full keyboard    │
│  • Essential info only      • Medium detail              • Full detail      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 CSS Breakpoints

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    screens: {
      'fold-outer': '344px',    // Fold 6 outer screen
      'xs': '475px',            // Small phones
      'sm': '640px',            // Large phones
      'md': '768px',            // Tablets
      'fold-inner': '884px',    // Fold 6 inner screen
      'lg': '1024px',           // Small desktop
      'xl': '1280px',           // Desktop
      '2xl': '1536px',          // Large desktop
    }
  }
}
```

### 3.4 Responsive Component Pattern

```tsx
// Example: Stats Grid
function StatsGrid({ stats }) {
  return (
    <div className="grid gap-4 
                    grid-cols-2              /* Fold outer: 2 col */
                    sm:grid-cols-2           /* Phone: 2 col */
                    fold-inner:grid-cols-4   /* Fold inner: 4 col */
                    lg:grid-cols-4           /* Desktop: 4 col */">
      {stats.map(stat => (
        <StatCard key={stat.id} {...stat} />
      ))}
    </div>
  );
}

// Example: Navigation
function Navigation() {
  return (
    <>
      {/* Mobile: Bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 
                      flex justify-around p-2 bg-white border-t
                      fold-inner:hidden">
        <NavIcon to="/" icon="home" />
        <NavIcon to="/chat" icon="chat" />
        <NavIcon to="/memory" icon="brain" />
        <NavIcon to="/intents" icon="target" />
        <NavIcon to="/improve" icon="sparkles" />
        <NavIcon to="/config" icon="settings" />
      </nav>
      
      {/* Desktop: Sidebar */}
      <aside className="hidden fold-inner:flex 
                        flex-col w-64 h-screen 
                        border-r bg-gray-50">
        <NavItem to="/" label="Home" icon="home" />
        <NavItem to="/chat" label="Chat Test" icon="chat" />
        <NavItem to="/memory" label="Memory Logs" icon="brain" />
        <NavItem to="/intents" label="Intents" icon="target" />
        <NavItem to="/improve" label="Improve" icon="sparkles" />
        <NavItem to="/config" label="Config" icon="settings" />
        <NavItem to="/logs" label="Logs" icon="scroll" />
      </aside>
    </>
  );
}
```

---

## 4. Page Specifications

### 4.1 Home Page

**Purpose:** Health at a glance. What you see immediately when opening the dashboard.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HOME PAGE                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ✅ System Healthy        CPU: 23%  GPU: 45%  Mem: 62%               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Today's Stats                                                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │ Commands │ │ Memories │ │ Avg      │ │ LLM      │                       │
│  │ Today    │ │ Created  │ │ Latency  │ │ Fallback │                       │
│  │   247    │ │    12    │ │  342ms   │ │   4.2%   │                       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                       │
│                                                                              │
│  Active Alerts                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ⚠️ High wake word false positive rate (0.8/hr) - View Details       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Recent Activity (live updating)                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 10:45  "turn on kitchen lights" → ✅ Executed               [View] │    │
│  │ 10:43  Memory created: "Coffee preference: black"           [View] │    │
│  │ 10:41  "what's the weather" → ✅ Answered                   [View] │    │
│  │ 10:38  "set timer for 5 minutes" → ✅ Timer set             [View] │    │
│  │ 10:35  LLM fallback: "liv room lamp" resolved               [View] │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Quick Actions                                                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                              │
│  │ Test Chat  │ │ View Logs  │ │ Add Memory │                              │
│  └────────────┘ └────────────┘ └────────────┘                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data Structure:**

```typescript
interface HomePageData {
  health: {
    status: 'healthy' | 'degraded' | 'unhealthy';
    cpu_percent: number;
    gpu_percent: number;
    memory_percent: number;
    components: ComponentHealth[];
  };
  
  today: {
    total_commands: number;
    memories_created: number;
    avg_latency_ms: number;
    llm_fallback_rate: number;
  };
  
  alerts: {
    severity: 'warning' | 'error';
    message: string;
    details_url: string;
    timestamp: string;
  }[];
  
  recent_activity: {
    timestamp: string;
    type: 'command' | 'memory' | 'improvement' | 'error';
    summary: string;
    status: 'success' | 'warning' | 'error';
    details_id: string;
  }[];
}
```

### 4.2 Chat Test Page

**Purpose:** Test commands without speaking. Debug the full classification flow.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CHAT TEST PAGE                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Test a command or question                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ turn on the liv room lamp                                       [⏎] │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  [Execute for Real] [Dry Run Only] [Clear]                                  │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ YOU: "turn on the liv room lamp"                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─ Classification ────────────────────────────────────────────────────┐    │
│  │ Intent: light_control                                               │    │
│  │ Confidence: 0.94                                                    │    │
│  │ Path: embedding (23ms)                                              │    │
│  │                                                                      │    │
│  │ Entities:                                                           │    │
│  │   • device: "liv room lamp" (raw)                                   │    │
│  │   • action: "on"                                                    │    │
│  │                                                                      │    │
│  │ Entity Resolution: ❌ No exact match                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─ LLM Intelligent Fallback ──────────────────────────────────────────┐    │
│  │ Resolved to: light.living_room_lamp                                 │    │
│  │                                                                      │    │
│  │ Reasoning: "liv room" is likely shorthand for "living room".        │    │
│  │ The entity "light.living_room_lamp" (Living Room Lamp) matches      │    │
│  │ both the location and the device type "lamp".                       │    │
│  │                                                                      │    │
│  │ Confidence: 0.92                                                    │    │
│  │ Latency: 287ms                                                      │    │
│  │                                                                      │    │
│  │ 💡 Suggestion: Add alias "liv room lamp" → light.living_room_lamp   │    │
│  │ [Add to Improvements]                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─ Execution ─────────────────────────────────────────────────────────┐    │
│  │ Service: light.turn_on                                              │    │
│  │ Entity: light.living_room_lamp                                      │    │
│  │ Result: ✅ Success                                                  │    │
│  │ State Change: off → on                                              │    │
│  │ Latency: 45ms                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ BARNABEE: "I've turned on the living room lamp."                    │    │
│  │                                                                      │    │
│  │ Total latency: 542ms                                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  [Add to Training Data] [Report Issue] [View Full Logs]                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data Structure:**

```typescript
interface ChatTestResult {
  input: string;
  
  classification: {
    intent: string;
    confidence: number;
    path: 'pattern' | 'embedding' | 'llm';
    latency_ms: number;
    entities: {
      type: string;
      value: string;
      raw_value: string;
      resolved_entity_id?: string;
    }[];
  };
  
  llm_fallback?: {
    triggered: boolean;
    resolved_entity_id: string;
    reasoning: string;
    confidence: number;
    latency_ms: number;
    suggested_alias?: {
      alias: string;
      target: string;
    };
  };
  
  execution?: {
    service: string;
    entity_id: string;
    success: boolean;
    previous_state?: string;
    new_state?: string;
    latency_ms: number;
    error?: string;
  };
  
  response: {
    text: string;
    total_latency_ms: number;
  };
}
```

### 4.3 Memory Logs Page

**Purpose:** Full visibility into what Barnabee remembers. Search, browse, edit, audit.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MEMORY LOGS PAGE                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 🔍 Search memories...                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Filters: [Type ▼] [Source ▼] [Owner ▼] [Date Range ▼] [Status ▼]          │
│                                                                              │
│  ┌─ Memory ────────────────────────────────────────────────────────────┐    │
│  │ CREATED  Jan 27, 10:43am                                            │    │
│  │                                                                      │    │
│  │ "Thom likes his coffee black"                                       │    │
│  │                                                                      │    │
│  │ Type: preference    Source: conversation    Owner: thom             │    │
│  │ Keywords: coffee, preference, black                                 │    │
│  │                                                                      │    │
│  │ Full Content:                                                       │    │
│  │ During morning conversation, Thom mentioned he prefers black        │    │
│  │ coffee, no sugar, no cream. He emphasized "just black."             │    │
│  │                                                                      │    │
│  │ Access History: 3 times (last: Jan 27, 2:15pm)                      │    │
│  │                                                                      │    │
│  │ [Edit] [Delete] [View Source] [Access History]                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─ Memory ────────────────────────────────────────────────────────────┐    │
│  │ ACCESSED  Jan 27, 9:15am  (accessed 5 times total)                  │    │
│  │                                                                      │    │
│  │ "Elizabeth's birthday is March 15"                                  │    │
│  │                                                                      │    │
│  │ Type: fact    Source: explicit    Owner: thom                       │    │
│  │                                                                      │    │
│  │ Last query that retrieved this: "when is elizabeth's birthday"      │    │
│  │                                                                      │    │
│  │ [Edit] [Delete] [View Source] [Access History]                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Showing 1-10 of 247 memories    [← Previous] [Next →]                      │
│                                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  [Show Deleted] [+ Create Memory] [Export All] [Memory Stats]               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data Structure:**

```typescript
interface MemoryListItem {
  id: string;
  summary: string;
  content: string;
  memory_type: 'fact' | 'preference' | 'decision' | 'event' | 'person' | 'project' | 'meeting' | 'journal';
  source_type: 'explicit' | 'conversation' | 'meeting' | 'journal';
  source_id?: string;
  owner: string;
  keywords: string[];
  
  created_at: string;
  updated_at: string;
  last_accessed?: string;
  access_count: number;
  
  status: 'active' | 'deleted';
  deleted_at?: string;
  deleted_by?: string;
}

interface MemoryAccessLog {
  timestamp: string;
  query: string;
  session_id: string;
}
```

### 4.4 Intents Page

**Purpose:** Understand and improve how Barnabee classifies commands.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  INTENTS PAGE                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Intent Categories                    Intent Detail                          │
│  ──────────────────                  ──────────────                          │
│                                                                              │
│  ┌───────────────────┐              ┌─────────────────────────────────────┐ │
│  │ ▼ HOME_CONTROL    │              │ light_control                       │ │
│  │   ● light_control │◄─────────────│                                     │ │
│  │   ○ lock_control  │              │ Training Examples: 47               │ │
│  │   ○ climate_ctrl  │              │ Accuracy: 97.2%                     │ │
│  │   ○ cover_control │              │ Avg Confidence: 0.91                │ │
│  │   ○ media_control │              │ LLM Fallback Rate: 3.2%             │ │
│  │                   │              │                                     │ │
│  │ ▶ INFORMATION     │              │ ─────────────────────────────────── │ │
│  │   (12 intents)    │              │                                     │ │
│  │                   │              │ Example Utterances:                 │ │
│  │ ▶ MEMORY          │              │ • "turn on the lights"              │ │
│  │   (4 intents)     │              │ • "switch off bedroom light"        │ │
│  │                   │              │ • "dim living room to 50%"          │ │
│  │ ▶ CALENDAR        │              │ • "lights on in the kitchen"        │ │
│  │   (6 intents)     │              │ • "can you turn off all lights"     │ │
│  │                   │              │                                     │ │
│  │ ▶ TASK            │              │ ─────────────────────────────────── │ │
│  │   (5 intents)     │              │                                     │ │
│  │                   │              │ Recent Misclassifications:          │ │
│  │ ▶ SYSTEM          │              │ ⚠️ "lights please" → unknown        │ │
│  │   (3 intents)     │              │    Correct: light_control           │ │
│  │                   │              │    [Add as Training Example]        │ │
│  │                   │              │                                     │ │
│  │                   │              │ ⚠️ "lamp on" → media_control        │ │
│  │                   │              │    Correct: light_control           │ │
│  │                   │              │    [Add as Training Example]        │ │
│  │                   │              │                                     │ │
│  │                   │              │ ─────────────────────────────────── │ │
│  │                   │              │                                     │ │
│  │                   │              │ [+ Add Example] [Edit Intent]       │ │
│  │                   │              │ [View Confusion Matrix]             │ │
│  └───────────────────┘              └─────────────────────────────────────┘ │
│                                                                              │
│  [+ Add New Intent] [Import Training Data] [Export] [Retrain Classifier]    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data Structure:**

```typescript
interface IntentCategory {
  name: string;
  intents: Intent[];
  total_examples: number;
}

interface Intent {
  name: string;
  category: string;
  description: string;
  
  training_examples: number;
  accuracy: number;
  avg_confidence: number;
  llm_fallback_rate: number;
  
  example_utterances: string[];
  
  recent_misclassifications: {
    utterance: string;
    predicted_intent: string;
    correct_intent: string;
    timestamp: string;
  }[];
}
```

### 4.5 Self-Improvement Page

**Purpose:** Control how Barnabee learns. Review auto-generated improvements. Add your own suggestions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SELF-IMPROVEMENT PAGE                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ ADD YOUR SUGGESTION ───────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  Type: [Entity Alias ▼]                                             │    │
│  │                                                                      │    │
│  │  When I say: [liv room lamp                                     ]   │    │
│  │  I mean:     [light.living_room_lamp                        ▼]      │    │
│  │                                                                      │    │
│  │  Note: [optional context                                        ]   │    │
│  │                                                                      │    │
│  │  [Submit Suggestion]                                                │    │
│  │                                                                      │    │
│  │  Or choose: [New Training Example] [New Synonym] [New Pattern]      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  PENDING IMPROVEMENTS (3)                           [Auto-approve Tier 1]   │
│  ─────────────────────────                                                  │
│                                                                              │
│  ┌─ Auto-Generated ────────────────────────────────────────────────────┐    │
│  │ 🔄 Entity Alias | Tier 1 (auto-approvable)                          │    │
│  │                                                                      │    │
│  │ Add aliases for light.living_room_lamp:                             │    │
│  │   • "liv room lamp" (seen 5 times)                                  │    │
│  │   • "living lamp" (seen 3 times)                                    │    │
│  │                                                                      │    │
│  │ Source: LLM fallback resolutions                                    │    │
│  │ Shadow Test: ✅ Passed (no regressions, +2 correct)                 │    │
│  │                                                                      │    │
│  │ [✓ Approve] [✗ Reject] [View Test Details]                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─ Your Suggestion ───────────────────────────────────────────────────┐    │
│  │ 📝 Training Example | Tier 1                                        │    │
│  │                                                                      │    │
│  │ Add "lights please" as example for intent: light_control            │    │
│  │                                                                      │    │
│  │ Submitted: Jan 27, 9:00am by thom                                   │    │
│  │ Shadow Test: ✅ Passed                                              │    │
│  │                                                                      │    │
│  │ [✓ Approve] [✗ Reject] [Edit] [View Test Details]                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  RECENTLY APPLIED (12 this week)                                            │
│  ───────────────────────────────                                            │
│  ✅ Added 3 aliases for "kitchen lights" - Jan 26, 3:00pm                   │
│  ✅ Added exemplar "lights please" → light_control - Jan 25, 10:00am        │
│  ⏪ Rolled back: synonym change caused regression - Jan 24, 8:00pm          │
│  ✅ Your suggestion: "bedroom lamp" alias - Jan 24, 2:00pm                  │
│                                                                              │
│  [View All History] [Export Learning Data] [Improvement Stats]              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data Structure:**

```typescript
interface UserSuggestion {
  type: 'alias' | 'training_example' | 'synonym' | 'pattern';
  source_text: string;        // "When I say this..."
  target: string;             // "I mean this..."
  note?: string;
  submitted_by: string;
  submitted_at: string;
}

interface PendingImprovement {
  id: string;
  type: 'alias' | 'exemplar' | 'synonym' | 'pattern';
  tier: 1 | 2;
  source: 'auto' | 'user_suggestion' | 'voice_command';
  
  description: string;
  details: {
    aliases?: string[];
    entity_id?: string;
    utterance?: string;
    intent?: string;
    occurrence_count?: number;
  };
  
  shadow_test: {
    passed: boolean;
    accuracy_before: number;
    accuracy_after: number;
    new_correct: number;
    regressions: string[];
  };
  
  created_at: string;
  submitted_by?: string;
}

interface AppliedImprovement {
  id: string;
  type: string;
  description: string;
  applied_at: string;
  applied_by: string;
  rolled_back?: boolean;
  rolled_back_at?: string;
  rollback_reason?: string;
}
```

### 4.6 Config Page

**Purpose:** All settings in one place. No .env file editing required.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CONFIG PAGE                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─ Home Assistant ─────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  URL:    [http://homeassistant.local:8123                        ]   │   │
│  │  Token:  [••••••••••••••••••••••••••••••••] [Show] [Test]            │   │
│  │                                                                       │   │
│  │  Status: ✅ Connected                                                │   │
│  │  Entities: 2,291 loaded | Last refresh: 2 min ago [Refresh Now]      │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ LLM Providers ──────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Primary: Azure OpenAI                                               │   │
│  │    Endpoint: [https://xxx.openai.azure.com                       ]   │   │
│  │    API Key:  [••••••••••••••••••] [Test]                             │   │
│  │    Model:    [gpt-4o                                             ]   │   │
│  │    Status:   ✅ Connected                                            │   │
│  │                                                                       │   │
│  │  Fallback: Ollama (Local)                                            │   │
│  │    URL:      [http://localhost:11434                             ]   │   │
│  │    Model:    [mistral:7b                                         ]   │   │
│  │    Status:   ✅ Available                                            │   │
│  │                                                                       │   │
│  │  [+ Add Provider]                                                    │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Classification ─────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Pattern match threshold:     [0.95 ───●───] (higher = fewer LLM)   │   │
│  │  Embedding threshold:         [0.85 ──●────]                         │   │
│  │  LLM fallback enabled:        [✓] Always try LLM if unsure           │   │
│  │  Speculative execution:       [✓] For confidence > [0.90 ─●──]       │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Self-Improvement ───────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Auto-apply Tier 1 changes:   [✓] Aliases, synonyms, exemplars       │   │
│  │  Signal threshold:            [3  ──●──] occurrences before propose  │   │
│  │  Shadow test required:        [✓] Always test before applying        │   │
│  │  Monitoring window:           [24 ───●─] hours                       │   │
│  │  Auto-rollback on regression: [✓]                                    │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─ Voice Pipeline ─────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Wake word sensitivity:       [0.5 ──●──] (higher = more sensitive)  │   │
│  │  Silence timeout:             [2000 ─●──] ms                         │   │
│  │  TTS Voice:                   [Kokoro - Warm ▼]                      │   │
│  │  TTS Speed:                   [1.0 ──●──]                            │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  [Save All Changes] [Reset to Defaults] [Export Config] [Import Config]     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.7 Logs Page

**Purpose:** Full system visibility. Debug issues. Audit everything.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LOGS PAGE                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 🔍 Search logs...                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Level: [All ▼]  Component: [All ▼]  Time: [Last Hour ▼]  [Live Tail 🔴]   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │ 10:45:23.456  INFO   voice.pipeline                                 │    │
│  │ Wake word detected, starting session: sess_abc123                   │    │
│  │ Device: kitchen_speaker | Confidence: 0.92                          │    │
│  │ ─────────────────────────────────────────────────────────────────── │    │
│  │                                                                      │    │
│  │ 10:45:24.102  INFO   voice.stt                                      │    │
│  │ Transcription complete                                              │    │
│  │ Text: "turn on the lights" | Confidence: 0.96 | Latency: 646ms      │    │
│  │ ─────────────────────────────────────────────────────────────────── │    │
│  │                                                                      │    │
│  │ 10:45:24.145  INFO   nlu.classifier                                 │    │
│  │ Classification: light_control (0.96)                                │    │
│  │ Path: embedding | Latency: 23ms                                     │    │
│  │ ─────────────────────────────────────────────────────────────────── │    │
│  │                                                                      │    │
│  │ 10:45:24.190  INFO   ha.resolver                                    │    │
│  │ Entity resolved: "lights" → light.living_room                       │    │
│  │ Method: context (user in living room)                               │    │
│  │ ─────────────────────────────────────────────────────────────────── │    │
│  │                                                                      │    │
│  │ 10:45:24.312  INFO   ha.executor                                    │    │
│  │ Command executed: light.turn_on                                     │    │
│  │ Entity: light.living_room | Result: success | Latency: 45ms         │    │
│  │ ─────────────────────────────────────────────────────────────────── │    │
│  │                                                                      │    │
│  │ 10:45:24.589  INFO   voice.tts                                      │    │
│  │ Response synthesized: "Done" | Latency: 277ms                       │    │
│  │ ─────────────────────────────────────────────────────────────────── │    │
│  │                                                                      │    │
│  │ 10:45:24.612  INFO   voice.pipeline                                 │    │
│  │ Session complete: sess_abc123                                       │    │
│  │ Total latency: 1156ms | Status: success                             │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Showing 1-50 of 12,847 entries    [Load More]                              │
│                                                                              │
│  [Export CSV] [Export JSON] [Clear Old Logs]                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Architecture

### 5.1 Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Frontend | Preact + TypeScript | 3KB vs React's 45KB, same API |
| Styling | Tailwind CSS | Utility-first, responsive, small bundle |
| Build | Vite | Fast dev, optimized prod builds |
| State | Preact Signals | Reactive, efficient updates |
| Backend | FastAPI | Already used for main API |
| Real-time | WebSocket | Live updates for logs, activity |

### 5.2 API Endpoints

```python
# Dashboard API routes

# Home
GET  /api/dashboard/health          # System health status
GET  /api/dashboard/stats/today     # Today's statistics
GET  /api/dashboard/activity/recent # Recent activity feed
GET  /api/dashboard/alerts          # Active alerts

# Chat Test
POST /api/dashboard/chat/test       # Test a command (dry run or execute)

# Memory
GET  /api/dashboard/memories        # List/search memories
GET  /api/dashboard/memories/{id}   # Get memory detail
PUT  /api/dashboard/memories/{id}   # Update memory
DELETE /api/dashboard/memories/{id} # Soft delete memory
POST /api/dashboard/memories/{id}/restore  # Restore deleted memory
GET  /api/dashboard/memories/{id}/access-log  # Access history

# Intents
GET  /api/dashboard/intents         # List all intents
GET  /api/dashboard/intents/{name}  # Get intent detail
POST /api/dashboard/intents/{name}/examples  # Add training example
GET  /api/dashboard/intents/misclassifications  # Recent misclassifications

# Self-Improvement
GET  /api/dashboard/improvements/pending   # Pending improvements
POST /api/dashboard/improvements/{id}/approve
POST /api/dashboard/improvements/{id}/reject
POST /api/dashboard/improvements/suggest   # Add user suggestion
GET  /api/dashboard/improvements/history   # Applied improvements

# Config
GET  /api/dashboard/config          # All configuration
PUT  /api/dashboard/config          # Update configuration
POST /api/dashboard/config/test-connection/{provider}  # Test a connection

# Logs
GET  /api/dashboard/logs            # Search/filter logs
GET  /api/dashboard/logs/export     # Export logs
WS   /api/dashboard/logs/stream     # Live log stream
```

### 5.3 WebSocket for Real-Time Updates

```typescript
// Real-time updates via WebSocket

interface WebSocketMessage {
  type: 'activity' | 'health' | 'log' | 'alert' | 'improvement';
  data: any;
  timestamp: string;
}

// Client connection
const ws = new WebSocket('/ws/dashboard');

ws.onmessage = (event) => {
  const message: WebSocketMessage = JSON.parse(event.data);
  
  switch (message.type) {
    case 'activity':
      // Prepend to recent activity list
      activitySignal.value = [message.data, ...activitySignal.value.slice(0, 49)];
      break;
    
    case 'health':
      // Update health status
      healthSignal.value = message.data;
      break;
    
    case 'log':
      // Append to live log stream (if viewing)
      if (liveLogEnabled.value) {
        logsSignal.value = [...logsSignal.value, message.data].slice(-500);
      }
      break;
    
    case 'alert':
      // Show toast notification
      showToast(message.data);
      break;
  }
};
```

---

## 6. File Structure

```
dashboard/
├── src/
│   ├── main.tsx                    # Entry point
│   ├── app.tsx                     # Root with router
│   │
│   ├── api/
│   │   ├── client.ts               # HTTP client
│   │   └── websocket.ts            # WebSocket client
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Toast.tsx
│   │   │   └── Slider.tsx
│   │   │
│   │   ├── layout/
│   │   │   ├── Navigation.tsx      # Responsive nav (bottom/sidebar)
│   │   │   ├── Header.tsx
│   │   │   └── Layout.tsx
│   │   │
│   │   └── domain/
│   │       ├── HealthStatus.tsx
│   │       ├── ActivityFeed.tsx
│   │       ├── StatsGrid.tsx
│   │       ├── ChatTestPanel.tsx
│   │       ├── MemoryCard.tsx
│   │       ├── IntentTree.tsx
│   │       ├── ImprovementCard.tsx
│   │       ├── ConfigSection.tsx
│   │       └── LogViewer.tsx
│   │
│   ├── pages/
│   │   ├── Home.tsx
│   │   ├── ChatTest.tsx
│   │   ├── Memory.tsx
│   │   ├── Intents.tsx
│   │   ├── Improve.tsx
│   │   ├── Config.tsx
│   │   └── Logs.tsx
│   │
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useApi.ts
│   │   └── useWebSocket.ts
│   │
│   ├── state/
│   │   └── signals.ts              # Preact signals
│   │
│   └── types/
│       └── index.ts
│
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

---

## 7. Implementation Checklist

### Backend

- [ ] Dashboard auth (JWT, session management)
- [ ] Home page APIs (health, stats, activity, alerts)
- [ ] Chat test API (dry run + execute modes)
- [ ] Memory APIs (CRUD, search, access logs)
- [ ] Intent APIs (list, detail, add examples, misclassifications)
- [ ] Improvement APIs (pending, approve, reject, suggest, history)
- [ ] Config APIs (get, update, test connections)
- [ ] Logs APIs (search, filter, export, stream)
- [ ] WebSocket handler for real-time updates

### Frontend

- [ ] Responsive layout (Fold 6 outer/inner, phone, desktop)
- [ ] Navigation (bottom nav for mobile, sidebar for desktop)
- [ ] Home page
- [ ] Chat Test page with full flow visualization
- [ ] Memory Logs page with search and filters
- [ ] Intents page with tree view and detail panel
- [ ] Self-Improvement page with suggestion form
- [ ] Config page with all settings
- [ ] Logs page with live tail

### Real-Time

- [ ] WebSocket connection management
- [ ] Live activity feed
- [ ] Live health updates
- [ ] Live log streaming
- [ ] Alert notifications

### Validation

- [ ] Works on Fold 6 outer screen (344px)
- [ ] Works on Fold 6 inner screen (884px)
- [ ] Works on desktop (1200px+)
- [ ] Chat test shows full classification flow
- [ ] User suggestions flow through to improvements
- [ ] Config changes apply without restart (where possible)
- [ ] Log search is fast (<500ms for 100k logs)

---

## 8. Acceptance Criteria

1. **Purpose-built pages:** Each page serves its stated purpose. Get what you need immediately.
2. **Full logging visibility:** Can see and search all system logs from dashboard.
3. **Chat testing works:** Can type commands and see full classification/execution flow.
4. **Memory audit trail:** Can see all memory operations, access history, source conversations.
5. **Intent management:** Can view all intents, add training examples, see misclassifications.
6. **Self-improvement control:** Can review pending, approve/reject, add own suggestions.
7. **All config in UI:** No need to edit .env files after initial setup.
8. **Responsive on all devices:** Works well on Fold 6 (both screens), phone, and desktop.

---

**End of Area 09: Dashboard & Admin**

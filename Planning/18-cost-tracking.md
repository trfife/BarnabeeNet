# Area 18: Operating Cost Analysis

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 01, 09, 15 (Data Layer, Dashboard, API Contracts)  
**Phase:** Parallel (all phases)  

---

## 1. Overview

### 1.1 Purpose

This specification defines the cost tracking and analysis system for BarnabeeNet V2. It provides visibility into ongoing operating costs, usage projections, and budget monitoring to ensure the system remains sustainable for long-term home use.

### 1.2 Scope

- **In Scope:** Cloud service costs, usage tracking, cost projections, budget alerts, dashboard integration
- **Out of Scope:** Hardware purchase decisions, development time tracking, one-time setup costs

### 1.3 Design Principles

1. **Transparent costs:** All variable costs tracked and visible
2. **Proactive alerts:** Budget thresholds warn before overspending
3. **Usage-based projections:** Estimate future costs from current usage patterns
4. **Low overhead:** Cost tracking should not add significant processing cost

---

## 2. Cost Categories

### 2.1 Monthly Cost Breakdown

| Category | Service | Billing Model | Estimated Monthly |
|----------|---------|---------------|-------------------|
| **LLM API** | Azure OpenAI GPT-4o | Per 1K tokens | $5-30 (varies with usage) |
| **LLM API** | Azure OpenAI ada-002 (embeddings) | Per 1K tokens | $1-5 |
| **Backup** | Backblaze B2 Storage | Per GB stored | $0.50-2 |
| **SMS** | Azure Communication Services | Per message | $0-5 (low volume) |
| **Finance** | SimpleFIN | Subscription | $0-5 (if paid tier) |
| **Infrastructure** | Electricity (servers) | Per kWh | $15-30 |
| **Total Estimated** | | | **$20-75/month** |

### 2.2 Usage-Based Cost Drivers

```
Cost = f(usage)

LLM Costs:
├── GPT-4o: $0.005/1K input tokens + $0.015/1K output tokens
│   └── Driven by: LLM fallback rate, response length, memory retrieval complexity
├── ada-002: $0.0001/1K tokens
│   └── Driven by: Memory creation rate, search frequency
│
Backup Costs:
├── B2 Storage: $0.005/GB/month
│   └── Driven by: Database growth, audio retention (if enabled)
├── B2 Download: $0.01/GB (free first 1GB/day)
│   └── Driven by: Restore operations (rare)
│
SMS Costs:
├── Azure SMS: ~$0.0075/message
│   └── Driven by: Notification volume, long content delivery
│
Electricity:
├── Server (Beast): ~200W average × 24h × 30d × $0.12/kWh = ~$17/month
├── Proxmox (BattleServer): ~30W × 24h × 30d × $0.12/kWh = ~$2.60/month
```

---

## 3. Data Model

### 3.1 Cost Tracking Schema

```sql
-- Service cost records (monthly aggregates)
CREATE TABLE cost_records (
    id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,           -- 'azure_openai', 'backblaze', 'azure_sms', 'simplefin', 'electricity'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    amount_cents INTEGER NOT NULL,   -- Cost in cents for precision
    currency TEXT DEFAULT 'USD',
    units_consumed REAL,             -- Tokens, GB, messages, kWh
    unit_type TEXT,                  -- 'tokens', 'gb', 'messages', 'kwh'
    source TEXT,                     -- 'api_usage', 'invoice', 'estimate'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(service, period_start, period_end)
);

-- Detailed usage tracking (for projections)
CREATE TABLE usage_tracking (
    id INTEGER PRIMARY KEY,
    service TEXT NOT NULL,
    usage_type TEXT NOT NULL,        -- 'gpt4o_input', 'gpt4o_output', 'embedding', 'sms', 'backup_gb'
    amount REAL NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON                    -- Additional context
);

-- Create index for time-based queries
CREATE INDEX idx_usage_tracking_recorded ON usage_tracking(recorded_at);
CREATE INDEX idx_usage_tracking_service ON usage_tracking(service, recorded_at);

-- Budget thresholds
CREATE TABLE cost_budgets (
    id INTEGER PRIMARY KEY,
    service TEXT,                    -- NULL for total budget
    monthly_limit_cents INTEGER NOT NULL,
    warning_threshold_percent INTEGER DEFAULT 80,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Budget alerts history
CREATE TABLE budget_alerts (
    id INTEGER PRIMARY KEY,
    budget_id INTEGER REFERENCES cost_budgets(id),
    alert_type TEXT NOT NULL,        -- 'warning', 'exceeded'
    period_month TEXT NOT NULL,      -- '2026-01'
    current_amount_cents INTEGER,
    threshold_cents INTEGER,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP
);
```

---

## 4. Usage Tracking

### 4.1 LLM Usage Collector

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json

@dataclass
class LLMUsage:
    """Track LLM API usage for cost calculation."""
    
    model: str
    input_tokens: int
    output_tokens: int
    request_type: str  # 'classification', 'memory_extraction', 'response_generation'
    
class UsageTracker:
    """Collect and aggregate usage data for cost tracking."""
    
    # Cost per 1K tokens (as of Jan 2026, verify periodically)
    LLM_COSTS = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "text-embedding-ada-002": {"input": 0.0001, "output": 0},
    }
    
    def __init__(self, db):
        self.db = db
    
    async def track_llm_usage(self, usage: LLMUsage):
        """Track a single LLM API call."""
        
        # Record input tokens
        await self.db.execute(
            """
            INSERT INTO usage_tracking (service, usage_type, amount, metadata)
            VALUES (?, ?, ?, ?)
            """,
            [
                "azure_openai",
                f"{usage.model}_input",
                usage.input_tokens,
                json.dumps({"request_type": usage.request_type})
            ]
        )
        
        # Record output tokens
        if usage.output_tokens > 0:
            await self.db.execute(
                """
                INSERT INTO usage_tracking (service, usage_type, amount, metadata)
                VALUES (?, ?, ?, ?)
                """,
                [
                    "azure_openai",
                    f"{usage.model}_output",
                    usage.output_tokens,
                    json.dumps({"request_type": usage.request_type})
                ]
            )
    
    async def track_sms(self, recipient: str, message_length: int):
        """Track SMS sent."""
        await self.db.execute(
            """
            INSERT INTO usage_tracking (service, usage_type, amount, metadata)
            VALUES (?, ?, ?, ?)
            """,
            [
                "azure_sms",
                "message",
                1,
                json.dumps({"length": message_length})
            ]
        )
    
    async def track_backup_size(self, size_bytes: int):
        """Track backup storage size (daily)."""
        size_gb = size_bytes / (1024 ** 3)
        
        await self.db.execute(
            """
            INSERT INTO usage_tracking (service, usage_type, amount, metadata)
            VALUES (?, ?, ?, ?)
            """,
            [
                "backblaze",
                "storage_gb",
                size_gb,
                json.dumps({"recorded": datetime.utcnow().isoformat()})
            ]
        )
```

### 4.2 Automatic Usage Aggregation

```python
from datetime import datetime, timedelta

class CostAggregator:
    """Aggregate usage into cost records."""
    
    def __init__(self, db, usage_tracker: UsageTracker):
        self.db = db
        self.usage_tracker = usage_tracker
    
    async def aggregate_daily(self):
        """
        Run daily to aggregate yesterday's usage into cost estimate.
        Scheduled via ARQ worker.
        """
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        start = datetime.combine(yesterday, datetime.min.time())
        end = datetime.combine(yesterday, datetime.max.time())
        
        # Aggregate LLM costs
        await self._aggregate_llm_costs(start, end)
        
        # Aggregate SMS costs
        await self._aggregate_sms_costs(start, end)
        
        # Check backup size
        await self._record_backup_cost(yesterday)
        
        # Check budget thresholds
        await self._check_budgets()
    
    async def _aggregate_llm_costs(self, start: datetime, end: datetime):
        """Calculate LLM costs for period."""
        
        rows = await self.db.fetchall(
            """
            SELECT usage_type, SUM(amount) as total
            FROM usage_tracking
            WHERE service = 'azure_openai'
              AND recorded_at BETWEEN ? AND ?
            GROUP BY usage_type
            """,
            [start, end]
        )
        
        total_cost_cents = 0
        total_tokens = 0
        
        for row in rows:
            usage_type = row["usage_type"]
            tokens = row["total"]
            
            # Parse model and direction from usage_type (e.g., "gpt-4o_input")
            parts = usage_type.rsplit("_", 1)
            if len(parts) == 2:
                model, direction = parts
                if model in UsageTracker.LLM_COSTS:
                    rate = UsageTracker.LLM_COSTS[model].get(direction, 0)
                    cost = (tokens / 1000) * rate
                    total_cost_cents += int(cost * 100)
                    total_tokens += tokens
        
        if total_cost_cents > 0:
            await self.db.execute(
                """
                INSERT OR REPLACE INTO cost_records 
                (service, period_start, period_end, amount_cents, units_consumed, unit_type, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "azure_openai",
                    start.date(),
                    end.date(),
                    total_cost_cents,
                    total_tokens,
                    "tokens",
                    "api_usage"
                ]
            )
    
    async def _aggregate_sms_costs(self, start: datetime, end: datetime):
        """Calculate SMS costs for period."""
        
        row = await self.db.fetchone(
            """
            SELECT COUNT(*) as count
            FROM usage_tracking
            WHERE service = 'azure_sms'
              AND recorded_at BETWEEN ? AND ?
            """,
            [start, end]
        )
        
        if row and row["count"] > 0:
            # $0.0075 per message = 0.75 cents
            cost_cents = int(row["count"] * 0.75)
            
            await self.db.execute(
                """
                INSERT OR REPLACE INTO cost_records 
                (service, period_start, period_end, amount_cents, units_consumed, unit_type, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "azure_sms",
                    start.date(),
                    end.date(),
                    cost_cents,
                    row["count"],
                    "messages",
                    "api_usage"
                ]
            )
    
    async def _record_backup_cost(self, date):
        """Record backup storage cost estimate."""
        
        # Get latest backup size
        row = await self.db.fetchone(
            """
            SELECT amount FROM usage_tracking
            WHERE service = 'backblaze' AND usage_type = 'storage_gb'
            ORDER BY recorded_at DESC LIMIT 1
            """
        )
        
        if row:
            size_gb = row["amount"]
            # $0.005/GB/month, so daily cost = monthly / 30
            daily_cost_cents = int((size_gb * 0.005 * 100) / 30)
            
            await self.db.execute(
                """
                INSERT OR REPLACE INTO cost_records 
                (service, period_start, period_end, amount_cents, units_consumed, unit_type, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "backblaze",
                    date,
                    date,
                    daily_cost_cents,
                    size_gb,
                    "gb",
                    "estimate"
                ]
            )
    
    async def _check_budgets(self):
        """Check if any budgets are approaching or exceeded."""
        
        current_month = datetime.utcnow().strftime("%Y-%m")
        month_start = datetime.utcnow().replace(day=1).date()
        
        # Get budgets
        budgets = await self.db.fetchall(
            "SELECT * FROM cost_budgets WHERE active = TRUE"
        )
        
        for budget in budgets:
            if budget["service"]:
                # Service-specific budget
                row = await self.db.fetchone(
                    """
                    SELECT SUM(amount_cents) as total
                    FROM cost_records
                    WHERE service = ? AND period_start >= ?
                    """,
                    [budget["service"], month_start]
                )
            else:
                # Total budget
                row = await self.db.fetchone(
                    """
                    SELECT SUM(amount_cents) as total
                    FROM cost_records
                    WHERE period_start >= ?
                    """,
                    [month_start]
                )
            
            current = row["total"] or 0
            limit = budget["monthly_limit_cents"]
            warning_threshold = int(limit * budget["warning_threshold_percent"] / 100)
            
            # Check if we need to alert
            if current >= limit:
                await self._send_budget_alert(budget, current_month, current, limit, "exceeded")
            elif current >= warning_threshold:
                await self._send_budget_alert(budget, current_month, current, warning_threshold, "warning")
    
    async def _send_budget_alert(
        self,
        budget: dict,
        period: str,
        current: int,
        threshold: int,
        alert_type: str,
    ):
        """Send budget alert via notification system."""
        
        # Check if already alerted this period
        existing = await self.db.fetchone(
            """
            SELECT id FROM budget_alerts
            WHERE budget_id = ? AND period_month = ? AND alert_type = ?
            """,
            [budget["id"], period, alert_type]
        )
        
        if existing:
            return
        
        # Record alert
        await self.db.execute(
            """
            INSERT INTO budget_alerts 
            (budget_id, alert_type, period_month, current_amount_cents, threshold_cents)
            VALUES (?, ?, ?, ?, ?)
            """,
            [budget["id"], alert_type, period, current, threshold]
        )
        
        # Send notification
        service_name = budget["service"] or "Total"
        current_dollars = current / 100
        threshold_dollars = threshold / 100
        
        message = (
            f"Budget Alert: {service_name} costs {'exceeded' if alert_type == 'exceeded' else 'approaching'} "
            f"threshold. Current: ${current_dollars:.2f}, Limit: ${threshold_dollars:.2f}"
        )
        
        # Use notification system (from Area 13)
        from barnabee.notifications import notify_super_user
        await notify_super_user(message, channel="push")
```

---

## 5. Cost Projections

### 5.1 Projection Calculator

```python
from datetime import datetime, timedelta
from typing import Dict, List

class CostProjector:
    """Project future costs based on usage patterns."""
    
    def __init__(self, db):
        self.db = db
    
    async def project_monthly(self, service: str = None) -> Dict:
        """
        Project this month's total based on current usage rate.
        """
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        days_elapsed = (now - month_start).days + 1
        days_in_month = 30  # Approximate
        
        # Get costs so far this month
        if service:
            row = await self.db.fetchone(
                """
                SELECT SUM(amount_cents) as total
                FROM cost_records
                WHERE service = ? AND period_start >= ?
                """,
                [service, month_start.date()]
            )
        else:
            row = await self.db.fetchone(
                """
                SELECT SUM(amount_cents) as total
                FROM cost_records
                WHERE period_start >= ?
                """,
                [month_start.date()]
            )
        
        current_total = row["total"] or 0
        
        # Simple linear projection
        if days_elapsed > 0:
            daily_rate = current_total / days_elapsed
            projected_total = daily_rate * days_in_month
        else:
            projected_total = 0
        
        return {
            "current_total_cents": current_total,
            "days_elapsed": days_elapsed,
            "daily_rate_cents": current_total / max(days_elapsed, 1),
            "projected_monthly_cents": int(projected_total),
            "projected_monthly_dollars": projected_total / 100,
        }
    
    async def get_usage_trends(self, service: str, days: int = 30) -> List[Dict]:
        """Get daily usage trends for a service."""
        
        start_date = datetime.utcnow().date() - timedelta(days=days)
        
        rows = await self.db.fetchall(
            """
            SELECT period_start as date, amount_cents, units_consumed
            FROM cost_records
            WHERE service = ? AND period_start >= ?
            ORDER BY period_start
            """,
            [service, start_date]
        )
        
        return [
            {
                "date": row["date"].isoformat() if hasattr(row["date"], 'isoformat') else row["date"],
                "cost_cents": row["amount_cents"],
                "units": row["units_consumed"],
            }
            for row in rows
        ]
    
    async def get_breakdown_by_service(self) -> List[Dict]:
        """Get current month's costs broken down by service."""
        
        month_start = datetime.utcnow().replace(day=1).date()
        
        rows = await self.db.fetchall(
            """
            SELECT service, SUM(amount_cents) as total, SUM(units_consumed) as units
            FROM cost_records
            WHERE period_start >= ?
            GROUP BY service
            ORDER BY total DESC
            """,
            [month_start]
        )
        
        return [
            {
                "service": row["service"],
                "total_cents": row["total"],
                "total_dollars": row["total"] / 100,
                "units": row["units"],
            }
            for row in rows
        ]
```

---

## 6. Dashboard Integration

### 6.1 Cost Dashboard API

```python
from fastapi import APIRouter, Depends
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/costs", tags=["costs"])

@router.get("/summary")
async def get_cost_summary(
    user: dict = Depends(require_super_user),
    projector: CostProjector = Depends(get_cost_projector),
):
    """Get cost summary for dashboard widget."""
    
    projection = await projector.project_monthly()
    breakdown = await projector.get_breakdown_by_service()
    
    return {
        "current_month": {
            "total_dollars": projection["current_total_cents"] / 100,
            "projected_dollars": projection["projected_monthly_dollars"],
            "days_elapsed": projection["days_elapsed"],
        },
        "breakdown": breakdown,
    }

@router.get("/trends/{service}")
async def get_cost_trends(
    service: str,
    days: int = 30,
    user: dict = Depends(require_super_user),
    projector: CostProjector = Depends(get_cost_projector),
):
    """Get cost trends for a specific service."""
    
    trends = await projector.get_usage_trends(service, days)
    return {"service": service, "days": days, "data": trends}

@router.get("/budgets")
async def get_budgets(
    user: dict = Depends(require_super_user),
    db = Depends(get_db),
):
    """Get all budget configurations."""
    
    budgets = await db.fetchall(
        "SELECT * FROM cost_budgets WHERE active = TRUE"
    )
    
    return {"budgets": budgets}

@router.put("/budgets/{budget_id}")
async def update_budget(
    budget_id: int,
    update: BudgetUpdate,
    user: dict = Depends(require_super_user),
    db = Depends(get_db),
):
    """Update budget threshold."""
    
    await db.execute(
        """
        UPDATE cost_budgets 
        SET monthly_limit_cents = ?, warning_threshold_percent = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        [update.monthly_limit_cents, update.warning_threshold_percent, budget_id]
    )
    
    return {"updated": True}

@router.post("/budgets")
async def create_budget(
    budget: BudgetCreate,
    user: dict = Depends(require_super_user),
    db = Depends(get_db),
):
    """Create new budget."""
    
    result = await db.execute(
        """
        INSERT INTO cost_budgets (service, monthly_limit_cents, warning_threshold_percent)
        VALUES (?, ?, ?)
        """,
        [budget.service, budget.monthly_limit_cents, budget.warning_threshold_percent]
    )
    
    return {"id": result.lastrowid, "created": True}
```

### 6.2 Dashboard Cost Widget

```typescript
// components/CostWidget.tsx
import { useEffect, useState } from 'preact/hooks';
import { Card } from './common/Card';
import { ProgressBar } from './common/ProgressBar';
import { api } from '../api/client';

interface CostSummary {
  current_month: {
    total_dollars: number;
    projected_dollars: number;
    days_elapsed: number;
  };
  breakdown: {
    service: string;
    total_dollars: number;
  }[];
}

export function CostWidget() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [budget, setBudget] = useState<number>(75); // Default $75/month
  
  useEffect(() => {
    api.get('/costs/summary').then(setSummary);
  }, []);
  
  if (!summary) {
    return <Card title="Costs">Loading...</Card>;
  }
  
  const { current_month, breakdown } = summary;
  const percentUsed = (current_month.total_dollars / budget) * 100;
  
  return (
    <Card title="Monthly Costs">
      <div class="space-y-4">
        {/* Current spend */}
        <div class="flex justify-between items-center">
          <span class="text-2xl font-bold">
            ${current_month.total_dollars.toFixed(2)}
          </span>
          <span class="text-gray-500">
            of ${budget} budget
          </span>
        </div>
        
        {/* Progress bar */}
        <ProgressBar 
          percent={percentUsed} 
          color={percentUsed > 80 ? 'yellow' : percentUsed > 100 ? 'red' : 'green'}
        />
        
        {/* Projection */}
        <div class="text-sm text-gray-500">
          Projected: ${current_month.projected_dollars.toFixed(2)} by end of month
          ({current_month.days_elapsed} days elapsed)
        </div>
        
        {/* Breakdown */}
        <div class="border-t pt-4 mt-4">
          <h4 class="text-sm font-medium mb-2">By Service</h4>
          <div class="space-y-2">
            {breakdown.map(item => (
              <div key={item.service} class="flex justify-between text-sm">
                <span class="capitalize">{item.service.replace('_', ' ')}</span>
                <span>${item.total_dollars.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Link to full page */}
        <a href="/costs" class="text-blue-500 text-sm">
          View details →
        </a>
      </div>
    </Card>
  );
}
```

---

## 7. Electricity Cost Estimation

### 7.1 Manual Entry for Electricity

Since electricity costs can't be tracked via API, provide a simple manual entry interface.

```python
@router.post("/electricity")
async def record_electricity(
    month: str,  # Format: "2026-01"
    kwh: float,
    rate_per_kwh: float = 0.12,
    user: dict = Depends(require_super_user),
    db = Depends(get_db),
):
    """Manually record electricity cost for the month."""
    
    year, month_num = month.split("-")
    start_date = f"{year}-{month_num}-01"
    
    # Calculate days in month
    import calendar
    days_in_month = calendar.monthrange(int(year), int(month_num))[1]
    end_date = f"{year}-{month_num}-{days_in_month:02d}"
    
    cost_cents = int(kwh * rate_per_kwh * 100)
    
    await db.execute(
        """
        INSERT OR REPLACE INTO cost_records 
        (service, period_start, period_end, amount_cents, units_consumed, unit_type, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ["electricity", start_date, end_date, cost_cents, kwh, "kwh", "manual"]
    )
    
    return {
        "month": month,
        "kwh": kwh,
        "cost_dollars": cost_cents / 100,
    }
```

### 7.2 Electricity Estimation Helper

```python
# Estimate based on server specs
POWER_ESTIMATES = {
    "beast": {
        "idle_watts": 150,
        "gpu_active_watts": 300,
        "avg_watts": 200,  # Estimated average with typical usage
    },
    "battleserver": {
        "avg_watts": 30,
    },
}

def estimate_monthly_electricity(
    rate_per_kwh: float = 0.12,
    servers: list = ["beast", "battleserver"],
) -> dict:
    """Estimate monthly electricity cost."""
    
    total_watts = sum(POWER_ESTIMATES[s]["avg_watts"] for s in servers)
    
    # kWh = watts × hours / 1000
    hours_per_month = 24 * 30
    kwh = (total_watts * hours_per_month) / 1000
    
    cost = kwh * rate_per_kwh
    
    return {
        "total_watts": total_watts,
        "kwh_per_month": kwh,
        "cost_dollars": cost,
        "breakdown": {
            server: {
                "watts": POWER_ESTIMATES[server]["avg_watts"],
                "kwh": (POWER_ESTIMATES[server]["avg_watts"] * hours_per_month) / 1000,
                "cost": ((POWER_ESTIMATES[server]["avg_watts"] * hours_per_month) / 1000) * rate_per_kwh,
            }
            for server in servers
        }
    }
```

---

## 8. ARQ Worker Tasks

### 8.1 Scheduled Cost Tasks

```python
# workers/cost_tasks.py
from arq import cron

async def aggregate_daily_costs(ctx):
    """Daily cost aggregation task."""
    aggregator = CostAggregator(ctx["db"], ctx["usage_tracker"])
    await aggregator.aggregate_daily()

async def record_backup_size(ctx):
    """Record current backup size."""
    import subprocess
    
    # Get B2 bucket size
    result = subprocess.run(
        ["b2", "get-bucket", "--showSize", "barnabee-backups"],
        capture_output=True,
        text=True,
    )
    
    # Parse size from output (implementation depends on b2 CLI output format)
    # ...
    
    await ctx["usage_tracker"].track_backup_size(size_bytes)

class WorkerSettings:
    functions = [aggregate_daily_costs, record_backup_size]
    
    cron_jobs = [
        # Run daily cost aggregation at 1:00 AM
        cron(aggregate_daily_costs, hour=1, minute=0),
        
        # Record backup size at 2:00 AM
        cron(record_backup_size, hour=2, minute=0),
    ]
```

---

## 9. Implementation Checklist

### Database Schema
- [ ] Create `cost_records` table
- [ ] Create `usage_tracking` table
- [ ] Create `cost_budgets` table
- [ ] Create `budget_alerts` table
- [ ] Add indexes for performance

### Usage Tracking
- [ ] LLM usage tracking in API calls
- [ ] SMS usage tracking
- [ ] Backup size tracking

### Cost Aggregation
- [ ] Daily aggregation worker
- [ ] LLM cost calculation
- [ ] SMS cost calculation
- [ ] Backup cost estimation

### Budget System
- [ ] Budget CRUD API
- [ ] Budget threshold checking
- [ ] Alert notifications

### Dashboard
- [ ] Cost summary widget
- [ ] Service breakdown view
- [ ] Trend charts
- [ ] Budget management page

### Projections
- [ ] Monthly projection calculation
- [ ] Usage trend analysis

---

## 10. Acceptance Criteria

1. **All variable costs tracked:** LLM tokens, SMS messages, backup storage
2. **Costs aggregated daily:** Previous day's usage converted to cost records
3. **Projections accurate:** Monthly projection within 20% of actual (after 10 days)
4. **Budget alerts work:** Notifications sent when thresholds reached
5. **Dashboard shows costs:** Super user can see current spend and projections
6. **Manual entry available:** Electricity and other fixed costs can be entered manually

---

## 11. Handoff Notes for Implementation Agent

### Critical Points

1. **Track at the source.** Instrument LLM client and SMS sender to track usage immediately.

2. **Cents for precision.** Store all costs in cents (integers) to avoid floating point issues.

3. **Don't over-track.** Daily aggregation is sufficient. Don't track every request individually beyond what's needed for billing.

4. **Budget alerts are notifications.** Use the notification system from Area 13 to send budget alerts.

5. **Electricity is manual.** No way to automatically track; provide simple monthly entry form.

### Common Pitfalls

- Forgetting to track LLM usage on error paths
- Double-counting when requests retry
- Not accounting for Azure's billing lag (costs may appear 24-48h later)
- Over-complicating projections (linear extrapolation is fine for home use)

### Cost Verification Checklist

- [ ] Compare tracked LLM tokens to Azure dashboard
- [ ] Verify SMS count matches Azure logs
- [ ] Check B2 dashboard against tracked backup size
- [ ] Validate budget alerts trigger correctly

---

**End of Area 18: Operating Cost Analysis**

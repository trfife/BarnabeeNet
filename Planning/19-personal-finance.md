# Area 19: Personal Finance Integration

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Areas 01, 03, 09, 13, 17 (Data Layer, Intent Classification, Dashboard, Notifications, Security)  
**Phase:** Extended Functionality  

---

## 1. Overview

### 1.1 Purpose

This specification defines a personal finance management system integrated with BarnabeeNet V2. Using SimpleFIN for bank account aggregation, this feature enables the super user (Thom) to query account balances, track spending, manage budgets, and set savings goals through voice commands and the dashboard.

### 1.2 Scope

- **In Scope:** Bank account sync, balance queries, spending tracking, budget management, savings goals, bill reminders
- **Out of Scope:** Bill pay, money transfers, investment advice, tax calculations

### 1.3 Access Restrictions

**CRITICAL:** This feature is restricted to the super user only.

| Restriction | Enforcement |
|-------------|-------------|
| User | Super user (Thom) only |
| Device | Registered "Thom's phone" device only for voice commands |
| Voice | Voice verification required for all financial queries |
| Dashboard | Finance pages only visible to super user |

### 1.4 Design Principles

1. **Security first:** Financial data is highly sensitive. Triple verification for all access.
2. **Read-only:** No ability to make transactions or transfers—information only.
3. **Offline-capable:** Local cache allows queries even if SimpleFIN is temporarily unavailable.
4. **Voice-optimized:** Responses designed for spoken delivery.

---

## 2. SimpleFIN Integration

### 2.1 What is SimpleFIN?

SimpleFIN is a privacy-focused financial data aggregation service. It acts as a bridge between your bank accounts and applications, providing:

- Read-only access to account balances and transactions
- No storage of bank credentials (uses bank's OAuth)
- Simple REST API
- One-time setup token (Access URL)

### 2.2 SimpleFIN Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SIMPLEFIN INTEGRATION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SIMPLEFIN BRIDGE                                  │   │
│  │                                                                      │   │
│  │  SimpleFIN.org  ◄───────►  Bank Aggregator  ◄───────►  Your Banks  │   │
│  │      (API)                   (Plaid/MX)               (via OAuth)   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                             │
│                               │ HTTPS (read-only)                           │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    BARNABEENET V2                                    │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────┐  │   │
│  │  │ SimpleFIN Sync  │     │  Finance DB     │     │  Finance    │  │   │
│  │  │    Worker       │────►│  (SQLite)       │◄────│  Service    │  │   │
│  │  │  (ARQ cron)     │     │                 │     │             │  │   │
│  │  └─────────────────┘     └─────────────────┘     └──────┬──────┘  │   │
│  │                                                          │         │   │
│  │                          ┌───────────────────────────────┘         │   │
│  │                          │                                          │   │
│  │                          ▼                                          │   │
│  │         ┌────────────────────────────────────────┐                 │   │
│  │         │           ACCESS POINTS                 │                 │   │
│  │         │                                         │                 │   │
│  │         │  Voice Commands    Dashboard (Web)     │                 │   │
│  │         │  (Super user +     (Super user only)   │                 │   │
│  │         │   device check)                        │                 │   │
│  │         └────────────────────────────────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 SimpleFIN Setup Flow

```python
from dataclasses import dataclass
from datetime import datetime
import httpx
import base64

@dataclass
class SimpleFINClient:
    """Client for SimpleFIN API."""
    
    access_url: str  # Encrypted in database
    
    def __init__(self, access_url: str):
        self.access_url = access_url
        # Access URL format: https://user:token@api.simplefin.org/...
        self._base_url, self._auth = self._parse_access_url(access_url)
    
    def _parse_access_url(self, url: str) -> tuple[str, tuple[str, str]]:
        """Extract base URL and auth from access URL."""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        auth = (parsed.username, parsed.password)
        base_url = f"{parsed.scheme}://{parsed.hostname}{parsed.path}"
        
        return base_url, auth
    
    async def get_accounts(self) -> list[dict]:
        """Fetch all linked accounts."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/accounts",
                auth=self._auth,
                timeout=30.0,
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("accounts", [])
    
    async def get_transactions(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> list[dict]:
        """Fetch transactions for all accounts."""
        params = {}
        if start_date:
            params["start-date"] = int(start_date.timestamp())
        if end_date:
            params["end-date"] = int(end_date.timestamp())
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/accounts",
                auth=self._auth,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Transactions are nested within accounts
            all_transactions = []
            for account in data.get("accounts", []):
                for txn in account.get("transactions", []):
                    txn["account_id"] = account["id"]
                    all_transactions.append(txn)
            
            return all_transactions
```

---

## 3. Data Model

### 3.1 Finance Database Schema

```sql
-- Financial accounts (synced from SimpleFIN)
CREATE TABLE finance_accounts (
    id INTEGER PRIMARY KEY,
    simplefin_id TEXT UNIQUE NOT NULL,
    institution_name TEXT NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL,          -- 'checking', 'savings', 'credit', 'investment', 'loan'
    account_number_mask TEXT,            -- Last 4 digits only: '****1234'
    current_balance_cents INTEGER,
    available_balance_cents INTEGER,
    currency TEXT DEFAULT 'USD',
    last_synced_at TIMESTAMP,
    hidden BOOLEAN DEFAULT FALSE,        -- User can hide accounts from queries
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transaction history
CREATE TABLE finance_transactions (
    id INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES finance_accounts(id) ON DELETE CASCADE,
    simplefin_id TEXT UNIQUE NOT NULL,
    transaction_date DATE NOT NULL,
    posted_date DATE,
    amount_cents INTEGER NOT NULL,       -- Negative for debits, positive for credits
    description TEXT NOT NULL,
    original_description TEXT,           -- Raw description from bank
    category TEXT,                       -- User-assigned or auto-categorized
    category_confidence REAL,            -- For auto-categorization
    merchant_name TEXT,
    pending BOOLEAN DEFAULT FALSE,
    notes TEXT,                          -- User notes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_transactions_account ON finance_transactions(account_id);
CREATE INDEX idx_transactions_date ON finance_transactions(transaction_date);
CREATE INDEX idx_transactions_category ON finance_transactions(category);

-- User-defined budgets
CREATE TABLE finance_budgets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,              -- Must match transaction categories
    monthly_limit_cents INTEGER NOT NULL,
    rollover BOOLEAN DEFAULT FALSE,      -- Unused budget carries to next month
    alert_threshold_percent INTEGER DEFAULT 80,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Budget tracking (monthly snapshots)
CREATE TABLE finance_budget_periods (
    id INTEGER PRIMARY KEY,
    budget_id INTEGER REFERENCES finance_budgets(id) ON DELETE CASCADE,
    period_month TEXT NOT NULL,          -- '2026-01'
    spent_cents INTEGER DEFAULT 0,
    limit_cents INTEGER NOT NULL,        -- Copied from budget (may include rollover)
    rollover_cents INTEGER DEFAULT 0,    -- Amount rolled over from previous month
    UNIQUE(budget_id, period_month)
);

-- Savings goals
CREATE TABLE finance_goals (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    target_cents INTEGER NOT NULL,
    current_cents INTEGER DEFAULT 0,
    target_date DATE,                    -- Optional deadline
    linked_account_id INTEGER REFERENCES finance_accounts(id),  -- Optional tracking account
    icon TEXT,                           -- For dashboard display
    active BOOLEAN DEFAULT TRUE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Goal contributions (manual tracking or auto-detected)
CREATE TABLE finance_goal_contributions (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER REFERENCES finance_goals(id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL,
    contribution_date DATE NOT NULL,
    source TEXT,                         -- 'manual', 'auto_detected', 'linked_account'
    transaction_id INTEGER REFERENCES finance_transactions(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recurring transactions (bills, subscriptions)
CREATE TABLE finance_recurring (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    typical_amount_cents INTEGER,
    frequency TEXT NOT NULL,             -- 'monthly', 'weekly', 'yearly', 'biweekly'
    typical_day INTEGER,                 -- Day of month/week
    last_occurrence DATE,
    next_expected DATE,
    merchant_pattern TEXT,               -- Regex to match transactions
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Category rules for auto-categorization
CREATE TABLE finance_category_rules (
    id INTEGER PRIMARY KEY,
    pattern TEXT NOT NULL,               -- Regex or keyword
    pattern_type TEXT DEFAULT 'contains', -- 'contains', 'regex', 'exact'
    category TEXT NOT NULL,
    priority INTEGER DEFAULT 100,        -- Lower = higher priority
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sync metadata
CREATE TABLE finance_sync_status (
    id INTEGER PRIMARY KEY,
    last_sync_at TIMESTAMP,
    last_sync_status TEXT,               -- 'success', 'error'
    last_error TEXT,
    accounts_synced INTEGER,
    transactions_synced INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. Sync Service

### 4.1 Background Sync Worker

```python
from datetime import datetime, timedelta
from typing import Optional
import structlog

logger = structlog.get_logger()

class FinanceSyncService:
    """Sync financial data from SimpleFIN."""
    
    SYNC_INTERVAL_HOURS = 4
    TRANSACTION_LOOKBACK_DAYS = 90
    
    def __init__(self, db, simplefin_client: SimpleFINClient):
        self.db = db
        self.simplefin = simplefin_client
        self.categorizer = TransactionCategorizer(db)
    
    async def sync_all(self) -> dict:
        """Full sync of accounts and transactions."""
        
        sync_start = datetime.utcnow()
        results = {
            "accounts_synced": 0,
            "transactions_synced": 0,
            "new_transactions": 0,
            "errors": [],
        }
        
        try:
            # Sync accounts
            accounts = await self.simplefin.get_accounts()
            for account in accounts:
                await self._sync_account(account)
                results["accounts_synced"] += 1
            
            # Sync transactions
            start_date = datetime.utcnow() - timedelta(days=self.TRANSACTION_LOOKBACK_DAYS)
            transactions = await self.simplefin.get_transactions(start_date=start_date)
            
            for txn in transactions:
                is_new = await self._sync_transaction(txn)
                results["transactions_synced"] += 1
                if is_new:
                    results["new_transactions"] += 1
            
            # Update budget spending
            await self._update_budget_spending()
            
            # Detect recurring transactions
            await self._detect_recurring()
            
            # Record sync status
            await self.db.execute(
                """
                INSERT INTO finance_sync_status 
                (last_sync_at, last_sync_status, accounts_synced, transactions_synced)
                VALUES (?, ?, ?, ?)
                """,
                [sync_start, "success", results["accounts_synced"], results["transactions_synced"]]
            )
            
            logger.info("finance_sync_complete", **results)
            
        except Exception as e:
            results["errors"].append(str(e))
            
            await self.db.execute(
                """
                INSERT INTO finance_sync_status 
                (last_sync_at, last_sync_status, last_error)
                VALUES (?, ?, ?)
                """,
                [sync_start, "error", str(e)]
            )
            
            logger.error("finance_sync_failed", error=str(e))
        
        return results
    
    async def _sync_account(self, account: dict):
        """Upsert account from SimpleFIN data."""
        
        # Map SimpleFIN account type to our types
        account_type = self._map_account_type(account.get("type", ""))
        
        # Extract last 4 digits from account number if available
        account_mask = None
        if account.get("account-number"):
            account_mask = f"****{account['account-number'][-4:]}"
        
        await self.db.execute(
            """
            INSERT INTO finance_accounts 
            (simplefin_id, institution_name, account_name, account_type, 
             account_number_mask, current_balance_cents, available_balance_cents,
             currency, last_synced_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(simplefin_id) DO UPDATE SET
                institution_name = excluded.institution_name,
                account_name = excluded.account_name,
                current_balance_cents = excluded.current_balance_cents,
                available_balance_cents = excluded.available_balance_cents,
                last_synced_at = excluded.last_synced_at,
                updated_at = excluded.updated_at
            """,
            [
                account["id"],
                account.get("org", {}).get("name", "Unknown"),
                account.get("name", "Account"),
                account_type,
                account_mask,
                int(float(account.get("balance", 0)) * 100),
                int(float(account.get("available", account.get("balance", 0))) * 100),
                account.get("currency", "USD"),
                datetime.utcnow(),
                datetime.utcnow(),
            ]
        )
    
    async def _sync_transaction(self, txn: dict) -> bool:
        """
        Upsert transaction from SimpleFIN data.
        Returns True if this is a new transaction.
        """
        
        # Check if exists
        existing = await self.db.fetchone(
            "SELECT id FROM finance_transactions WHERE simplefin_id = ?",
            [txn["id"]]
        )
        
        # Get local account ID
        account = await self.db.fetchone(
            "SELECT id FROM finance_accounts WHERE simplefin_id = ?",
            [txn["account_id"]]
        )
        
        if not account:
            return False
        
        # Auto-categorize if new
        category = None
        confidence = None
        if not existing:
            category, confidence = await self.categorizer.categorize(txn.get("description", ""))
        
        # Parse dates
        txn_date = datetime.fromtimestamp(txn.get("transacted_at", txn.get("posted", 0)))
        posted_date = datetime.fromtimestamp(txn.get("posted", 0)) if txn.get("posted") else None
        
        await self.db.execute(
            """
            INSERT INTO finance_transactions
            (account_id, simplefin_id, transaction_date, posted_date, amount_cents,
             description, original_description, category, category_confidence,
             pending)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(simplefin_id) DO UPDATE SET
                posted_date = excluded.posted_date,
                pending = excluded.pending
            """,
            [
                account["id"],
                txn["id"],
                txn_date.date(),
                posted_date.date() if posted_date else None,
                int(float(txn.get("amount", 0)) * 100),
                self._clean_description(txn.get("description", "")),
                txn.get("description", ""),
                category,
                confidence,
                txn.get("pending", False),
            ]
        )
        
        return not existing
    
    async def _update_budget_spending(self):
        """Recalculate budget spending for current month."""
        
        current_month = datetime.utcnow().strftime("%Y-%m")
        month_start = datetime.utcnow().replace(day=1).date()
        
        # Get all active budgets
        budgets = await self.db.fetchall(
            "SELECT * FROM finance_budgets WHERE active = TRUE"
        )
        
        for budget in budgets:
            # Calculate spending for this category this month
            row = await self.db.fetchone(
                """
                SELECT COALESCE(SUM(ABS(amount_cents)), 0) as spent
                FROM finance_transactions
                WHERE category = ?
                  AND transaction_date >= ?
                  AND amount_cents < 0  -- Only count debits
                """,
                [budget["category"], month_start]
            )
            
            spent = row["spent"]
            
            # Upsert budget period
            await self.db.execute(
                """
                INSERT INTO finance_budget_periods
                (budget_id, period_month, spent_cents, limit_cents)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(budget_id, period_month) DO UPDATE SET
                    spent_cents = excluded.spent_cents
                """,
                [budget["id"], current_month, spent, budget["monthly_limit_cents"]]
            )
            
            # Check for alert
            await self._check_budget_alert(budget, spent)
    
    async def _check_budget_alert(self, budget: dict, spent: int):
        """Send notification if budget threshold reached."""
        
        limit = budget["monthly_limit_cents"]
        threshold = int(limit * budget["alert_threshold_percent"] / 100)
        
        if spent >= limit:
            await self._send_budget_notification(
                budget["name"],
                spent,
                limit,
                "exceeded"
            )
        elif spent >= threshold:
            await self._send_budget_notification(
                budget["name"],
                spent,
                threshold,
                "warning"
            )
    
    async def _send_budget_notification(
        self,
        budget_name: str,
        spent: int,
        threshold: int,
        alert_type: str,
    ):
        """Send budget alert via notification system."""
        from barnabee.notifications import notify_super_user
        
        spent_dollars = spent / 100
        threshold_dollars = threshold / 100
        
        if alert_type == "exceeded":
            message = f"Budget alert: {budget_name} exceeded! Spent ${spent_dollars:.2f}"
        else:
            message = f"Budget warning: {budget_name} at ${spent_dollars:.2f} (threshold: ${threshold_dollars:.2f})"
        
        await notify_super_user(message, channel="push", priority="normal")
    
    def _map_account_type(self, simplefin_type: str) -> str:
        """Map SimpleFIN account type to our types."""
        type_map = {
            "checking": "checking",
            "savings": "savings",
            "credit": "credit",
            "credit card": "credit",
            "investment": "investment",
            "brokerage": "investment",
            "loan": "loan",
            "mortgage": "loan",
        }
        return type_map.get(simplefin_type.lower(), "checking")
    
    def _clean_description(self, description: str) -> str:
        """Clean up transaction description."""
        import re
        
        # Remove extra whitespace
        cleaned = " ".join(description.split())
        
        # Remove common noise patterns
        patterns_to_remove = [
            r'\d{2}/\d{2}',  # Dates like 01/15
            r'#\d+',         # Transaction numbers
            r'CARD \d+',     # Card numbers
        ]
        
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned)
        
        return cleaned.strip()
```

### 4.2 Transaction Categorization

```python
from typing import Optional, Tuple
import re

class TransactionCategorizer:
    """Auto-categorize transactions."""
    
    # Default categories
    CATEGORIES = [
        "groceries",
        "dining",
        "transportation",
        "utilities",
        "entertainment",
        "shopping",
        "healthcare",
        "personal",
        "home",
        "travel",
        "income",
        "transfer",
        "fees",
        "other",
    ]
    
    # Default rules (loaded from DB, but these are fallbacks)
    DEFAULT_RULES = [
        ("walmart|target|costco|kroger|safeway|grocery", "groceries"),
        ("uber eats|doordash|grubhub|mcdonald|starbucks|restaurant|cafe", "dining"),
        ("uber|lyft|gas|shell|chevron|exxon|parking", "transportation"),
        ("electric|water|gas bill|internet|comcast|verizon", "utilities"),
        ("netflix|hulu|spotify|amazon prime|movie|theater", "entertainment"),
        ("amazon|ebay|best buy|apple", "shopping"),
        ("pharmacy|cvs|walgreens|doctor|hospital|medical", "healthcare"),
        ("payroll|salary|direct deposit|income", "income"),
        ("transfer|zelle|venmo|payment", "transfer"),
        ("fee|interest|charge", "fees"),
    ]
    
    def __init__(self, db):
        self.db = db
        self._rules_cache = None
    
    async def categorize(self, description: str) -> Tuple[Optional[str], Optional[float]]:
        """
        Categorize a transaction description.
        Returns (category, confidence).
        """
        
        if not description:
            return None, None
        
        description_lower = description.lower()
        
        # Load rules from DB (cached)
        rules = await self._get_rules()
        
        # Check rules in priority order
        for pattern, category in rules:
            if re.search(pattern, description_lower):
                return category, 0.9  # High confidence for rule match
        
        # No match - could add LLM fallback here
        return "other", 0.5
    
    async def _get_rules(self) -> list:
        """Get categorization rules (DB + defaults)."""
        
        if self._rules_cache:
            return self._rules_cache
        
        # Load from DB
        db_rules = await self.db.fetchall(
            "SELECT pattern, category FROM finance_category_rules ORDER BY priority"
        )
        
        rules = [(row["pattern"], row["category"]) for row in db_rules]
        
        # Add defaults
        rules.extend(self.DEFAULT_RULES)
        
        self._rules_cache = rules
        return rules
    
    async def learn_from_correction(self, description: str, correct_category: str):
        """Add a rule based on user correction."""
        
        # Extract key words from description
        words = description.lower().split()
        
        # Find distinctive words (not common words)
        common_words = {"the", "a", "an", "to", "for", "of", "in", "at", "on"}
        distinctive = [w for w in words if w not in common_words and len(w) > 3]
        
        if distinctive:
            # Create pattern from most distinctive word
            pattern = distinctive[0]
            
            await self.db.execute(
                """
                INSERT INTO finance_category_rules (pattern, category, priority)
                VALUES (?, ?, ?)
                """,
                [pattern, correct_category, 50]  # Higher priority than defaults
            )
            
            # Invalidate cache
            self._rules_cache = None
```

---

## 5. Voice Commands

### 5.1 Intent Taxonomy

Add to `03-intent-classification.md`:

```yaml
finance:
  balance:
    description: "Query account balance"
    examples:
      - "What's my checking balance?"
      - "How much is in my savings?"
      - "What's my credit card balance?"
      - "What are my account balances?"
    entities:
      - account_type: optional, enum(checking, savings, credit, all)
  
  spending:
    description: "Query spending by category or total"
    examples:
      - "How much did I spend on groceries this month?"
      - "What did I spend at restaurants last week?"
      - "How much have I spent this month?"
      - "Show me my dining expenses"
    entities:
      - category: optional, string
      - time_period: optional, enum(today, this_week, this_month, last_month)
  
  budget.status:
    description: "Check budget progress"
    examples:
      - "How am I doing on my dining budget?"
      - "What's my budget status?"
      - "Am I over budget on entertainment?"
    entities:
      - budget_name: optional, string
  
  budget.create:
    description: "Create a new budget"
    examples:
      - "Set a $500 monthly budget for dining"
      - "Create a grocery budget of $800"
      - "I want to budget $200 for entertainment"
    entities:
      - category: required, string
      - amount: required, money
  
  goal.status:
    description: "Check savings goal progress"
    examples:
      - "How's my vacation savings?"
      - "How close am I to my goal?"
      - "Show me my savings progress"
    entities:
      - goal_name: optional, string
  
  goal.create:
    description: "Create a new savings goal"
    examples:
      - "Create a vacation savings goal for $3000"
      - "I want to save $10000 for a car by December"
      - "Start a new savings goal"
    entities:
      - goal_name: required, string
      - amount: required, money
      - target_date: optional, date
  
  bills:
    description: "Query upcoming bills"
    examples:
      - "What bills are due this week?"
      - "When is my rent due?"
      - "Show me upcoming bills"
    entities:
      - time_period: optional, enum(this_week, this_month)
  
  transactions:
    description: "Query recent transactions"
    examples:
      - "What were my last 5 transactions?"
      - "Show me recent purchases"
      - "What did I buy yesterday?"
    entities:
      - count: optional, number
      - time_period: optional
```

### 5.2 Voice Command Handler

```python
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timedelta

@dataclass
class FinanceQueryResult:
    """Result of a finance query for voice response."""
    spoken_response: str
    data: dict
    follow_up: Optional[str] = None

class FinanceVoiceHandler:
    """Handle voice commands for finance features."""
    
    def __init__(self, db, finance_service: 'FinanceService'):
        self.db = db
        self.finance = finance_service
    
    async def handle_balance(
        self,
        account_type: Optional[str] = None,
    ) -> FinanceQueryResult:
        """Handle balance query."""
        
        if account_type and account_type != "all":
            accounts = await self.finance.get_accounts_by_type(account_type)
        else:
            accounts = await self.finance.get_all_accounts()
        
        if not accounts:
            return FinanceQueryResult(
                spoken_response="I couldn't find any accounts to check.",
                data={"accounts": []},
            )
        
        if len(accounts) == 1:
            account = accounts[0]
            balance = account["current_balance_cents"] / 100
            return FinanceQueryResult(
                spoken_response=f"Your {account['account_name']} balance is ${balance:,.2f}",
                data={"accounts": accounts},
            )
        
        # Multiple accounts - summarize
        total = sum(a["current_balance_cents"] for a in accounts) / 100
        response_parts = [f"Your total balance across {len(accounts)} accounts is ${total:,.2f}."]
        
        for account in accounts[:3]:  # Limit to 3 for voice
            balance = account["current_balance_cents"] / 100
            response_parts.append(f"{account['account_name']}: ${balance:,.2f}")
        
        if len(accounts) > 3:
            response_parts.append(f"Plus {len(accounts) - 3} more accounts.")
        
        return FinanceQueryResult(
            spoken_response=" ".join(response_parts),
            data={"accounts": accounts, "total": total},
            follow_up="Would you like more details on any account?",
        )
    
    async def handle_spending(
        self,
        category: Optional[str] = None,
        time_period: str = "this_month",
    ) -> FinanceQueryResult:
        """Handle spending query."""
        
        start_date, end_date, period_name = self._parse_time_period(time_period)
        
        if category:
            spending = await self.finance.get_spending_by_category(
                category, start_date, end_date
            )
            amount = spending / 100
            
            return FinanceQueryResult(
                spoken_response=f"You've spent ${amount:,.2f} on {category} {period_name}.",
                data={"category": category, "amount": amount, "period": period_name},
            )
        else:
            # Total spending
            total, by_category = await self.finance.get_total_spending(start_date, end_date)
            total_amount = total / 100
            
            response = f"Your total spending {period_name} is ${total_amount:,.2f}."
            
            # Top categories
            if by_category:
                top = by_category[:3]
                response += " Top categories: "
                response += ", ".join([
                    f"{cat['category']} at ${cat['amount'] / 100:,.2f}"
                    for cat in top
                ])
            
            return FinanceQueryResult(
                spoken_response=response,
                data={"total": total_amount, "by_category": by_category},
            )
    
    async def handle_budget_status(
        self,
        budget_name: Optional[str] = None,
    ) -> FinanceQueryResult:
        """Handle budget status query."""
        
        if budget_name:
            budget = await self.finance.get_budget_by_name(budget_name)
            if not budget:
                return FinanceQueryResult(
                    spoken_response=f"I couldn't find a budget called {budget_name}.",
                    data={},
                )
            
            spent = budget["spent_cents"] / 100
            limit = budget["limit_cents"] / 100
            remaining = (budget["limit_cents"] - budget["spent_cents"]) / 100
            percent = (budget["spent_cents"] / budget["limit_cents"]) * 100
            
            if percent > 100:
                response = f"You've exceeded your {budget['name']} budget. Spent ${spent:,.2f} of ${limit:,.2f}."
            elif percent > 80:
                response = f"Your {budget['name']} budget is at {percent:.0f}%. You have ${remaining:,.2f} remaining."
            else:
                response = f"Your {budget['name']} budget looks good. ${remaining:,.2f} of ${limit:,.2f} remaining."
            
            return FinanceQueryResult(
                spoken_response=response,
                data=budget,
            )
        else:
            # All budgets
            budgets = await self.finance.get_all_budgets_status()
            
            if not budgets:
                return FinanceQueryResult(
                    spoken_response="You don't have any budgets set up yet.",
                    data={"budgets": []},
                )
            
            over_budget = [b for b in budgets if b["spent_cents"] > b["limit_cents"]]
            warning = [b for b in budgets if 80 <= (b["spent_cents"] / b["limit_cents"]) * 100 <= 100]
            
            if over_budget:
                response = f"You're over budget on {len(over_budget)} categories: "
                response += ", ".join([b["name"] for b in over_budget])
            elif warning:
                response = f"You're approaching your limit on {len(warning)} budgets: "
                response += ", ".join([b["name"] for b in warning])
            else:
                response = f"All {len(budgets)} budgets are looking good this month."
            
            return FinanceQueryResult(
                spoken_response=response,
                data={"budgets": budgets},
            )
    
    async def handle_goal_status(
        self,
        goal_name: Optional[str] = None,
    ) -> FinanceQueryResult:
        """Handle savings goal query."""
        
        if goal_name:
            goal = await self.finance.get_goal_by_name(goal_name)
            if not goal:
                return FinanceQueryResult(
                    spoken_response=f"I couldn't find a goal called {goal_name}.",
                    data={},
                )
            
            current = goal["current_cents"] / 100
            target = goal["target_cents"] / 100
            percent = (goal["current_cents"] / goal["target_cents"]) * 100
            remaining = target - current
            
            response = f"Your {goal['name']} goal is {percent:.0f}% complete. "
            response += f"You have ${current:,.2f} of ${target:,.2f}."
            
            if goal["target_date"]:
                response += f" Target date: {goal['target_date']}."
            
            return FinanceQueryResult(
                spoken_response=response,
                data=goal,
            )
        else:
            goals = await self.finance.get_all_goals()
            
            if not goals:
                return FinanceQueryResult(
                    spoken_response="You don't have any savings goals set up.",
                    data={"goals": []},
                )
            
            response = f"You have {len(goals)} savings goals. "
            for goal in goals[:2]:
                percent = (goal["current_cents"] / goal["target_cents"]) * 100
                response += f"{goal['name']}: {percent:.0f}% complete. "
            
            return FinanceQueryResult(
                spoken_response=response,
                data={"goals": goals},
            )
    
    async def handle_bills(
        self,
        time_period: str = "this_week",
    ) -> FinanceQueryResult:
        """Handle upcoming bills query."""
        
        start_date, end_date, period_name = self._parse_time_period(time_period)
        
        bills = await self.finance.get_upcoming_bills(end_date)
        
        if not bills:
            return FinanceQueryResult(
                spoken_response=f"You don't have any bills due {period_name}.",
                data={"bills": []},
            )
        
        total = sum(b["typical_amount_cents"] for b in bills) / 100
        
        response = f"You have {len(bills)} bills due {period_name}, totaling about ${total:,.2f}. "
        
        for bill in bills[:3]:
            amount = bill["typical_amount_cents"] / 100
            response += f"{bill['name']}: ${amount:,.2f}, due {bill['next_expected']}. "
        
        return FinanceQueryResult(
            spoken_response=response,
            data={"bills": bills, "total": total},
        )
    
    async def handle_transactions(
        self,
        count: int = 5,
        time_period: Optional[str] = None,
    ) -> FinanceQueryResult:
        """Handle recent transactions query."""
        
        if time_period:
            start_date, end_date, period_name = self._parse_time_period(time_period)
            transactions = await self.finance.get_transactions_in_range(start_date, end_date, limit=count)
        else:
            transactions = await self.finance.get_recent_transactions(count)
        
        if not transactions:
            return FinanceQueryResult(
                spoken_response="I couldn't find any recent transactions.",
                data={"transactions": []},
            )
        
        response = f"Here are your last {len(transactions)} transactions: "
        
        for txn in transactions:
            amount = abs(txn["amount_cents"]) / 100
            direction = "from" if txn["amount_cents"] > 0 else "at"
            response += f"${amount:,.2f} {direction} {txn['description'][:30]}. "
        
        return FinanceQueryResult(
            spoken_response=response,
            data={"transactions": transactions},
        )
    
    def _parse_time_period(self, period: str) -> tuple:
        """Parse time period to date range."""
        today = datetime.utcnow().date()
        
        if period == "today":
            return today, today, "today"
        elif period == "this_week":
            start = today - timedelta(days=today.weekday())
            return start, today, "this week"
        elif period == "this_month":
            start = today.replace(day=1)
            return start, today, "this month"
        elif period == "last_month":
            first_of_this = today.replace(day=1)
            last_of_prev = first_of_this - timedelta(days=1)
            first_of_prev = last_of_prev.replace(day=1)
            return first_of_prev, last_of_prev, "last month"
        else:
            # Default to this month
            start = today.replace(day=1)
            return start, today, "this month"
```

---

## 6. Dashboard Pages

### 6.1 Finance Dashboard Routes

```
/finance                → Finance overview
/finance/accounts       → Account list and details
/finance/transactions   → Transaction search and categorization
/finance/budgets        → Budget management
/finance/goals          → Savings goals
/finance/recurring      → Bills and recurring payments
```

### 6.2 Finance Overview Page

```typescript
// pages/Finance.tsx
import { useEffect, useState } from 'preact/hooks';
import { Card } from '../components/common/Card';
import { ProgressBar } from '../components/common/ProgressBar';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { Navigate } from 'preact-router';

interface FinanceOverview {
  net_worth: number;
  accounts: {
    id: number;
    name: string;
    type: string;
    balance: number;
  }[];
  spending_this_month: number;
  budget_status: {
    name: string;
    spent: number;
    limit: number;
  }[];
  goals: {
    name: string;
    current: number;
    target: number;
  }[];
  upcoming_bills: {
    name: string;
    amount: number;
    due_date: string;
  }[];
  last_sync: string;
}

export function Finance() {
  const { isSuperUser } = useAuth();
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  
  // Redirect if not super user
  if (!isSuperUser) {
    return <Navigate to="/" />;
  }
  
  useEffect(() => {
    api.get('/finance/overview').then(setOverview);
  }, []);
  
  if (!overview) {
    return <div class="p-4">Loading financial data...</div>;
  }
  
  return (
    <div class="p-6 space-y-6">
      <div class="flex justify-between items-center">
        <h1 class="text-2xl font-bold">Finance</h1>
        <span class="text-sm text-gray-500">
          Last sync: {new Date(overview.last_sync).toLocaleString()}
        </span>
      </div>
      
      {/* Net Worth */}
      <Card>
        <div class="text-sm text-gray-500">Net Worth</div>
        <div class={`text-3xl font-bold ${overview.net_worth >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          ${overview.net_worth.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </div>
      </Card>
      
      {/* Accounts Grid */}
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        {overview.accounts.map(account => (
          <Card key={account.id}>
            <div class="text-sm text-gray-500 capitalize">{account.type}</div>
            <div class="font-medium">{account.name}</div>
            <div class={`text-lg ${account.balance >= 0 ? '' : 'text-red-600'}`}>
              ${account.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </div>
          </Card>
        ))}
      </div>
      
      {/* Budget Status */}
      <Card title="Budget Status">
        <div class="space-y-4">
          {overview.budget_status.map(budget => {
            const percent = (budget.spent / budget.limit) * 100;
            return (
              <div key={budget.name}>
                <div class="flex justify-between text-sm mb-1">
                  <span>{budget.name}</span>
                  <span>${budget.spent.toFixed(2)} / ${budget.limit.toFixed(2)}</span>
                </div>
                <ProgressBar 
                  percent={percent}
                  color={percent > 100 ? 'red' : percent > 80 ? 'yellow' : 'green'}
                />
              </div>
            );
          })}
          <a href="/finance/budgets" class="text-blue-500 text-sm">Manage budgets →</a>
        </div>
      </Card>
      
      {/* Goals */}
      <Card title="Savings Goals">
        <div class="space-y-4">
          {overview.goals.map(goal => {
            const percent = (goal.current / goal.target) * 100;
            return (
              <div key={goal.name}>
                <div class="flex justify-between text-sm mb-1">
                  <span>{goal.name}</span>
                  <span>{percent.toFixed(0)}%</span>
                </div>
                <ProgressBar percent={percent} color="blue" />
                <div class="text-xs text-gray-500 mt-1">
                  ${goal.current.toLocaleString()} of ${goal.target.toLocaleString()}
                </div>
              </div>
            );
          })}
          <a href="/finance/goals" class="text-blue-500 text-sm">Manage goals →</a>
        </div>
      </Card>
      
      {/* Upcoming Bills */}
      <Card title="Upcoming Bills">
        <div class="space-y-2">
          {overview.upcoming_bills.map(bill => (
            <div key={bill.name} class="flex justify-between py-2 border-b last:border-0">
              <span>{bill.name}</span>
              <div class="text-right">
                <div>${bill.amount.toFixed(2)}</div>
                <div class="text-xs text-gray-500">{bill.due_date}</div>
              </div>
            </div>
          ))}
          <a href="/finance/recurring" class="text-blue-500 text-sm">View all bills →</a>
        </div>
      </Card>
    </div>
  );
}
```

---

## 7. API Endpoints

### 7.1 Finance API Router

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, date

router = APIRouter(prefix="/api/finance", tags=["finance"])

# All finance endpoints require super user
async def require_finance_access(user: dict = Depends(require_super_user)):
    """Verify super user access for finance endpoints."""
    return user

@router.get("/overview")
async def get_finance_overview(
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Get finance dashboard overview."""
    return await finance.get_overview()

@router.get("/accounts")
async def list_accounts(
    include_hidden: bool = False,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> List[dict]:
    """List all financial accounts."""
    return await finance.get_all_accounts(include_hidden=include_hidden)

@router.get("/accounts/{account_id}")
async def get_account(
    account_id: int,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Get account details."""
    account = await finance.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.put("/accounts/{account_id}")
async def update_account(
    account_id: int,
    update: AccountUpdate,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Update account settings (e.g., hide)."""
    return await finance.update_account(account_id, update.dict())

@router.get("/transactions")
async def list_transactions(
    account_id: Optional[int] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> List[dict]:
    """List transactions with filters."""
    return await finance.list_transactions(
        account_id=account_id,
        category=category,
        start_date=start_date,
        end_date=end_date,
        search=search,
        limit=limit,
        offset=offset,
    )

@router.put("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    update: TransactionUpdate,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Update transaction (category, notes)."""
    return await finance.update_transaction(transaction_id, update.dict())

@router.get("/spending")
async def get_spending(
    start_date: date,
    end_date: date,
    group_by: str = Query("category", regex="^(category|day|week|month)$"),
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Get spending breakdown."""
    return await finance.get_spending(start_date, end_date, group_by)

# Budgets
@router.get("/budgets")
async def list_budgets(
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> List[dict]:
    """List all budgets with current status."""
    return await finance.get_all_budgets_status()

@router.post("/budgets")
async def create_budget(
    budget: BudgetCreate,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Create a new budget."""
    return await finance.create_budget(budget.dict())

@router.put("/budgets/{budget_id}")
async def update_budget(
    budget_id: int,
    update: BudgetUpdate,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Update budget."""
    return await finance.update_budget(budget_id, update.dict())

@router.delete("/budgets/{budget_id}")
async def delete_budget(
    budget_id: int,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Delete budget."""
    await finance.delete_budget(budget_id)
    return {"deleted": True}

# Goals
@router.get("/goals")
async def list_goals(
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> List[dict]:
    """List all savings goals."""
    return await finance.get_all_goals()

@router.post("/goals")
async def create_goal(
    goal: GoalCreate,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Create a new savings goal."""
    return await finance.create_goal(goal.dict())

@router.put("/goals/{goal_id}")
async def update_goal(
    goal_id: int,
    update: GoalUpdate,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Update goal."""
    return await finance.update_goal(goal_id, update.dict())

@router.post("/goals/{goal_id}/contribution")
async def add_contribution(
    goal_id: int,
    contribution: ContributionCreate,
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> dict:
    """Add manual contribution to goal."""
    return await finance.add_contribution(goal_id, contribution.dict())

# Recurring
@router.get("/recurring")
async def list_recurring(
    user: dict = Depends(require_finance_access),
    finance: FinanceService = Depends(get_finance_service),
) -> List[dict]:
    """List recurring transactions (bills)."""
    return await finance.get_recurring()

@router.post("/sync")
async def trigger_sync(
    user: dict = Depends(require_finance_access),
    sync_service: FinanceSyncService = Depends(get_sync_service),
) -> dict:
    """Manually trigger a sync."""
    result = await sync_service.sync_all()
    return result
```

---

## 8. Implementation Checklist

### SimpleFIN Integration
- [ ] SimpleFIN client implementation
- [ ] Access URL secure storage
- [ ] Account sync
- [ ] Transaction sync
- [ ] Error handling and retry logic

### Data Layer
- [ ] Create all finance tables
- [ ] Add indexes
- [ ] Migration scripts

### Sync Worker
- [ ] ARQ task for scheduled sync
- [ ] Budget spending recalculation
- [ ] Recurring transaction detection

### Categorization
- [ ] Default category rules
- [ ] Auto-categorization logic
- [ ] Learning from corrections

### Voice Commands
- [ ] Add finance intents to taxonomy
- [ ] Train intent classifier
- [ ] Voice handler implementation
- [ ] Voice verification integration

### Dashboard
- [ ] Finance overview page
- [ ] Accounts page
- [ ] Transactions page with search/filter
- [ ] Budgets management page
- [ ] Goals page
- [ ] Recurring bills page

### Security
- [ ] Super user enforcement on all endpoints
- [ ] Device restriction for voice commands
- [ ] Voice verification for all queries
- [ ] Audit logging for finance access

### Notifications
- [ ] Budget threshold alerts
- [ ] Large transaction alerts
- [ ] Bill due reminders
- [ ] Low balance warnings

---

## 9. Acceptance Criteria

1. **Sync works:** Accounts and transactions sync from SimpleFIN every 4 hours
2. **Voice queries work:** Super user can query balances, spending, budgets via voice on registered device
3. **Security enforced:** Non-super users cannot access any finance features
4. **Budgets track:** Budget spending updates automatically from transactions
5. **Goals track:** Savings goals show progress correctly
6. **Bills predicted:** Recurring bills detected and shown with due dates
7. **Dashboard functional:** All finance pages load and display data correctly

---

## 10. Handoff Notes for Implementation Agent

### Critical Points

1. **Super user ONLY.** Triple-check that all finance endpoints and voice commands verify super user status AND device restriction.

2. **SimpleFIN is read-only.** No ability to make transactions. This is intentional and important.

3. **Voice confirmation required.** Even for queries, require voice verification for finance commands.

4. **Sync errors should degrade gracefully.** If SimpleFIN is down, use cached data and show last sync time.

5. **Categorization will need tuning.** Start with rules, expect to add user corrections over time.

### Common Pitfalls

- Forgetting device restriction on voice commands
- Not handling SimpleFIN API rate limits or downtime
- Exposing full account numbers (always mask to last 4 digits)
- Logging sensitive financial data
- Not updating budget spending when transactions change

### Security Review Checklist

- [ ] All endpoints check super user role
- [ ] Voice commands check device + voice
- [ ] No full account numbers stored or logged
- [ ] SimpleFIN access URL encrypted in database
- [ ] Finance access logged for audit trail

---

**End of Area 19: Personal Finance Integration**

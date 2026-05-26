from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import json
import os
import traceback
import hashlib
import time

load_dotenv()

# ── In-memory cache ───────────────────────────────────────────
class SimpleCache:
    def __init__(self, ttl_seconds=3600):
        self._cache = {}
        self._ttl = ttl_seconds

    def get(self, key):
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key, value):
        self._cache[key] = (value, time.time())

    def delete(self, key):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()

    def size(self):
        return len(self._cache)

cache = SimpleCache(ttl_seconds=3600)
CACHE_ENABLED = True
print("In-memory cache ready")

# ── FastAPI setup ─────────────────────────────────────────────
app = FastAPI(
    title="FlexiKitch Dashboard Chatbot API",
    description="AI chatbot for FlexiKitch Power BI dashboard",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── OpenAI client ─────────────────────────────────────────────
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Request/Response models ───────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    query_used: str = ""

# ── Load all dataframes ───────────────────────────────────────
def load_dataframes():
    dfs = {}

    # Capsule CRM
    try:
        df = pd.read_csv('data/Capsule Opportunites.csv', low_memory=False)
        df['AUD Value'] = pd.to_numeric(df['AUD Value'], errors='coerce').fillna(0)
        df['AUD Value'] = df['AUD Value'].astype(float)
        df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
        df['Actual Close Date'] = pd.to_datetime(df['Actual Close Date'], errors='coerce')
        dfs['Capsule'] = df
        print(f"  Capsule: {len(df)} rows")
    except Exception as e:
        print(f"  Capsule error: {e}")

    # GSC Chart
    try:
        df = pd.read_csv('data/Chart.csv')
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['CTR'] = df['CTR'].str.replace('%', '').astype(float)
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce')
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        df['Impressions'] = pd.to_numeric(df['Impressions'], errors='coerce').fillna(0)
        dfs['Chart'] = df
        print(f"  Chart: {len(df)} rows")
    except Exception as e:
        print(f"  Chart error: {e}")

    # Pages
    try:
        df = pd.read_csv('data/Pages.csv')
        df.columns = ['Page', 'Clicks', 'Impressions', 'CTR', 'Position']
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        df['Impressions'] = pd.to_numeric(df['Impressions'], errors='coerce').fillna(0)
        df['CTR'] = df['CTR'].str.replace('%', '').astype(float)
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce').fillna(0)
        dfs['Pages'] = df
        print(f"  Pages: {len(df)} rows")
    except Exception as e:
        print(f"  Pages error: {e}")

    # Queries
    try:
        df = pd.read_csv('data/Queries.csv')
        df.columns = ['Query', 'Clicks', 'Impressions', 'CTR', 'Position']
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        df['Impressions'] = pd.to_numeric(df['Impressions'], errors='coerce').fillna(0)
        df['CTR'] = df['CTR'].str.replace('%', '').astype(float)
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce').fillna(0)
        dfs['Queries'] = df
        print(f"  Queries: {len(df)} rows")
    except Exception as e:
        print(f"  Queries error: {e}")

    # GA4
    try:
        df = pd.read_csv('data/Google Analytics 12 months.csv', skiprows=6, engine='python')
        df.columns = df.columns.str.strip()
        df['Sessions'] = pd.to_numeric(df['Sessions'], errors='coerce').fillna(0)
        df = df.rename(columns={
            'Session primary channel group (Default Channel Group)': 'Channel'
        })
        dfs['GA4'] = df
        print(f"  GA4: {len(df)} rows")
    except Exception as e:
        print(f"  GA4 error: {e}")

    # Countries
    try:
        df = pd.read_csv('data/Countries.csv')
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        df['Impressions'] = pd.to_numeric(df['Impressions'], errors='coerce').fillna(0)
        dfs['Countries'] = df
        print(f"  Countries: {len(df)} rows")
    except Exception as e:
        print(f"  Countries error: {e}")

    # Devices
    try:
        df = pd.read_csv('data/Devices.csv')
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        dfs['Devices'] = df
        print(f"  Devices: {len(df)} rows")
    except Exception as e:
        print(f"  Devices error: {e}")

    # Search Appearance
    try:
        df = pd.read_csv('data/Search appearance.csv')
        dfs['Search Appearance'] = df
        print(f"  Search Appearance: {len(df)} rows")
    except Exception as e:
        print(f"  Search Appearance error: {e}")

    # Targets
    try:
        df = pd.read_excel('data/Target_Table_2026.xlsx')
        dfs['Targets'] = df
        print(f"  Targets: {len(df)} rows")
    except Exception as e:
        print(f"  Targets error: {e}")

    return dfs

# ── Branded / Non-branded split ───────────────────────────────
def calculate_branded_split():
    try:
        queries = DATAFRAMES.get('Queries', pd.DataFrame())
        branded_keywords = ['flexikitch', 'flexi kitchen', 'flexi kitch', 'flexikitch pty', 'prompcorp']
        pattern = '|'.join(branded_keywords)

        branded = queries[queries['Query'].str.contains(pattern, case=False, na=False)] if not queries.empty else pd.DataFrame()
        non_branded = queries[~queries['Query'].str.contains(pattern, case=False, na=False)] if not queries.empty else pd.DataFrame()

        total_clicks = int(queries['Clicks'].sum()) if not queries.empty else 0
        branded_clicks = int(branded['Clicks'].sum()) if not branded.empty else 0
        non_branded_clicks = int(non_branded['Clicks'].sum()) if not non_branded.empty else 0

        return {
            'branded_clicks': branded_clicks,
            'non_branded_clicks': non_branded_clicks,
            'branded_impressions': int(branded['Impressions'].sum()) if not branded.empty else 0,
            'non_branded_impressions': int(non_branded['Impressions'].sum()) if not non_branded.empty else 0,
            'total_clicks': total_clicks,
            'branded_pct': round(branded_clicks / total_clicks * 100, 2) if total_clicks else 0,
            'non_branded_pct': round(non_branded_clicks / total_clicks * 100, 2) if total_clicks else 0
        }
    except Exception as e:
        return {'error': str(e)}

# ── Pre-calculate data summary ────────────────────────────────
def get_data_summary():
    capsule = DATAFRAMES.get('Capsule', pd.DataFrame())
    chart = DATAFRAMES.get('Chart', pd.DataFrame())

    won = capsule[capsule['Milestone'] == 'Won'].copy()
    won_by_year = won.groupby(won['Actual Close Date'].dt.year)['AUD Value'].sum().to_dict()
    won_count_by_year = won.groupby(won['Actual Close Date'].dt.year)['Opportunity Id'].count().to_dict()

    gsc_by_year = {}
    for year in sorted(chart['Date'].dt.year.dropna().unique()):
        y = chart[chart['Date'].dt.year == year]
        gsc_by_year[int(year)] = {
            'rows': len(y),
            'clicks': int(y['Clicks'].sum()),
            'impressions': int(y['Impressions'].sum()),
            'ctr_pct': round(y['Clicks'].sum() / y['Impressions'].sum() * 100, 2) if y['Impressions'].sum() > 0 else 0,
            'avg_position': round((y['Position'] * y['Impressions']).sum() / y['Impressions'].sum(), 2) if y['Impressions'].sum() > 0 else 0
        }

    return {
        'won_revenue_by_year': {int(k): round(float(v), 2) for k, v in won_by_year.items()},
        'won_deals_count_by_year': {int(k): int(v) for k, v in won_count_by_year.items()},
        'gsc_by_year': gsc_by_year,
        'pipeline_names': capsule['Pipeline'].dropna().unique().tolist(),
        'milestone_names': capsule['Milestone'].dropna().unique().tolist(),
        'total_won_deals': len(won),
        'total_won_revenue': round(float(won['AUD Value'].sum()), 2),
        'avg_deal_value': round(float(won['AUD Value'].mean()), 2),
        'active_pipeline_count': len(capsule[~capsule['Milestone'].isin(['Won', 'Lost'])]),
        'overall_ctr': round(chart['Clicks'].sum() / chart['Impressions'].sum() * 100, 2) if chart['Impressions'].sum() > 0 else 0,
        'total_clicks': int(chart['Clicks'].sum()),
        'total_impressions': int(chart['Impressions'].sum()),
    }

# ── Load on startup ───────────────────────────────────────────
print("Loading all dataframes...")
DATAFRAMES = load_dataframes()
print(f"Loaded {len(DATAFRAMES)} dataframes: {list(DATAFRAMES.keys())}")
print(f"  Pipeline values: {DATAFRAMES['Capsule']['Pipeline'].unique()}")

BRANDED_SPLIT = calculate_branded_split()
print(f"  Branded split: {BRANDED_SPLIT}")

DATA_SUMMARY = get_data_summary()
print(f"  Won revenue years: {list(DATA_SUMMARY['won_revenue_by_year'].keys())}")
print(f"  Won deals years: {list(DATA_SUMMARY['won_deals_count_by_year'].keys())}")

# ── Conversation store ────────────────────────────────────────
conversations: dict = {}

# ── Build schema for AI ───────────────────────────────────────
def get_schema_description():
    schema = {}
    for name, df in DATAFRAMES.items():
        schema[name] = {
            'columns': list(df.columns),
            'rows': len(df),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'sample': df.head(2).to_dict('records')
        }
    return schema

SCHEMA = get_schema_description()

# ── Generate Pandas query ─────────────────────────────────────
def generate_pandas_query(question: str, conversation_history: list) -> str:
    schema_str = json.dumps(SCHEMA, indent=2, default=str)
    summary_str = json.dumps(DATA_SUMMARY, indent=2, default=str)
    branded_str = json.dumps(BRANDED_SPLIT, indent=2, default=str)

    prompt = f"""
You are a Python/Pandas expert. Generate ONLY executable Python code to answer this question.

DATA SUMMARY (pre-computed from actual data):
{summary_str}

BRANDED SPLIT (pre-computed):
{branded_str}

SCHEMA:
{schema_str}

VARIABLE NAMES (already loaded):
- capsule: CRM opportunities (Milestone, Pipeline, AUD Value, Owner, Created, Actual Close Date)
- chart: GSC daily trend (Date, Clicks, Impressions, CTR, Position)
- pages: Top pages (Page, Clicks, Impressions, CTR, Position)
- queries: Search queries (Query, Clicks, Impressions, CTR, Position)
- ga4: GA4 sessions (Channel, Date, Sessions)
- countries: Clicks by country
- devices: Clicks by device
- search_appearance: Search appearance types
- targets: 2026 monthly targets

RULES:

[GENERAL]
1. Store final answer in variable: result
2. result must be DataFrame, dict, list, number, or string
3. Do NOT import anything — pd and np are available
4. Do NOT use print()
5. Never chain .fillna() after .sum() .mean() .count()
6. If cannot answer: result = "I cannot find this information in the dashboard data."

[DEALS COUNT vs REVENUE]
7. "How many deals" or "number of deals" or "count" = COUNT of opportunities
   result = len(capsule[capsule['Milestone'] == 'Won'])
8. "Revenue" or "value" or "how much earned" = SUM of AUD Value
   result = capsule[capsule['Milestone'] == 'Won']['AUD Value'].sum()
9. NEVER confuse count with revenue

[MONTHLY BREAKDOWNS]
10. Monthly won DEAL COUNT for a year (use Created date to match Power BI):
    won = capsule[(capsule['Milestone'] == 'Won') & (capsule['Created'].dt.year == YEAR)].copy()
    won['Month'] = won['Created'].dt.month
    result = won.groupby('Month')['Opportunity Id'].count().reset_index()
    result.columns = ['Month', 'Won Deals']
11. Monthly won REVENUE for a year (use Created date to match Power BI):
    won = capsule[(capsule['Milestone'] == 'Won') & (capsule['Created'].dt.year == YEAR)].copy()
    won['Month'] = won['Created'].dt.month
    result = won.groupby('Month')['AUD Value'].sum().reset_index()
    result.columns = ['Month', 'Revenue']
12. For a SPECIFIC month use Created date:
    won = capsule[(capsule['Milestone'] == 'Won') & 
                  (capsule['Created'].dt.year == YEAR) &
                  (capsule['Created'].dt.month == MONTH)]
    result = won['AUD Value'].sum()
13. For MONTHLY revenue/deals breakdowns always use Created date (matches Power BI)
14. For YEARLY total revenue use Actual Close Date
15. Demand/enquiries always use Created date
16. Available won revenue years: {list(DATA_SUMMARY['won_revenue_by_year'].keys())}
17. Available won deals years: {list(DATA_SUMMARY['won_deals_count_by_year'].keys())}
18. If year not in those lists: result = "No data available for that year."
19. NEVER assume a year has no data without checking above lists

[CTR]
20. NEVER use chart['CTR'].mean() — gives wrong result
21. Overall CTR: result = round(chart['Clicks'].sum() / chart['Impressions'].sum() * 100, 2)
22. Yearly CTR:
    y = chart[chart['Date'].dt.year == YEAR]
    result = round(y['Clicks'].sum() / y['Impressions'].sum() * 100, 2)

[AVERAGE POSITION]
23. Always weighted average:
    result = round((chart['Position'] * chart['Impressions']).sum() / chart['Impressions'].sum(), 2)
24. With year filter:
    y = chart[chart['Date'].dt.year == YEAR]
    result = round((y['Position'] * y['Impressions']).sum() / y['Impressions'].sum(), 2)

[PIPELINE]
25. Pipeline names EXACTLY: "Sales Pipeline", "Key Account Pipeline", "High Value Pipeline (75k+)"
26. Pipeline revenue: filter Milestone=='Won' AND Pipeline name
27. Pipeline % = pipeline won revenue / total won revenue * 100

[DAYS IN STAGE]
28. Calculate dynamically from Created date:
    active = capsule[~capsule['Milestone'].isin(['Won', 'Lost'])].copy()
    active['Days in Stage'] = (pd.Timestamp.today() - active['Created']).dt.days
29. For specific owner:
    owner_active = active[active['Owner'] == 'OWNER NAME']
    result = int(owner_active['Days in Stage'].max())
30. For all owners:
    result = active.groupby('Owner')['Days in Stage'].max().sort_values(ascending=False).reset_index()

[BRANDED vs NON-BRANDED]
31. Use pre-computed BRANDED_SPLIT data — do not recalculate:
    result = {{'branded_clicks': {BRANDED_SPLIT.get('branded_clicks', 0)}, 'non_branded_clicks': {BRANDED_SPLIT.get('non_branded_clicks', 0)}, 'branded_pct': {BRANDED_SPLIT.get('branded_pct', 0)}, 'non_branded_pct': {BRANDED_SPLIT.get('non_branded_pct', 0)}}}

[SEO vs CRM SEPARATION]
32. Sales/revenue/deals questions: ONLY use capsule — never chart
33. SEO/clicks/CTR/position questions: ONLY use chart/pages/queries — never capsule

QUESTION: {question}

Return ONLY Python code. No markdown, no backticks, no explanations.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=600,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    code = response.choices[0].message.content.strip()
    code = code.replace('```python', '').replace('```', '').strip()
    return code

# ── Execute query safely ──────────────────────────────────────
def execute_query(code: str) -> tuple:
    safe_globals = {
        'pd': pd,
        'np': np,
        'capsule': DATAFRAMES.get('Capsule', pd.DataFrame()),
        'chart': DATAFRAMES.get('Chart', pd.DataFrame()),
        'pages': DATAFRAMES.get('Pages', pd.DataFrame()),
        'queries': DATAFRAMES.get('Queries', pd.DataFrame()),
        'ga4': DATAFRAMES.get('GA4', pd.DataFrame()),
        'countries': DATAFRAMES.get('Countries', pd.DataFrame()),
        'devices': DATAFRAMES.get('Devices', pd.DataFrame()),
        'search_appearance': DATAFRAMES.get('Search Appearance', pd.DataFrame()),
        'targets': DATAFRAMES.get('Targets', pd.DataFrame()),
    }
    local_vars = {}

    try:
        exec(code, safe_globals, local_vars)
        result = local_vars.get('result', 'No result variable found')
        return result, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)}"

# ── Format answer ─────────────────────────────────────────────
def format_answer(question: str, result, code: str, error: str = None) -> str:

    # Convert result to string first
    if error:
        result_str = f"Query error: {error}\nCode:\n{code}"
    elif isinstance(result, pd.DataFrame):
        result_str = "Empty result — no matching data found" if len(result) == 0 else result.head(30).to_string(index=False)
    elif isinstance(result, dict):
        result_str = json.dumps(result, indent=2, default=str)
    elif isinstance(result, (list, tuple)):
        result_str = json.dumps(result[:30], indent=2, default=str)
    elif isinstance(result, (int, float, np.integer, np.floating)):
        result_str = str(result)
    else:
        result_str = str(result)

    # Build dynamic context
    try:
        summary_str = json.dumps(DATA_SUMMARY, indent=2, default=str)
        branded_str = json.dumps(BRANDED_SPLIT, indent=2, default=str)
        dynamic_context = f"""
LIVE DATA SUMMARY:
{summary_str}

BRANDED SPLIT:
{branded_str}
"""
    except Exception as e:
        dynamic_context = f"Context unavailable: {str(e)}"

    prompt = f"""
You are a business intelligence assistant for FlexiKitch / Prompcorp (Australia).
FlexiKitch sells and leases commercial kitchen equipment.

QUESTION: {question}

QUERY RESULT:
{result_str}

{dynamic_context}

RULES:
- Answer using numbers from QUERY RESULT as primary source
- For sales/revenue/deals: ONLY reference CRM data — NEVER mention CTR, position, impressions
- For SEO questions: ONLY reference SEO data — NEVER mention revenue, deals, pipeline
- Format nicely: $8.7M not 8747092.87, 1,234 deals not 1234
- For monthly breakdowns show month names not numbers (1=January, 2=February, 3=March, 4=April, 5=May, 6=June, 7=July, 8=August, 9=September, 10=October, 11=November, 12=December)
- Revenue is always AUD
- Keep concise — 2-5 sentences or a clean list
- Never say "Hello!" — answer directly
- Never mention pandas, dataframe, code, or technical terms
- For partial year data (e.g. 2026) mention it is partial year
- If error in result, apologise briefly and suggest rephrasing
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=700,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# ── Chat endpoint ─────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        question = request.question.strip()
        session_id = request.session_id

        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")

        if session_id not in conversations:
            conversations[session_id] = []

        cache_key = f"chat:{hashlib.md5(question.lower().encode()).hexdigest()}"

        if CACHE_ENABLED:
            cached = cache.get(cache_key)
            if cached:
                print(f"Cache HIT: {question[:50]}")
                conversations[session_id].append({"role": "user", "content": question})
                conversations[session_id].append({"role": "assistant", "content": cached})
                return ChatResponse(answer=cached, session_id=session_id, query_used="[cached]")
            print(f"Cache MISS: {question[:50]}")

        conversations[session_id].append({"role": "user", "content": question})

        print(f"\nQuestion: {question}")
        print("Generating query...")
        code = generate_pandas_query(question, conversations[session_id][-6:])
        print(f"Generated code:\n{code}")

        print("Executing...")
        result, error = execute_query(code)
        print(f"{'Error: ' + error if error else 'Success'}")

        print("Formatting answer...")
        answer = format_answer(question, result, code, error)

        if CACHE_ENABLED and not error:
            cache.set(cache_key, answer)
            print(f"Cached: {question[:50]}")

        conversations[session_id].append({"role": "assistant", "content": answer})
        print(f"Answer: {answer[:100]}...")

        return ChatResponse(answer=answer, session_id=session_id, query_used=code)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Server error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# ── Health check ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "running",
        "dataframes": list(DATAFRAMES.keys()),
        "cache_keys": cache.size(),
        "won_revenue_years": list(DATA_SUMMARY['won_revenue_by_year'].keys()),
        "won_deals_years": list(DATA_SUMMARY['won_deals_count_by_year'].keys()),
        "branded_split": BRANDED_SPLIT
    }

# ── Cache endpoints ───────────────────────────────────────────
@app.delete("/cache/clear")
async def clear_cache():
    cache.clear()
    return {"message": "Cache cleared successfully"}

@app.get("/cache/stats")
async def cache_stats():
    return {
        "type": "in-memory",
        "keys_cached": cache.size(),
        "ttl_seconds": 3600
    }

# ── Root ──────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "FlexiKitch Dashboard Chatbot API v4.0",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/health",
        "chat": "POST http://localhost:8000/chat",
        "cache_clear": "DELETE http://localhost:8000/cache/clear"
    }
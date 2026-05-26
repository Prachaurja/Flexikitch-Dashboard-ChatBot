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
    description="AI chatbot for FlexiKitch Power BI dashboard — Text to Pandas",
    version="3.0.0"
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
        print(f"  Capsule: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        print(f" Capsule error: {e}")

    # GSC Chart
    try:
        df = pd.read_csv('data/Chart.csv')
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['CTR'] = df['CTR'].str.replace('%', '').astype(float)
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce')
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        df['Impressions'] = pd.to_numeric(df['Impressions'], errors='coerce').fillna(0)
        dfs['Chart'] = df
        print(f"  Chart: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        print(f" Chart error: {e}")

    # Pages
    try:
        df = pd.read_csv('data/Pages.csv')
        df.columns = ['Page', 'Clicks', 'Impressions', 'CTR', 'Position']
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        df['Impressions'] = pd.to_numeric(df['Impressions'], errors='coerce').fillna(0)
        df['CTR'] = df['CTR'].str.replace('%', '').astype(float)
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce').fillna(0)
        dfs['Pages'] = df
        print(f"  Pages: {len(df)} rows, columns: {list(df.columns)}")
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
        print(f"  Queries: {len(df)} rows, columns: {list(df.columns)}")
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
        print(f"  GA4: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        print(f"  GA4 error: {e}")

    # Countries
    try:
        df = pd.read_csv('data/Countries.csv')
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        df['Impressions'] = pd.to_numeric(df['Impressions'], errors='coerce').fillna(0)
        dfs['Countries'] = df
        print(f"  Countries: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        print(f"  Countries error: {e}")

    # Devices
    try:
        df = pd.read_csv('data/Devices.csv')
        df['Clicks'] = pd.to_numeric(df['Clicks'], errors='coerce').fillna(0)
        dfs['Devices'] = df
        print(f"  Devices: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        print(f"  Devices error: {e}")

    # Search Appearance
    try:
        df = pd.read_csv('data/Search appearance.csv')
        dfs['Search Appearance'] = df
        print(f"  Search_appearance: {len(df)} rows")
    except Exception as e:
        print(f"  Search Appearance error: {e}")

    # Targets
    try:
        df = pd.read_excel('data/Target_Table_2026.xlsx')
        dfs['Targets'] = df
        print(f"  Targets: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        print(f"  Targets error: {e}")

    return dfs


# ── Branded / Non-branded split helper ──────────────────────
def calculate_branded_split():
    try:
        queries = DATAFRAMES.get('Queries', pd.DataFrame())

        # Exact same keywords used in Power BI Branded_Split table
        branded_keywords = [
            'flexikitch',
            'flexi kitchen',
            'flexi kitch',
            'flexikitch pty',
            'prompcorp'
        ]

        # Build pattern
        pattern = '|'.join(branded_keywords)

        branded = queries[queries['Query'].str.contains(pattern, case=False, na=False)] if not queries.empty and 'Query' in queries.columns else pd.DataFrame()
        non_branded = queries[~queries['Query'].str.contains(pattern, case=False, na=False)] if not queries.empty and 'Query' in queries.columns else pd.DataFrame()

        total_clicks = int(queries['Clicks'].sum()) if not queries.empty and 'Clicks' in queries.columns else 0
        branded_clicks = int(branded['Clicks'].sum()) if not branded.empty and 'Clicks' in branded.columns else 0
        non_branded_clicks = int(non_branded['Clicks'].sum()) if not non_branded.empty and 'Clicks' in non_branded.columns else 0

        branded_impr = int(branded['Impressions'].sum()) if not branded.empty and 'Impressions' in branded.columns else 0
        non_branded_impr = int(non_branded['Impressions'].sum()) if not non_branded.empty and 'Impressions' in non_branded.columns else 0

        branded_pct = round(branded_clicks / total_clicks * 100, 2) if total_clicks else 0
        non_branded_pct = round(non_branded_clicks / total_clicks * 100, 2) if total_clicks else 0

        return {
            'branded_clicks': branded_clicks,
            'non_branded_clicks': non_branded_clicks,
            'branded_impressions': branded_impr,
            'non_branded_impressions': non_branded_impr,
            'total_clicks': total_clicks,
            'branded_pct': branded_pct,
            'non_branded_pct': non_branded_pct
        }
    except Exception as e:
        return {'error': str(e)}

# ── Load on startup ───────────────────────────────────────────
print("Loading all dataframes...")
DATAFRAMES = load_dataframes()
print(f"Loaded {len(DATAFRAMES)} dataframes: {list(DATAFRAMES.keys())}")
print(f"  Pipeline values: {DATAFRAMES['Capsule']['Pipeline'].unique()}")
BRANDED_SPLIT = calculate_branded_split()
print(f"  Branded split: {BRANDED_SPLIT}")

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
            'sample': df.head(3).to_dict('records')
        }
    return schema

SCHEMA = get_schema_description()

# ── Step 1: Generate Pandas query ────────────────────────────
def generate_pandas_query(question: str, conversation_history: list) -> str:
    schema_str = json.dumps(SCHEMA, indent=2, default=str)

    prompt = f"""
You are a Python/Pandas expert. Generate ONLY a Python code snippet to answer this question using the available dataframes.

AVAILABLE DATAFRAMES (already loaded, do not reload):
{schema_str}

    DATAFRAME NAMES TO USE:
    - capsule → Capsule CRM data (opportunities, milestones, AUD values, owners)
    - chart → GSC daily trend (Date, Clicks, Impressions, CTR, Position)
    - pages → Top pages SEO data (Page, Clicks, Impressions, CTR, Position)
    - queries → Top search queries (Query, Clicks, Impressions, CTR, Position)
    - ga4 → Google Analytics sessions by channel
    - countries → Clicks by country
    - devices → Clicks by device
    - search_appearance → Search appearance types
    - targets → 2026 monthly targets

    STRICT RULES:
    1. Use ONLY these variable names: capsule, chart, pages, queries, ga4, countries, devices, search_appearance, targets
    2. Store your FINAL result in a variable called: result
    3. result must be either: a DataFrame, a dict, a list, a number, or a string
    4. Do NOT import anything — pandas (pd) and numpy (np) are already available
    5. Do NOT use print() — just assign to result
    6. Keep code simple and correct
    7. For ANY date filtering ALWAYS apply the year filter — even if few rows exist:
    y = chart[chart['Date'].dt.year == 2024]
    NEVER skip the year filter even if you think data might be sparse
    8. For average position with year filter ALWAYS use weighted average:
    y = chart[chart['Date'].dt.year == 2024]
    result = round((y['Position'] * y['Impressions']).sum() / y['Impressions'].sum(), 2)
    9. For milestone filtering: capsule[capsule['Milestone'] == 'Won']
    10. For string contains: df[df['col'].str.contains('text', case=False, na=False)]
    11. Never chain .fillna() after .sum(), .mean(), .count() or any aggregation
    12. If question cannot be answered with data, set result = "I cannot find this information in the dashboard data."
    13. CRITICAL — CTR values (0.49) mean 0.49% — NEVER use chart['CTR'].mean() for overall CTR — it gives WRONG result
    14. CRITICAL — For overall organic CTR ALWAYS use: result = round(chart['Clicks'].sum() / chart['Impressions'].sum() * 100, 2)
    15. CRITICAL — For yearly CTR ALWAYS use: result = round(chart[chart['Date'].dt.year == YEAR]['Clicks'].sum() / chart[chart['Date'].dt.year == YEAR]['Impressions'].sum() * 100, 2)
    16. For organic clicks: result = int(chart['Clicks'].sum())
    17. For organic impressions: result = int(chart['Impressions'].sum())
    18. Never filter chart by channel — it only contains organic GSC data
    19. Pipeline names in capsule are EXACTLY these three:
        - "Sales Pipeline"
        - "Key Account Pipeline"
        - "High Value Pipeline (75k+)"
    20. ALWAYS filter by both Milestone AND Pipeline for pipeline-specific revenue:
        filtered = capsule[(capsule['Milestone'] == 'Won') & (capsule['Pipeline'] == 'Key Account Pipeline')]
        result = filtered['AUD Value'].sum()
    21. For pipeline percentage ALWAYS divide by total WON revenue only:
        won_total = capsule[capsule['Milestone'] == 'Won']['AUD Value'].sum()
        pipeline_won = capsule[(capsule['Milestone'] == 'Won') & (capsule['Pipeline'] == 'Key Account Pipeline')]['AUD Value'].sum()
        result = round(pipeline_won / won_total * 100, 2)
    22. Never divide by total AUD Value of all milestones — only Won deals
    23. For overall average position use weighted average: result = round((chart['Position'] * chart['Impressions']).sum() / chart['Impressions'].sum(), 2)
    24. For won revenue: capsule[(capsule['Milestone'] == 'Won')]['AUD Value'].sum()
    25. For active pipeline: capsule[~capsule['Milestone'].isin(['Won', 'Lost'])]
    26. "Days in Stage" is not a column in the CSV — calculate it dynamically:
        from datetime import date
        today = pd.Timestamp.today()
        days_in_stage = (today - capsule['Created']).dt.days
    27. For max days in stage for a specific owner:
        owner_data = capsule[(capsule['Owner'] == 'Luke Mitrousis') & (~capsule['Milestone'].isin(['Won', 'Lost']))]
        today = pd.Timestamp.today()
        result = int((today - owner_data['Created']).dt.days.max())
    28. For days in stage always filter to active pipeline only (exclude Won and Lost)
    29. For all owners days in stage:
        active = capsule[~capsule['Milestone'].isin(['Won', 'Lost'])].copy()
        active['Days in Stage'] = (pd.Timestamp.today() - active['Created']).dt.days
        result = active.groupby('Owner')['Days in Stage'].max().sort_values(ascending=False).reset_index()
    30. For monthly revenue/sales ALWAYS use Actual Close Date with dynamic year and month:
        won = capsule[(capsule['Milestone'] == 'Won') & 
                    (capsule['Actual Close Date'].dt.year == YEAR) & 
                    (capsule['Actual Close Date'].dt.month == MONTH)]
        result = won['AUD Value'].sum()
    31. For yearly revenue/sales ALWAYS use Actual Close Date with dynamic year:
        won = capsule[(capsule['Milestone'] == 'Won') & 
                    (capsule['Actual Close Date'].dt.year == YEAR)]
        result = won['AUD Value'].sum()
    32. Replace YEAR and MONTH with the actual numbers from the question
        e.g. "January 2025" → year=2025, month=1
        e.g. "March 2026" → year=2026, month=3
        e.g. "2024" → year=2024, no month filter
    33. Sales/revenue questions are ALWAYS from capsule — never from chart
    34. Never mix SEO data (chart, CTR, position, impressions) into sales/revenue answers
    35. Never mix revenue/deals data into SEO answers
    36. ALWAYS check data existence by actually querying — never assume a year has no data:
    won_check = capsule[(capsule['Milestone'] == 'Won') & 
                        (capsule['Actual Close Date'].dt.year == YEAR)]
    if len(won_check) == 0:
        result = "No won revenue data found for YEAR in the dataset."
    else:
        result = won_check['AUD Value'].sum()
    37. Available years with won revenue data: 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026
    38. NEVER say a year has no data without checking — 2025 and 2026 both have real data
39. For SEO chart data check existence the same way:
    chart_check = chart[chart['Date'].dt.year == YEAR]
    if len(chart_check) == 0:
        result = "No SEO data found for YEAR in the dataset."
    else:
        result = round(chart_check['Clicks'].sum() / chart_check['Impressions'].sum() * 100, 2)
    39. Never return 0 or NaN for future years — always return a meaningful message
    40. When asked for "monthly revenue" or "monthly breakdown" without specifying 
        a single month, return a month-by-month breakdown:
        won = capsule[(capsule['Milestone'] == 'Won') & 
                    (capsule['Actual Close Date'].dt.year == YEAR)]
        won = won.copy()
        won['Month'] = won['Actual Close Date'].dt.month
        result = won.groupby('Month')['AUD Value'].sum().reset_index()
        result.columns = ['Month', 'Revenue']
    41. When asked for a SPECIFIC month revenue (e.g. "January 2025") return single value:
        won = capsule[(capsule['Milestone'] == 'Won') & 
                    (capsule['Actual Close Date'].dt.year == YEAR) &
                    (capsule['Actual Close Date'].dt.month == MONTH)]
        result = won['AUD Value'].sum()

QUESTION: {question}

Return ONLY the Python code, no explanations, no markdown, no backticks.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=500,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    code = response.choices[0].message.content.strip()
    code = code.replace('```python', '').replace('```', '').strip()
    return code

# ── Step 2: Execute the query safely ─────────────────────────
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
        result = local_vars.get('result', 'No result variable found in generated code')
        return result, None
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)}"
        return None, error

# ── Step 3: Format result into natural language ───────────────
def format_answer(question: str, result, code: str, error: str = None) -> str:

    # ── Convert result to string FIRST ───────────────────────
    if error:
        result_str = f"Query error: {error}\nCode attempted:\n{code}"
    elif isinstance(result, pd.DataFrame):
        if len(result) == 0:
            result_str = "Empty result — no matching data found"
        else:
            result_str = result.head(30).to_string(index=False)
    elif isinstance(result, dict):
        result_str = json.dumps(result, indent=2, default=str)
    elif isinstance(result, (list, tuple)):
        result_str = json.dumps(result[:30], indent=2, default=str)
    elif isinstance(result, (int, float, np.integer, np.floating)):
        result_str = str(result)
    else:
        result_str = str(result)

    # ── Build dynamic context from actual data ────────────────
    try:
        chart = DATAFRAMES.get('Chart', pd.DataFrame())
        capsule = DATAFRAMES.get('Capsule', pd.DataFrame())

        # GSC yearly breakdown — computed live from actual data
        gsc_context = {}
        for year in sorted(chart['Date'].dt.year.dropna().unique()):
            y = chart[chart['Date'].dt.year == year]
            avg_pos = round((y['Position'] * y['Impressions']).sum() / y['Impressions'].sum(), 2)
            ctr = round(y['Clicks'].sum() / y['Impressions'].sum() * 100, 2)
            gsc_context[int(year)] = {
                'rows': len(y),
                'avg_position': avg_pos,
                'ctr_pct': ctr,
                'clicks': int(y['Clicks'].sum()),
                'impressions': int(y['Impressions'].sum())
            }

        # CRM summary — computed live from actual data
        won = capsule[capsule['Milestone'] == 'Won']
        crm_context = {
            'total_won_deals': len(won),
            'total_won_revenue_aud': round(float(won['AUD Value'].sum()), 2),
            'avg_deal_value_aud': round(float(won['AUD Value'].mean()), 2)
        }

        dynamic_context = f"""
LIVE DATA CONTEXT (auto-computed from actual CSV files):
GSC yearly breakdown: {json.dumps(gsc_context, indent=2)}
CRM summary: {json.dumps(crm_context, indent=2)}
Overall organic CTR: {round(chart['Clicks'].sum() / chart['Impressions'].sum() * 100, 2)}%
Total organic clicks (all time): {int(chart['Clicks'].sum())}
Total organic impressions (all time): {int(chart['Impressions'].sum())}
"""
    except Exception as e:
        dynamic_context = f"Live context unavailable: {str(e)}"

    # ── Build prompt ──────────────────────────────────────────
    prompt = f"""
You are a friendly and accurate business intelligence assistant for FlexiKitch / Prompcorp (Australia).
FlexiKitch sells and leases commercial kitchen equipment.

QUESTION: {question}

QUERY RESULT (from actual data):
{result_str}

{dynamic_context}

YOUR JOB:
- Answer using ONLY the numbers from QUERY RESULT — that is the primary source
- Use LIVE DATA CONTEXT only as supporting reference when needed
- For sales/revenue/deals questions ONLY use CRM data — completely ignore GSC/SEO context
- For SEO/clicks/impressions/CTR/position questions ONLY use GSC data — completely ignore CRM context
- NEVER mix SEO metrics (CTR, position, impressions, clicks) into sales or revenue answers
- NEVER mix revenue, deals, pipeline, owners into SEO answers
- Format numbers nicely: $48.2M, 4,694 deals, 22.6K clicks, 0.49% CTR
- For yearly questions mention if it is a partial year
- Keep answers concise — 2 to 4 sentences max unless more detail is requested
- NEVER mention pandas, dataframe, code or any technical terms
- Never say "Hello!" at the start — just answer directly and confidently
- For CTR always show as X.XX% format (e.g. 0.49% not 0.0049)
- Revenue is always in AUD
- If result shows no data for a future year say so clearly and politely
- If the query result has an error apologise briefly and suggest rephrasing the question if needed
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=600,
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

        # ── Check cache ───────────────────────────────────────
        cache_key = f"chat:{hashlib.md5(question.lower().encode()).hexdigest()}"

        if CACHE_ENABLED:
            cached = cache.get(cache_key)
            if cached:
                print(f"⚡ Cache HIT: {question[:50]}")
                conversations[session_id].append({"role": "user", "content": question})
                conversations[session_id].append({"role": "assistant", "content": cached})
                return ChatResponse(
                    answer=cached,
                    session_id=session_id,
                    query_used="[cached]"
                )
            print(f"Cache MISS: {question[:50]}")

        # ── Add to history ────────────────────────────────────
        conversations[session_id].append({
            "role": "user",
            "content": question
        })

        print(f"\nQuestion: {question}")

        # ── Step 1: Generate code ─────────────────────────────
        print("Generating Pandas query...")
        code = generate_pandas_query(question, conversations[session_id][-6:])
        print(f"Generated code:\n{code}")

        # ── Step 2: Execute ───────────────────────────────────
        print("Executing query...")
        result, error = execute_query(code)

        if error:
            print(f"Execution error: {error}")
        else:
            print(f"Query executed successfully")

        # ── Step 3: Format answer ─────────────────────────────
        print("Formatting answer...")
        answer = format_answer(question, result, code, error)

        # ── Save to cache ─────────────────────────────────────
        if CACHE_ENABLED and not error:
            cache.set(cache_key, answer)
            print(f"Cached: {question[:50]}")

        # ── Add to history ────────────────────────────────────
        conversations[session_id].append({
            "role": "assistant",
            "content": answer
        })

        print(f"Answer: {answer[:100]}...")

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            query_used=code
        )

    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Server error: {tb}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# ── Health check ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "running",
        "method": "Text to Pandas (Method 3)",
        "dataframes_loaded": list(DATAFRAMES.keys()),
        "total_rows": {name: len(df) for name, df in DATAFRAMES.items()},
        "cache": {
            "enabled": CACHE_ENABLED,
            "type": "in-memory",
            "keys_cached": cache.size()
        }
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
        "message": "FlexiKitch Dashboard Chatbot API v3.0",
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/health",
        "chat": "POST http://localhost:8000/chat",
        "cache_clear": "DELETE http://localhost:8000/cache/clear"
    }
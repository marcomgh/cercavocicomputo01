from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import pandas as pd
import random
import string
from datetime import date

app = FastAPI()

# Sessioni
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

# Database in RAM
USERS = {}
USAGE = {}
DAILY_LIMIT = 10


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("email"):
        return RedirectResponse("/app")
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <html>
    <head>
    <style>
    body {
        font-family: Arial, sans-serif;
        background: #f5f7fa;
        display: flex;
        justify-content: center;
        padding-top: 80px;
    }
    .card {
        background: white;
        padding: 30px;
        width: 350px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    input, button {
        width: 100%;
        padding: 12px;
        margin-top: 10px;
        border-radius: 8px;
        border: 1px solid #ccc;
    }
    button {
        background: #007bff;
        color: white;
        border: none;
        cursor: pointer;
    }
    button:hover {
        background: #0056d2;
    }
    h2 {
        text-align: center;
    }
    </style>
    </head>
    <body>
    <div class="card">
        <h2>Accedi</h2>
        <form action="/send-otp" method="post">
            <input type="email" name="email" placeholder="Email" required>
            <button type="submit">Invia codice</button>
        </form>
    </div>
    </body>
    </html>
    """


@app.post("/send-otp", response_class=HTMLResponse)
async def send_otp(email: str = Form(...)):
    otp = "".join(random.choices(string.digits, k=6))
    USERS[email] = {"otp": otp}

    return f"""
    <html>
    <head>
    <style>
    body {{
        font-family: Arial, sans-serif;
        background: #f5f7fa;
        display: flex;
        justify-content: center;
        padding-top: 80px;
    }}
    .card {{
        background: white;
        padding: 30px;
        width: 350px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }}
    input, button {{
        width: 100%;
        padding: 12px;
        margin-top: 10px;
        border-radius: 8px;
        border: 1px solid #ccc;
    }}
    button {{
        background: #28a745;
        color: white;
        border: none;
        cursor: pointer;
    }}
    button:hover {{
        background: #1f7f36;
    }}
    h3 {{
        text-align: center;
    }}
    </style>
    </head>
    <body>
    <div class="card">
        <h3>Codice inviato a {email}</h3>
        <p style="text-align:center;"><b>Codice OTP (solo test): {otp}</b></p>
        <form action="/verify-otp" method="post">
            <input type="hidden" name="email" value="{email}">
            <input type="text" name="otp" placeholder="Inserisci codice" required>
            <button type="submit">Accedi</button>
        </form>
    </div>
    </body>
    </html>
    """


@app.post("/verify-otp", response_class=HTMLResponse)
async def verify_otp(request: Request, email: str = Form(...), otp: str = Form(...)):
    if email in USERS and USERS[email]["otp"] == otp:
        request.session["email"] = email
        return RedirectResponse("/app", status_code=302)
    return "<h3>Codice errato</h3>"


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")


@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    email = request.session.get("email")
    if not email:
        return RedirectResponse("/login")

    usage = USAGE.get(email, {"date": date.today(), "count": 0})
    count = usage["count"]

    return f"""
    <html>
    <head>
    <style>
    body {{
        font-family: Arial, sans-serif;
        background: #eef1f5;
        padding: 40px;
    }}
    .container {{
        max-width: 700px;
        margin: auto;
    }}
    .card {{
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }}
    button, input {{
        width: 100%;
        padding: 12px;
        margin-top: 10px;
        border-radius: 8px;
        border: 1px solid #ccc;
    }}
    button {{
        background: #007bff;
        color: white;
        border: none;
    }}
    button:hover {{
        background: #0056d2;
    }}
    .logout {{
        float: right;
        color: #d9534f;
        text-decoration: none;
        font-weight: bold;
    }}
    </style>
    </head>
    <body>
    <div class="container">

        <a class="logout" href="/logout">Logout</a>
        <h2>Ciao {email}</h2>
        <p>Ricerche oggi: <b>{count} / {DAILY_LIMIT}</b></p>

        <div class="card">
            <h3>Cerca nel tuo file</h3>
            <form action="/search" method="post" enctype="multipart/form-data">
                <input type="file" name="file" required>
                <input type="text" name="query" placeholder="Voce da cercare" required>
                <button type="submit">Cerca</button>
            </form>
        </div>

    </div>
    </body>
    </html>
    """


@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, file: UploadFile = File(...), query: str = Form(...)):
    email = request.session.get("email")
    if not email:
        return RedirectResponse("/login")

    today = date.today()
    usage = USAGE.get(email, {"date": today, "count": 0})

    if usage["date"] != today:
        usage = {"date": today, "count": 0}

    if usage["count"] >= DAILY_LIMIT:
        return """
        <html><body style="font-family: Arial; padding: 40px;">
        <h3>Hai raggiunto il limite giornaliero di ricerche.</h3>
        <a href="/app">Torna indietro</a>
        </body></html>
        """

    usage["count"] += 1
    USAGE[email] = usage

    filename = file.filename.lower()

    try:
        if filename.endswith(".csv"):
            results = []
            chunksize = 2000
            file.file.seek(0)

            for chunk in pd.read_csv(file.file, chunksize=chunksize, dtype=str):
                chunk = chunk.fillna("").astype(str)
                combined = chunk.agg(" ".join, axis=1)
                mask = combined.str.contains(query, case=False, na=False)
                if mask.any():
                    results.append(chunk[mask])

            if not results:
                return f"""
                <html><body style="font-family: Arial; padding: 40px;">
                <h3>Nessun risultato trovato per: <b>{query}</b></h3>
                <a href="/app">Torna indietro</a>
                </body></html>
                """

            final_df = pd.concat(results, ignore_index=True)
            table_html = final_df.to_html(index=False)

            return f"""
            <html><body style="font-family: Arial; padding: 40px;">
            <h3>Risultati per: <b>{query}</b></h3>
            {table_html}
            <br><a href="/app">Torna indietro</a>
            </body></html>
            """

        elif filename.endswith(".xlsx"):
            file.file.seek(0)
            df = pd.read_excel(file.file, dtype=str)
            df = df.fillna("").astype(str)
            combined = df.agg(" ".join, axis=1)
            mask = combined.str.contains(query, case=False, na=False)
            results = df[mask]

            if results.empty:
                return f"""
                <html><body style="font-family: Arial; padding: 40px;">
                <h3>Nessun risultato trovato per: <b>{query}</b></h3>
                <a href="/app">Torna indietro</a>
                </body></html>
                """

            table_html = results.to_html(index=False)

            return f"""
            <html><body style="font-family: Arial; padding: 40px;">
            <h3>Risultati per: <b>{query}</b></h3>
            {table_html}
            <br><a href="/app">Torna indietro</a>
            </body></html>
            """

        else:
            return """
            <html><body style="font-family: Arial; padding: 40px;">
            <h3>Formato non supportato. Usa CSV o XLSX.</h3>
            <a href="/app">Torna indietro</a>
            </body></html>
            """

    except Exception as e:
        return f"""
        <html><body style="font-family: Arial; padding: 40px;">
        <h3>Errore: {str(e)}</h3>
        <a href="/app">Torna indietro</a>
        </body></html>
        """

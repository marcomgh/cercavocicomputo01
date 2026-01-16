from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import pandas as pd
import random
import string
from datetime import date
import stripe

# ---------------------------------------------------------
# STRIPE TEST MODE
# ---------------------------------------------------------
stripe.api_key = "sk_test_51SqBuc3V8G72nVD2R4IEotDqXJS8eTbO1WTh87RpyBLrke8dKfsZE6U8w4w8e8xCxkrSaMoaR66PIxlFo4F4krFg00Ptudcln3"

# ---------------------------------------------------------
# FASTAPI APP
# ---------------------------------------------------------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

# Database in RAM
USERS = {}
USAGE = {}
DAILY_LIMIT = 10


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# STRIPE SUBSCRIPTION SYSTEM
# ---------------------------------------------------------
@app.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page():
    return """
    <html><body style='font-family: Arial; padding: 40px;'>
    <h2>Abbonamento annuale</h2>
    <p>3,99€/anno – accesso illimitato all'app</p>
    <form action="/create-checkout" method="post">
        <button type="submit" style="padding: 12px; background:#007bff; color:white; border:none; border-radius:8px;">
            Paga con Stripe
        </button>
    </form>
    </body></html>
    """


@app.post("/create-checkout")
async def create_checkout(request: Request):
    email = request.session.get("email")
    if not email:
        return RedirectResponse("/login")

    session = stripe.checkout.Session.create(
        customer_email=email,
        client_reference_id=email,  # 🔥 IMPORTANTE PER RIPRISTINARE LA SESSIONE
        payment_method_types=["card"],
        line_items=[{
            "price": "price_1SqCgn3V8G72nVD2xpkQcXtL",
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"https://cercavocicomputo01.onrender.com/success?email={email}",
        cancel_url="https://cercavocicomputo01.onrender.com/cancel",
    )

    return RedirectResponse(session.url, status_code=303)


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, "whsec_7GLYJeFLiOxDRIagitYghTjX8n7FNReE"
        )
    except Exception:
        return "Invalid", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session["customer_email"]

        USERS[email] = USERS.get(email, {})
        USERS[email]["active_until"] = date.today().replace(year=date.today().year + 1)

    return "OK", 200


# ---------------------------------------------------------
# SUCCESS & CANCEL PAGES
# ---------------------------------------------------------
@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    email = request.query_params.get("email")

    # 🔥 RIPRISTINA LA SESSIONE DOPO IL PAGAMENTO
    if email:
        request.session["email"] = email

    return """
    <html><body style='font-family: Arial; padding: 40px;'>
    <h2>Pagamento riuscito ✅</h2>
    <p>Il tuo abbonamento è ora attivo per 12 mesi.</p>
    <a href="/app">Vai all'app</a>
    </body></html>
    """


@app.get("/cancel", response_class=HTMLResponse)
async def cancel_page():
    return """
    <html><body style='font-family: Arial; padding: 40px;'>
    <h2>Pagamento annullato ❌</h2>
    <p>Puoi riprovare quando vuoi.</p>
    <a href="/subscribe">Torna all'abbonamento</a>
    </body></html>
    """


# ---------------------------------------------------------
# APP PAGE (ACCESS CONTROL)
# ---------------------------------------------------------
@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    email = request.session.get("email")
    if not email:
        return RedirectResponse("/login")

    user = USERS.get(email, {})
    if "active_until" not in user or user["active_until"] < date.today():
        return RedirectResponse("/subscribe")

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


# ---------------------------------------------------------
# SEARCH ENGINE
# ---------------------------------------------------------
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

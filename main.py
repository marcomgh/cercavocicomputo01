from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from datetime import date
import stripe
import random
import string

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

stripe.api_key = "sk_test_51SqBuc3V8G72nVD2R4IEotDqXJS8eTbO1WTh87RpyBLrke8dKfsZE6U8w4w8e8xCxkrSaMoaR66PIxlFo4F4krFg00Ptudcln3"

USERS = {}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if request.session.get("email"):
        return RedirectResponse("/app")
    return RedirectResponse("/login")

@app.get("/login", response_class=HTMLResponse)
async def login():
    return """
    <html><body style='font-family:Arial;padding:40px;'>
    <h2>Login</h2>
    <form action="/send-otp" method="post">
        <input type="email" name="email" placeholder="Email" required>
        <button type="submit">Invia codice</button>
    </form>
    </body></html>
    """

@app.post("/send-otp", response_class=HTMLResponse)
async def send_otp(email: str = Form(...)):
    otp = "".join(random.choices(string.digits, k=6))
    USERS[email] = {"otp": otp}
    return f"""
    <html><body style='font-family:Arial;padding:40px;'>
    <h3>Codice OTP (solo test): {otp}</h3>
    <form action="/verify-otp" method="post">
        <input type="hidden" name="email" value="{email}">
        <input type="text" name="otp" placeholder="Inserisci codice" required>
        <button type="submit">Accedi</button>
    </form>
    </body></html>
    """

@app.post("/verify-otp")
async def verify_otp(request: Request, email: str = Form(...), otp: str = Form(...)):
    if email in USERS and USERS[email]["otp"] == otp:
        request.session["email"] = email
        return RedirectResponse("/app")
    return HTMLResponse("<h3>Codice errato</h3>")

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

@app.get("/subscribe", response_class=HTMLResponse)
async def subscribe():
    return """
    <html><body style='font-family:Arial;padding:40px;'>
    <h2>Abbonamento annuale</h2>
    <p>3,99€/anno – accesso illimitato all'app</p>
    <form action="/create-checkout" method="post">
        <button type="submit">Paga con Stripe</button>
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
        client_reference_id=email,
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

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    email = request.query_params.get("email")
    if email:
        request.session["email"] = email
    return """
    <html><body style='font-family:Arial;padding:40px;'>
    <h2>Pagamento riuscito ✅</h2>
    <p>Il tuo abbonamento è ora attivo per 12 mesi.</p>
    <a href="/app">Vai all'app</a>
    </body></html>
    """

@app.get("/cancel", response_class=HTMLResponse)
async def cancel():
    return """
    <html><body style='font-family:Arial;padding:40px;'>
    <h2>Pagamento annullato ❌</h2>
    <p>Puoi riprovare quando vuoi.</p>
    <a href="/subscribe">Torna all'abbonamento</a>
    </body></html>
    """

@app.get("/app", response_class=HTMLResponse)
async def app(request: Request):
    email = request.session.get("email")
    if not email:
        return RedirectResponse("/login")

    user = USERS.get(email, {})
    if "active_until" not in user or user["active_until"] < date.today():
        return RedirectResponse("/subscribe")

    return f"""
    <html><body style='font-family:Arial;padding:40px;'>
    <h2>Ciao {email}</h2>
    <p>Abbonamento valido fino al: {user['active_until']}</p>
    <p>Benvenuto nell'app!</p>
    <a href="/logout">Logout</a>
    </body></html>
    """

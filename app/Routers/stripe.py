import os
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import stripe

from app.Model.StripeModel import StripeModel
from sqlalchemy.orm import Session
from database import AsyncSessionLocal
import app.Utils.database_handler as crud
from app.Utils.Auth import get_current_user
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = os.getenv('STRIPE_API_KEY')

YOUR_DOMAIN = 'http://localhost:5173'

Base_Price_Id = "price_1Q2EPWAZfjTlvHBok0I7tr1x"
endpoint_secret = 'whsec_nu25GaHsnPVts5TUOEOReptzASV1mi1i'
# Dependency to get the database session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
        
        
@router.post("/checkout")
async def checkout(model: StripeModel, db: Session = Depends(get_db)):
    try:
        print("model.email:", model.email)
        checkout_session = stripe.checkout.Session.create(
            customer_email=model.email,
            line_items=[{"price": model.plan_id, "quantity": 1}],
            
            mode="subscription",
            
            success_url= YOUR_DOMAIN + "/phones",
            cancel_url= YOUR_DOMAIN + "/phones",
        )
        print("checkout session:", checkout_session)
        # await crud.update_usertype(db, model.email, 1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return checkout_session.url

@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    print("webhook")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    print("event:", event)
    if event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        await handle_subscription_created(db, subscription)
        
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        await handle_subscription_updated(db, subscription)
        
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        await handle_subscription_deleted(db, subscription)
        
    elif event['type'] == 'customer.subscription.succeeded':
        invoice = event['data']['object']
        await handle_subscription_succeeded(db, invoice)
        
    elif event['type'] == 'customer.subscription.failed':
        invoice = event['data']['object']
        await handle_subscription_failed(db, invoice)
        
    else:
        print(f"Unhandled event type {event['type']}")
    return JSONResponse(status_code=200, content={"success": True})



async def handle_subscription_created(db: Session, subscription: dict):
    customer_id = subscription['customer']
    plan_id = subscription['items']['data'][0]['price']['id']
    
    start_date = subscription['start_date']
    end_date = subscription['current_period_end']
    
    print("subscription created:", subscription)
    
async def handle_subscription_updated(db: Session, subscription: dict):
    # customer_id = subscription['customer']
    # plan_id = subscription['items']['data'][0]['price']['id']
    
    # start_date = subscription['start_date']
    # end_date = subscription['current_period_end']
    
    print("subscription updated:", subscription)
    
async def handle_subscription_deleted(db: Session, subscription: dict):
    # customer_id = subscription['customer']
    print("subscription deleted:", subscription)
    
async def handle_subscription_succeeded(db: Session, invoice):
    sub_id = invoice
    line_item = invoice['lines']['data'][0]
    plan_id = line_item['plan']['id']
    email = invoice['customer_email']
    print("Invoice:", invoice)
    
    user = await crud.get_user_by_email(db, email)
    
    if plan_id == Base_Price_Id:
        await crud.update_usertype(db, user, 1)
    
    print('Payment successful:', invoice)

async def handle_subscription_failed(db: Session, invoice):
    print("Subscription failed:", invoice)
    

from twilio.rest import Client
from sqlalchemy.orm import Session
from database import AsyncSessionLocal
from app.Utils.sendgrid import send_mail
from dotenv import load_dotenv
from datetime import datetime
import app.Utils.database_handler as crud
from app.Model.DatabaseModel import Variables
import os
from concurrent.futures import ThreadPoolExecutor
import asyncio



load_dotenv()

# Dependency to get the database session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
        
        
twilioPhoneNumber = os.getenv("TWILIO_PHONE_NUMBER")
twilioAccountSID = os.getenv("TWILIO_ACCOUNT_SID")
twilioAuthToken = os.getenv("TWILIO_AUTH_TOKEN")


async def getTwilioCredentials(db: Session):
    print("getTwilioCredentials: ")
    variables = await crud.get_variables(db)
    print("variables: ", variables)
    number = ''
    sid = ''
    token = ''
    if variables:
        number = variables.twilioPhoneNumber or twilioPhoneNumber
        sid = variables.twilioAccountSID or twilioAccountSID
        token = variables.twilioAuthToken or twilioAuthToken
    else:
        number = twilioPhoneNumber
        sid = twilioAccountSID
        token = twilioAuthToken
    return number, sid, token


async def send_sms_via_phone_number(phone_number: str, sms: str, db: Session):
    twilioPhoneNumber, twilioAccountSID, twilioAuthToken = await getTwilioCredentials(db)
    # Initialize the Twilio client
    client = Client(twilioAccountSID, twilioAuthToken)
    print("sms - :", sms)
    if not sms:
        sms = "from getDelmar.com"
    
    # Use a thread pool executor to run the Twilio client in a separate thread
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        print("sms: ", sms)
        # Correctly pass arguments to client.messages.create
        future = loop.run_in_executor(
            executor,
            lambda: client.messages.create(
                to=phone_number,
                from_=twilioPhoneNumber,
                body=sms
            )
        )
        message = await asyncio.wrap_future(future)
    
    print("send message: ", message)
    
    # Optionally print the message SID
    return bool(message.sid)

async def send_opt_in_phone(phone_number: str, phone_id: int, db: Session):
    twilioPhoneNumber, twilioAccountSID, twilioAuthToken = await getTwilioCredentials(db)
    
    # Initialize the Twilio client
    client = Client(twilioAccountSID, twilioAuthToken)

    messaging_service_sid = "MGbcc5781c1f66253ace25265ebf172701"
    
    message_body = crud.get_optin_message
    from_phone_number = '+17082486451'  # Twilio phone number
    # from_phone_number = '+1 708 248 6451'  # Twilio phone number
    print("twilio: ", message_body, from_phone_number)

    # message = client.messages.create(
    #     body=message_body,
    #     # from_=from_phone_number,
    #     messaging_service_sid = messaging_service_sid,
    #     to="+1 708 774 5070"
    #     to=phone_number
    # )
    
    await crud.update_opt_in_status_sent_timestamp(db, phone_id)
    # asyncio.sleep(1)
    
    message = client.messages.create(
        body=message_body,
        from_=from_phone_number,
        messaging_service_sid = messaging_service_sid,
        to=phone_number
        # to=phone_number
    )
    
    if(message.sid):
        await crud.update_opt_in_status_phone(db, phone_id, 1)
    else:
        await crud.update_opt_in_status_phone(db, phone_id, 4)
    
    # # message = client.messages.create(
    # #     body=message_body,
    # #     # from_=from_phone_number,
    # #     messaging_service_sid = messaging_service_sid,
    # #     to="+17735179242"
    # # )
    # if(message.sid):
    #     await crud.update_opt_in_status_phone(db, phone_id, 2)
    # else:
    #     await crud.update_opt_in_status_phone(db, phone_id, 3)

    # Optionally print the message SID
    # return bool(message.sid)
    return True

async def send(message_id: int, db: Session):
    message = await crud.get_message(db, message_id)
    await crud.update_message_status(db, message.id, 1)
    sent_time = datetime.utcnow()
    phone_numbers = message.phone_numbers

    async def send_all_sms():
        all_sent_success = True
        for phone_number in phone_numbers:
            try:
                # print("phone_number: ", phone_number)
                phone_sent_success = await send_sms_via_phone_number(phone_number, message.last_message, db)
                # await asyncio.sleep(1)  # Sleep for 1 second between sends to avoid rate limiting
                # phone_sent_success = True
                print("phone_sent_success: ", phone_sent_success)
                await crud.update_sent_status(db, message_id, phone_sent_success)
                if not phone_sent_success:
                    all_sent_success = False
            except Exception as e:
                print(f"Error sending SMS to {phone_number}: {e}")
                all_sent_success = False
        return all_sent_success

    # Use asyncio to run the send_all_sms function
    all_sent_success = await send_all_sms()

    return all_sent_success

async def send_sms():
    # Create thread for messages with status 1 (queued)
    
    try:
        async with AsyncSessionLocal() as session:
            messages = await crud.get_main_table(session)
            current_time = datetime.utcnow()
            # print("messages: ", messages)
            for message in messages:
                if message.message_status == 0 and message.qued_timestamp <= current_time:
                    print("send message: ", message.id)
                    # Create task to send message
                    await send(message.id, session)
                    # Update status to queued (1)
                
                
    except Exception as e:
        print(f"Error in send_sms_scheduling: {e}")
        return False
    
    return True
            
#     async def schedule_send_sms(message_id: int, run_time: datetime, db: Session):
#         try:
#             print("schedule_send_sms")
#             loop.create_task(run_at(run_time), send(message_id, db))
#         except Exception as e:
#             print(f"Error in schedule_send_sms: {e}")
    

            
#     try:
#         messages = await crud.get_main_table(db)
#         for message in messages:
#             if message.message_status == 0:
#                 if message.qued_timestamp > datetime.utcnow():
#                     if(message.qued_timestamp - datetime.utcnow().total_seconds() < 86400):
#                         await schedule_send_sms(message.id, message.qued_timestamp, db)
#                         await crud.update_message_status(db, message.id, 1)
#                 else:
#                     await send(message.id, db)

#     except Exception as e:
#         print(f"Error in send_sms_thread: {e}")


    


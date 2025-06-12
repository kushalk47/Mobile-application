import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId
from pydantic import BaseModel, Field
from typing import Optional
from app.config import get_db # Assuming get_db is correctly implemented
import logging

# Logging setup
# Ensure logging level is set to DEBUG or INFO to see these messages
logging.basicConfig(level=logging.DEBUG) # Set to DEBUG temporarily for detailed logs
logger = logging.getLogger(__name__)

# Session model
class UserSession(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    token: str = Field(default_factory=lambda: secrets.token_hex(32))
    user_id: str
    user_type: str
    login_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=SESSION_EXPIRATION_MINUTES))

    model_config = {'populate_by_name': True}

SESSION_COOKIE_NAME = "session_token"
SESSION_EXPIRATION_MINUTES = 1440  # 1 day

async def get_sessions_collection():
    db = get_db()
    return db.get_collection("sessions")

# Create a session, save it to DB, and RETURN the secure random token
async def create_user_session(user_id: str, user_type: str) -> str:
    sessions_collection = await get_sessions_collection()

    session = UserSession(user_id=user_id, user_type=user_type)
    session_dict = session.model_dump(mode='json', exclude={'id'})

    try:
        insert_result = await sessions_collection.insert_one(session_dict)
        if not insert_result.inserted_id:
             raise Exception("Failed to insert session document")

        logger.info(f"Session created for user {user_id} with token (first 8 chars): {session.token[:8]}...")

        return session.token
    except Exception as e:
        logger.error(f"Error creating session document for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session document")


# Get session from cookie using the secure random token
async def get_current_session(request: Request) -> Optional[UserSession]:
    logger.debug("--- Inside get_current_session ---")
    # Get the session token from the cookie
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    logger.debug(f"Attempting to retrieve cookie '{SESSION_COOKIE_NAME}'. Value found: {session_token is not None}")

    if not session_token:
        logger.debug("No session token found in cookie.")
        logger.debug("--- Exiting get_current_session (No Token) ---")
        return None

    logger.debug(f"Session token found in cookie (first 8 chars): {session_token[:8]}...")

    sessions_collection = await get_sessions_collection()
    try:
        # Look up session by the 'token' field
        logger.debug(f"Querying DB for session with token (first 8 chars): {session_token[:8]}...")
        session_doc = await sessions_collection.find_one({"token": session_token})
        logger.debug(f"DB Query Result: Session document found: {session_doc is not None}")


        if session_doc:
            # Convert ObjectId back to string for the Pydantic model
            if '_id' in session_doc and isinstance(session_doc['_id'], ObjectId):
                 session_doc['_id'] = str(session_doc['_id'])

            session = UserSession(**session_doc)
            logger.debug(f"Pydantic UserSession created for user ID: {session.user_id}")

            # Check expiration (using timezone-aware comparison)
            now_utc = datetime.now(timezone.utc)
            logger.debug(f"Current UTC time: {now_utc}")
            logger.debug(f"Session expires at: {session.expires_at}")

            if session.expires_at < now_utc:
                logger.info(f"Session {session.id} with token (first 8 chars) {session_token[:8]}... expired.")
                # --- Optional: Delete expired session from DB here ---
                try:
                    logger.debug(f"Attempting to delete expired session {session.id} from DB.")
                    await sessions_collection.delete_one({"_id": ObjectId(session.id)})
                    logger.info(f"Expired session {session.id} deleted from DB.")
                except Exception as delete_e:
                    logger.error(f"Error deleting expired session {session.id}: {delete_e}")
                # ----------------------------------------------------
                logger.debug("--- Exiting get_current_session (Expired) ---")
                return None

            logger.debug("Session is not expired.")

            # Optional: update activity timestamp (sliding window)
            try:
                 logger.debug(f"Updating last_active for session {session.id}.")
                 await sessions_collection.update_one(
                     {"_id": ObjectId(session.id)},
                     {"$set": {"last_active": datetime.now(timezone.utc)}}
                 )
                 logger.debug(f"Last_active updated for session {session.id}.")
            except Exception as update_e:
                 logger.error(f"Error updating last_active for session {session.id}: {update_e}")

            logger.debug(f"Valid session found for user {session.user_id}.")
            logger.debug("--- Exiting get_current_session (Success) ---")
            return session
        else:
             logger.debug(f"No session document found in DB for token (first 8 chars): {session_token[:8]}...")
             logger.debug("--- Exiting get_current_session (Not Found) ---")
             return None # Session token not found in DB

    except Exception as e:
        # Log error if DB query fails or other unexpected errors occur
        logger.error(f"Error during session retrieval for token (first 8 chars) {session_token[:8]}...: {e}")
        logger.debug("--- Exiting get_current_session (Error) ---")
        return None

# Logout - Delete session from DB using the token and delete the cookie
async def delete_user_session(request: Request, response: Response):
    logger.debug("--- Inside delete_user_session ---")
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    logger.debug(f"Attempting to retrieve cookie '{SESSION_COOKIE_NAME}' for deletion. Value found: {session_token is not None}")

    if session_token:
        sessions_collection = await get_sessions_collection()
        try:
            # Delete session by the 'token' field
            logger.debug(f"Attempting to delete session with token (first 8 chars) {session_token[:8]}... from DB.")
            delete_result = await sessions_collection.delete_one({"token": session_token})
            if delete_result.deleted_count > 0:
                logger.info(f"Session with token (first 8 chars) {session_token[:8]}... deleted from DB.")
            else:
                 logger.warning(f"Attempted to delete session with token (first 8 chars) {session_token[:8]}... but it was not found in DB.")

        except Exception as e:
            logger.error(f"Error deleting session with token (first 8 chars) {session_token[:8]}... from DB: {e}")

        # Delete the cookie from the browser regardless of DB deletion success
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        logger.info(f"Session cookie '{SESSION_COOKIE_NAME}' deleted.")
    else:
        logger.debug("No session token found in cookie to delete.")
    logger.debug("--- Exiting delete_user_session ---")


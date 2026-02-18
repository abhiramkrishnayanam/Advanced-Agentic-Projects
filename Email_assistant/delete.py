# This is a conceptual example for selecting and trashing an email.
# Assumes 'service' is an authenticated Gmail service object and proper scopes are set.
import datetime
# ... (imports from previous example)
from bs4 import BeautifulSoup
from sender import get_gmail_service


def select_and_trash_message(user_id, search_query):
    """
    Finds a message based on a search query.
    """
    service = get_gmail_service()
    try:
        response = service.users().messages().list(
            userId=user_id,
            q=search_query,
            maxResults=1
        ).execute()

        messages = response.get('messages', [])
        if not messages:
            return {"status": "not_found", "message": f"No messages found for '{search_query}'"}

        message_id = messages[0]['id']
        print(f"Found message ID: {message_id}")

        return {"status": "found", "message_id": message_id, "query": search_query}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    
def trash_message(user_id, message_id):
    service = get_gmail_service()
    try:
        service.users().messages().trash(userId=user_id, id=message_id).execute()
        return {"status": "success", "message_id": message_id, "info": "Message moved to trash."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
if __name__ == '__main__':
    user_id = 'me'
    query = 'to: abhiramkrishnayanam@gmail.com'

    result = select_and_trash_message(user_id, query)
    print(result)


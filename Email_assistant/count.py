import datetime
from sender import get_gmail_service
import datetime
from googleapiclient.discovery import build

def get_today_date_query():
    """Generates Gmail API 'q' parameter for today's date."""
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    return f"after:{today.strftime('%Y/%m/%d')} before:{tomorrow.strftime('%Y/%m/%d')}"

def get_email_count_today():
    """
    Counts emails received today, handling pagination for high-volume accounts.
    Returns:
        The total number of emails received today.
    """
    service = get_gmail_service()
    query = get_today_date_query() + " in:inbox"
    total_messages = 0
    next_page_token = None
    
    try:
        while True:
            # Make the API call, optionally including the page token
            results = service.users().messages().list(
                userId='me',
                q=query,
                pageToken=next_page_token
            ).execute()
            
            messages = results.get('messages', [])
            total_messages += len(messages)
            
            # Check for a next page token
            next_page_token = results.get('nextPageToken')
            if not next_page_token:
                break  # No more pages to retrieve
                
        return total_messages
    
    except Exception as error:
        print(f"An error occurred: {error}")
        return 0

if __name__ == '__main__':
    service = get_gmail_service()
    
    # --- Conceptual example usage ---
    if service:
        count = get_email_count_today()
        print(f"Emails received today: {count}")
    else:
        print("Failed to get Gmail service.")





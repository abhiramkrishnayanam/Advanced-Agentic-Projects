from googleapiclient.discovery import build
from sender import get_gmail_service
import base64
from langchain_groq import ChatGroq
import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)

def extract_metadata(message):
    headers = message['payload'].get('headers', [])
    metadata = {'from': 'Unknown sender', 'to': 'Unknown recipient'}
    
    for header in headers:
        if header['name'].lower() == 'from':
            metadata['from'] = header['value']
        elif header['name'].lower() == 'to':
            metadata['to'] = header['value']
            
    return metadata

def get_thread_summary(user_id, thread_id):
    service = get_gmail_service()
    thread = service.users().threads().get(userId=user_id, id=thread_id).execute()

    full_thread_content = []
    metadata_info = []

    for message in thread['messages']:
        # Extract metadata from each message
        metadata = extract_metadata(message)
        metadata_info.append(metadata)

        # Extract plain text content
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                    decoded_data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    full_thread_content.append(decoded_data)
        elif 'body' in message['payload'] and 'data' in message['payload']['body']:
            decoded_data = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            full_thread_content.append(decoded_data)

    combined_text = "\n".join(full_thread_content)

    # Simplify metadata: pick first message's sender/recipient
    first_metadata = metadata_info[0] if metadata_info else {'from': 'Unknown', 'to': 'Unknown'}
    llm= ChatGroq(model="gemma2-9b-it", temperature= 0)
    # Generate prompt
    prompt = f"""
You are an intelligent email assistant that summarizes email threads.

Sender: {first_metadata['from']}
Recipient: {first_metadata['to']}

Here is the full content of the email thread:
\"\"\" 
{combined_text}
\"\"\"

Provide a clear and concise summary of the email thread in a few sentences.
"""

    # Call the LLM function
    summary = llm.invoke([{"role": "user", "content": prompt}]).content.strip()

    return {
        "sender": first_metadata['from'],
        "recipient": first_metadata['to'],
        "summary": summary
    }


# Assuming 'service' is the authenticated Gmail service object
def find_thread_id(service, user_id, query):
    """
    Finds a thread ID based on a search query.
    
    Args:
        service: The Gmail service object.
        user_id: The user's email address (e.g., 'me').
        query: The search query to filter threads (e.g., 'subject:My Project').

    Returns:
        The thread ID of the first matching thread, or None if no match is found.
    """
    try:
        # Use the list method with a query to find threads
        response = service.users().threads().list(userId=user_id, q=query).execute()
        threads = response.get('threads', [])
        
        if not threads:
            print(f"No threads found matching the query: '{query}'")
            return None
        
        # Select the ID of the first thread in the results
        thread_id = threads[0]['id']
        print(f"Found thread ID: {thread_id}")
        return thread_id

    except Exception as error:
        print(f"An error occurred: {error}")
        return None


def generate_thread_summary_node(user_id, query):
    """
    LangGraph node function to extract the thread summary from Gmail.

    Args:
        user_id (str): The user's Gmail ID (usually 'me').
        query (str): Search query to find the desired thread.
        llm (callable): The LLM function that takes a prompt and returns a summary string.

    Returns:
        dict: Structured output containing sender, recipient, and summary.
    """
    user_id = "me"
    service = get_gmail_service()

    thread_id = find_thread_id(service, user_id, query)

    if not thread_id:
        return {
            "status": "error",
            "message": "No thread found for the given query."
        }

    summary_info = get_thread_summary(user_id, thread_id)

    return {
        "status": "success",
        "sender": summary_info['sender'],
        "recipient": summary_info['recipient'],
        "summary": summary_info['summary']
    }

if __name__ == '__main__':
    user_id = 'me'
    query = ' subject: Hi'

    result = generate_thread_summary_node(user_id, query)

    print(result)


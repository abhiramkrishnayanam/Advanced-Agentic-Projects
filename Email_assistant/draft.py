from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from trustcall import create_extractor
import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)

# Initialize the model (using Groq instead of OpenAI as in your original code)
model = ChatGroq(model="openai/gpt-oss-20b", temperature=0)

# Define the schema for storing email addresses
class EmailContacts(BaseModel):
    """A tool to store and manage email addresses for user contacts."""
    email_addresses: dict = Field(
        description="A dictionary mapping contact names to their corresponding email addresses."
    )

# Create the extractor with 'auto' tool_choice
trustcall_extractor = create_extractor(
    model,
    tools=[EmailContacts],
    tool_choice="auto",
    enable_inserts=True,
)

# Instruction for the model when extracting information
TRUSTCALL_INSTRUCTION = """
You are a specialized tool designed to extract email addresses and their corresponding contact names. Your output must be a valid JSON object matching the `EmailContacts` schema.

**Instructions:**
- If a contact and email are mentioned, add or update the entry in the `email_addresses` dictionary.
- If the email address for an existing contact changes, you must overwrite the old email with the new one.

**Examples:**
1.  **New Contact:**
    User: "My friend Alice's email is alice@gmail.com."
    Output:
    {
        "email_addresses": {
            "alice": "alice@gmail.com"
        }
    }

2.  **Update Existing Contact:**
    User: "Actually, Alice's new email is alice.smith@company.com."
    Output:
    {
        "email_addresses": {
            "alice": "alice.smith@company.com"
        }
    }

If no email address is mentioned, return an empty dictionary. Do not include any other text.
"""




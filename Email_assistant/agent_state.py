from pydantic import BaseModel, Field
from typing import Optional, Annotated, Dict, Any
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

class AgentState(BaseModel):
    query: Optional[str]= Field(description="the user query")                   
    user_id: Optional[str]= "me"
    summary: Optional[dict]= Field(default=None, description="Summary of the particular thread")
    deleted: Optional[dict] = Field(default=None, description="Details of the deleted message")
    count: Optional[int]= Field(default=None, description="number of emails recieved today")
    flagged_messages: Optional[list] = Field(default=[],description= "List of Flagged messages")
    answers: Optional[str]= Field(default=None,description= "Answer for the query asked by customer")
    gmail_service_warning: Optional[str]= Field(default=None,description= "Warinig for gmail not provided service")
    messages: Optional[Annotated[list[AnyMessage], add_messages]] = None
    pending_action: Optional[Dict[str, Any]] = None
    next_node: Optional[str]= Field(default=None,description= "Next node to be routed")
    to: Optional[str] = Field(
        default=None,
        description="Recipient's email address. Must be a valid email format."
    )
    subject: Optional[str] = Field(
        default=None,
        description="Subject line of the email."
    )
    body: Optional[str] = Field(
        default=None,
        description="Main content/body of the email."
    )
    query_dlt: Optional[str] = Field(
        default=None,
        description="Query to be send to send to trash function"
    )
    
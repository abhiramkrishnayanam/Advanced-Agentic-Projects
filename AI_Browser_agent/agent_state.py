from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class BrowserAgentState(BaseModel):
    user_query: Optional[str] = None      
    intent: Optional[List[Dict[str, Any]]] = []  # LLM output is a list of steps
    action_plan: Optional[List[Dict[str, Any]]] = []
    next_step: Optional[Dict[str, Any]] = None    # currently executing step
    current_step: int = 0                          # pointer in action_plan
    current_url: Optional[str] = None
    dom_snapshot: Optional[Dict[str, Any]] = {}
    execution_trace: List[Dict[str, Any]] = []  
    error: Optional[str] = None
    
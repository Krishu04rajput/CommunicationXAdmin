import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Set, Optional
from dataclasses import dataclass
from enum import Enum

class CallStatus(Enum):
    PENDING = "pending"
    RINGING = "ringing"
    ACTIVE = "active"
    ENDED = "ended"
    DECLINED = "declined"
    MISSED = "missed"

class CallType(Enum):
    AUDIO = "audio"
    VIDEO = "video"

@dataclass
class CallSession:
    call_id: str
    caller_id: str
    recipient_id: str
    server_id: Optional[str]
    call_type: CallType
    status: CallStatus
    created_at: datetime
    participants: Set[str]
    offers: Dict[str, dict]
    answers: Dict[str, dict]
    ice_candidates: Dict[str, list]

class CallManager:
    def __init__(self):
        self.active_calls: Dict[str, CallSession] = {}
        self.user_calls: Dict[str, str] = {}  # user_id -> call_id
        self.call_listeners: Dict[str, list] = {}  # user_id -> [callback functions]
    
    def create_call(self, caller_id: str, recipient_id: str, call_type: CallType, server_id: Optional[str] = None) -> str:
        """Create a new call session"""
        call_id = str(uuid.uuid4())
        
        call_session = CallSession(
            call_id=call_id,
            caller_id=caller_id,
            recipient_id=recipient_id,
            server_id=server_id,
            call_type=call_type,
            status=CallStatus.PENDING,
            created_at=datetime.now(),
            participants=set(),
            offers={},
            answers={},
            ice_candidates={}
        )
        
        self.active_calls[call_id] = call_session
        self.user_calls[caller_id] = call_id
        
        return call_id
    
    def join_call(self, call_id: str, user_id: str) -> bool:
        """Add user to call session"""
        if call_id not in self.active_calls:
            return False
        
        call = self.active_calls[call_id]
        call.participants.add(user_id)
        self.user_calls[user_id] = call_id
        
        if len(call.participants) >= 2 and call.status == CallStatus.PENDING:
            call.status = CallStatus.ACTIVE
        
        return True
    
    def leave_call(self, user_id: str) -> Optional[str]:
        """Remove user from call session"""
        if user_id not in self.user_calls:
            return None
        
        call_id = self.user_calls[user_id]
        call = self.active_calls.get(call_id)
        
        if call:
            call.participants.discard(user_id)
            
            if len(call.participants) == 0:
                call.status = CallStatus.ENDED
                del self.active_calls[call_id]
            
            del self.user_calls[user_id]
        
        return call_id
    
    def accept_call(self, call_id: str, user_id: str) -> bool:
        """Accept incoming call"""
        if call_id not in self.active_calls:
            return False
        
        call = self.active_calls[call_id]
        if user_id != call.recipient_id:
            return False
        
        call.status = CallStatus.RINGING
        return self.join_call(call_id, user_id)
    
    def decline_call(self, call_id: str, user_id: str) -> bool:
        """Decline incoming call"""
        if call_id not in self.active_calls:
            return False
        
        call = self.active_calls[call_id]
        if user_id != call.recipient_id:
            return False
        
        call.status = CallStatus.DECLINED
        return True
    
    def end_call(self, call_id: str) -> bool:
        """End active call"""
        if call_id not in self.active_calls:
            return False
        
        call = self.active_calls[call_id]
        call.status = CallStatus.ENDED
        
        # Remove all participants
        for user_id in list(call.participants):
            if user_id in self.user_calls:
                del self.user_calls[user_id]
        
        del self.active_calls[call_id]
        return True
    
    def get_call(self, call_id: str) -> Optional[CallSession]:
        """Get call session by ID"""
        return self.active_calls.get(call_id)
    
    def get_user_call(self, user_id: str) -> Optional[CallSession]:
        """Get active call for user"""
        call_id = self.user_calls.get(user_id)
        if call_id:
            return self.active_calls.get(call_id)
        return None
    
    def set_offer(self, call_id: str, user_id: str, offer: dict) -> bool:
        """Set WebRTC offer for call"""
        if call_id not in self.active_calls:
            return False
        
        call = self.active_calls[call_id]
        call.offers[user_id] = offer
        return True
    
    def set_answer(self, call_id: str, user_id: str, answer: dict) -> bool:
        """Set WebRTC answer for call"""
        if call_id not in self.active_calls:
            return False
        
        call = self.active_calls[call_id]
        call.answers[user_id] = answer
        return True
    
    def add_ice_candidate(self, call_id: str, user_id: str, candidate: dict) -> bool:
        """Add ICE candidate for call"""
        if call_id not in self.active_calls:
            return False
        
        call = self.active_calls[call_id]
        if user_id not in call.ice_candidates:
            call.ice_candidates[user_id] = []
        call.ice_candidates[user_id].append(candidate)
        return True

# Global call manager instance
call_manager = CallManager()
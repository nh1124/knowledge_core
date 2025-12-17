"""Enum definitions for Memory types and scopes."""
from enum import Enum


class MemoryType(str, Enum):
    """Type of memory determining update strategy."""
    FACT = "fact"       # Fixed facts - overwrite on update
    STATE = "state"     # Current state - latest wins
    EPISODE = "episode" # Past events - append only
    POLICY = "policy"   # User preferences/rules


class Scope(str, Enum):
    """Scope of memory visibility."""
    GLOBAL = "global"   # Visible to all agents
    AGENT = "agent"     # Visible only to specific agent


class InputChannel(str, Enum):
    """Source channel of memory input."""
    CHAT = "chat"
    MANUAL = "manual"
    API = "api"
    IMPORT = "import"


class AuditAction(str, Enum):
    """Type of audit action performed."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    CONFIRM = "confirm"
    REJECT = "reject"


class ActorType(str, Enum):
    """Type of actor performing the action."""
    SYSTEM = "system"
    USER = "user"
    ADMIN = "admin"

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime


# PUBLIC_INTERFACE
class UserRegisterRequest(BaseModel):
    """Request model for user registration."""
    email: EmailStr = Field(..., description="The user's email for registration.")
    password: str = Field(..., min_length=6, description="User password (min 6 chars).")
    username: str = Field(..., description="Unique username.")


# PUBLIC_INTERFACE
class UserLoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr = Field(..., description="User email address.")
    password: str = Field(..., description="User password.")


# PUBLIC_INTERFACE
class UserResponse(BaseModel):
    """Returned user info (does not include password)."""
    user_id: int = Field(..., description="User ID.")
    username: str = Field(..., description="Username.")
    email: EmailStr = Field(..., description="User email (for identification).")


# PUBLIC_INTERFACE
class TokenResponse(BaseModel):
    """Returned authentication token after login or registration."""
    access_token: str = Field(..., description="JWT access token for future requests.")
    token_type: str = Field(default="bearer", description="Type of the token.")


# PUBLIC_INTERFACE
class GameStartRequest(BaseModel):
    """Request model to start a new game."""
    opponent_type: Literal["human", "ai"] = Field(..., description="Start a game with another user (human) or vs AI.")
    opponent_username: Optional[str] = Field(None, description="If human, the opponent's username.")


# PUBLIC_INTERFACE
class GameBoard(BaseModel):
    """Model for game board state."""
    board: List[List[Optional[str]]] = Field(..., description="3x3 tic-tac-toe board, values X, O, or None for each cell.")


# PUBLIC_INTERFACE
class MoveRequest(BaseModel):
    """Request model for making a move."""
    game_id: int = Field(..., description="Game session ID.")
    row: int = Field(..., ge=0, le=2, description="Row in board (0-2).")
    col: int = Field(..., ge=0, le=2, description="Col in board (0-2).")


# PUBLIC_INTERFACE
class MoveResponse(BaseModel):
    """Response after a move; includes new state and messages."""
    board: List[List[Optional[str]]]
    status: str
    message: Optional[str] = None
    winner: Optional[str] = None
    next_turn: Optional[str] = None


# PUBLIC_INTERFACE
class GameHistoryItem(BaseModel):
    game_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    players: List[str]
    winner: Optional[str]
    moves_count: int


# PUBLIC_INTERFACE
class GameHistoryResponse(BaseModel):
    history: List[GameHistoryItem]


# PUBLIC_INTERFACE
class LeaderboardEntry(BaseModel):
    username: str
    wins: int
    losses: int
    draws: int
    games_played: int


# PUBLIC_INTERFACE
class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]

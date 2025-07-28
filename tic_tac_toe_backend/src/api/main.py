from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, List, Optional
from starlette.websockets import WebSocketState
from datetime import datetime, timedelta

from .models import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    GameStartRequest,
    MoveRequest,
    MoveResponse,
    GameHistoryResponse,
    GameHistoryItem,
    LeaderboardResponse,
    LeaderboardEntry,
)
from .core import TicTacToeGame, ai_move, get_leaderboard_stub

import hashlib
import jwt

SECRET_KEY = "tictactoe-secret"  # For demo purposes only! Move to env variable in production.
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# In-memory mock DBs for demo:
users_db: Dict[str, dict] = {}  # email: {password_hash, username, id}
sessions_db: Dict[int, dict] = {}  # game_id: {game, players, start, moves}
user_games: Dict[int, List[int]] = {}  # user_id: List[game_id]
game_id_counter = 1
user_id_counter = 1

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(
    title="Tic Tac Toe API",
    description="Backend for Tic Tac Toe platform. Handles user accounts, game moves, game history, leaderboards, and real-time WS.",
    version="0.1.0",
    openapi_tags=[
        {"name": "auth", "description": "User authentication (register/login)"},
        {"name": "game", "description": "Start/play Tic Tac Toe games"},
        {"name": "history", "description": "Retrieve game history"},
        {"name": "ws", "description": "Websockets for real-time updates"},
        {"name": "leaderboard", "description": "Current leaderboard"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

##---- Utility Functions ----##
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, pw_hash: str) -> bool:
    return hash_password(password) == pw_hash


# PUBLIC_INTERFACE
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token with optional expiry."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decode JWT and load user from mock db. Raises on error."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email or email not in users_db:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return users_db[email]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


@app.get("/", tags=["health"])
def health_check():
    """Health check route for backend"""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.post("/register", response_model=TokenResponse, tags=["auth"], summary="Register user")
async def register_user(request: UserRegisterRequest):
    """Register a new user. Returns JWT on success.

    Args:
        request (UserRegisterRequest): Email, username, password.
    Returns:
        TokenResponse: Authentication JWT token.
    """
    global user_id_counter
    if request.email in users_db:
        raise HTTPException(status_code=409, detail="Email already registered")
    for udata in users_db.values():
        if udata["username"] == request.username:
            raise HTTPException(status_code=409, detail="Username already taken")
    pw_hash = hash_password(request.password)
    user_doc = {
        "id": user_id_counter,
        "username": request.username,
        "email": request.email,
        "password_hash": pw_hash,
    }
    users_db[request.email] = user_doc
    user_id_counter += 1
    token = create_access_token({"sub": request.email})
    return TokenResponse(access_token=token, token_type="bearer")


# PUBLIC_INTERFACE
@app.post("/login", response_model=TokenResponse, tags=["auth"], summary="Login user")
async def login_user(request: UserLoginRequest):
    """Authenticate user and return JWT token.

    Args:
        request (UserLoginRequest): Email and password.
    Returns:
        TokenResponse: JWT on success.
    """
    user = users_db.get(request.email)
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user["email"]})
    return TokenResponse(access_token=token, token_type="bearer")


# PUBLIC_INTERFACE
@app.post("/new_game", response_model=int, tags=["game"], summary="Start new game")
async def start_game(request: GameStartRequest, user: dict = Depends(get_current_user)):
    """Start a new Tic Tac Toe game session vs another user or AI.

    - If human: expects opponent_username to be a valid user (demo: makes vs AI if missing).
    Returns: game ID.
    """
    global game_id_counter
    players = [user["username"]]
    opponent = None
    if request.opponent_type == "human" and request.opponent_username:
        for udata in users_db.values():
            if udata["username"] == request.opponent_username:
                opponent = udata["username"]
                break
        if not opponent:
            raise HTTPException(status_code=404, detail="Opponent not found")
        players.append(opponent)
        is_ai = False
    else:
        players.append("AI")
        is_ai = True

    game = TicTacToeGame()
    game_rec = {
        "id": game_id_counter,
        "game": game,
        "players": players,
        "is_ai": is_ai,
        "player_turn": players[0],
        "moves": [],
        "created_at": datetime.utcnow(),
        "winner": None,
    }
    sessions_db[game_id_counter] = game_rec
    # Track for user history:
    for uname in players:
        uid = None
        for u in users_db.values():
            if u["username"] == uname:
                uid = u["id"]
                break
        if uid is not None:
            user_games.setdefault(uid, []).append(game_id_counter)
    gid = game_id_counter
    game_id_counter += 1
    return gid


# PUBLIC_INTERFACE
@app.post("/make_move", response_model=MoveResponse, tags=["game"], summary="Make a move")
async def make_move(request: MoveRequest, user: dict = Depends(get_current_user)):
    """Play a move in an active game. Returns new game state, status, winner (if over)."""
    gid = request.game_id
    if gid not in sessions_db:
        raise HTTPException(status_code=404, detail="Game not found")
    game_rec = sessions_db[gid]
    username = user["username"]
    if username not in game_rec["players"]:
        raise HTTPException(status_code=403, detail="You are not a player in this game.")

    # Mark the move
    mark = "X" if username == game_rec["players"][0] else "O"
    game: TicTacToeGame = game_rec["game"]
    success = game.make_move(request.row, request.col, mark if game.current == mark else game.current)

    if not success:
        return MoveResponse(
            board=game.serialize_board(),
            status="invalid",
            message="Invalid move! Cell already taken or not your turn.",
            winner=None,
            next_turn=game.current,
        )

    game_rec["moves"].append({"player": username, "pos": (request.row, request.col), "symbol": mark})
    winner = game.check_winner()
    is_draw = game.is_draw()

    # AI move (if applicable and it's AI's turn next)
    ai_message = None
    if game_rec["is_ai"] and game.current == "O":
        row, col = ai_move(game.serialize_board(), "O")
        if row != -1 and col != -1:
            game.make_move(row, col, "O")
            game_rec["moves"].append({"player": "AI", "pos": (row, col), "symbol": "O"})
        # Recompute winner:
        winner = game.check_winner()
        is_draw = game.is_draw()
        ai_message = f"AI played at row={row}, col={col}"

    # Set winner; cleanup if done
    if winner:
        game_rec["winner"] = winner
        game_status = "won"
        message = f"Winner is {winner}" + (f". {ai_message}" if ai_message else "")
    elif is_draw:
        game_status = "draw"
        message = "It's a draw."
    else:
        game_status = "continue"
        message = "Continue playing." + (f" {ai_message}" if ai_message else "")

    return MoveResponse(
        board=game.serialize_board(),
        status=game_status,
        message=message,
        winner=winner,
        next_turn=game.current if not (winner or is_draw) else None,
    )


# PUBLIC_INTERFACE
@app.get("/game_state/{game_id}", response_model=MoveResponse, tags=["game"], summary="Get current game state")
async def get_game_state(game_id: int, user: dict = Depends(get_current_user)):
    """Get board state and info for a running game."""
    if game_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Game not found")
    game_rec = sessions_db[game_id]
    game: TicTacToeGame = game_rec["game"]
    winner = game.check_winner()
    draw = game.is_draw()
    game_status = "won" if winner else ("draw" if draw else "continue")
    return MoveResponse(
        board=game.serialize_board(),
        status=game_status,
        winner=winner,
        next_turn=game.current if not (winner or draw) else None,
    )


# PUBLIC_INTERFACE
@app.get("/game_history", response_model=GameHistoryResponse, tags=["history"], summary="Get current user's game history")
async def get_history(user: dict = Depends(get_current_user)):
    """Fetch games played by currently logged in user."""
    uid = user["id"]
    history = []
    for gid in user_games.get(uid, []):
        gm = sessions_db.get(gid)
        if gm:
            history.append(GameHistoryItem(
                game_id=gm["id"],
                started_at=gm["created_at"],
                completed_at=None,  # Not tracking in-memory (could use winner for this)
                players=gm["players"],
                winner=gm["winner"],
                moves_count=len(gm["moves"]),
            ))
    return GameHistoryResponse(history=history)


# PUBLIC_INTERFACE
@app.get("/leaderboard", response_model=LeaderboardResponse, tags=["leaderboard"], summary="Get top players leaderboard (stub)")
async def get_leaderboard():
    """Leaderboard of top players (stubbed, replace with DB calls in production)."""
    stub = get_leaderboard_stub()
    return LeaderboardResponse(
        leaderboard=[LeaderboardEntry(**entry) for entry in stub]
    )


# PUBLIC_INTERFACE
@app.websocket("/ws/game/{game_id}")
async def websocket_game_updates(websocket: WebSocket, game_id: int):
    """
    WebSocket for broadcasting game updates to clients. Usage: connect to ws://host/ws/game/{game_id}.
    Provides push update after every move.

    Project Note: To use: Open the websocket and receive/send messages for real-time board state.
    """
    await websocket.accept()
    try:
        while True:
            if websocket.application_state != WebSocketState.CONNECTED:
                break
            # For demo: just echo ping requests, in prod add pub/sub for moves
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            elif game_id in sessions_db:
                game_rec = sessions_db[game_id]
                game: TicTacToeGame = game_rec["game"]
                await websocket.send_json({
                    "board": game.serialize_board(),
                    "next_turn": game.current,
                    "winner": game.check_winner(),
                })
            else:
                await websocket.send_text("Invalid game_id")
    except WebSocketDisconnect:
        pass

# Misc: Docs route for websocket usage notes
@app.get("/websocket_info", tags=["ws"], summary="Get websocket usage instructions")
def websocket_info():
    """Instructions for real-time connection via websocket."""
    return {
        "usage":
            "Connect using WebSocket at ws://HOST/ws/game/{game_id} to receive/send game state updates in real-time. "
            "Send 'ping' for a pong, or any text to get latest board update."
    }

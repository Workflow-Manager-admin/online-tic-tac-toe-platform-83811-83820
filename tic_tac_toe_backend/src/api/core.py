from typing import List, Optional

class TicTacToeGame:
    """Core game logic for Tic Tac Toe."""

    def __init__(self, board: Optional[List[List[Optional[str]]]] = None, player_x: str = "X", player_o: str = "O"):
        if board is None:
            self.board = [[None for _ in range(3)] for _ in range(3)]
        else:
            self.board = [row[:] for row in board]
        self.player_x = player_x
        self.player_o = player_o
        self.current: str = self.player_x

    # PUBLIC_INTERFACE
    def make_move(self, row: int, col: int, player: str) -> bool:
        """Attempt to mark the board. Returns True if successful."""
        if self.board[row][col] is None and player == self.current:
            self.board[row][col] = player
            self.current = self.player_o if player == self.player_x else self.player_x
            return True
        return False

    # PUBLIC_INTERFACE
    def check_winner(self) -> Optional[str]:
        """Checks for a winner. Returns 'X', 'O', or None."""
        lines = []
        # Rows and columns
        for i in range(3):
            lines.append(self.board[i])
            lines.append([self.board[0][i], self.board[1][i], self.board[2][i]])
        # Diagonals
        lines.append([self.board[0][0], self.board[1][1], self.board[2][2]])
        lines.append([self.board[0][2], self.board[1][1], self.board[2][0]])
        for line in lines:
            if line[0] and line[0] == line[1] == line[2]:
                return line[0]
        return None

    # PUBLIC_INTERFACE
    def is_draw(self) -> bool:
        return all(cell for row in self.board for cell in row) and not self.check_winner()

    # PUBLIC_INTERFACE
    def serialize_board(self) -> List[List[Optional[str]]]:
        return [row[:] for row in self.board]


# PUBLIC_INTERFACE
def ai_move(board: List[List[Optional[str]]], symbol: str) -> (int, int):
    """Naive AI: picks the first available cell (can be replaced with better AI)."""
    for i in range(3):
        for j in range(3):
            if board[i][j] is None:
                return i, j
    return -1, -1  # Should not happen


# PUBLIC_INTERFACE
def get_leaderboard_stub() -> List[dict]:
    """Stub: Replace with DB logic."""
    return [
        {"username": "alice", "wins": 10, "losses": 2, "draws": 5, "games_played": 17},
        {"username": "bob", "wins": 7, "losses": 4, "draws": 3, "games_played": 14},
        {"username": "carol", "wins": 4, "losses": 9, "draws": 2, "games_played": 15},
    ]

class FanoronaEngine:
    WHITE = 'W'
    BLACK = 'B'
    EMPTY = '.'

    def __init__(self, max_moves_without_capture=50):
        self.rows = 5
        self.cols = 9
        self.board = self._create_initial_board()
        self.current_player = self.WHITE
        
        self.game_over = False
        self.winner = None
        self.no_capture_counter = 0
        self.max_moves_without_capture = max_moves_without_capture

        self.in_chain = False
        self.chain_piece = None
        self.visited_positions = set()
        self.last_direction = None

    def _create_initial_board(self):
        board = [[self.EMPTY for _ in range(self.cols)] for _ in range(self.rows)]

        for r in range(2):
            for c in range(self.cols):
                board[r][c] = self.BLACK

        row2 = [
            self.BLACK, self.WHITE, self.BLACK, self.WHITE, self.EMPTY,
            self.BLACK, self.WHITE, self.BLACK, self.WHITE
        ]
        for c in range(self.cols):
            board[2][c] = row2[c]

        for r in range(3, 5):
            for c in range(self.cols):
                board[r][c] = self.WHITE

        return board

    def _is_valid_position(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def get_neighbors(self, r, c):
        ortho_dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        diag_dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)] if (r + c) % 2 == 0 else []

        neighbors = []
        for dr, dc in ortho_dirs + diag_dirs:
            nr, nc = r + dr, c + dc
            if self._is_valid_position(nr, nc):
                neighbors.append(((nr, nc), (dr, dc)))
        return neighbors

    def _get_captures_in_direction(self, start_r, start_c, dr, dc, opponent):
        captured = []
        curr_r, curr_c = start_r + dr, start_c + dc
        while self._is_valid_position(curr_r, curr_c):
            if self.board[curr_r][curr_c] == opponent:
                captured.append((curr_r, curr_c))
                curr_r += dr
                curr_c += dc
            else:
                break
        return captured

    def get_valid_moves(self):
        if self.game_over:
            return []

        opponent = self.BLACK if self.current_player == self.WHITE else self.WHITE
        captures = []
        paika_moves = []

        if self.in_chain:
            pieces_to_check = [self.chain_piece]
        else:
            pieces_to_check = [
                (r, c) for r in range(self.rows) for c in range(self.cols)
                if self.board[r][c] == self.current_player
            ]

        for r1, c1 in pieces_to_check:
            for (r2, c2), (dr, dc) in self.get_neighbors(r1, c1):
                if self.board[r2][c2] != self.EMPTY:
                    continue

                if self.in_chain:
                    if (r2, c2) in self.visited_positions:
                        continue
                    if (dr, dc) == self.last_direction:
                        continue

                app_captured = self._get_captures_in_direction(r2, c2, dr, dc, opponent)
                with_captured = self._get_captures_in_direction(r1, c1, -dr, -dc, opponent)

                if app_captured:
                    captures.append({
                        'from': (r1, c1),
                        'to': (r2, c2),
                        'type': 'approach',
                        'captures': app_captured,
                        'direction': (dr, dc)
                    })
                if with_captured:
                    captures.append({
                        'from': (r1, c1),
                        'to': (r2, c2),
                        'type': 'withdrawal',
                        'captures': with_captured,
                        'direction': (dr, dc)
                    })

                if not app_captured and not with_captured and not self.in_chain:
                    paika_moves.append({
                        'from': (r1, c1),
                        'to': (r2, c2),
                        'type': 'paika',
                        'captures': [],
                        'direction': (dr, dc)
                    })

        if self.in_chain:
            return captures

        return captures if captures else paika_moves

    def make_move(self, move):
        valid_moves = self.get_valid_moves()

        matching_move = next(
            (vm for vm in valid_moves 
             if vm['from'] == move['from'] and vm['to'] == move['to'] and vm['type'] == move['type']),
            None
        )

        if not matching_move:
            raise ValueError("Movimento inválido.")

        r1, c1 = matching_move['from']
        r2, c2 = matching_move['to']
        move_type = matching_move['type']
        captures = matching_move['captures']
        dr, dc = matching_move['direction']

        self.board[r1][c1] = self.EMPTY
        self.board[r2][c2] = self.current_player

        if move_type in ('approach', 'withdrawal'):
            self.no_capture_counter = 0
            for cr, cc in captures:
                self.board[cr][cc] = self.EMPTY

            self.visited_positions.add((r1, c1))
            self.chain_piece = (r2, c2)
            self.last_direction = (dr, dc)
            self.in_chain = True

            if not self.get_valid_moves():
                self.end_turn()
        else:
            self.no_capture_counter += 1
            self.end_turn()

        self._update_game_status()
        return True

    def end_turn(self):
        self.in_chain = False
        self.chain_piece = None
        self.visited_positions.clear()
        self.last_direction = None
        self.current_player = self.BLACK if self.current_player == self.WHITE else self.WHITE
        self._update_game_status()

    def surrender(self):
        """Declara a vitória do adversário por desistência do jogador atual."""
        if not self.game_over:
            self.game_over = True
            self.winner = self.BLACK if self.current_player == self.WHITE else self.WHITE

    def _update_game_status(self):
        white_count = sum(row.count(self.WHITE) for row in self.board)
        black_count = sum(row.count(self.BLACK) for row in self.board)

        if white_count == 0:
            self.game_over = True
            self.winner = self.BLACK
            return
        elif black_count == 0:
            self.game_over = True
            self.winner = self.WHITE
            return

        if self.no_capture_counter >= self.max_moves_without_capture:
            self.game_over = True
            self.winner = 'DRAW'
            return

        if not self.in_chain and not self.get_valid_moves():
            self.game_over = True
            self.winner = self.BLACK if self.current_player == self.WHITE else self.WHITE

    def get_state(self):
        return {
            "board": self.board,
            "current_player": self.current_player,
            "in_chain": self.in_chain,
            "chain_piece": self.chain_piece,
            "visited_positions": list(self.visited_positions),
            "last_direction": self.last_direction,
            "game_over": self.game_over,
            "winner": self.winner,
            "no_capture_counter": self.no_capture_counter
        }
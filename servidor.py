import json
import queue
import socket
import threading
import tkinter as tk
from tkinter import messagebox

class FanoronaServerGUI:
    def __init__(self, root, port=5555):
        self.root = root
        self.root.title("Fanorona - SERVIDOR (Jogador 1 - Pretas)")
        self.root.resizable(False, False)

        # Configurações de layout
        self.CELL_SIZE = 80
        self.MARGIN = 50
        self.RADIUS = 25
        self.ROWS = 5
        self.COLS = 9

        # Configurações de Rede
        self.port = port
        self.my_symbol = 'X'
        self.conn = None
        self.msg_queue = queue.Queue()

        # Estado do jogo (Organização ajustada de acordo com a imagem)
        self.board = [
            ['X'] * 9,
            ['X'] * 9,
            ['X', 'O', 'X', 'O', '.', 'X', 'O', 'X', 'O'],
            ['O'] * 9,
            ['O'] * 9
        ]
        self.current_player = 'O'  # Brancas ('O') começam o jogo

        # Seleção e Sequência
        self.selected_piece = None
        self.valid_moves = []
        self.in_chain = False
        self.chain_piece = None
        self.chain_visited = set()

        self.start_server_connection()

    def start_server_connection(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.bind(('0.0.0.0', self.port))
        self.server_sock.listen(1)

        wait_win = tk.Toplevel(self.root)
        wait_win.title("Aguardando Cliente")
        tk.Label(wait_win, text=f"Servidor rodando!\nAguardando conexão do Cliente na porta {self.port}...", padx=20, pady=20).pack()
        self.root.update()

        def accept_connection():
            self.conn, _ = self.server_sock.accept()
            wait_win.destroy()
            self.create_widgets()
            self.update_game_state()

            threading.Thread(target=self.listen_network, daemon=True).start()
            self.root.after(100, self.check_queue)

        threading.Thread(target=accept_connection, daemon=True).start()

    def listen_network(self):
        buffer = ""
        while True:
            try:
                data = self.conn.recv(1024).decode('utf-8')
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self.msg_queue.put(json.loads(line))
            except Exception:
                break

    def send_network(self, data):
        try:
            msg = json.dumps(data) + "\n"
            self.conn.sendall(msg.encode('utf-8'))
        except Exception as e:
            print("Erro de envio:", e)

    def check_queue(self):
        while not self.msg_queue.empty():
            msg = self.msg_queue.get()
            self.process_network_message(msg)
        self.root.after(100, self.check_queue)

    def process_network_message(self, msg):
        mtype = msg.get("type")
        if mtype == "MOVE":
            src, dst, choice = tuple(msg["src"]), tuple(msg["dst"]), msg.get("choice")
            captures = self.get_all_captures(self.current_player)
            moves = captures if captures else self.get_all_paika(self.current_player)
            
            for m in moves:
                if m['src'] == src and m['dst'] == dst:
                    self.execute_move(m, remote_choice=choice)
                    break
        elif mtype == "PASS_CHAIN":
            self.pass_turn()
        elif mtype == "CHAT":
            self.append_chat(f"Oponente: {msg['text']}")
        elif mtype == "SURRENDER":
            messagebox.showinfo("Fim de Jogo", "🏳️ Você venceu! O Cliente desistiu da partida.")
            self.reset_game(broadcast=False)
        elif mtype == "RESET":
            self.reset_game(broadcast=False)

    # --- CHAT ---

    def send_chat_msg(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.append_chat(f"Você: {text}")
        self.send_network({"type": "CHAT", "text": text})
        self.chat_entry.delete(0, tk.END)

    def append_chat(self, msg):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, msg + "\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')

    # --- REGRAS DO JOGO ---

    def is_valid_pos(self, r, c):
        return 0 <= r < self.ROWS and 0 <= c < self.COLS

    def get_neighbors(self, r, c):
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if (r + c) % 2 == 0:
            dirs += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        return [(r + dr, c + dc, dr, dc) for dr, dc in dirs if self.is_valid_pos(r + dr, c + dc)]

    def get_captures_for_piece(self, r, c, visited=None, last_dir=None):
        if visited is None:
            visited = {(r, c)}
        opp = 'O' if self.board[r][c] == 'X' else 'X'
        moves = []

        for nr, nc, dr, dc in self.get_neighbors(r, c):
            if self.board[nr][nc] == '.' and (nr, nc) not in visited:
                if last_dir is not None and (dr, dc) == last_dir:
                    continue

                app_caps = []
                curr_r, curr_c = nr + dr, nc + dc
                while self.is_valid_pos(curr_r, curr_c) and self.board[curr_r][curr_c] == opp:
                    app_caps.append((curr_r, curr_c))
                    curr_r += dr; curr_c += dc

                wit_caps = []
                curr_r, curr_c = r - dr, c - dc
                while self.is_valid_pos(curr_r, curr_c) and self.board[curr_r][curr_c] == opp:
                    wit_caps.append((curr_r, curr_c))
                    curr_r -= dr; curr_c -= dc

                if app_caps or wit_caps:
                    moves.append({'src': (r, c), 'dst': (nr, nc), 'dir': (dr, dc), 'approach': app_caps, 'withdrawal': wit_caps})
        return moves

    def get_all_captures(self, player):
        return [m for r in range(self.ROWS) for c in range(self.COLS) if self.board[r][c] == player for m in self.get_captures_for_piece(r, c)]

    def get_all_paika(self, player):
        moves = []
        for r in range(self.ROWS):
            for c in range(self.COLS):
                if self.board[r][c] == player:
                    for nr, nc, dr, dc in self.get_neighbors(r, c):
                        if self.board[nr][nc] == '.':
                            moves.append({'src': (r, c), 'dst': (nr, nc), 'dir': (dr, dc), 'approach': [], 'withdrawal': []})
        return moves

    # --- INTERFACE ---

    def create_widgets(self):
        self.info_frame = tk.Frame(self.root, bg="#2c3e50", pady=10)
        self.info_frame.pack(fill=tk.X)

        self.label_status = tk.Label(self.info_frame, text="", font=("Arial", 12, "bold"), fg="white", bg="#2c3e50")
        self.label_status.pack()

        main_frame = tk.Frame(self.root)
        main_frame.pack(padx=10, pady=10)

        width = self.MARGIN * 2 + (self.COLS - 1) * self.CELL_SIZE
        height = self.MARGIN * 2 + (self.ROWS - 1) * self.CELL_SIZE
        self.canvas = tk.Canvas(main_frame, width=width, height=height, bg="#d7ccc8", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        chat_frame = tk.LabelFrame(main_frame, text="Chat da Partida", font=("Arial", 10, "bold"), padx=10, pady=10)
        chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.chat_display = tk.Text(chat_frame, width=28, height=18, state='disabled', wrap='word', font=("Arial", 9))
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        input_frame = tk.Frame(chat_frame)
        input_frame.pack(fill=tk.X)

        self.chat_entry = tk.Entry(input_frame)
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.chat_entry.bind("<Return>", lambda event: self.send_chat_msg())

        btn_send = tk.Button(input_frame, text="Enviar", command=self.send_chat_msg, bg="#3498db", fg="white", font=("Arial", 9, "bold"))
        btn_send.pack(side=tk.RIGHT)

        self.control_frame = tk.Frame(self.root, pady=10)
        self.control_frame.pack(fill=tk.X)

        tk.Button(self.control_frame, text="Desistir", font=("Arial", 10, "bold"), command=self.surrender, bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=20)
        tk.Button(self.control_frame, text="Novo Jogo", font=("Arial", 10), command=lambda: self.reset_game(broadcast=True)).pack(side=tk.RIGHT, padx=20)

    def draw_board(self):
        self.canvas.delete("all")
        for r in range(self.ROWS):
            y1 = self.MARGIN + r * self.CELL_SIZE
            self.canvas.create_line(self.MARGIN, y1, self.MARGIN + (self.COLS - 1) * self.CELL_SIZE, y1, fill="#5d4037", width=2)

        for c in range(self.COLS):
            x1 = self.MARGIN + c * self.CELL_SIZE
            self.canvas.create_line(x1, self.MARGIN, x1, self.MARGIN + (self.ROWS - 1) * self.CELL_SIZE, fill="#5d4037", width=2)

        for r in range(self.ROWS):
            for c in range(self.COLS):
                if (r + c) % 2 == 0:
                    x1, y1 = self.MARGIN + c * self.CELL_SIZE, self.MARGIN + r * self.CELL_SIZE
                    for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                        if self.is_valid_pos(r + dr, c + dc):
                            self.canvas.create_line(x1, y1, self.MARGIN + (c + dc) * self.CELL_SIZE, self.MARGIN + (r + dr) * self.CELL_SIZE, fill="#5d4037")

        if self.current_player == self.my_symbol:
            for move in self.valid_moves:
                cx, cy = self.MARGIN + move['dst'][1] * self.CELL_SIZE, self.MARGIN + move['dst'][0] * self.CELL_SIZE
                self.canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill="#2ecc71", outline="#27ae60", width=2)

        for r in range(self.ROWS):
            for c in range(self.COLS):
                piece = self.board[r][c]
                if piece != '.':
                    cx, cy = self.MARGIN + c * self.CELL_SIZE, self.MARGIN + r * self.CELL_SIZE
                    color = "#2c3e50" if piece == 'X' else "#ecf0f1"
                    outline = "#f1c40f" if (r, c) == self.selected_piece else "#7f8c8d"
                    self.canvas.create_oval(cx - self.RADIUS, cy - self.RADIUS, cx + self.RADIUS, cy + self.RADIUS, fill=color, outline=outline, width=3)

    def update_game_state(self):
        x_cnt = sum(row.count('X') for row in self.board)
        o_cnt = sum(row.count('O') for row in self.board)

        if x_cnt == 0:
            messagebox.showinfo("Fim de Jogo", "🎉 Cliente (Brancas) Venceu!")
            self.reset_game(broadcast=False)
            return
        elif o_cnt == 0:
            messagebox.showinfo("Fim de Jogo", "🎉 Você (Pretas) Venceu!")
            self.reset_game(broadcast=False)
            return

        is_my_turn = (self.current_player == self.my_symbol)
        msg = f"Você (Pretas) | {'SUA VEZ' if is_my_turn else 'VEZ DO CLIENTE'} | Pretas: {x_cnt} | Brancas: {o_cnt}"
        self.label_status.config(text=msg)
        self.draw_board()

    def on_canvas_click(self, event):
        if self.current_player != self.my_symbol:
            return

        col = round((event.x - self.MARGIN) / self.CELL_SIZE)
        row = round((event.y - self.MARGIN) / self.CELL_SIZE)

        if not self.is_valid_pos(row, col):
            return

        if self.in_chain:
            if (row, col) == self.chain_piece:
                self.send_network({"type": "PASS_CHAIN"})
                self.pass_turn()
                return
            for move in self.valid_moves:
                if move['dst'] == (row, col):
                    self.process_local_move(move)
                    return
            return

        if self.selected_piece and (row, col) in [m['dst'] for m in self.valid_moves]:
            for move in self.valid_moves:
                if move['dst'] == (row, col):
                    self.process_local_move(move)
                    return

        if self.board[row][col] == self.current_player:
            captures = self.get_all_captures(self.current_player)
            if captures:
                piece_caps = [m for m in captures if m['src'] == (row, col)]
                self.selected_piece = (row, col) if piece_caps else None
                self.valid_moves = piece_caps
            else:
                paikas = [m for m in self.get_all_paika(self.current_player) if m['src'] == (row, col)]
                self.selected_piece = (row, col) if paikas else None
                self.valid_moves = paikas
            self.draw_board()

    def process_local_move(self, move):
        choice = None
        if move['approach'] and move['withdrawal']:
            choice = self.choose_capture_type()

        self.send_network({"type": "MOVE", "src": list(move['src']), "dst": list(move['dst']), "choice": choice})
        self.execute_move(move, remote_choice=choice)

    def choose_capture_type(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Escolha")
        dialog.geometry("250x100")
        dialog.transient(self.root)
        dialog.grab_set()

        choice = tk.StringVar(value="A")
        tk.Label(dialog, text="Como deseja capturar?").pack(pady=10)

        def select(val):
            choice.set(val); dialog.destroy()

        tk.Button(dialog, text="Aproximação", command=lambda: select("A")).pack(side=tk.LEFT, padx=10)
        tk.Button(dialog, text="Afastamento", command=lambda: select("W")).pack(side=tk.RIGHT, padx=10)
        self.root.wait_window(dialog)
        return choice.get()

    def execute_move(self, move, remote_choice=None):
        src_r, src_c = move['src']
        dst_r, dst_c = move['dst']

        self.board[dst_r][dst_c] = self.board[src_r][src_c]
        self.board[src_r][src_c] = '.'

        captured = []
        if move['approach'] and move['withdrawal']:
            captured = move['approach'] if remote_choice == "A" else move['withdrawal']
        elif move['approach']:
            captured = move['approach']
        elif move['withdrawal']:
            captured = move['withdrawal']

        for cr, cc in captured:
            self.board[cr][cc] = '.'

        if captured:
            if not self.in_chain:
                self.chain_visited = {(src_r, src_c), (dst_r, dst_c)}
            else:
                self.chain_visited.add((dst_r, dst_c))

            chain_caps = self.get_captures_for_piece(dst_r, dst_c, visited=self.chain_visited, last_dir=move['dir'])
            if chain_caps:
                self.in_chain = True
                self.chain_piece = (dst_r, dst_c)
                self.selected_piece = (dst_r, dst_c)
                self.valid_moves = chain_caps
                self.update_game_state()
                return

        self.pass_turn()

    def pass_turn(self):
        self.in_chain = False
        self.chain_piece = None
        self.chain_visited = set()
        self.selected_piece = None
        self.valid_moves = []
        self.current_player = 'O' if self.current_player == 'X' else 'X'
        self.update_game_state()

    def surrender(self):
        if messagebox.askyesno("Desistir", "Deseja mesmo desistir?"):
            self.send_network({"type": "SURRENDER"})
            messagebox.showinfo("Fim de Jogo", "🏳️ Você desistiu. Vitória do Cliente!")
            self.reset_game(broadcast=False)

    def reset_game(self, broadcast=True):
        if broadcast:
            self.send_network({"type": "RESET"})
        self.board = [
            ['X'] * 9,
            ['X'] * 9,
            ['X', 'O', 'X', 'O', '.', 'X', 'O', 'X', 'O'],
            ['O'] * 9,
            ['O'] * 9
        ]
        self.current_player = 'O'
        self.in_chain = False
        self.selected_piece = None
        self.valid_moves = []
        self.update_game_state()

if __name__ == "__main__":
    root = tk.Tk()
    app = FanoronaServerGUI(root)
    root.mainloop()
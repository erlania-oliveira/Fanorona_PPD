import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import queue
import time
import Pyro5.api
from fanorona_engine import FanoronaEngine

SERVER_IP = '127.0.0.1'  # Altere para o IP do servidor se estiver jogando em dispositivos diferentes
SERVER_PORT = 55555

ROWS = 5
COLS = 9
CELL_SIZE = 80
MARGIN = 50
WIDTH = COLS * CELL_SIZE + 2 * MARGIN + 350
HEIGHT = ROWS * CELL_SIZE + 2 * MARGIN + 80

COLOR_BG = "#D2B48C"
COLOR_LINE = "#4A2E10"
COLOR_WHITE_PIECE = "#F5F5F5"
COLOR_BLACK_PIECE = "#2B2B2B"
COLOR_SELECTED = "#FFD700"
COLOR_VALID_MOVE = "#32CD32"

class FanoronaClientRMI:
    def __init__(self, root, host=SERVER_IP, port=SERVER_PORT):
        self.root = root
        self.root.title("Fanorona Multiplayer - RMI (Pyro5)")
        self.root.geometry(f"{WIDTH}x{HEIGHT}")
        self.root.resizable(False, False)

        self.uri = f"PYRO:FanoronaServer@{host}:{port}"
        self.my_symbol = None
        self.running = True

        self.engine = FanoronaEngine()
        self.net_queue = queue.Queue()

        self.selected_pos = None
        self.valid_moves = []
        self.last_state_version = -1
        self.last_chat_count = 0

        self._create_widgets()
        self._connect_to_rmi_server()

        self.root.after(50, self._check_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_widgets(self):
        main_frame = tk.Frame(self.root, bg=COLOR_BG)
        main_frame.pack(fill=tk.BOTH, expand=True)

        canvas_width = COLS * CELL_SIZE + 2 * MARGIN
        canvas_height = ROWS * CELL_SIZE + 2 * MARGIN
        self.canvas = tk.Canvas(main_frame, width=canvas_width, height=canvas_height, bg=COLOR_BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        sidebar = tk.Frame(main_frame, bg="#EEDC82", width=320)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        self.lbl_status = tk.Label(sidebar, text="Conectando ao Servidor RMI...", font=("Arial", 11, "bold"), bg="#EEDC82", wraplength=300)
        self.lbl_status.pack(pady=10)

        tk.Label(sidebar, text="Chat da Partida", font=("Arial", 10, "bold"), bg="#EEDC82").pack(anchor="w", padx=5)
        self.chat_area = scrolledtext.ScrolledText(sidebar, width=35, height=15, state='disabled', font=("Arial", 9))
        self.chat_area.pack(padx=5, pady=5)

        chat_input_frame = tk.Frame(sidebar, bg="#EEDC82")
        chat_input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.txt_chat = tk.Entry(chat_input_frame, font=("Arial", 10))
        self.txt_chat.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.txt_chat.bind("<Return>", lambda event: self._send_chat())

        btn_send = tk.Button(chat_input_frame, text="Enviar", command=self._send_chat, bg="#8B4513", fg="white", font=("Arial", 9, "bold"))
        btn_send.pack(side=tk.RIGHT)

        actions_frame = tk.Frame(sidebar, bg="#EEDC82")
        actions_frame.pack(fill=tk.X, padx=5, pady=15)

        self.btn_surrender = tk.Button(actions_frame, text="Desistir", command=self._surrender, state=tk.DISABLED, bg="#B22222", fg="white", font=("Arial", 10, "bold"))
        self.btn_surrender.pack(fill=tk.X, pady=3)

    def _connect_to_rmi_server(self):
        try:
            with Pyro5.api.Proxy(self.uri) as proxy:
                response = proxy.connect_player("Jogador_Client")

            if response.get("status") == "ERROR":
                messagebox.showerror("Erro de Conexão", response.get("message"))
                self.root.destroy()
                return

            self.my_symbol = response["player"]
            color_name = "BRANCAS (W)" if self.my_symbol == 'W' else "PRETAS (B)"
            self.lbl_status.config(text=f"Você é as Peças: {color_name}\n{response['message']}")

            self.poll_thread = threading.Thread(target=self._poll_server, daemon=True)
            self.poll_thread.start()

        except Exception as e:
            messagebox.showerror("Erro de Conexão RMI", f"Não foi possível conectar ao servidor RMI:\n{e}")
            self.root.destroy()

    def _poll_server(self):
        """Thread isolada de polling com seu próprio proxy Pyro5."""
        with Pyro5.api.Proxy(self.uri) as poll_proxy:
            while self.running:
                try:
                    data = poll_proxy.get_game_state()
                    version = data.get("version", 0)

                    if version > self.last_state_version:
                        self.last_state_version = version
                        self.net_queue.put({"type": "UPDATE_STATE", "data": data})
                except Exception as e:
                    print(f"[RMI POLLING] Erro ao consultar servidor: {e}")
                    time.sleep(1.0)
                time.sleep(0.15)

    def _check_queue(self):
        try:
            while True:
                msg = self.net_queue.get_nowait()
                if msg["type"] == "UPDATE_STATE":
                    self._apply_server_state(msg["data"])
        except queue.Empty:
            pass

        if self.running:
            self.root.after(50, self._check_queue)

    def _apply_server_state(self, data):
        state = data["state"]
        players = data.get("players", {})
        chat_history = data.get("chat_history", [])

        self.engine.board = state["board"]
        self.engine.current_player = state["current_player"]
        self.engine.game_over = state["game_over"]
        self.engine.winner = state["winner"]
        self.engine.in_chain = state["in_chain"]
        self.engine.chain_piece = tuple(state["chain_piece"]) if state["chain_piece"] else None
        self.engine.visited_positions = set(tuple(p) for p in state["visited_positions"])
        self.engine.last_direction = tuple(state["last_direction"]) if state["last_direction"] else None

        if len(players) < 2:
            self.lbl_status.config(text=f"Sua Peça: {self.my_symbol}\nAguardando segundo jogador...")
        elif self.engine.game_over:
            if self.engine.winner == "DRAW":
                self.lbl_status.config(text="FIM DE JOGO: Empate!")
            elif self.engine.winner == self.my_symbol:
                self.lbl_status.config(text="FIM DE JOGO: Você VENCEU! 🎉")
            else:
                self.lbl_status.config(text="FIM DE JOGO: Você PERDEU! ❌")
        else:
            turn_txt = "Sua Vez de Jogar!" if self.engine.current_player == self.my_symbol else "Vez do Oponente..."
            chain_txt = " (Captura em Cadeia!)" if self.engine.in_chain else ""
            self.lbl_status.config(text=f"Sua Peça: {self.my_symbol}\n{turn_txt}{chain_txt}")

        # Habilita/Desabilita o botão Desistir (Apenas na vez do jogador atual com 2 jogadores conectados)
        if not self.engine.game_over and self.engine.current_player == self.my_symbol and len(players) == 2:
            self.btn_surrender.config(state=tk.NORMAL)
        else:
            self.btn_surrender.config(state=tk.DISABLED)

        if len(chat_history) > self.last_chat_count:
            self.chat_area.config(state='normal')
            for entry in chat_history[self.last_chat_count:]:
                sender = "Você" if entry["sender"] == self.my_symbol else f"Jogador ({entry['sender']})"
                self.chat_area.insert(tk.END, f"{sender}: {entry['text']}\n")
            self.chat_area.see(tk.END)
            self.chat_area.config(state='disabled')
            self.last_chat_count = len(chat_history)

        self._redraw()

    def _redraw(self):
        self.canvas.delete("all")
        self._draw_board_lines()
        self._draw_pieces()
        self._draw_highlights()

    def _draw_board_lines(self):
        """Desenha a grade oficial do tabuleiro Fanorona com interseções fortes e fracas."""
        for r in range(ROWS):
            y = MARGIN + r * CELL_SIZE
            self.canvas.create_line(MARGIN, y, MARGIN + (COLS - 1) * CELL_SIZE, y, fill=COLOR_LINE, width=3)

        for c in range(COLS):
            x = MARGIN + c * CELL_SIZE
            self.canvas.create_line(x, MARGIN, x, MARGIN + (ROWS - 1) * CELL_SIZE, fill=COLOR_LINE, width=3)

        for r in range(ROWS - 1):
            for c in range(COLS - 1):
                x1 = MARGIN + c * CELL_SIZE
                y1 = MARGIN + r * CELL_SIZE
                x2 = MARGIN + (c + 1) * CELL_SIZE
                y2 = MARGIN + (r + 1) * CELL_SIZE

                if (r + c) % 2 == 0:
                    self.canvas.create_line(x1, y1, x2, y2, fill=COLOR_LINE, width=2)
                else:
                    self.canvas.create_line(x2, y1, x1, y2, fill=COLOR_LINE, width=2)

    def _draw_pieces(self):
        radius = CELL_SIZE // 3
        for r in range(ROWS):
            for c in range(COLS):
                piece = self.engine.board[r][c]
                if piece in (self.engine.WHITE, self.engine.BLACK):
                    x = MARGIN + c * CELL_SIZE
                    y = MARGIN + r * CELL_SIZE
                    color = COLOR_WHITE_PIECE if piece == self.engine.WHITE else COLOR_BLACK_PIECE
                    self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="#000000", width=2)

    def _draw_highlights(self):
        if self.selected_pos:
            r, c = self.selected_pos
            x = MARGIN + c * CELL_SIZE
            y = MARGIN + r * CELL_SIZE
            radius = CELL_SIZE // 3 + 4
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=COLOR_SELECTED, width=4)

        for move in self.valid_moves:
            tr, tc = move['to']
            x = MARGIN + tc * CELL_SIZE
            y = MARGIN + tr * CELL_SIZE
            radius = 12
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=COLOR_VALID_MOVE, outline="")

    def _on_canvas_click(self, event):
        if self.engine.game_over or self.engine.current_player != self.my_symbol:
            return

        col = round((event.x - MARGIN) / CELL_SIZE)
        row = round((event.y - MARGIN) / CELL_SIZE)

        if not (0 <= row < ROWS and 0 <= col < COLS):
            return

        clicked_pos = (row, col)

        if self.selected_pos:
            candidate_moves = [m for m in self.valid_moves if m['to'] == clicked_pos]
            if candidate_moves:
                chosen_move = candidate_moves[0]
                if len(candidate_moves) > 1:
                    types = [m['type'] for m in candidate_moves]
                    if 'approach' in types and 'withdrawal' in types:
                        ans = messagebox.askyesno("Tipo de Captura", "Clique 'SIM' para Captura por APROXIMAÇÃO ou 'NÃO' para AFASTAMENTO.")
                        chosen_type = 'approach' if ans else 'withdrawal'
                        chosen_move = next(m for m in candidate_moves if m['type'] == chosen_type)

                self._send_move(chosen_move)
                self.selected_pos = None
                self.valid_moves = []
                self._redraw()
                return

        if self.engine.board[row][col] == self.my_symbol:
            if self.engine.in_chain and clicked_pos != self.engine.chain_piece:
                return
            self.selected_pos = clicked_pos
            self.valid_moves = self.engine.get_valid_moves_for_piece(row, col)
            self._redraw()
        else:
            self.selected_pos = None
            self.valid_moves = []
            self._redraw()

    def _send_move(self, move):
        def execute_rmi():
            try:
                move_payload = {
                    'from': list(move['from']),
                    'to': list(move['to']),
                    'type': move['type'],
                    'captures': [list(c) for c in move.get('captures', [])],
                    'direction': list(move['direction'])
                }
                with Pyro5.api.Proxy(self.uri) as proxy:
                    proxy.make_move(self.my_symbol, move_payload)
            except Exception as err:
                messagebox.showerror("Erro de Jogada", str(err))

        threading.Thread(target=execute_rmi, daemon=True).start()

    def _surrender(self):
        if self.engine.current_player != self.my_symbol or self.engine.game_over:
            messagebox.showwarning("Aviso", "Você só pode desistir durante o seu turno!")
            return

        if messagebox.askyesno("Desistir", "Tem certeza de que deseja desistir da partida?"):
            def execute_rmi():
                try:
                    with Pyro5.api.Proxy(self.uri) as proxy:
                        proxy.surrender(self.my_symbol)
                except Exception as err:
                    messagebox.showerror("Erro", str(err))

            threading.Thread(target=execute_rmi, daemon=True).start()

    def _send_chat(self):
        text = self.txt_chat.get().strip()
        if text:
            self.txt_chat.delete(0, tk.END)
            def execute_rmi():
                try:
                    with Pyro5.api.Proxy(self.uri) as proxy:
                        proxy.send_chat(self.my_symbol, text)
                except Exception as err:
                    print(f"Erro ao enviar chat RMI: {err}")

            threading.Thread(target=execute_rmi, daemon=True).start()

    def _on_closing(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FanoronaClientRMI(root, host=SERVER_IP, port=SERVER_PORT)
    root.mainloop()






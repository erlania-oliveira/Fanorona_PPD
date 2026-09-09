import socket
import threading
import queue
import json
import tkinter as tk
from tkinter import messagebox
from fanorona_engine import FanoronaEngine

HOST = '127.0.0.1'
PORT = 55555
"""HOST = '192.168.3.5'"""
  # Substitua pelo IPv4 real do seu PC
"""PORT = 55555"""

class FanoronaClientGUI:
    def __init__(self, root, host=HOST, port=PORT):
        self.root = root
        self.root.title("Fanorona - Cliente Distribuído")
        self.root.resizable(False, False)

        self.net_queue = queue.Queue()
        self.my_player = None
        self.game_started = False
        
        self.local_engine = FanoronaEngine()

        # Dimensões expandidas para acomodar o Chat na lateral
        self.WIDTH = 1180
        self.HEIGHT = 550
        self.BOARD_WIDTH = 900
        self.CHAT_WIDTH = 280
        
        self.ROWS = 5
        self.COLS = 9
        self.OFFSET_X = 100
        self.OFFSET_Y = 80
        self.SPACING_X = (self.BOARD_WIDTH - 2 * self.OFFSET_X) // (self.COLS - 1)
        self.SPACING_Y = (self.HEIGHT - 2 * self.OFFSET_Y - 60) // (self.ROWS - 1)
        self.RADIUS = 22

        self.selected_pos = None
        self.available_moves_for_selected = []

        self._create_widgets()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((host, port))
        except Exception as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao servidor:\n{e}")
            self.root.destroy()
            return

        threading.Thread(target=self._listen_server, daemon=True).start()
        self.root.after(50, self._check_queue)
        self.redraw()

    def _create_widgets(self):
        # Container Superior (Tabuleiro + Chat)
        top_container = tk.Frame(self.root, bg="#3C2814")
        top_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Tabuleiro (Canvas)
        self.canvas = tk.Canvas(
            top_container, 
            width=self.BOARD_WIDTH, 
            height=self.HEIGHT - 60, 
            bg="#D7B991", 
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # Painel Lateral de Chat
        chat_frame = tk.Frame(top_container, bg="#2B1B0E", width=self.CHAT_WIDTH)
        chat_frame.pack(side=tk.RIGHT, fill=tk.Y)
        chat_frame.pack_propagate(False)

        lbl_chat_title = tk.Label(
            chat_frame, 
            text="Chat da Partida", 
            font=("Arial", 11, "bold"), 
            fg="#FFFFFF", 
            bg="#2B1B0E"
        )
        lbl_chat_title.pack(side=tk.TOP, pady=8)

        # Área de Histórico de Mensagens
        self.txt_chat = tk.Text(
            chat_frame, 
            state=tk.DISABLED, 
            bg="#F5F5F5", 
            font=("Arial", 9), 
            wrap=tk.WORD,
            highlightthickness=0
        )
        self.txt_chat.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=5)

        # Input e Botão de Envio
        input_frame = tk.Frame(chat_frame, bg="#2B1B0E")
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)

        self.entry_chat = tk.Entry(input_frame, font=("Arial", 10))
        self.entry_chat.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.entry_chat.bind("<Return>", lambda event: self._send_chat_message())

        btn_send = tk.Button(
            input_frame, 
            text="Enviar", 
            font=("Arial", 9, "bold"), 
            bg="#5CB85C", 
            fg="#FFFFFF", 
            command=self._send_chat_message
        )
        btn_send.pack(side=tk.RIGHT)

        # Painel Inferior de Status
        self.panel = tk.Frame(self.root, bg="#3C2814", height=60)
        self.panel.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_status = tk.Label(
            self.panel, 
            text="Conectando ao servidor...", 
            font=("Arial", 11, "bold"), 
            fg="#FFFFFF", 
            bg="#3C2814"
        )
        self.lbl_status.pack(side=tk.LEFT, padx=15, pady=15)

        self.btn_surrender = tk.Button(
            self.panel, 
            text="Desistir", 
            font=("Arial", 10, "bold"), 
            bg="#D9534F", 
            fg="#FFFFFF", 
            state=tk.DISABLED,
            command=self._on_surrender_click
        )
        self.btn_surrender.pack(side=tk.RIGHT, padx=10, pady=12)

    def _send_chat_message(self):
        """Envia o texto digitado na caixa de chat para o servidor."""
        text = self.entry_chat.get().strip()
        if text:
            self._send_to_server({"type": "CHAT", "text": text})
            self.entry_chat.delete(0, tk.END)

    def _send_to_server(self, data):
        try:
            payload = (json.dumps(data) + "\n").encode('utf-8')
            self.socket.sendall(payload)
        except Exception as e:
            print(f"[CLIENTE] Erro ao enviar mensagem: {e}")

    def _listen_server(self):
        buffer = ""
        while True:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = json.loads(line)
                        self.net_queue.put(msg)
            except Exception as e:
                print(f"[CLIENTE] Desconectado do servidor: {e}")
                break

    def _check_queue(self):
        try:
            while True:
                msg = self.net_queue.get_nowait()
                self._handle_server_message(msg)
        except queue.Empty:
            pass

        self.root.after(50, self._check_queue)

    def _handle_server_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "INIT":
            self.my_player = msg.get("player")
            p_str = "BRANCAS (W)" if self.my_player == 'W' else "PRETAS (B)"
            self.root.title(f"Fanorona - Você é o Jogador {p_str}")
            self.redraw()

        elif msg_type == "GAME_START":
            self.game_started = True
            self.redraw()

        elif msg_type == "CHAT":
            sender = msg.get("sender")
            text = msg.get("text")
            sender_str = "BRANCAS" if sender == 'W' else "PRETAS"
            
            # Adiciona a mensagem formatada na caixa de texto do Chat
            self.txt_chat.config(state=tk.NORMAL)
            self.txt_chat.insert(tk.END, f"[{sender_str}]: {text}\n")
            self.txt_chat.see(tk.END)  # Rola automaticamente para a última mensagem
            self.txt_chat.config(state=tk.DISABLED)

        elif msg_type == "UPDATE_STATE":
            state = msg.get("state")
            self.local_engine.board = state["board"]
            self.local_engine.current_player = state["current_player"]
            self.local_engine.in_chain = state["in_chain"]
            self.local_engine.chain_piece = tuple(state["chain_piece"]) if state["chain_piece"] else None
            self.local_engine.visited_positions = {tuple(p) for p in state["visited_positions"]}
            self.local_engine.last_direction = tuple(state["last_direction"]) if state["last_direction"] else None
            self.local_engine.game_over = state["game_over"]
            self.local_engine.winner = state["winner"]

            if not self.local_engine.in_chain:
                self.selected_pos = None
                self.available_moves_for_selected = []
            else:
                if self.local_engine.current_player == self.my_player:
                    self.selected_pos = self.local_engine.chain_piece
                    self.available_moves_for_selected = self.local_engine.get_valid_moves()

            self.redraw()

        elif msg_type == "ERROR":
            messagebox.showwarning("Aviso", msg.get("message"))

        elif msg_type == "DISCONNECT":
            self.game_started = False
            messagebox.showinfo("Fim da Partida", msg.get("message"))
            self.redraw()

    def _grid_to_screen(self, r, c):
        x = self.OFFSET_X + c * self.SPACING_X
        y = self.OFFSET_Y + r * self.SPACING_Y
        return x, y

    def _screen_to_grid(self, x, y):
        for r in range(self.ROWS):
            for c in range(self.COLS):
                gx, gy = self._grid_to_screen(r, c)
                if (x - gx) ** 2 + (y - gy) ** 2 <= (self.RADIUS + 6) ** 2:
                    return r, c
        return None

    def redraw(self):
        self.canvas.delete("all")

        drawn_lines = set()
        for r in range(self.ROWS):
            for c in range(self.COLS):
                x1, y1 = self._grid_to_screen(r, c)
                for (nr, nc), _ in self.local_engine.get_neighbors(r, c):
                    line_id = tuple(sorted([(r, c), (nr, nc)]))
                    if line_id not in drawn_lines:
                        x2, y2 = self._grid_to_screen(nr, nc)
                        self.canvas.create_line(x1, y1, x2, y2, fill="#3C2814", width=3)
                        drawn_lines.add(line_id)

        if self.game_started:
            valid_targets = {m['to'] for m in self.available_moves_for_selected}
            for tr, tc in valid_targets:
                tx, ty = self._grid_to_screen(tr, tc)
                r_target = self.RADIUS // 2
                self.canvas.create_oval(
                    tx - r_target, ty - r_target, tx + r_target, ty + r_target,
                    fill="#2ECC71", outline=""
                )

        for r in range(self.ROWS):
            for c in range(self.COLS):
                piece = self.local_engine.board[r][c]
                x, y = self._grid_to_screen(r, c)

                if self.selected_pos == (r, c) and self.game_started:
                    self.canvas.create_oval(
                        x - self.RADIUS - 4, y - self.RADIUS - 4,
                        x + self.RADIUS + 4, y + self.RADIUS + 4,
                        outline="#FFD700", width=4
                    )

                if piece == self.local_engine.WHITE:
                    self.canvas.create_oval(
                        x - self.RADIUS, y - self.RADIUS,
                        x + self.RADIUS, y + self.RADIUS,
                        fill="#F5F5F5", outline="#3C2814", width=2
                    )
                elif piece == self.local_engine.BLACK:
                    self.canvas.create_oval(
                        x - self.RADIUS, y - self.RADIUS,
                        x + self.RADIUS, y + self.RADIUS,
                        fill="#1A1A1A", outline="#1A1A1A", width=2
                    )

        if not self.game_started:
            status_msg = "Aguardando o Jogador 2 (Pretas) conectar..."
            self.btn_surrender.config(state=tk.DISABLED)
        else:
            turn_str = "BRANCAS (W)" if self.local_engine.current_player == 'W' else "PRETAS (B)"
            my_str = "BRANCAS" if self.my_player == 'W' else "PRETAS"
            status_msg = f"Você é: {my_str} | Vez: {turn_str}"

            if self.local_engine.in_chain:
                status_msg += " (Cadeia Ativa)"

            if self.local_engine.game_over:
                self.btn_surrender.config(state=tk.DISABLED)
                if self.local_engine.winner == 'DRAW':
                    status_msg = "FIM DE JOGO: EMPATE!"
                else:
                    w_str = "BRANCAS" if self.local_engine.winner == 'W' else "PRETAS"
                    status_msg = f"FIM DE JOGO: VITÓRIA DAS {w_str}!"
            else:
                self.btn_surrender.config(state=tk.NORMAL)

        self.lbl_status.config(text=status_msg)

    def _on_canvas_click(self, event):
        if not self.game_started or self.local_engine.game_over or self.local_engine.current_player != self.my_player:
            return

        grid_pos = self._screen_to_grid(event.x, event.y)
        if not grid_pos:
            return

        cr, cc = grid_pos
        all_valid_moves = self.local_engine.get_valid_moves()

        matching_moves = [m for m in self.available_moves_for_selected if m['to'] == (cr, cc)]
        if matching_moves:
            if len(matching_moves) == 1:
                self._send_move(matching_moves[0])
            else:
                self._prompt_capture_type(matching_moves)
            return

        if self.local_engine.board[cr][cc] == self.my_player:
            if not self.local_engine.in_chain or (self.local_engine.in_chain and (cr, cc) == self.local_engine.chain_piece):
                self.selected_pos = (cr, cc)
                self.available_moves_for_selected = [m for m in all_valid_moves if m['from'] == (cr, cc)]
                self.redraw()

    def _send_move(self, move):
        payload_move = {
            'from': list(move['from']),
            'to': list(move['to']),
            'type': move['type'],
            'captures': [list(c) for c in move['captures']],
            'direction': list(move['direction'])
        }
        self._send_to_server({"type": "MOVE", "move": payload_move})

    def _prompt_capture_type(self, options):
        dialog = tk.Toplevel(self.root)
        dialog.title("Escolha o tipo de captura")
        dialog.geometry("320x130")
        dialog.transient(self.root)
        dialog.grab_set()

        lbl = tk.Label(dialog, text="Essa jogada permite dois tipos de captura:", font=("Arial", 10))
        lbl.pack(pady=10)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)

        for move in options:
            label = "Aproximação" if move['type'] == 'approach' else "Afastamento"
            btn = tk.Button(
                btn_frame, 
                text=label, 
                font=("Arial", 10, "bold"),
                width=12,
                command=lambda m=move, d=dialog: [d.destroy(), self._send_move(m)]
            )
            btn.pack(side=tk.LEFT, padx=10)

    def _on_surrender_click(self):
        if not self.game_started or self.local_engine.game_over:
            return

        confirm = messagebox.askyesno(
            "Confirmar Desistência", 
            "Deseja realmente desistir da partida?"
        )
        if confirm:
            self._send_to_server({"type": "SURRENDER"})

if __name__ == "__main__":
    root = tk.Tk()
    app = FanoronaClientGUI(root)
    root.mainloop()
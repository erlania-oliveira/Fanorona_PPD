import socket
import threading
import json
from fanorona_engine import FanoronaEngine

HOST = '0.0.0.0'# Escuta todas as interfaces de rede
PORT = 55555
"""HOST = '127.0.0.1'"""
"""PORT = 55556"""

class FanoronaServer:
    def __init__(self, host=HOST, port=PORT):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(2)

        self.engine = FanoronaEngine()
        self.clients = {}  # { 'W': socket_conn1, 'B': socket_conn2 }
        self.lock = threading.Lock()
        self.game_started = False

        print(f"[SERVIDOR] Servidor iniciado em {host}:{port}")
        print("[SERVIDOR] Aguardando a conexão dos 2 jogadores...")

    def broadcast(self, message):
        """Envia uma mensagem JSON formatada para ambos os clientes."""
        payload = (json.dumps(message) + "\n").encode('utf-8')
        for player_symbol, conn in list(self.clients.items()):
            try:
                conn.sendall(payload)
            except Exception as e:
                print(f"[SERVIDOR] Erro ao enviar mensagem para {player_symbol}: {e}")

    def send_to(self, conn, message):
        """Envia uma mensagem JSON formatada para um cliente específico."""
        payload = (json.dumps(message) + "\n").encode('utf-8')
        try:
            conn.sendall(payload)
        except Exception as e:
            print(f"[SERVIDOR] Erro de envio: {e}")

    def handle_client(self, conn, player_symbol):
        """Thread responsável por escutar as ações de cada cliente."""
        buffer = ""
        while True:
            try:
                data = conn.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = json.loads(line)
                        self.process_action(player_symbol, msg)
            except Exception as e:
                print(f"[SERVIDOR] Conexão perdida com jogador {player_symbol}: {e}")
                break

        with self.lock:
            if player_symbol in self.clients:
                del self.clients[player_symbol]
            self.game_started = False
        
        self.broadcast({
            "type": "DISCONNECT",
            "disconnected_player": player_symbol,
            "message": f"O jogador das peças {player_symbol} desconectou."
        })
        conn.close()

    def process_action(self, player_symbol, msg):
        """Processa as ações enviadas pelos clientes."""
        action_type = msg.get("type")

        # Chat pode ser enviado a qualquer momento (não depende de turno ou de o jogo ter começado)
        if action_type == "CHAT":
            text = msg.get("text", "").strip()
            if text:
                self.broadcast({
                    "type": "CHAT",
                    "sender": player_symbol,
                    "text": text
                })
            return

        with self.lock:
            # Bloqueia jogadas de tabuleiro se o jogo ainda não iniciou
            if not self.game_started:
                self.send_to(self.clients[player_symbol], {
                    "type": "ERROR", 
                    "message": "Aguarde o segundo jogador conectar para iniciar a partida!"
                })
                return

            if self.engine.current_player != player_symbol and not self.engine.game_over:
                self.send_to(self.clients[player_symbol], {
                    "type": "ERROR", 
                    "message": "Não é a sua vez de jogar!"
                })
                return

            if action_type == "MOVE":
                raw_move = msg.get("move")
                move = {
                    'from': tuple(raw_move['from']),
                    'to': tuple(raw_move['to']),
                    'type': raw_move['type'],
                    'captures': [tuple(c) for c in raw_move.get('captures', [])],
                    'direction': tuple(raw_move['direction'])
                }

                try:
                    self.engine.make_move(move)
                    self._broadcast_state()
                except ValueError as err:
                    self.send_to(self.clients[player_symbol], {
                        "type": "ERROR", 
                        "message": str(err)
                    })

            elif action_type == "END_TURN":
                if self.engine.in_chain:
                    self.engine.end_turn()
                    self._broadcast_state()

            elif action_type == "SURRENDER":
                self.engine.surrender()
                self._broadcast_state()

    def _broadcast_state(self):
        """Empacota o estado atual da engine e envia a ambos os clientes."""
        state = self.engine.get_state()
        state["chain_piece"] = list(state["chain_piece"]) if state["chain_piece"] else None
        state["visited_positions"] = [list(pos) for pos in state["visited_positions"]]
        state["last_direction"] = list(state["last_direction"]) if state["last_direction"] else None

        self.broadcast({
            "type": "UPDATE_STATE",
            "state": state
        })

    def start(self):
        conn_w, addr_w = self.server_socket.accept()
        self.clients['W'] = conn_w
        print(f"[SERVIDOR] Jogador 1 conectado ({addr_w}) -> Peças BRANCAS (W)")
        self.send_to(conn_w, {"type": "INIT", "player": "W", "message": "Aguardando Jogador 2..."})
        
        threading.Thread(target=self.handle_client, args=(conn_w, 'W'), daemon=True).start()

        conn_b, addr_b = self.server_socket.accept()
        self.clients['B'] = conn_b
        print(f"[SERVIDOR] Jogador 2 conectado ({addr_b}) -> Peças PRETAS (B)")
        self.send_to(conn_b, {"type": "INIT", "player": "B", "message": "Partida iniciada!"})

        threading.Thread(target=self.handle_client, args=(conn_b, 'B'), daemon=True).start()

        with self.lock:
            self.game_started = True

        self.broadcast({"type": "GAME_START", "message": "Ambos os jogadores conectados! A partida começou."})
        self._broadcast_state()

        while True:
            pass

if __name__ == "__main__":
    server = FanoronaServer()
    server.start()
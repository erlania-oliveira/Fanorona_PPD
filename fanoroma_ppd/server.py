import Pyro5.api
from Pyro5 import config
import threading
from fanorona_engine import FanoronaEngine

HOST = "0.0.0.0"
PORT = 55555

@Pyro5.api.expose
class FanoronaServerRMI:
    def __init__(self):
        self.engine = FanoronaEngine()
        self.players = {}        # {'W': "Jogador 1", 'B': "Jogador 2"}
        self.chat_history = []
        self.state_version = 0
        self.lock = threading.Lock()

    def connect_player(self, player_name):
        with self.lock:
            if 'W' not in self.players:
                self.players['W'] = player_name
                print(f"[RMI] Jogador 1 conectado -> Peças BRANCAS (W)")
                return {"status": "OK", "player": "W", "message": "Aguardando Jogador 2..."}
            elif 'B' not in self.players:
                self.players['B'] = player_name
                self.state_version += 1
                print(f"[RMI] Jogador 2 conectado -> Peças PRETAS (B)")
                return {"status": "OK", "player": "B", "message": "Partida iniciada!"}
            else:
                return {"status": "ERROR", "message": "Servidor cheio!"}

    def make_move(self, player_symbol, move):
        with self.lock:
            if len(self.players) < 2:
                raise ValueError("Aguarde o segundo jogador conectar!")

            if self.engine.current_player != player_symbol and not self.engine.game_over:
                raise ValueError("Não é a sua vez de jogar!")

            formatted_move = {
                'from': tuple(move['from']),
                'to': tuple(move['to']),
                'type': move['type'],
                'captures': [tuple(c) for c in move.get('captures', [])],
                'direction': tuple(move['direction'])
            }

            self.engine.make_move(formatted_move)
            self.state_version += 1
            return True

    def end_turn(self, player_symbol):
        with self.lock:
            if self.engine.current_player == player_symbol and self.engine.in_chain:
                self.engine.end_turn()
                self.state_version += 1
                return True
            return False

    def surrender(self, player_symbol):
        with self.lock:
            if not self.engine.game_over:
                self.engine.surrender()
                self.state_version += 1
                return True
            return False

    def send_chat(self, sender, text):
        with self.lock:
            self.chat_history.append({"sender": sender, "text": text})
            self.state_version += 1
            return True

    def get_game_state(self):
        with self.lock:
            state = self.engine.get_state()
            state["chain_piece"] = list(state["chain_piece"]) if state["chain_piece"] else None
            state["visited_positions"] = [list(p) for p in state["visited_positions"]]
            state["last_direction"] = list(state["last_direction"]) if state["last_direction"] else None

            return {
                "version": self.state_version,
                "state": state,
                "players": self.players,
                "chat_history": self.chat_history
            }

def start_server():
    config.HOST = "0.0.0.0"
    daemon = Pyro5.api.Daemon(host=HOST, port=PORT)
    # ATENÇÃO: FanoronaServerRMI() instanciado aqui com () para ser um Singleton compartilhado
    uri = daemon.register(FanoronaServerRMI(), objectId="FanoronaServer")
    print(f"[SERVIDOR RMI] Servidor iniciado na porta {PORT}.")
    print(f"[SERVIDOR RMI] URI de Acesso: {uri}")
    print("[SERVIDOR RMI] Aguardando chamadas de métodos dos clientes...")
    daemon.requestLoop()

if __name__ == "__main__":
    start_server()
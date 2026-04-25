import socket
from abc import ABC, abstractmethod


class Receiver(ABC):

    def __init__(self, sock: socket.socket, addr: tuple, verbose: bool = False):
        self.sock        = sock
        self.addr        = addr
        self.verbose     = verbose
        self.expected_np = 1    # próximo paquete esperado en orden
        self.last_np     = 0    # último NP recibido en orden (para el close)

    def _send_raw(self, pkt: bytes) -> None:
        self.sock.sendto(pkt, self.addr)

    @abstractmethod
    def receive_file(self, dest_path: str) -> None:
        pass

    @abstractmethod
    def receive_bytes(self) -> bytes:
        pass

    @abstractmethod
    def close(self) -> None:
        pass
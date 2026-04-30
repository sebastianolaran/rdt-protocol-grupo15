import socket
from abc import ABC, abstractmethod

from lib.protocol import CONSTANTS


class Sender(ABC):

    def __init__(self, sock: socket.socket, addr: tuple, verbose: bool = False):
        self.sock    = sock
        self.addr    = addr
        self.verbose = verbose
        self.next_np = 1
        self.base = 1
        self.max_retries = CONSTANTS["MAX_RETRIES"]

    def _send_raw(self, pkt: bytes) -> None:
        self.sock.sendto(pkt, self.addr)

    def _recv_ack(self) -> bytes:
        if self.recv_queue:
            return self.recv_queue.get(timeout=CONSTANTS["DEFAULT_TIMEOUT"])
        else:
            self.sock.settimeout(CONSTANTS["DEFAULT_TIMEOUT"])
            raw, _ = self.sock.recvfrom(CONSTANTS["MAX_PKT_SIZE"])
            return raw

    @abstractmethod
    def send_file(self, filepath: str) -> None:
        pass

    @abstractmethod
    def send_bytes(self, data: bytes) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    
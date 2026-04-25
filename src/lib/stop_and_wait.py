import queue
import socket
import time

from lib.protocol import CONSTANTS, Packet
from lib.receiver import Receiver
from lib.sender import Sender


class SAWSender(Sender):

    def __init__(self, sock: socket.socket, addr: tuple,
                 verbose: bool = False, recv_queue: queue.Queue = None):
        super().__init__(sock, addr, verbose)
        self.recv_queue = recv_queue  

    def _recv_ack(self) -> bytes:
        try:
            return super()._recv_ack()
        except queue.Empty:
            raise TimeoutError("queue timeout")

    def send_file(self, filepath: str) -> None:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(CONSTANTS["MAX_PAYLOAD"])
                if not chunk:
                    break
                self.send_bytes(chunk)

    def send_bytes(self, data: bytes) -> None:
        pkt = Packet.build(self.next_np, 0, 0, 0, data)
        for _ in range(self.max_retries):
            try:
                self._send_raw(pkt)
                raw = self._recv_ack()
                ack_pkt = Packet.parse(raw)
                if ack_pkt.ack == self.next_np + 1:
                    self.next_np += 1
                    self.last_np = self.next_np - 1
                    return
            except (TimeoutError, OSError, ValueError):
                pass
        raise TimeoutError(f"sin ACK tras {self.max_retries} intentos")

    def close(self) -> None:
        fin = Packet.build(self.next_np, 0, CONSTANTS["FLAG_C"], 0, b"")
        for _ in range(self.max_retries):
            try:
                self._send_raw(fin)
                raw = self._recv_ack()
                resp = Packet.parse(raw)
                if resp.flags & CONSTANTS["FLAG_C"]:
                    ack_final = Packet.build(
                        self.next_np + 1, resp.np + 1, 0, 0, b""
                    )
                    self._send_raw(ack_final)
                    time.sleep(2 * CONSTANTS["DEFAULT_TIMEOUT"])
                    return
            except (TimeoutError, OSError, ValueError):
                pass
        raise TimeoutError("CLOSE sin respuesta")


class SAWReceiver(Receiver):

    def __init__(self, sock: socket.socket, addr: tuple,
                 verbose: bool = False, recv_queue: queue.Queue = None):
        super().__init__(sock, addr, verbose)
        self.recv_queue = recv_queue

    def _recv_packet(self) -> bytes:
        if self.recv_queue:
            try:
                return self.recv_queue.get(timeout=CONSTANTS["DEFAULT_TIMEOUT"])
            except queue.Empty:
                raise TimeoutError("queue timeout")
        self.sock.settimeout(CONSTANTS["DEFAULT_TIMEOUT"])
        raw, _ = self.sock.recvfrom(CONSTANTS["MAX_PKT_SIZE"])
        return raw

    def receive_file(self, dest_path: str) -> None:
        data = self.receive_bytes()
        with open(dest_path, "wb") as f:
            f.write(data)

    def receive_bytes(self) -> bytes:
        chunks = []
        while True:
            try:
                raw = self._recv_packet()
            except (TimeoutError, OSError):
                continue
            try:
                pkt = Packet.parse(raw)
            except ValueError:
                continue

            if pkt.flags & CONSTANTS["FLAG_C"]:
                self.close()
                break

            if pkt.np == self.expected_np:
                chunks.append(pkt.data)
                ack = Packet.build(0, self.expected_np + 1, 0, 0, b"")
                self._send_raw(ack)
                self.last_np = pkt.np
                self.expected_np += 1
            elif pkt.np < self.expected_np:
                ack = Packet.build(0, pkt.np + 1, 0, 0, b"")
                self._send_raw(ack)

        return b"".join(chunks)

    def close(self) -> None:
        fin_ack = Packet.build(
            0, self.last_np + 1, CONSTANTS["FLAG_C"], 0, b""
        )
        self._send_raw(fin_ack)
        try:
            self._recv_packet()
        except (TimeoutError, OSError, ValueError):
            pass

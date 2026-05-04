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
        
        self.alpha = CONSTANTS["RTO_ALPHA"]
        self.beta = CONSTANTS["RTO_BETA"]
        self.srtt = None
        self.rttvar = None
        self.rto = CONSTANTS["DEFAULT_TIMEOUT_SAW"]

    def _recv_ack(self) -> bytes:
        try:
            if self.recv_queue:
                return self.recv_queue.get(timeout=self.rto)
            self.sock.settimeout(self.rto)
            raw, _ = self.sock.recvfrom(CONSTANTS["MAX_PKT_SIZE"])
            return raw
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
        send_time = None
        retransmitted = False
        for _ in range(self.max_retries):
            try:
                if send_time is None:
                    send_time = time.time()
                self._send_raw(pkt)
                raw = self._recv_ack()
                ack_pkt = Packet.parse(raw)
                if ack_pkt.flags & CONSTANTS["FLAG_I"]:
                    resp = Packet.build(0, 1, CONSTANTS["FLAG_I"] | 0b0000, ack_pkt.win, b"")
                    self._send_raw(resp)
                    continue
                if ack_pkt.ack == self.next_np + 1:
                    if not retransmitted:
                        self._update_rto_on_ack(send_time)
                    self.next_np += 1
                    return
            except TimeoutError:
                retransmitted = True
            except (OSError, ValueError):
                pass
        raise TimeoutError(
            f"TIMEOUT_ABORT: sin ACK tras {self.max_retries} intentos"
        )

    def _update_rto_on_ack(self, send_time: float) -> None:
        if send_time is None:
            return
        rtt_sample = time.time() - send_time
        if self.srtt is None:
            self.srtt = rtt_sample
            self.rttvar = rtt_sample / 2
        else:
            self.rttvar = (1 - self.beta) * self.rttvar + \
                self.beta * abs(rtt_sample - self.srtt)
            self.srtt = (1 - self.alpha) * self.srtt + \
                self.alpha * rtt_sample
        self.rto = min(
            CONSTANTS["RTO_MAX"],
            max(self.srtt + 4 * self.rttvar, CONSTANTS["RTO_MIN"])
        )

    def close(self) -> None:
        fin = Packet.build(self.next_np, 0, CONSTANTS["FLAG_C"], 0, b"")
        for _ in range(self.max_retries):
            self._send_raw(fin)
            try:
                while True:
                    try:
                        if self.recv_queue:
                            raw = self.recv_queue.get(
                                timeout=CONSTANTS["DEFAULT_TIMEOUT"]
                            )
                        else:
                            self.sock.settimeout(CONSTANTS["DEFAULT_TIMEOUT"])
                            raw, _ = self.sock.recvfrom(CONSTANTS["MAX_PKT_SIZE"])
                        resp = Packet.parse(raw)
                        if resp.flags & CONSTANTS["FLAG_C"]:
                            ack_final = Packet.build(
                                self.next_np + 1, resp.np + 1, 0, 0, b""
                            )
                            self._send_raw(ack_final)
                            time.sleep(2 * CONSTANTS["DEFAULT_TIMEOUT_SAW"])
                            return
                    except ValueError:
                        pass
            except (TimeoutError, OSError):
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
                return self.recv_queue.get(timeout=CONSTANTS["DEFAULT_TIMEOUT_SAW"])
            except queue.Empty:
                raise TimeoutError("queue timeout")
        self.sock.settimeout(CONSTANTS["DEFAULT_TIMEOUT_SAW"])
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
                if self.verbose:
                    np = int.from_bytes(raw[:2], 'big') if len(raw) >= 2 \
                        else '?'
                    print(f"[CHECKSUM_ERROR] paquete descartado NP={np}")
                continue

            if pkt.flags & CONSTANTS["FLAG_I"]:
                resp = Packet.build(0, 1, CONSTANTS["FLAG_I"] | 0b0000, pkt.win, b"")
                self._send_raw(resp)
                continue

            if pkt.flags & CONSTANTS["FLAG_C"]:
                self.last_np = pkt.np
                self.close()
                break

            if pkt.np == self.expected_np:
                chunks.append(pkt.data)
                self.expected_np += 1
                ack = Packet.build(0, self.expected_np , 0, 0, b"")
                self._send_raw(ack)
                self.last_np = pkt.np
            elif pkt.np < self.expected_np:
                ack = Packet.build(0, self.expected_np, 0, 0, b"")
                self._send_raw(ack)

        return b"".join(chunks)

    def close(self) -> None:
        fin_ack = Packet.build(
            0, self.last_np + 1, CONSTANTS["FLAG_C"], 0, b""
        )
        self._send_raw(fin_ack)
        start_time = time.time()
        timeout_wait = 2 * CONSTANTS.get("RTO_MAX", 1.0)
        while time.time() - start_time < timeout_wait:
            try:
                raw = self._recv_packet()
                resp = Packet.parse(raw)
                if resp.flags & CONSTANTS["FLAG_C"]:
                    self._send_raw(fin_ack)
                    start_time = time.time()
                else:
                    return
            except (TimeoutError, OSError, ValueError):
                pass

import queue
import socket
import time

from lib.protocol import CONSTANTS, Packet
from lib.receiver import Receiver
from lib.sender import Sender


class SRSender(Sender):
    """
    Sender Selective Repeat: mantiene hasta SR_WINDOW_SIZE paquetes en vuelo.
    Solo retransmite el paquete cuyo timer venció, no toda la ventana.
    """

    def __init__(self, sock: socket.socket, addr: tuple,
                 verbose: bool = False, recv_queue: queue.Queue = None):
        super().__init__(sock, addr, verbose)
        self.recv_queue = recv_queue
        self.window = CONSTANTS["SR_WINDOW_SIZE"]
        # np → (pkt_bytes, send_time, retries): paquetes enviados sin ACK
        self.buffer = {}
        self.base = 1  # paquete más antiguo sin ACKear

    def _recv_ack(self) -> bytes:
        # Unifica la interfaz: queue.Empty → TimeoutError igual que el socket
        try:
            return super()._recv_ack()
        except queue.Empty:
            raise TimeoutError("queue timeout")

    def send_file(self, filepath: str) -> None:
        """
        Lee el archivo completo en chunks y los envía con SR.
        El loop alterna entre tres tareas:
          1. Llenar la ventana con nuevos chunks
          2. Procesar ACKs entrantes y avanzar la base
          3. Retransmitir paquetes con timer vencido
        """
        chunks = []
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(CONSTANTS["MAX_PAYLOAD"])
                if not chunk:
                    break
                chunks.append(chunk)

        index = 0
        while index < len(chunks) or self.buffer:
            # 1) Llenar ventana: enviar mientras haya chunks y espacio
            while index < len(chunks) and self.next_np < self.base + self.window:
                self.send_bytes(chunks[index])
                index += 1

            # Todos los chunks enviados y ACKeados: terminar
            if not self.buffer and index >= len(chunks):
                break

            # 2) Intentar recibir un ACK (no bloqueante — timeout corto)
            try:
                raw = self._recv_ack()
                ack_pkt = Packet.parse(raw)
                acked_np = ack_pkt.ack - 1  # ack = np+1 del paquete confirmado
                if self.base <= acked_np < self.next_np:
                    # ACK acumulativo: el receiver confirmó todo hasta acked_np
                    for np in range(self.base, acked_np + 1):
                        self.buffer.pop(np, None)
                # Avanzar base hasta el primer paquete aún pendiente
                while self.base < self.next_np and self.base not in self.buffer:
                    self.base += 1
            except (TimeoutError, OSError, ValueError):
                pass

            # 3) Retransmitir paquetes con timer vencido
            self.check_timeouts()

    def check_timeouts(self) -> None:
        """
        Recorre el buffer y retransmite individualmente cada paquete
        cuyo timer venció. Si un paquete superó MAX_RETRIES aborta
        la transferencia completa.
        """
        for np in list(self.buffer):
            pkt_bytes, send_time, retries = self.buffer[np]
            if time.time() - send_time > CONSTANTS["DEFAULT_TIMEOUT"]:
                if retries < CONSTANTS["MAX_RETRIES"]:
                    if self.verbose:
                        print(f"[SR] Retransmitiendo NP={np} "
                              f"(intento {retries + 1})")
                    self.buffer[np] = (pkt_bytes, time.time(), retries + 1)
                    self._send_raw(pkt_bytes)
                else:
                    raise TimeoutError(
                        f"TIMEOUT_ABORT: sin ACK tras "
                        f"{self.max_retries} intentos en NP={np}"
                    )

    def send_bytes(self, data: bytes) -> None:
        """
        Mete el chunk en el buffer y lo envía sin esperar ACK.
        El ACK se procesa en el loop de send_file.
        flags=0 y win=0: paquetes de datos nunca llevan FLAG_I ni FLAG_C.
        """
        pkt = Packet.build(self.next_np, 0, 0, 0, data)
        self.buffer[self.next_np] = (pkt, time.time(), 0)
        self._send_raw(pkt)
        self.next_np += 1

    def close(self) -> None:
        """
        Two-way close iniciado por el sender:
          1. Envía FIN (FLAG_C)
          2. Espera FIN-ACK (FLAG_C del receiver)
          3. Envía ACK final y entra en TIME_WAIT (2×timeout)
        TIME_WAIT evita que un FIN-ACK retrasado llegue a una sesión nueva.
        """
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


class SRReceiver(Receiver):
    """
    Receiver Selective Repeat: acepta paquetes fuera de orden dentro
    de la ventana, los bufferéa y los entrega en orden al hacer flush.
    """

    def __init__(self, sock: socket.socket, addr: tuple,
                 verbose: bool = False, recv_queue: queue.Queue = None):
        super().__init__(sock, addr, verbose)
        self.recv_queue = recv_queue
        self.buffer = {}  # np → data: paquetes fuera de orden pendientes
        self.window = CONSTANTS["SR_WINDOW_SIZE"]

    def _recv_packet(self) -> bytes:
        # Misma abstracción que el sender: queue (servidor) o socket (cliente)
        if self.recv_queue:
            try:
                return self.recv_queue.get(timeout=CONSTANTS["DEFAULT_TIMEOUT"])
            except queue.Empty:
                raise TimeoutError("queue timeout")
        self.sock.settimeout(CONSTANTS["DEFAULT_TIMEOUT"])
        raw, _ = self.sock.recvfrom(CONSTANTS["MAX_PKT_SIZE"])
        return raw

    def receive_file(self, dest_path: str) -> None:
        """Recibe el stream y lo escribe directamente en disco."""
        data = self.receive_bytes()
        with open(dest_path, "wb") as f:
            f.write(data)

    def receive_bytes(self) -> bytes:
        """
        Loop principal de recepción. Cuatro casos posibles por paquete:
          - CRC inválido      → descartar silenciosamente, sin ACK
          - FLAG_C            → iniciar two-way close y terminar
          - NP == expected    → entregar, flush del buffer, ACK adelantado
          - NP > expected     → buffereár si está en ventana, ACK del último en orden
          - NP < expected     → duplicado, reenviar mismo ACK
        """
        chunks = []

        while True:
            try:
                raw = self._recv_packet()
            except (TimeoutError, OSError):
                # Timeout esperando datos — reintentar
                continue

            try:
                pkt = Packet.parse(raw)
            except ValueError:
                # CRC inválido: descarte silencioso, no enviar ACK
                # El sender retransmitirá por timeout
                if self.verbose:
                    np = int.from_bytes(raw[:2], 'big') if len(raw) >= 2 \
                        else '?'
                    print(f"[CHECKSUM_ERROR] paquete descartado NP={np}")
                continue

            if pkt.flags & CONSTANTS["FLAG_C"]:
                self.close()
                break

            if pkt.np == self.expected_np:
                chunks.append(pkt.data)
                self.expected_np += 1
                self.last_np = pkt.np
                # Flush: entregar en orden todo lo que ya estaba buffereado
                while self.expected_np in self.buffer:
                    chunks.append(self.buffer.pop(self.expected_np))
                    self.expected_np += 1
                # ACK adelantado: confirma todo lo entregado hasta acá
                ack = Packet.build(0, self.expected_np, 0, 0, b"")
                self._send_raw(ack)

            elif pkt.np > self.expected_np:
                # Fuera de orden: buffereár solo si está dentro de la ventana
                # Si está fuera de ventana se ignora pero igual se ACKea
                if pkt.np < self.expected_np + self.window:
                    self.buffer[pkt.np] = pkt.data
                # ACK del último en orden para que el sender sepa dónde está la base
                ack = Packet.build(0, self.expected_np, 0, 0, b"")
                self._send_raw(ack)

            else:
                # Duplicado: ya fue entregado, reenviar mismo ACK
                ack = Packet.build(0, self.expected_np, 0, 0, b"")
                self._send_raw(ack)

        return b"".join(chunks)

    def close(self) -> None:
        """
        Two-way close desde el lado del receiver:
          1. Responde FIN-ACK (FLAG_C) al sender
          2. Espera el ACK final — si no llega asume que llegó
             porque el sender tiene TIME_WAIT activo
        """
        fin_ack = Packet.build(
            0, self.last_np + 1, CONSTANTS["FLAG_C"], 0, b""
        )
        self._send_raw(fin_ack)
        try:
            self._recv_packet()
        except (TimeoutError, OSError, ValueError):
            pass
# RDT (Reliable Data Transfer)

import socket
import time
from .protocol import Packet
from .constants import MAX_PKT_SIZE, ERR_OK

# Stop & Wait: Envia paquete, espera ACK, retransmite si hay timeout.
def send_stop_and_wait(sock, addr, data_blocks, verbose=False):

    seq_num = 0
    sock.settimeout(0.5) # Timeout para manejar la pérdida del 10%

    for block in data_blocks:
        pkt = Packet(seq_num, 0, 0, block)
        raw_pkt = pkt.pack()

        while True:
            try:
                sock.sendto(raw_pkt, addr)
                if verbose: print(f"[*] Enviando paquete {seq_num}")

                ack_raw, _ = sock.recvfrom(MAX_PKT_SIZE)
                ack_pkt = Packet.unpack(ack_raw)

                if ack_pkt.ack_num == seq_num + 1:
                    if verbose: print(f"[+] ACK {ack_pkt.ack_num} recibido")
                    seq_num += 1
                    break
            except socket.timeout:
                if verbose: print(f"[!] Timeout: Retransmitiendo paquete {seq_num}")
                continue

def receive_stop_and_wait(sock, storage_path, verbose=False):
    expected_seq = 0
    #
    pass

# Selective Repeat:
# 1. Envia todos los paquetes de la ventana inicial.
# 2. Mantiene un hilo o temporizador por cada paquete.
# 3. Solo retransmite los paquetes específicos que no recibieron ACK.
def send_selective_repeat(sock, addr, data_blocks, window_size=5, verbose=False):
    #
    pass
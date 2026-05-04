#!/usr/bin/env python3
"""
Topología: 1 servidor + 3 clientes conectados a un switch central.

    h1 (server)
        |
       s1 ── h2 (client1)
        |
       s1 ── h3 (client2)
        |
       s1 ── h4 (client3)

Uso:
    sudo python3 topology.py
"""

from mininet.net import Mininet
from mininet.node import OVSController
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI


def run():
    setLogLevel('info')

    net = Mininet(controller=OVSController, link=TCLink)

    # Nodos
    net.addController('c0')
    switch = net.addSwitch('s1')

    server  = net.addHost('h1', ip='10.0.0.1/24')
    client1 = net.addHost('h2', ip='10.0.0.2/24')
    client2 = net.addHost('h3', ip='10.0.0.3/24')
    client3 = net.addHost('h4', ip='10.0.0.4/24')
    client4 = net.addHost('h5', ip='10.0.0.5/24')
    client5 = net.addHost('h6', ip='10.0.0.6/24')


    # Links — podés ajustar bw (Mbps), delay y loss según la prueba
    net.addLink(server,  switch, loss=0)
    net.addLink(client1, switch,loss=10)
    net.addLink(client2, switch, loss=10)
    net.addLink(client3, switch, loss=10)
    net.addLink(client4, switch, loss=10)
    net.addLink(client5, switch, loss=10)

    net.start()

    # --- Arrancar el servidor en background ---
    server.cmd('cd /ruta/a/tu/proyecto && python3 start-server '
               '-H 10.0.0.1 -p 8080 -s /tmp/storage &')

    import time
    time.sleep(1)  # dale un segundo al servidor para que arranque

  
    CLI(net)

    net.stop()


if __name__ == '__main__':
    run()
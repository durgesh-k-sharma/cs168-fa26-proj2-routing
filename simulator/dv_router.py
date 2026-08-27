"""
Your awesome Distance Vector router for CS 168

Based on skeleton code by:
  MurphyMc, zhangwen0411, lab352
"""

import sim.api as api
from cs168.dv import (
    RoutePacket,
    Table,
    TableEntry,
    DVRouterBase,
    Ports,
    FOREVER,
    INFINITY,
)


class DVRouter(DVRouterBase):

    # A route should time out after this interval
    ROUTE_TTL = 15

    # -----------------------------------------------
    # At most one of these should ever be on at once
    SPLIT_HORIZON = False
    POISON_REVERSE = False
    # -----------------------------------------------

    # Determines if you send poison for expired routes
    POISON_EXPIRED = False

    # Determines if you send updates when a link comes up
    SEND_ON_LINK_UP = False

    # Determines if you send poison when a link goes down
    POISON_ON_LINK_DOWN = False

    def __init__(self):
        """
        Called when the instance is initialized.
        DO NOT remove any existing code from this method.
        However, feel free to add to it for memory purposes in the final stage!
        """
        assert not (
            self.SPLIT_HORIZON and self.POISON_REVERSE
        ), "Split horizon and poison reverse can't both be on"

        self.start_timer()  # Starts signaling the timer at correct rate.

        # Contains all current ports and their latencies.
        # See the write-up for documentation.
        self.ports = Ports()

        # This is the table that contains all current routes
        self.table = Table()
        self.table.owner = self

        ##### Begin Stage 10A #####
        self.history = {}
        ##### End Stage 10A #####

    def add_static_route(self, host, port):
        """
        Adds a static route to this router's table.

        Called automatically by the framework whenever a host is connected
        to this router.

        :param host: the host.
        :param port: the port that the host is attached to.
        :returns: nothing.
        """
        # `port` should have been added to `peer_tables` by `handle_link_up`
        # when the link came up.
        assert port in self.ports.get_all_ports(), "Link should be up, but is not."

        ##### Begin Stage 1 #####
        latency = self.ports.get_latency(port)
        self.table[host] = TableEntry(
            dst=host, port=port, latency=latency, expire_time=FOREVER
        )
        ##### End Stage 1 #####

    def handle_data_packet(self, packet, in_port):
        """
        Called when a data packet arrives at this router.

        You may want to forward the packet, drop the packet, etc. here.

        :param packet: the packet that arrived.
        :param in_port: the port from which the packet arrived.
        :return: nothing.
        """
        
        ##### Begin Stage 2 #####
        if packet.dst not in self.table:
            return
        entry = self.table[packet.dst]
        if entry.latency >= INFINITY:
            return
        self.send(packet, port=entry.port)
        ##### End Stage 2 #####

    def send_routes(self, force=False, single_port=None):
        """
        Send route advertisements for all routes in the table.

        :param force: if True, advertises ALL routes in the table;
                      otherwise, advertises only those routes that have
                      changed since the last advertisement.
               single_port: if not None, sends updates only to that port; to
                            be used in conjunction with handle_link_up.
        :return: nothing.
        """
        
        ##### Begin Stages 3, 6, 7, 8, 10 #####
        ports_to_send = (
            [single_port]
            if single_port is not None
            else list(self.ports.get_all_ports())
        )
        for port in ports_to_send:
            for dst, entry in self.table.items():
                lat = min(entry.latency, INFINITY)
                if self.SPLIT_HORIZON and entry.port == port:
                    continue
                elif self.POISON_REVERSE and entry.port == port:
                    lat = INFINITY

                if force or (self.history.get((port, dst)) != lat):
                    self.send_route(port, dst, lat)
                    self.history[(port, dst)] = lat
        ##### End Stages 3, 6, 7, 8, 10 #####

    def expire_routes(self):
        """
        Clears out expired routes from table.
        accordingly.
        """
        
        ##### Begin Stages 5, 9 #####
        for dst, entry in list(self.table.items()):
            if entry.has_expired:
                if self.POISON_EXPIRED:
                    if entry.latency < INFINITY:
                        self.table[dst] = TableEntry(
                            dst=dst,
                            port=entry.port,
                            latency=INFINITY,
                            expire_time=FOREVER,
                        )
                else:
                    del self.table[dst]
        ##### End Stages 5, 9 #####

    def handle_route_advertisement(self, route_dst, route_latency, port):
        """
        Called when the router receives a route advertisement from a neighbor.

        :param route_dst: the destination of the advertised route.
        :param route_latency: latency from the neighbor to the destination.
        :param port: the port that the advertisement arrived on.
        :return: nothing.
        """
        
        ##### Begin Stages 4, 10 #####
        link_lat = self.ports.get_latency(port)
        total_lat = min(route_latency + link_lat, INFINITY)
        new_expire = api.current_time() + self.ROUTE_TTL

        if route_dst not in self.table:
            if route_latency < INFINITY:
                self.table[route_dst] = TableEntry(
                    dst=route_dst, port=port, latency=total_lat, expire_time=new_expire
                )
                self.send_routes(force=False)
        else:
            curr_entry = self.table[route_dst]
            if port == curr_entry.port:
                # Rule 2: Updates From Next-Hop
                self.table[route_dst] = TableEntry(
                    dst=route_dst, port=port, latency=total_lat, expire_time=new_expire
                )
                if curr_entry.latency != total_lat:
                    self.send_routes(force=False)
            elif total_lat < curr_entry.latency:
                # Rule 1: Bellman-Ford update (strictly shorter)
                self.table[route_dst] = TableEntry(
                    dst=route_dst, port=port, latency=total_lat, expire_time=new_expire
                )
                self.send_routes(force=False)
        ##### End Stages 4, 10 #####

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this router goes up.

        :param port: the port that the link is attached to.
        :param latency: the link latency.
        :returns: nothing.
        """
        self.ports.add_port(port, latency)

        ##### Begin Stage 10B #####
        if self.SEND_ON_LINK_UP:
            self.send_routes(force=True, single_port=port)
        ##### End Stage 10B #####

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this router goes down.

        :param port: the port number used by the link.
        :returns: nothing.
        """
        self.ports.remove_port(port)

        ##### Begin Stage 10B #####
        changed = False
        for dst, entry in list(self.table.items()):
            if entry.port == port:
                if self.POISON_ON_LINK_DOWN:
                    if entry.latency < INFINITY:
                        self.table[dst] = TableEntry(
                            dst=dst,
                            port=port,
                            latency=INFINITY,
                            expire_time=FOREVER,
                        )
                        changed = True
                else:
                    del self.table[dst]
                    changed = True
        if changed:
            self.send_routes(force=False)
        ##### End Stage 10B #####

    # Feel free to add any helper methods!

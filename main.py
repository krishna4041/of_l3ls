from kytos.core import KytosEvent, KytosNApp, log
from kytos.core.helpers import listen_to
from pyof.foundation.network_types import Ethernet, EtherType, IPv4
from pyof.v0x04.common.action import ActionOutput
from pyof.v0x04.common.flow_match import Match
from pyof.v0x04.common.port import Port, PortNo
from pyof.v0x04.controller2switch.flow_mod import FlowMod, FlowModCommand
from pyof.v0x04.controller2switch.packet_out import PacketOut

from napps.krishna4041.of_l3ls import settings


class Main(KytosNApp):
    def setup(self):
        pass

    def execute(self):
        pass

    # @listen_to('kytos/core.switch.new')
    # def create_switching_table(self, event):
    #     switch = event.content['switch']
    #     switch.l3_table = {}

    #     arp_flow_mod = FlowMod()
    #     arp_flow_mod.command = FlowModCommand.OFPFC_ADD
    #     arp_flow_mod.match = Match()
    #     arp_flow_mod.match.dl_type = EtherType.ARP
    #     # arp_flow_mod.instructions = ActionOutput(port=PortNo.OFPP_FLOOD.value)
    #     event_out = KytosEvent(name=('krishna4041/of_l3ls.messages.out.'
    #                            'ofpt_flow_mod'),
    #                      content={'destination': switch.connection,
    #                               'message': arp_flow_mod})
    #     self.controller.buffers.msg_out.put(event_out)

    @listen_to('kytos/of_core.v0x04.messages.in.ofpt_packet_in')
    def handle_packet_in(self, event):
        packet_in = event.content['message']

        ethernet = Ethernet()
        ethernet.unpack(packet_in.data.value)

        if ethernet.ether_type.value == EtherType.IPV4:
            ipv4 = IPv4()
            ipv4.unpack(ethernet.data.value)

            in_port = packet_in.in_port.value
            switch = event.source.switch
            switch.l3_table[ipv4.source] = in_port
            log.info('Packet received from %s to %s.', ipv4.source,
                     ipv4.destination)

            dest_port = switch.l3_table.get(ipv4.destination, None)

            if dest_port is not None:
                log.info('%s is at port %d.', ipv4.destination, dest_port)
                flow_mod = FlowMod()
                flow_mod.command = FlowModCommand.OFPFC_ADD
                flow_mod.match = Match()
                flow_mod.match.nw_src = ipv4.source
                flow_mod.match.nw_dst = ipv4.destination
                flow_mod.match.dl_type = ethernet.ether_type
                flow_mod.actions.append(ActionOutput(port=dest_ports[0]))
                event_out = KytosEvent(name=('krishna4041/of_l3ls.messages.out.'
                                             'ofpt_flow_mod'),
                                       content={'destination': event.source,
                                                'message': flow_mod})
                self.controller.buffers.msg_out.put(event_out)
                log.info('Flow installed! Subsequent packets will be sent directly.')

            packet_out = PacketOut()
            packet_out.buffer_id = packet_in.buffer_id
            packet_out.in_port = packet_in.in_port
            packet_out.data = packet_in.data

            port = dest_port if dest_port is not None else PortNo.OFPP_FLOOD
            packet_out.actions.append(ActionOutput(port=port))
            event_out = KytosEvent(name=('krishna4041/of_l3ls.messages.out.'
                                         'ofpt_packet_out'),
                                   content={'destination': event.source,
                                            'message': packet_out})

            self.controller.buffers.msg_out.put(event_out)

    def shutdown(self):
        pass
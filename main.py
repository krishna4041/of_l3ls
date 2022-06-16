import struct
from kytos.core import KytosEvent, KytosNApp, log
from kytos.core.helpers import listen_to
from pyof.foundation.network_types import Ethernet, EtherType, IPv4
from pyof.v0x04.common.action import ActionOutput
from pyof.v0x04.common.flow_match import (
    Match,
    OxmClass,
    OxmOfbMatchField,
    MatchType,
    OxmTLV,
)
from pyof.v0x04.common.flow_instructions import (
    InstructionApplyAction,
)
from pyof.v0x04.common.port import PortNo
from pyof.v0x04.controller2switch.flow_mod import FlowMod, FlowModCommand
from pyof.v0x04.controller2switch.packet_out import PacketOut


class Main(KytosNApp):
    def setup(self):
        pass

    def execute(self):
        pass

    @listen_to("kytos/of_core.handshake.completed")
    def create_switching_table(self, event):
        switch = event.content["switch"]
        switch.l3_table = {}

        arp_flow_mod = FlowMod()
        arp_flow_mod.command = FlowModCommand.OFPFC_ADD
        arp_flow_mod.priority = 10000
        oxmtlv1 = OxmTLV(
            oxm_class=OxmClass.OFPXMC_OPENFLOW_BASIC,
            oxm_field=OxmOfbMatchField.OFPXMT_OFB_ETH_TYPE,
            oxm_hasmask=False,
            oxm_value=EtherType.ARP.value.to_bytes(2, "big"),
        )
        match = Match(match_type=MatchType.OFPMT_OXM, oxm_match_fields=[oxmtlv1])
        arp_flow_mod.match = match
        action_output = ActionOutput(port=PortNo.OFPP_FLOOD)
        instructions = [InstructionApplyAction([action_output])]
        arp_flow_mod.instructions = instructions
        event_out = KytosEvent(
            name=("krishna4041/of_l3ls.messages.out." "ofpt_flow_mod"),
            content={"destination": switch.connection, "message": arp_flow_mod},
        )
        self.controller.buffers.msg_out.put(event_out)

        flow_mod_miss_entry = FlowMod()
        flow_mod_miss_entry.command = FlowModCommand.OFPFC_ADD
        flow_mod_miss_entry.match = Match()
        action_output = ActionOutput(port=PortNo.OFPP_CONTROLLER)
        instructions = [InstructionApplyAction([action_output])]
        flow_mod_miss_entry.instructions = instructions
        event_out = KytosEvent(
            name=("krishna4041/of_l3ls.messages.out." "ofpt_flow_mod"),
            content={"destination": switch.connection, "message": flow_mod_miss_entry},
        )
        self.controller.buffers.msg_out.put(event_out)

    @listen_to("kytos/of_core.v0x04.messages.in.ofpt_packet_in")
    def handle_packet_in(self, event):
        packet_in = event.content["message"]

        ethernet = Ethernet()
        ethernet.unpack(packet_in.data.value)

        if ethernet.ether_type.value == EtherType.IPV4:
            ipv4 = IPv4()
            ipv4.unpack(ethernet.data.value)

            in_port = packet_in.in_port
            switch = event.source.switch
            dest_port = switch.l3_table.get(ipv4.destination)
            log.info(f"Packet received from {ipv4.source} to {ipv4.destination}.")

            if ipv4.source not in switch.l3_table:
                switch.l3_table[ipv4.source] = in_port
                log.info(f"{ipv4.source} is at port {in_port}.")
                flow_mod = FlowMod()
                flow_mod.command = FlowModCommand.OFPFC_ADD
                oxmtlv1 = OxmTLV(
                    oxm_class=OxmClass.OFPXMC_OPENFLOW_BASIC,
                    oxm_field=OxmOfbMatchField.OFPXMT_OFB_ETH_TYPE,
                    oxm_hasmask=False,
                    oxm_value=EtherType.IPV4.value.to_bytes(2, "big"),
                )
                oxmtlv2 = OxmTLV(
                    oxm_class=OxmClass.OFPXMC_OPENFLOW_BASIC,
                    oxm_field=OxmOfbMatchField.OFPXMT_OFB_IPV4_SRC,
                    oxm_hasmask=False,
                    oxm_value=struct.pack(
                        "bbbb", *[int(val) for val in ipv4.source.split(".")]
                    ),
                )
                oxmtlv3 = OxmTLV(
                    oxm_class=OxmClass.OFPXMC_OPENFLOW_BASIC,
                    oxm_field=OxmOfbMatchField.OFPXMT_OFB_IPV4_DST,
                    oxm_hasmask=False,
                    oxm_value=struct.pack(
                        "bbbb", *[int(val) for val in ipv4.destination.split(".")]
                    ),
                )
                match = Match(
                    match_type=MatchType.OFPMT_OXM,
                    oxm_match_fields=[oxmtlv1, oxmtlv2, oxmtlv3],
                )
                flow_mod.match = match
                instructions = [InstructionApplyAction([ActionOutput(port=in_port)])]
                flow_mod.instructions = instructions
                event_out = KytosEvent(
                    name=("krishna4041/of_l3ls.messages.out." "ofpt_flow_mod"),
                    content={"destination": event.source, "message": flow_mod},
                )
                self.controller.buffers.msg_out.put(event_out)
                log.info(
                    f"Flow installed! Subsequent packets from {ipv4.source} "
                    f"to {ipv4.destination} will be sent directly."
                )

            packet_out = PacketOut()
            packet_out.buffer_id = packet_in.buffer_id
            packet_out.in_port = packet_in.in_port
            packet_out.data = packet_in.data

            port = dest_port if dest_port is not None else PortNo.OFPP_FLOOD
            packet_out.actions.append(ActionOutput(port=port))
            event_out = KytosEvent(
                name=("krishna4041/of_l3ls.messages.out." "ofpt_packet_out"),
                content={"destination": event.source, "message": packet_out},
            )
            self.controller.buffers.msg_out.put(event_out)

    def shutdown(self):
        pass

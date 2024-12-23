import socket
import time
import logging
import math

MAX_HTD_VOLUME = 60
DEFAULT_HTD_LYNC6_PORT = 10006

_LOGGER = logging.getLogger(__name__)


def to_correct_string(message):
    string = ""
    for i in range(len(message)):
        string += hex(message[i]) + ","
    return string[:-1]


class HtdLync6Client:
    def __init__(self, ip_address, port=DEFAULT_HTD_LYNC6_PORT):
        self.ip_address = ip_address
        self.port = port
        self.zones = {
            k: {
                'zone': k,
                'power': None,
                'input': None,
                'vol': None,
                'mute': None,
                'source': None,
            } for k in range(1, 7)
        }

    def parse(self, cmd, message, zone_number):

        if len(message) > 14:
            zones = list()
            # each chunk represents a different zone that should be 14 bytes long,
            # query_all should work for each zone but doesn't, so we only take the first chunk

                # zone0 = message[0:14]
            zone1 = message[14:28]
            zone2 = message[28:42]
            zone3 = message[42:56]
            zone4 = message[56:70]
            zone5 = message[70:84]
            zone6 = message[84:98]
            #zone7 = message[98:112]
            #zone8 = message[112:126]
            #zone9 = message[126:140]
            #zone10 = message[140:154]
            #zone11 = message[154:168]
            #zone12 = message[168:182]
            zones.append(zone1)
            zones.append(zone2)
            zones.append(zone3)
            zones.append(zone4)
            zones.append(zone5)
            zones.append(zone6)
            #zones.append(zone7)
            #zones.append(zone8)
            #zones.append(zone9)
            #zones.append(zone10)
            #zones.append(zone11)
            #zones.append(zone12)

            # go through each zone
            for i in zones:
                success = False
                success = self.parse_message(cmd, i, zone_number) or success

            if not success:
                _LOGGER.warning(f"Update for Zone #{zone_number} failed.")

        elif len(message) == 14:
            self.parse_message(cmd, message, zone_number)

        if zone_number is None:
            return self.zones

        return self.zones[zone_number]

    def parse_message(self, cmd, message, zone_number):
        if len(message) != 14:
            return False

        zone = message[2]

        # it seems that even though we send one zone we may not get what we want
        if zone in range(1, 7):
            self.zones[zone]['power'] = "on" if (message[4] & 1 << 0) >> 0 else "off"
            self.zones[zone]['source'] = message[8] + 1
            self.zones[zone]['vol'] = message[9] - 196 if message[9] else 0
            self.zones[zone]['mute'] = "on" if (
                message[4] & 1 << 1) >> 1 else "off"

            _LOGGER.debug(
                f"Command for Zone #{zone} retrieved (requested #{zone_number}) --> Cmd = {to_correct_string(cmd)} | Message = {to_correct_string(message)}")

            return True
        else:
            _LOGGER.warning(
                f"Sent command for Zone #{zone_number} but got #{zone} --> Cmd = {to_correct_string(cmd)} | Message = {to_correct_string(message)}")

        return False

    def set_source(self, zone, input):
        if zone not in range(1, 7):
            _LOGGER.warning("Invalid Zone")
            return

        if input not in range(1, 13):
            _LOGGER.warning("invalid input number")
            return

        _LOGGER.warning("Set Zone")
        if input not in range(13,19):
            cmd = bytearray([0x02,0x00,zone,0x04,input + 15])
            return self.send_command(cmd, zone)
        else:
            cmd = bytearray([0x02,0x00,zone,0x04,input + 86])
            return self.send_command(cmd, zone)

    def set_volume(self, zone, vol):
        if vol not in range(0, 101):
            _LOGGER.warning("Invalid Volume")
            return

        zone_info = self.query_zone(zone)

        volume_int = int(math.floor(MAX_HTD_VOLUME *vol / 100))

        # volume = 0
        if volume_int > 60:
            volume_int = 60
        elif volume_int < 0:
            volume_int = 0

        if volume_int == 60:
            volume = 0x00
        else:
            volume = 0xFF - (59 - volume_int)

        cmd = bytearray([0x02, 0x01, zone, 0x15, volume])
        cmdpwr = bytearray([0x02, 0x00, zone, 0x04, 0x57])
        self.send_command(cmdpwr, zone)
        self.send_command(cmd, zone)
        self.send_command(cmdpwr, zone)
        self.send_command(cmd, zone)
        return 

    def toggle_mute_off(self, zone):
        if zone not in range(0, 7):
            _LOGGER.warning("Invalid Zone")
            return
        cmd = bytearray([0x02, 0x00, zone, 0x04, 0x1F])     
        return self.send_command(cmd, zone)

    def toggle_mute_on(self, zone):
        if zone not in range(0, 7):
            _LOGGER.warning("Invalid Zone")
            return
        cmd = bytearray([0x02, 0x00, zone, 0x04, 0x1E])     
        return self.send_command(cmd, zone)


    def query_zone(self, zone):
        if zone not in range(1, 7):
            _LOGGER.warning("Invalid Zone")
            return
        cmd = bytearray([0x02, 0x00, zone, 0x05, 0x00])
        return self.send_command(cmd, zone)

    def query_all(self):
        cmd = bytearray([0x02, 0x00, 0x00, 0x05, 0x00])
        _LOGGER.warning("Query All")
        return self.send_command(cmd)

    def set_power(self, zone, pwr):
        if zone not in range(0, 7):
            _LOGGER.warning("Invalid Zone")
            return

        if pwr not in [0, 1]:
            _LOGGER.warning("invalid power command")
            return

        if zone != 0:
            if pwr == 1:
                cmd = bytearray([0x02, 0x00, zone, 0x04, 0x57])
            else:
                cmd = bytearray([0x02, 0x00, zone, 0x04, 0x58])            
            return self.send_command(cmd, zone)
        else:
            cmd = bytearray([0x02, 0x00, zone, 0x04, 0x55 if pwr else 0x56])
            return self.send_command(cmd, zone)



    def send_command(self, cmd, zone=None):
        cmd.append(self.checksum(cmd))
        mySocket = socket.socket()
        mySocket.settimeout(.5)
        try:
            mySocket.connect((self.ip_address, self.port))
            mySocket.send(cmd)
            data = mySocket.recv(1024)
            mySocket.close()

            return self.parse(cmd, data, zone)
        except socket.timeout:
            return self.unknown_response(cmd, zone)

    def unknown_response(self, cmd, zone):
        for zone in range(1, 7):
            self.zones[zone]['power'] = "unknown"
            self.zones[zone]['source'] = 0
            self.zones[zone]['vol'] = 0
            self.zones[zone]['mute'] = "unknown"

        return self.zones[zone]

    def checksum(self, message):
        cs = 0
        for b in message:
            cs += b
        csb = cs & 0xff
        return csb

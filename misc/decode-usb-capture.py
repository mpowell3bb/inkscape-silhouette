#!/bin/env python3
#
#
# Attributes in pcap.usb:
#   'src',
#   'addr',
#   'dst',
#   'usbpcap_header_len',
#   'irp_id',
#   'usbd_status',
#   'function',
#   'irp_info',
#   'irp_info_reserved',
#   'irp_info_direction',
#   'bus_id',
#   'device_address',
#   'endpoint_address',
#   'endpoint_address_direction',
#   'endpoint_address_number',
#   'transfer_type',
#   'data_len',
#   'control_stage']


import argparse
import binascii
import pyshark
import os
import sys

URB_FUNCTION_BULK_OR_INTERRUPT_TRANSFER = 9

def dump(data):
    col = 0
    for b in data.encode():
        sys.stdout.write('%02x' % b)
        col += 1
        if col == 16:
            sys.stdout.write('\n')
            col = 0
    if col > 0:
        sys.stdout.write('\n')

class GenericCmd:
    def __init__(self, cmd, sig, name, description):
        self.cmd = cmd
        self.sig = sig
        self.name = name
        self.description = description

    def match(self, msg):
        return msg.startswith(self.cmd)
        
    def split(self, msg):
        msg, _, remainder = msg.partition('\x03')
        return msg, remainder

    def report(self, msg):
        args = msg[len(self.cmd):]
        msgstr = binascii.b2a_qp(msg.encode('iso-8859-1')).decode()
        return '{:20s} {} {} {}'.format(msgstr, self.name, self.sig, args)

    def decode(self, msg):
        out, remainder = None, None
        if self.match(msg):
            # Split at '^C' and return before and after
            msg, remainder = self.split(msg)
            out = self.report(msg)
        return out, remainder


class CutterButton(GenericCmd):
    MSGLEN = 3
    def split(self, msg):
        # Split at '^C' and return before and after
        one = msg[0:3]
        remainder = msg[3:]
        return one, remainder

    def report(self, msg):
        arg = msg[len(self.cmd)]
        msgstr = binascii.b2a_qp(msg.encode('iso-8859-1')).decode()
        return '{:20s} {} {} {:x}'.format(msgstr, self.name, self.sig, ord(arg))

class CutCmd(GenericCmd):
    def report(self, msg):
        msgstr = '{} <data>'.format(msg[0:len(self.cmd)+1])
        arg = msg[len(self.cmd)]
        point_data = msg[len(self.cmd)+1:].encode('iso-8859-1')
        points = point_data.hex(' ')
        return '{:20s} {} {} {}\n      {}'.format(msgstr, self.name, self.sig, arg,
                                                  points)
    
    
COMMAND_TABLE = [
    CutterButton('\x1b\x00', 'd',    'Button', 'd is action, 0=None, 1=up, 2=down, 3=left, 4=right'),
    GenericCmd('\x1b\x04', '',     'Initialize Device',   None),
    GenericCmd('\x1b\x05', '',     'Query Status',        None),
    GenericCmd('\x1b\x0b', '',     'Query Firmware',      None),
    GenericCmd('\x1b\x0f', '',     'Query Tool Setup',    None),
    GenericCmd('\x1b\x11', '',     'Query Firmware',      None),
    GenericCmd('\x1b\x15', '',     'Query Tool Setup',    None),
    GenericCmd('\x1b\x1b', '',     'Escape',              None),
    GenericCmd('!',        'n',    'Speed',               None),
    CutCmd    ('BD',       '',     'BDn, unknown, data follows', None),
    CutCmd    ('BE',       'n',    'BEn, Tool down? data follows', None),
    GenericCmd('B',        'l',    'Line Scale',          None),
    GenericCmd('FA',       '',     'Calibration Query',   None),
    GenericCmd('FC',       'p,q[,n]', 'Cutter Offset',    None),
    GenericCmd('FE',       'l[,n]', 'Lift Control', 'l=1 lift, l=0 unlift, n is the pen'),
    GenericCmd('FF',       's,e,n', 'Sharpen Corners', 's=start, e=end (0 resets?), n is the pen'),
    GenericCmd('FG',       '',     'Query Firmware',      None),
    GenericCmd('FN',       'n',    'Set Orientation',     'n=0 portrait, n=1 landscape'),
    GenericCmd('FX',       'n',    'Set Downward Force',  'n from 1 to something in thirties depending on model'),
    GenericCmd('L',        'p',    'Line Type',           None),
    GenericCmd('M',        'x,y',  'Move Abs',            None),
    GenericCmd('O',        '',     'Move Rel',            None),
    GenericCmd('TB123,',   'h,w,y,x', 'Reg Mark Auto',       'h,w of region, y,x of origin, mm/20'),
    GenericCmd('TB23,',    'h,w',  'Reg Mark Manual',     'h, w of region'),
    GenericCmd('TB50,',    'n',    'Set Orientation',     None),
    GenericCmd('TB51,',    'l',    'Set Regmark Length',  'Length of one arm of the right angle marks'),
    GenericCmd('TB52,',    'n',    'Set Regmark Type',    'n=0 is Original,SD, n=2 is Cameo,Portrait'),
    GenericCmd('TB53,',    'n',    'Set Regmark Width',   None),
    GenericCmd('TB55,',    'n',    '?Do Registration?',   None),
    GenericCmd('TB71',     '',     'Calibration Query',   None),
    GenericCmd('TB99',     '',     'Use Regmarks',        None),
    GenericCmd('TF',       'd,n',  'Set Tool Depth',      'For Autoblade; d is depth, n is tool (generally must be 1)'),
    GenericCmd('TG',       'n',    'Set Cutting Mat',     None),
    GenericCmd('TI',       '',     'Query Title',         None),
    GenericCmd('Z',        'x,y',  'Write Upper Right',   'Apparently sets the coordinate of the upper right of the cut area'),
    GenericCmd('[',        '',     'Read Lower Left',     None),
    GenericCmd('\\',       'x,y',  'Write Lower Left',    'Apparently sets the coordinate of the lower left of the cut area'),
]


def default_decoder(msg):
    # Split at '^C' and return before and after
    msg, _, remainder = msg.partition('\x03')
    return msg, remainder


def parse_one_command(msg):
    # Lookup in protocol table
    # Set default
    matched = False
    for entry in COMMAND_TABLE:
        out, remainder = entry.decode(msg)
        if out is not None:
            matched = True
            break

    if not matched:
        msg, remainder = default_decoder(msg)
        out = 'Unknown command: ' + msg
    #print('out=', out)
    return out, remainder


def parse_commands(payload):
    #print('Parsing "%s"' % payload)
    out = []
    remainder = payload
    while True:
        one, remainder = parse_one_command(remainder)
        out.append(one)
        if remainder == '':
            break
    return out


def parse_response(data):
    #print('Parsing response "%s"' % data)
    out = []
    remainder = data
    while True:
        one, _, remainder = remainder.partition('\x03')
        report = '"{}"'.format(one)
        out.append(report)
        if remainder == '':
            break
    assert (len(out) < 2)
    return out[0]



def process_pcap(file_name, verbose=0):
    print('Opening {}...'.format(file_name))

    pcap = pyshark.FileCapture(file_name)
    index = 0
    # print(dir(pcap[0].usb))
    # print(pcap[0].layers)
    # print(pcap[0].usb.function)
    # print(pcap[0].usb.irp_info_direction)
    # print(pcap[0].usb.endpoint_address_direction)
    # print(dir(pcap[0].data))
    # print(pcap[15].data.usb_capdata)

    line = ''
    for p in pcap:
        index += 1
        f = int(p.usb.function)
        #usb.data_fragment
        if f != URB_FUNCTION_BULK_OR_INTERRUPT_TRANSFER:
            continue
        if p.usb.src == "host":
            addr = p.usb.dst
            direction = ' >'
        else:
            addr = p.usb.src
            direction = '< '
        if getattr(p, 'data', None) is None:
            #print('{:5d} {} {}'.format(index, direction, addr))
            pass
        else:
            data_bytes = p.data.usb_capdata.replace(':',' ')
            # fromhex() ignores whitespace
            cutter_msg = bytes.fromhex(data_bytes).decode('iso-8859-1')
            if verbose:
                #print('{:5d} {}  {} {:24s} {}'.format(index, addr, direction, data_bytes[0:23], cutter_msg[0:8]))
                print('{:5d} {}  {}'.format(index, addr, direction))
                #dump(p.data.usb_capdata)
                #print(p.data.usb_capdata)
                print('     ', cutter_msg)
                # print('---')
            if direction == ' >':
                #import pdb; pdb.set_trace()
                # Print any assembled output line
                if line:
                    print(line)
                line = '{:5d} '.format(index)
                decoded = parse_commands(cutter_msg)
                line += decoded[0]
                for d in decoded[1:]:
                    print(line)
                    line = '      {}'.format(d)
            else:
                # Start response in column 56
                pad = 56 - len(line)
                if pad > 0:
                    line += ' ' * pad
                decoded = parse_response(cutter_msg)
                line += decoded
                # Always newline after response
                print(line)
                line = ''
    if line:
        print(line)
        line = ''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PCAP reader')
    parser.add_argument('pcap', metavar='<pcap file name>',
                        help='pcap file to parse')
    args = parser.parse_args()

    file_name = args.pcap
    if not os.path.isfile(file_name):
        print('"{}" does not exist'.format(file_name), file=sys.stdout)
        sys.exit(-1)

    process_pcap(file_name, 0)
    sys.exit(0)

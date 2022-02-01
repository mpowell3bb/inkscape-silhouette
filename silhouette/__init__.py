# __init__ is needed for import statements across subdirectories.


from __future__ import print_function

import os
import re
import sys
import time
from .SCameo    import SilhouetteCameo
from .SPortrait import SilhouettePortrait
from .definitions import *

usb_reset_needed = False  # https://github.com/fablabnbg/inkscape-silhouette/issues/10

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/pyusb-1.0.2')      # have a pyusb fallback

sys_platform = sys.platform.lower()
if sys_platform.startswith('win'):
  import usb.core
elif sys_platform.startswith('darwin'):
  import usb1, usb.core
  usb1ctx = usb1.USBContext()
else:   # if sys_platform.startswith('linux'):
  try:
    import usb.core  # where???
  except Exception as e:
      try:
          import libusb1 as usb
      except Exception as e1:
        try:
          import usb
        except Exception as e2:
          print("The python usb module could not be found. Try", file=sys.stderr)
          print("\t sudo zypper in python-usb \t\t# if you run SUSE", file=sys.stderr)
          print("\t sudo apt-get install python-usb   \t\t# if you run Ubuntu", file=sys.stderr)
          print("\n\n\n", file=sys.stderr)
          raise e2

try:
    try:
      usb_vi = usb.version_info[0]
      usb_vi_str = str(usb.version_info)
    except AttributeError:
      usb_vi = 0
      if sys_platform.startswith('win'):
        usb_vi = 1
        pass # windows does not seem to detect the usb.version , gives attribute error. Other tests of pyusb work, pyusb is installed.
      usb_vi_str = 'unknown'


    if usb_vi < 1:
      print("Your python usb module appears to be "+usb_vi_str+" -- We need version 1.x", file=sys.stderr)
      print("For Debian 8 try:\n  echo > /etc/apt/sources.list.d/backports.list 'deb http://ftp.debian.org debian jessie-backports main\n  apt-get update\n  apt-get -t jessie-backports install python-usb", file=sys.stderr)
      print("\n\n\n", file=sys.stderr)
      print("For Ubuntu 14.04try:\n  pip install pyusb --upgrade", file=sys.stderr)
      print("\n\n\n", file=sys.stderr)
      sys.exit(0)
except NameError:
    pass # on OS X usb.version_info[0] will always fail as libusb1 is being used


# taken from
#  robocut/CutDialog.ui
#  robocut/CutDialog.cpp


DEVICE = [
 # CAUTION: keep in sync with sendto_silhouette.inx
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_PORTRAIT, 'name': 'Silhouette Portrait',
   'width_mm':  206, 'length_mm': 3000, 'regmark': True, 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_PORTRAIT2, 'name': 'Silhouette Portrait2',
   'width_mm':  203, 'length_mm': 3000, 'regmark': True, 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_PORTRAIT3, 'name': 'Silhouette Portrait3',
   'width_mm':  216, 'length_mm': 3000, 'regmark': True, 'driver': SilhouettePortrait },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_CAMEO, 'name': 'Silhouette Cameo',
   # margin_top_mm is just for safety when moving backwards with thin media
   # margin_left_mm is a physical limit, but is relative to width_mm!
   'width_mm':  304, 'length_mm': 3000, 'margin_left_mm':9.0, 'margin_top_mm':1.0, 'regmark': True, 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_CAMEO2, 'name': 'Silhouette Cameo2',
   # margin_top_mm is just for safety when moving backwards with thin media
   # margin_left_mm is a physical limit, but is relative to width_mm!
   'width_mm':  304, 'length_mm': 3000, 'margin_left_mm':9.0, 'margin_top_mm':1.0, 'regmark': True, 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_CAMEO3, 'name': 'Silhouette Cameo3',
   # margin_top_mm is just for safety when moving backwards with thin media
   # margin_left_mm is a physical limit, but is relative to width_mm!
   'width_mm':  304.8, 'length_mm': 3000, 'margin_left_mm':0.0, 'margin_top_mm':0.0, 'regmark': True, 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_CAMEO4, 'name': 'Silhouette Cameo4',
   # margin_top_mm is just for safety when moving backwards with thin media
   # margin_left_mm is a physical limit, but is relative to width_mm!
   'width_mm':  304.8, 'length_mm': 3000, 'margin_left_mm':0.0, 'margin_top_mm':0.0, 'regmark': True, 'driver': SilhouetteCameo },
#### Uncomment when confirmed:
# { 'vendor_id': VENDOR_ID_GRAPHTEC,
#   'product_id': VENDOR_ID_SILHOUETTE_CAMEO4PLUS,
#   'name': 'Silhouette Cameo4 Plus',
#   'width_mm': 372, # A bit of a guess, not certain what actual cuttable is
#   'length_mm': 3000,
#   'margin_left_mm': 0.0, 'margin_top_mm': 0.0, 'regmark': True, 'driver': SilhouetteCameo },
##############################
 { 'vendor_id': VENDOR_ID_GRAPHTEC,
   'product_id': PRODUCT_ID_SILHOUETTE_CAMEO4PRO,
   'name': 'Silhouette Cameo4 Pro',
   'width_mm': 600, # 24 in. is 609.6mm, but Silhouette Studio shows a thin cut
                    # margin that leaves 600mm of cuttable width. However,
                    # I am not certain if this should be margin_left_mm = 4.8
                    # and width_mm = 604.8; trying to leave things as close to
                    # the prior Cameo4 settings above.
   'length_mm': 3000,
   'margin_left_mm': 0.0, 'margin_top_mm': 0.0, 'regmark': True, 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_CC200_20, 'name': 'Craft Robo CC200-20',
   'width_mm':  200, 'length_mm': 1000, 'regmark': True, 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_CC300_20, 'name': 'Craft Robo CC300-20', 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_SD_1, 'name': 'Silhouette SD 1', 'driver': SilhouetteCameo },
 { 'vendor_id': VENDOR_ID_GRAPHTEC, 'product_id': PRODUCT_ID_SILHOUETTE_SD_2, 'name': 'Silhouette SD 2', 'driver': SilhouetteCameo },
]



def open_cutter(log=sys.stderr, cmdfile=None, inc_queries=False,
                dry_run=False, progress_cb=None, force_hardware=None):
  """ Queries device and returns an instance of the appropriate class """

  for h in DEVICE:
    try:
      if sys_platform.startswith('win'):
        print("device lookup under windows not tested. Help adding code!", file=log)
        dev = usb.core.find(idVendor=h['vendor_id'], idProduct=h['product_id'])

      elif sys_platform.startswith('darwin'):
        dev = usb1ctx.openByVendorIDAndProductID(h['vendor_id'], h['product_id'])

      else:   # linux
        dev = usb.core.find(idVendor=h['vendor_id'], idProduct=h['product_id'])
    except usb.core.NoBackendError:
      dev = None
    if dev:
      hardware = h
      break

  if dev is None:
    try:
      if sys_platform.startswith('win'):
        print("device fallback under windows not tested. Help adding code!", file=log)
        dev = usb.core.find(idVendor=VENDOR_ID_GRAPHTEC)
        hardware = { 'name': 'Unknown Graphtec device' }
        if dev:
          hardware['name'] += " 0x%04x" % dev.idProduct
          hardware['product_id'] = dev.idProduct
          hardware['vendor_id'] = dev.idVendor

      elif sys_platform.startswith('darwin'):
        print("device fallback under macosx not implemented. Help adding code!", file=log)

      else:   # linux
        dev = usb.core.find(idVendor=VENDOR_ID_GRAPHTEC)
        hardware = { 'name': 'Unknown Graphtec device ' }
        if dev:
          hardware['name'] += " 0x%04x" % dev.idProduct
          hardware['product_id'] = dev.idProduct
          hardware['vendor_id'] = dev.idVendor
    except usb.core.NoBackendError:
      dev = None

  if dev is None:
    if dry_run:
      print("No device detected; continuing dry run with dummy device",
            file=log)
      hardware = dict(name='Crashtest Dummy Device')
    else:
      msg = ''
      try:
          for dev in usb.core.find(find_all=True):
            msg += "(%04x,%04x) " % (dev.idVendor, dev.idProduct)
      except NameError:
          msg += "unable to list devices on OS X"
      raise ValueError('No Graphtec Silhouette devices found.\nCheck USB and Power.\nDevices: '+msg)

  try:
    dev_bus = dev.bus
  except:
    dev_bus = -1

  try:
    dev_addr = dev.address
  except:
    dev_addr = -1

  print("%s found on usb bus=%d addr=%d" % (hardware['name'], dev_bus, dev_addr), file=log)

  if dev is not None:
    if sys_platform.startswith('win'):
      print("device init under windows not implemented. Help adding code!", file=log)

    elif sys_platform.startswith('darwin'):
      dev.claimInterface(0)
      # usb_enpoint = 1
      # dev.bulkWrite(usb_endpoint, data)

    else:     # linux
      try:
        if dev.is_kernel_driver_active(0):
          print("is_kernel_driver_active(0) returned nonzero", file=log)
          if dev.detach_kernel_driver(0):
            print("detach_kernel_driver(0) returned nonzero", file=log)
      except usb.core.USBError as e:
        print("usb.core.USBError:", e, file=log)
        if e.errno == 13:
          msg = """
  If you are not running as root, this might be a udev issue.
  Try a file /etc/udev/rules.d/99-graphtec-silhouette.rules
  with the following example syntax:
  SUBSYSTEM=="usb", ATTR{idVendor}=="%04x", ATTR{idProduct}=="%04x", MODE="666"

  Then run 'sudo udevadm trigger' to load this file.

  Alternatively, you can add yourself to group 'lp' and logout/login.""" % (hardware['vendor_id'], hardware['product_id'])
          print(msg, file=log)
          print(msg, file=sys.stderr)
        sys.exit(0)

      if usb_reset_needed:
        for i in range(5):
          try:
            dev.reset()
            break
          except usb.core.USBError as e:
            print("reset failed: ", e, file=log)
            print("retrying reset in 5 sec", file=log)
            time.sleep(5)

      try:
        dev.set_configuration()
        dev.set_interface_altsetting()      # Probably not really necessary.
      except usb.core.USBError:
        pass

  if force_hardware:
    for h in DEVICE:
      if h["name"] == force_hardware:
        print("NOTE: Overriding device from", hardware.get('name','None'),
              "to", h['name'], file=log)
        hardware = h
        break

  print("dev name:", hardware['name'], file=log)
  driver = hardware['driver']
  return driver(dev, hardware, log, cmdfile, inc_queries, dry_run, progress_cb)

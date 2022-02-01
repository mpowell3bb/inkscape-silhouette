# (c) 2013,2014 jw@suse.de
# (c) 2016 juewei@fabmail.org
# (c) 2016 Alexander Wenger
# (c) 2017 Johann Gail
#
# Distribute under GPLv2 or ask.
#
# Driver for a Graphtec Silhouette Cameo plotter.
# modeled after https://github.com/nosliwneb/robocut.git
# https://github.com/pmonta/gerber2graphtec/blob/master/file2graphtec
#
# Native resolution of the plotter is 0.05mm -- All movements are integer multiples of this.
#
# 2015-06-04, juewei@fabmail.org using print_function. added wait_for_ready().
#             plot(bboxonly=None) is now the special case for not doing anything. False is normal plot.
# 2015-06-05  Renamed cut_bbox() to find_bbox(). It does not cut anything.
# 2015-06-06  refactored plot_cmds() from plot().
# 2016-05-16  no reset per default, this helps usbip.
# 2016-05-21  detect python-usb < 1.0 and give instructions.
# 2017-04-20  Adding Cameo3 USB IDs
# 2020-06-    Adding Cameo4 and refactor code
# 2021-06-03  Adding Cameo4 Pro
# 2021-06-05  Allow commands to be transcribed to file, for later (re-)sending

import sys
import time
from .definitions import *


def _bbox_extend(bb, x, y):
    # The coordinate system origin is in the top lefthand corner.
    # Downwards and rightwards we count positive. Just like SVG or HPGL.
    # Thus lly is a higher number than ury
    if not 'llx' in bb or x < bb['llx']: bb['llx'] = x
    if not 'urx' in bb or x > bb['urx']: bb['urx'] = x
    if not 'lly' in bb or y > bb['lly']: bb['lly'] = y
    if not 'ury' in bb or y < bb['ury']: bb['ury'] = y


#   1   mm =   20 SU
#   1   in =  508 SU
#   8.5 in = 4318 SU
#  11   in = 5588 SU

def _mm_2_SU(mm):
  """Convert mm to SU (SilhuetteUnit) using round

  Parameters
  ----------
      mm : int, float
          input millimetre

  Returns
  -------
      int
          output SU
  """
  return int(round(mm * 20.0))

def _inch_2_SU(inch):
  """Convert inch to SU (SilhuetteUnit) using round

  Parameters
  ----------
      inch : int, float
          input inch

  Returns
  -------
      int
          output SU
  """
  return int(round(inch * 508.0))

def to_bytes(b_or_s):
  """Ensure a value is bytes"""
  if isinstance(b_or_s, str): return b_or_s.encode()
  if isinstance(b_or_s, bytes): return b_or_s
  raise TypeError("Value must be a string or bytes.")

def delimit_commands(cmd_or_list):
  """
     Convert a command or list of commands into a properly
     delimited byte sequence.
  """
  lst = cmd_or_list if isinstance(cmd_or_list, list) else [cmd_or_list]
  return b''.join(to_bytes(c) + CMD_ETX for c in lst)



class Graphtec:
  """ Common driver code for Silhouettte series of cutters """

  def __init__(self, dev, hardware, log=sys.stderr, cmdfile=None, inc_queries=False,
               dry_run=False, progress_cb=None):
    """ This initializer simply finds the first known device.
        The default paper alignment is left hand side for devices with known width
        (currently Cameo and Portrait). Otherwise it is right hand side.
        Use setup() to specify your needs.

        If cmdfile is specified, it is taken as a file-like object in which to
        record a transcript of all commands sent to the cutter. If inc_queries is
        True, then that transcript further includes all of the queries sent to
        the cutter (but not the responses read back). (The latter parameter
        inc_queries has no effect when cmdfile is unspecified or falsy.)

        If dry_run is True, no commands will be sent to the usb device. The device
        is still searched for and queries to it are allowed, as the responses
        might affect inkscape_silhouette's behavior during the dry run. (Note that
        we might be dumping information from the run for later use that depends
        on what device is being driven.) Of course, when dry_run is True, it is
        allowed that there be no device currently attached.

        The progress_cb is called with the following parameters:
        int(strokes_done), int(strikes_total), str(status_flags)
        The status_flags contain 't' when there was a (non-fatal) write timeout
        on the device.
    """
    self.leftaligned = False            # True: only works for DEVICE with known hardware.width_mm
    self.log = log
    self.commands = cmdfile
    self.inc_queries = inc_queries
    self.dry_run = dry_run
    self.progress_cb = progress_cb
    self.margins_printed = None

    if self.dry_run:
      print("Dry run specified; no commands will be sent to cutter.",
            file=self.log)

    self.hardware = hardware
    self.dev = dev
    self.need_interface = False         # probably never needed, but harmful on some versions of usb.core
    self.regmark = False
    if self.dev is None or 'width_mm' in self.hardware:
      self.leftaligned = True
    self.enable_sw_clipping = True
    self.clip_fuzz = 0.05
    self.mock_response = None

  def __del__(self, *args):
    if self.commands:
      self.commands.close()

  # Class data providing mock responses when there is no device:
  mock_responses = {
    CMD_ESC+CMD_ENQ: RESP_READY+CMD_ETX,
    QUERY_FIRMWARE_VERSION+CMD_ETX: b'None '+CMD_ETX
  }

  def product_id(self):
    return self.hardware['product_id'] if 'product_id' in self.hardware else None

  def write(self, data, is_query=False, timeout=10000):
    """Send a command to the device. Long commands are sent in chunks of 4096 bytes.
       A nonblocking read() is attempted before write(), to find spurious diagnostics."""

    data = to_bytes(data)

    # Capture command to transcript if there is one:
    if self.commands and ((not is_query) or self.inc_queries):
        self.commands.write(data)

    # If there is no device, the only thing we might need to do is mock
    # a response:
    if self.dev is None:
      if data in self.mock_responses:
        self.mock_response = self.mock_responses[data]
      return None

    # If it is a dry run and not a query, we also do nothing:
    if self.dry_run and not is_query:
      return None

    # robocut/Plotter.cpp:73 says: Send in 4096 byte chunks. Not sure where I got this from, I'm not sure it is actually necessary.
    try:
      resp = self.read(timeout=10) # poll the inbound buffer
      if resp:
        print("response before write('%s'): '%s'" % (data, resp), file=self.log)
    except:
      pass
    endpoint = 0x01
    chunksz = 4096
    r = 0
    o = 0
    msg=''
    retry = 0
    while o < len(data):
      if o:
        if self.progress_cb:
          self.progress_cb(o,len(data),msg)
        elif self.log:
          self.log.write(" %d%% %s\r" % (100.*o/len(data),msg))
          self.log.flush()
      chunk = data[o:o+chunksz]
      try:
        if self.need_interface:
          try:
            r = self.dev.write(endpoint, chunk, interface=0, timeout=timeout)
          except AttributeError:
            r = self.dev.bulkWrite(endpoint, chunk, interface=0, timeout=timeout)
        else:
          try:
            r = self.dev.write(endpoint, chunk, timeout=timeout)
          except AttributeError:
            r = self.dev.bulkWrite(endpoint, chunk, timeout=timeout)
      except TypeError as te:
        # write() got an unexpected keyword argument 'interface'
        raise TypeError("Write Exception: %s, %s dev=%s" % (type(te), te, type(self.dev)))
      except AttributeError as ae:
        # write() got an unexpected keyword argument 'interface'
        raise TypeError("Write Exception: %s, %s dev=%s" % (type(ae), ae, type(self.dev)))

      except Exception as e:
        # raise USBError(_str_error[ret], ret, _libusb_errno[ret])
        # usb.core.USBError: [Errno 110] Operation timed
        #print("Write Exception: %s, %s errno=%s" % (type(e), e, e.errno), file=s.log)
        import errno
        try:
          if e.errno == errno.ETIMEDOUT:
            time.sleep(1)
            msg += 't'
            continue
        except Exception as ee:
          msg += "s.dev.write Error:  {}".format(ee)
      else:
        if len(msg):
          msg = ''
          self.log.write("\n")

      # print("write([%d:%d], len=%d) = %d" % (o,o+chunksz, len(chunk), r), file=s.log)
      if r == 0 and retry < 5:
        time.sleep(1)
        retry += 1
        msg += 'r'
      elif r <= 0:
        raise ValueError('write %d bytes failed: r=%d' % (len(chunk), r))
      else:
        retry = 0
      o += r

    if o != len(data):
      raise ValueError('write all %d bytes failed: o=%d' % (len(data), o))

  def safe_write(self, data):
    """
        Wrapper for write with special emphasis not overloading the cutter
        with long commands.
        Use this only for commands, not queries.
    """

    data = to_bytes(data)

    # Silhouette Studio uses packet size of maximal 3k, 1k is default
    safemaxchunksz = 1024
    so = 0
    while so < len(data):
      safechunksz = min(safemaxchunksz, len(data)-so)
      candidate = data[so:so+safechunksz]
      # strip string candidate of unfinished command at its end
      safechunk = candidate[0:(candidate.rfind(CMD_ETX) + 1)]
      self.write(data = safechunk, is_query = False)
      self.wait_for_ready(timeout=120, poll_interval=0.05)
      so += len(safechunk)

  def send_command(self, cmd, is_query = False, timeout=10000):
    """ Sends a command or a list of commands """
    self.write(delimit_commands(cmd), is_query=is_query, timeout=timeout)

  def safe_send_command(self, cmd):
    data = delimit_commands(cmd)
    if len(data) == 0: return
    self.safe_write(data)

  def send_escape(self, esc, is_query=False):
    """ Sends a Escape Command """
    self.write(CMD_ESC + esc, is_query=is_query) # Concatenation will typecheck

  def read(self, size=64, timeout=5000):
    """Low level read method, returns response as bytes"""
    endpoint = 0x82
    data = None
    if self.dev is None:
      data = self.mock_response
      self.mock_response = None
      if data is None: return None
    elif self.need_interface:
        try:
            data = self.dev.read(endpoint, size, timeout=timeout, interface=0)
        except AttributeError:
            data = self.dev.bulkRead(endpoint, size, timeout=timeout, interface=0)
    else:
        try:
            data = self.dev.read(endpoint, size, timeout=timeout)
        except AttributeError:
            data = self.dev.bulkRead(endpoint, size, timeout=timeout)
    if data is None:
      raise ValueError('read failed: none')
    if isinstance(data, (bytes, bytearray)):
        return data
    elif isinstance(data, str):
        return data.encode()
    else:
        try:
            return data.tobytes() # with py3
        except:
            return data.tostring().encode() # with py2/3 - dropped in py39

  def try_read(self, size=64, timeout=1000):
    ret=None
    try:
      ret = self.read(size=size,timeout=timeout)
      print("try_read got: '%s'" % ret)
    except:
      pass
    return ret

  def send_receive_command(self, cmd, tx_timeout=10000, rx_timeout=1000):
    """ Sends a query and returns its response as a string """
    self.send_command(cmd, is_query=True, timeout=tx_timeout)
    try:
      resp = self.read(timeout=rx_timeout)
      if len(resp) > 1:
        return resp[:-1].decode()
    except:
      pass
    return None

  def status(self):
    """Query the device status. This can return one of the four strings
       'ready', 'moving', 'unloaded', 'fail' or a raw (unknown) byte sequence."""

    # Status request.
    self.send_escape(CMD_ENQ, is_query=True)
    resp = b"None\x03"
    try:
      resp = self.read(timeout=5000).strip()
    except usb.core.USBError as e:
      print("usb.core.USBError:", e, file=self.log)
      pass
    if resp[-1] != CMD_ETX[0]:
      raise ValueError('status response not terminated with 0x03: %s' % (resp[-1]))
    return RESP_DECODING.get(bytes(resp[:-1]), bytes(resp[:-1]))

  def wait_for_ready(self, timeout=30, poll_interval=2.0, verbose=False):
    # get_version() is likely to timeout here...
    # if verbose: print("device version: '%s'" % s.get_version(), file=sys.stderr)
    state = self.status()
    if self.dry_run:
      # not actually sending commands, so don't really care about being ready
      return state
    npolls = int(timeout/poll_interval)
    for i in range(1, npolls):
      if (state == 'ready'): break
      if (state == 'None'):
        raise NotImplementedError("Waiting for ready but no device exists.")
      if verbose: print(" %d/%d: status=%s\r" % (i, npolls, state), end='', file=sys.stderr)
      if not verbose:
        if state == 'unloaded':
          print(" %d/%d: please load media ...\r" % (i, npolls, state), end='', file=sys.stderr)
        elif i > npolls/3:
          print(" %d/%d: status=%s\r" % (i, npolls, state), end='', file=sys.stderr)
      time.sleep(poll_interval)
      state = self.status()
    if verbose: print("",file=sys.stderr)
    return state

  def get_version(self):
    """Retrieve the firmware version string from the device."""
    return self.send_receive_command(QUERY_FIRMWARE_VERSION, rx_timeout = 10000)

  def set_boundary(self, top, left, bottom, right):
    """ Sets boundary box """
    self.send_command(["\\%d,%d" % (top, left), "Z%d,%d" % (bottom, right)])

  def find_bbox(self, cut):
    """Find the bounding box of the cut, returns (xmin,ymin,xmax,ymax)"""
    bb = {}
    for path in cut:
      for pt in path:
        _bbox_extend(bb,pt[0],pt[1])
    return bb

  def flip_cut(self, cut):
    """this returns a flipped copy of the cut about the y-axis,
       keeping min and max values as they are."""
    bb = self.find_bbox(cut)
    new_cut = []
    for path in cut:
      new_path = []
      for pt in path:
        new_path.append((pt[0], bb['lly']+bb['ury']-pt[1]))
      new_cut.append(new_path)
    return new_cut

  def mirror_cut(self, cut):
    """this returns a mirrored copy of the cut about the x-axis,
       keeping min and max values as they are."""
    bb = self.find_bbox(cut)
    new_cut = []
    for path in cut:
      new_path = []
      for pt in path:
        new_path.append((bb['llx']+bb['urx']-pt[0], pt[1]))
      new_cut.append(new_path)
    return new_cut

  def acceleration_cmd(self, acceleration):
    """ TJa """
    return "TJ%d" % acceleration

  def move_mm_cmd(self, mmy, mmx):
    """ My,x """
    return "M%d,%d" % (_mm_2_SU(mmy), _mm_2_SU(mmx))

  def draw_mm_cmd(self, mmy, mmx):
    """ Dy,x """
    return "D%d,%d" % (_mm_2_SU(mmy), _mm_2_SU(mmx))

  def upper_left_mm_cmd(self, mmy, mmx):
    r""" \y,x """
    return "\\%d,%d" % (_mm_2_SU(mmy), _mm_2_SU(mmx))

  def lower_right_mm_cmd(self, mmy, mmx):
    """ Zy,x """
    return "Z%d,%d" % (_mm_2_SU(mmy), _mm_2_SU(mmx))

  def automatic_regmark_test_mm_cmd(self, height, width, top, left):
    """ TB123,h,w,t,l """
    return "TB123,%d,%d,%d,%d" % (_mm_2_SU(height), _mm_2_SU(width), _mm_2_SU(top), _mm_2_SU(left))

  def manual_regmark_mm_cmd(self, height, width):
    """ TB23,h,w """
    return "TB23,%d,%d" % (_mm_2_SU(height), _mm_2_SU(width))


  def clip_point(self, x, y, bbox):
    """
        Clips coords x and y by the 'clip' element of bbox.
        Returns the clipped x, clipped y, and a flag which is true if
        no actual clipping took place.
    """
    inside = True
    if 'clip' not in bbox:
      return x, y, inside
    if 'count' not in bbox['clip']:
      bbox['clip']['count'] = 0
    if bbox['clip']['llx'] - x > self.clip_fuzz:
      x = bbox['clip']['llx']
      inside = False
    if x - bbox['clip']['urx'] > self.clip_fuzz:
      x = bbox['clip']['urx']
      inside = False
    if bbox['clip']['ury'] - y > self.clip_fuzz:
      y = bbox['clip']['ury']
      inside = False
    if y - bbox['clip']['lly'] > self.clip_fuzz:
      y = bbox['clip']['lly']
      inside = False
    if not inside:
      #print(f"Clipped point ({x},{y})", file=self.log)
      bbox['clip']['count'] += 1
    return x, y, inside


  def plot_cmds(self, plist, bbox, x_off, y_off):
    """
        bbox coordinates are in mm
        bbox *should* contain a proper { 'clip': {'llx': , 'lly': , 'urx': , 'ury': } }
        otherwise a hardcoded flip width is used to make the coordinate system left aligned.
        x_off, y_off are in mm, relative to the clip urx, ury.
    """

    # Change by Alexander Senger:
    # Well, there seems to be a clash of different coordinate systems here:
    # Cameo uses a system with the origin in the top-left corner, x-axis
    # running from top to bottom and y-axis from left to right.
    # Inkscape uses a system where the origin is also in the top-left corner
    # but x-axis is running from left to right and y-axis from top to
    # bottom.
    # The transform between these two systems used so far was to set Cameo in
    # landscape-mode ("FN0.TB50,1" in Cameo-speak) and flip the x-coordinates
    # around the mean x-value (rotate by 90 degrees, mirror and shift x).
    # My proposed change: just swap x and y in the data (mirror about main diagonal)
    # This is easier and avoids utilizing landscape-mode.
    # Why should we bother? Pure technical reason: At the beginning of each cutting run,
    # Cameo makes a small "tick" in the margin of the media to align the blade.
    # This gives a small offset which is automatically compensated for in
    # portrait mode but not (correctly) in landscape mode.
    # As a result we get varying offsets which can be really annoying if doing precision
    # work.

    # Change by Sven Fabricius:
    # Update the code to use millimeters in all places to prevent mixing with device units.
    # The conversion to SU (SilhouetteUnits) will be done in command create function.
    # Removing all kinds of multiplying, dividing and rounding.

    if bbox is None: bbox = {}
    bbox['count'] = 0
    if not 'only' in bbox: bbox['only'] = False
    if 'clip' in bbox and 'urx' in bbox['clip']:
      flipwidth=bbox['clip']['urx']
    if 'clip' in bbox and 'llx' in bbox['clip']:
      x_off += bbox['clip']['llx']
    if 'clip' in bbox and 'ury' in bbox['clip']:
      y_off += bbox['clip']['ury']

    last_inside = True
    plotcmds=[]
    for path in plist:
      if len(path) < 2: continue
      x = path[0][0] + x_off
      y = path[0][1] + y_off
      _bbox_extend(bbox, x, y)
      bbox['count'] += 1

      x, y, last_inside = self.clip_point(x, y, bbox)

      if bbox['only'] is False:
        plotcmds.append(self.move_mm_cmd(y, x))

      for j in range(1,len(path)):
        x = path[j][0] + x_off
        y = path[j][1] + y_off
        _bbox_extend(bbox, x, y)
        bbox['count'] += 1

        x, y, inside = self.clip_point(x, y, bbox)

        if bbox['only'] is False:
          if not self.enable_sw_clipping or (inside and last_inside):
            plotcmds.append(self.draw_mm_cmd(y, x))
          else:
            # // if outside the range just move
            plotcmds.append(self.move_mm_cmd(y, x))
        last_inside = inside
    return plotcmds


  def plot(self, mediawidth=210.0, mediaheight=297.0, margintop=None,
           marginleft=None, pathlist=None, offset=None, bboxonly=False,
           end_paper_offset=0, endposition='below', regmark=False, regsearch=False,
           regwidth=180, reglength=230, regoriginx=15.0, regoriginy=20.0):
    """plot sends the pathlist to the device (real or dummy) and computes the
       bounding box of the pathlist, which is returned.

       Each path in pathlist is rendered as a connected stroke (aka "pen_down"
       mode). Movements between paths are not rendered (aka "pen_up" mode).

       A path is a sequence of 2-tupel, all measured in mm.
           The tool is lowered at the beginning and raised at the end of each path.
       offset = (X_MM, Y_MM) can be specified, to easily move the design to the
           desired position.  The top and left media margin is always added to the
           origin. Default: margin only.
       bboxonly:  True for drawing the bounding instead of the actual cut design;
                  None for not moving at all (just return the bounding box).
                  Default: False for normal cutting or drawing.
       end_paper_offset: [mm] adds to the final move, if endposition is 'below'.
                If the end_paper_offset is negative, the end position is within the drawing
                (reverse movements are clipped at the home position)
                It reverse over the last home position.
       endposition: Default 'below': The media is moved to a position below the actual cut (so another
                can be started without additional steps, also good for using the cross-cutter).
                'start': The media is returned to the position where the cut started.
       Example: The letter Y (20mm tall, 9mm wide) can be generated with
                pathlist=[[(0,0),(4.5,10),(4.5,20)],[(9,0),(4.5,10)]]
    """
    bbox = { }
    if margintop  is None and 'margin_top_mm'  in self.hardware: margintop  = self.hardware['margin_top_mm']
    if marginleft is None and 'margin_left_mm' in self.hardware: marginleft = self.hardware['margin_left_mm']
    if margintop  is None: margintop = 0
    if marginleft is None: marginleft = 0

    # if 'margin_top_mm' in s.hardware:
    #   print("hardware margin_top_mm = %s" % (s.hardware['margin_top_mm']), file=s.log)
    # if 'margin_left_mm' in s.hardware:
    #   print("hardware margin_left_mm = %s" % (s.hardware['margin_left_mm']), file=s.log)

    if self.leftaligned and 'width_mm' in self.hardware:
      # marginleft += s.hardware['width_mm'] - mediawidth  ## FIXME: does not work.
      mediawidth = self.hardware['width_mm']

    print("mediabox: (%g,%g)-(%g,%g)" % (marginleft,margintop, mediawidth,mediaheight), file=self.log)

    width  = mediawidth
    height = mediaheight
    top    = margintop
    left   = marginleft
    if width < left: width  = left
    if height < top: height = top

    x_off = left
    y_off = top
    if offset is None:
      offset = (0,0)
    else:
      if type(offset) != type([]) and type(offset) != type(()):
        offset = (offset, 0)

    if regmark:
      # after registration logically (0,0) is at regmark position
      # compensate the offset of the regmark to the svg document origin.
      #bb = s.find_bbox(pathlist)
      #print("bb llx=%g ury=%g" % (bb['llx'], bb['ury']), file=s.log)
      #regoriginx = bb['llx']
      #regoriginy = bb['ury']
      print("bb regoriginx=%g regoriginy=%g" % (regoriginx, regoriginy), file=self.log)
      offset = (offset[0] - regoriginx, offset[1] - regoriginy)

      # Limit the cutting area inside cutting marks
      height = reglength
      width = regwidth

      self.do_regmark(regsearch, regoriginx, regoriginy, regwidth, reglength)


    # // I think this is the feed command. Sometimes it is 5588 - maybe a maximum?
    #s.write(b"FO%d\x03" % (height-top))


    #FMx, x = 0/1: 1 leads to additional horizontal offset of 5 mm, why? Has other profound
    # impact (will not cut in certain configuration if x=0). Seems dangerous. Not used
    # in communication of Sil Studio with Cameo2.
    #FEx,0 , x = 0 cutting of distinct paths in one go, x = 1 head is lifted at sharp angles
    #\xmin, ymin Zxmax,ymax, designate cutting area

    # needed only for the trackenhancing feature, defines the usable length, rollers three times forward and back.
    # needs a pressure of 19 or more, else nothing will happen
    #p = b"FU%d\x03" % (height)
    #p = b"FU%d,%d\x03" % (height,width) # optional
    #s.write(p)

    self.pre_plot(width, height)

    bbox['clip'] = {'urx':width, 'ury':top, 'llx':left, 'lly':height}
    bbox['only'] = bboxonly
    cmd_list = self.plot_cmds(pathlist,bbox,offset[0],offset[1])
    print("Final bounding box and point counts: " + str(bbox), file=self.log)

    if bboxonly == True:
      # move the bounding box
      cmd_list = [
        self.move_mm_cmd(bbox['ury'], bbox['llx']),
        self.draw_mm_cmd(bbox['ury'], bbox['urx']),
        self.draw_mm_cmd(bbox['lly'], bbox['urx']),
        self.draw_mm_cmd(bbox['lly'], bbox['llx']),
        self.draw_mm_cmd(bbox['ury'], bbox['llx'])]

    # potentially long command string needs extra care
    self.safe_send_command(cmd_list)

    # Silhouette Cameo2 does not start new job if not properly parked on left side
    # Attention: This needs the media to not extend beyond the left stop
    if not 'llx' in bbox: bbox['llx'] = 0  # survive empty pathlist
    if not 'lly' in bbox: bbox['lly'] = 0
    if not 'urx' in bbox: bbox['urx'] = 0
    if not 'ury' in bbox: bbox['ury'] = 0
    if endposition == 'start':
      new_home = self.home_to_start()
    else: #includes 'below'
      new_home = [
        self.move_mm_cmd(bbox['lly'] + end_paper_offset, 0),
        "SO0"]
    #new_home += b"FN0\x03TB50,0\x03"
    self.send_command(new_home)

    return {
        'bbox': bbox,
        'unit' : 1,
        'trailer': new_home
      }


  def move_origin(self, feed_mm):
    self.wait_for_ready()
    self.send_command([
      self.move_mm_cmd(feed_mm, 0),
      "SO0",
      "FN0"])
    self.wait_for_ready()

  def load_dumpfile(self,file):
    """ s is unused
    """
    data1234=None
    for line in open(file,'r').readlines():
      if re.match(r'\s*\[', line):
        exec('data1234='+line)
        break
      elif re.match(r'\s*<\s*svg', line):
        print(line)
        print("Error: xml/svg file. Please load into inkscape. Use extensions -> export -> sendto silhouette, [x] dump to file")
        return None
      else:
        print(line,end='')
    return data1234


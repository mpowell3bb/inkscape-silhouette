import time
from .Graphtec import Graphtec, _mm_2_SU
from .definitions import *


class SilhouettePortraitTool:
  def __init__(self):
    pass

  def select(self):
    """ select tool command """
    return None

  def pressure(self, pressure):
    """ set pressure command """
    return "FX%d" % (pressure)

  def speed(self, speed):
    """ set speed command """
    return "!%d" % (speed)

  def depth(self, depth):
    """ set depth command """
    return "TF%d,1" % (depth)

  def lift(self, lift):
    """ set lift command """
    if lift:
      return "FE1,0"
    else:
      return "FE0,0"

  def sharpen_corners(self, start, end):
    return [
      "FF%d,0,0" % (start),
      "FF%d,%d,0" % (start, end)]



class SilhouettePortrait(Graphtec):
  """ Driver class for Silhouettte Portrait 3 cutter """

  def set_cutting_mat(self, cuttingmat):
    """Setting Cutting mat for Portrait 3

    Parameters
    ----------
        cuttingmat : any key in SILHOUETTE_MATS or None
            type of the cutting mat
    """
    mat_command = 'TG'

    matparms = SILHOUETTE_MATS.get(cuttingmat, ('0', False, False))
    self.send_command(mat_command + matparms[0])


  def get_tool_setup(self):
    """ gets the type of the tool installed"""
    # tool setup request.
    self.send_escape(CMD_NAK, is_query=True)
    try:
      resp = self.read(timeout=1000)
      if len(resp) > 1:
        return resp[:-1].decode()
    except:
      pass
    return 'none'


  def initialize(self):
    """Send the init command. Called by setup()."""
    # Initialize plotter.
    try:
      self.send_escape(CMD_EOT)
    except Exception as e:
      raise ValueError("Write Exception: %s, %s errno=%s\n\nFailed to write the first 3 bytes. Permissions? inf-wizard?" % (type(e), e, e.errno))

    # Initial palaver
    print("Device Version: '%s'" % self.get_version(), file=self.log)

    resp = self.send_receive_command("TB71")
    if resp:
      # response '    0,    0' on portrait
      print("TB71: '%s'" % resp, file=self.log)

    resp = self.send_receive_command("FA")
    if resp:
      # response '    0,    0' on portrait
      print("FA: '%s'" % resp, file=self.log)

    resp = self.send_receive_command("TI")
    if resp:
      # response ''
      print("TI: '%s'" % resp, file=self.log)

    # Additional commands seen in init by Silhouette Studio
    # 0x1B,0x11
    # Response "Portrait 3 V1.04    ",0x03
    self.send_escape(b'\x11', is_query=True)
    resp = self.read(timeout=1000)
    if resp:
      # response 'Portrait 3 V1.04    '
      print(": '%s'" % resp, file=self.log)


  def setup(self, media=132, speed=None, pressure=None,
            toolholder=None, pen=None, cuttingmat=None, sharpencorners=False,
            sharpencorners_start=0.1, sharpencorners_end=0.1, autoblade=None,
            depth=None, sw_clipping=True, clip_fuzz=0.05, trackenhancing=False,
            bladediameter=0.9, landscape=False, leftaligned=None,
            mediawidth=210.0, mediaheight=297.0):
    """Setup the Silhouette Device

    Parameters
    ----------
        media : int, optional
            range is [100..300], "Print Paper Light Weight". Defaults to 132.
        speed : int, optional
            range is [1..10] for Cameo3 and older, 
            range is [1..30] for Cameo4. Defaults to None, from paper (132 -> 10).
        pressure : int, optional
            range is [1..33], Notice: Cameo runs trackenhancing if you select a pressure of 19 or more. Defaults to None, from paper (132 -> 5).
        toolholder : int, optional, not used on Portrait
            range is [1..2]. Defaults to 1.
        pen : bool, optional
            media dependent. Defaults to None.
            True means force tool to be pen, False means tool to be cut,
            None means read from cutter.
        cuttingmat : Any key in CAMEO_MATS, optional
            setting the cutting mat. Defaults to None.
        sharpencorners : bool, optional
            Defaults to False.
        sharpencorners_start : float, optional
            Defaults to 0.1.
        sharpencorners_end : float, optional
            Defaults to 0.1.
        autoblade : bool, optional
            Defaults to None.
        depth : int, optional
            range is [0..10] Defaults to None.
        sw_clipping : bool, optional
            Defaults to True.
        clip_fuzz : float, optional
            Defaults to 1/20 mm, the device resolution
        trackenhancing : bool, optional
            Defaults to False.
        bladediameter : float, optional
            Defaults to 0.9.
        landscape : bool, optional
            Defaults to False.
        leftaligned : bool, optional
            Loaded media is aligned left(=True) or right(=False). Defaults to device dependant.
        mediawidth : float, optional
            Defaults to 210.0.
        mediaheight : float, optional
            Defaults to 297.0.
    """

    print("---\nPortrait class", "dry_run:", self.dry_run,
          file=self.log)

    if leftaligned is not None:
      self.leftaligned = leftaligned

    tool = SilhouettePortraitTool()

    self.initialize()

    ## Query tool setup
    resp = self.get_tool_setup()
    print("tool resp: %s" % resp, file=self.log)
    tool_id = resp.split(',')[0].strip()
    print("tool: %s" % tool_id, file=self.log)

    if tool_id == SILHOUETTE_CAMEO4_TOOL_AUTOBLADE:
      autoblade = True
      bladediameter = 0.9
    elif tool_id == SILHOUETTE_CAMEO4_TOOL_PEN:
      pen = True

   
    self.set_cutting_mat(cuttingmat)

    #FNx, x = 0 seem to be some kind of reset, x = 1: plotter head moves to other
    # side of media (boundary check?), but next cut run will stall
    #TB50,x: x = 1 landscape mode, x = 0 portrait mode
    if landscape:
      self.send_command(["FN0", "TB50,1"])
    else:
      self.send_command(["FN0", "TB50,0"])

    # Set depth for autoblade
    if autoblade and depth is not None:
      if depth < 0: depth = 0
      if depth > 10: depth = 10
      print("manual depth setting: %d" % depth, file=self.log)
    if media is not None:
      if media < 100 or media > 300: media = 300
      for i in MEDIA:
        if i[0] == media:
          print("Media=%d, cap='%s', name='%s'" % (media, i[4], i[5]), file=self.log)
          if pressure is None: pressure = i[1]
          if speed is None:    speed = i[2]
          if depth is None:    depth = i[3]
          break

    if speed is not None:
      if speed < 1: speed = 1
      if speed > 10: speed = 10
      self.send_command(tool.speed(speed))
      print("speed: %d" % speed, file=self.log)

    if pressure is not None:
      if pressure <  1: pressure = 1
      if pressure > 33: pressure = 33
      self.send_command(tool.pressure(pressure))
      print("pressure: %d" % pressure, file=self.log)

    if depth is not None:
      self.send_command(tool.depth(depth))

    self.send_command("FC0")

    if self.leftaligned:
      print("Loaded media is expected left-aligned.", file=self.log)
    else:
      print("Loaded media is expected right-aligned.", file=self.log)

    # Depend on sharpencorners ?
    self.send_command(tool.lift(0))
    self.send_command(tool.sharpen_corners(1, 1))

    self.send_command("FC%d" % (_mm_2_SU(bladediameter)))

    self.enable_sw_clipping = sw_clipping
    self.clip_fuzz = clip_fuzz

    # # if enabled, rollers three times forward and back.
    # # needs a pressure of 19 or more, else nothing will happen
    # if trackenhancing is not None:
    #   if trackenhancing:
    #     self.send_command("FY0")
    #   else:
    #     # or pass?
    #     self.send_command("FY1")


  def do_regmark(self, regsearch, regoriginx, regoriginy, regwidth, reglength):
    self.send_command("TB50,0")
    self.send_command("TB99")
    self.send_command("TB52,2")     #type of regmarks: 0='Original,SD', 2='Cameo,Portrait'
    self.send_command("TB51,400")   # length of regmarks
    self.send_command("TB53,10")    # width of regmarks
    self.send_command("TB55,1")

    if regsearch:
      # automatic regmark test
      # On Portrait3, y, x are always 118, which is the size of the regmark square
      self.send_command(self.automatic_regmark_test_mm_cmd(reglength, regwidth, 5.9, 5.9))
    else:
      # The procedure is to use manual controls to position the tool over the square, then
      # send command .TB23'.
      # Ideally we would pop-up a window with 4 direction buttons
      #self.send_command(self.move_mm_cmd(self, regoriginy, regoriginx))
      self.send_command(self.manual_regmark_mm_cmd(reglength, regwidth))

    ## SS sends another TB99
    self.send_command("TB99")

    while True:
      state = self.status()
      if state != 'moving':
        break
      time.sleep(1)
    if state == 'fail':
      raise ValueError("Couldn't find registration marks. %s" % str(resp))
    self.wait_for_ready(timeout=10, poll_interval=0.5)


  def pre_plot(self, width, height):
    self.send_command([
      self.upper_left_mm_cmd(0, 0),
      self.lower_right_mm_cmd(height, width)])

  def home_to_start(self):
    """ Return commands to home the head back to the start """
    return [
      "TB0",
      "L0",
      self.upper_left_mm_cmd(0, 0),
      self.move_mm_cmd(0, 0),
      "FN0",
      "TB50,0"]
    

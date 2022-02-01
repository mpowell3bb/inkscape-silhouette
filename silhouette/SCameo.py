from .Graphtec import Graphtec, _mm_2_SU
from .definitions import *


class SilhouetteCameoTool:
  def __init__(self, toolholder=1):
    if toolholder is None:
      toolholder = 1
    self.toolholder = toolholder

  def select(self):
    """ select tool command """
    return "J%d" % self.toolholder

  def pressure(self, pressure):
    """ set pressure command """
    return "FX%d,%d" % (pressure, self.toolholder)

  def speed(self, speed):
    """ set speed command """
    return "!%d,%d" % (speed, self.toolholder)

  def depth(self, depth):
    """ set depth command """
    return "TF%d,%d" % (depth, self.toolholder)

  def cutter_offset(self, xmm, ymm):
    """ set cutter offset command using mm """
    return "FC%d,%d,%d" % (_mm_2_SU(xmm), _mm_2_SU(ymm), self.toolholder)

  def lift(self, lift):
    """ set lift command """
    if lift:
      return "FE1,%d" % self.toolholder
    else:
      return "FE0,%d" % self.toolholder

  def sharpen_corners(self, start, end):
    return [
      "FF%d,0,%d" % (start, self.toolholder),
      "FF%d,%d,%d" % (start, end, self.toolholder)]


class SilhouetteCameo(Graphtec):
  """ Driver class for Silhouettte Cameo series of cutters """

  def set_cutting_mat(self, cuttingmat, mediawidth, mediaheight):
    """Setting Cutting mat only for Cameo 3, 4 and Portrait 3

    Parameters
    ----------
        cuttingmat : any key in SILHOUETTE_MATS or None
            type of the cutting mat
        mediawidth : float
            width of the media
        mediaheight : float
            height of the media
    """
    if self.product_id() not in PRODUCT_LINE_CAMEO3_ON:
      return
    mat_command = 'TG'

    matparms = SILHOUETTE_MATS.get(cuttingmat, ('0', False, False))
    self.send_command(mat_command + matparms[0])

    #FNx, x = 0 seem to be some kind of reset, x = 1: plotter head moves to other
    # side of media (boundary check?), but next cut run will stall
    #TB50,x: x = 1 landscape mode, x = 0 portrait mode
    self.send_command(["FN0", "TB50,0"])

    if matparms[1]:
      # Note this does _not_ reproduce the \left,bot and Zright,top
      # commands emitted by Silhouette Studio (see ../Commands.md), although
      # it's close. Is that OK or are we creating potential (minor) problems?
      self.set_boundary(
        0, 0, _inch_2_SU(matparms[1]), _inch_2_SU(matparms[2]))
    else:
      bottom = _mm_2_SU(self.hardware['length_mm'] if 'length_mm' in self.hardware else mediaheight)
      right = _mm_2_SU(self.hardware['width_mm'] if 'width_mm' in self.hardware else mediawidth)
      self.set_boundary(0, 0, bottom, right)


  def get_tool_setup(self):
    """ gets the type of the tools installed in Cameo 4, Portrait 3 """

    if self.product_id() not in PRODUCT_LINE_CAMEO4:
      return 'none'

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
    # taken from robocut/Plotter.cpp:331 ff
    # Initialize plotter.
    try:
      self.send_escape(CMD_EOT)
    except Exception as e:
      raise ValueError("Write Exception: %s, %s errno=%s\n\nFailed to write the first 3 bytes. Permissions? inf-wizard?" % (type(e), e, e.errno))

    # Initial palaver
    print("Device Version: '%s'" % self.get_version(), file=self.log)

    # Additional commands seen in init by Silhouette Studio
    """
    # Get Upper Left Coords: 2 six digit numbers.
    resp = self.send_receive_command("[")
    if resp:
      # response '0,0'
      print("[: '%s'" % resp, file=self.log)

    # Get Lower Right Coordinates: 2 six digit numbers
    resp = self.send_receive_command("U")
    if resp:
      # response '20320,4120' max. usable print range?
      # response ' 20320,   3840' on Portrait
      print("U: '%s'" % resp, file=self.log)

    # Unknown: 1 five digit number. Maybe last speed set?
    resp = self.send_receive_command("FQ0")
    if resp:
      # response '10'
      # response '    5' on portrait
      print("FQ0: '%s'" % resp, file=self.log)

    # Unknown: 1 five digit number. Maybe last blade offset or last pressure?
    resp = self.send_receive_command("FQ2")
    if resp:
      # response '18'
      # response '   17' on portrait
      print("FQ2: '%s'" % resp, file=self.log)
    """

    if self.product_id() in PRODUCT_LINE_CAMEO3_ON:

      # Unknown: 2 five digit numbers. Probably machine stored calibration offset of the regmark sensor optics
      resp = self.send_receive_command("TB71")
      if resp:
        # response '    0,    0' on portrait
        print("TB71: '%s'" % resp, file=self.log)
      # Unknown: 2 five digit numbers. Probably machine stored calibration factors of carriage and roller (carriage, roller / unit 1/100% i.e. 0.0001)
      resp = self.send_receive_command("FA")
      if resp:
        # response '    0,    0' on portrait
        print("FA: '%s'" % resp, file=self.log)

    # Silhouette Studio does not appear to issue this command when using a cameo 4
    if self.product_id() == PRODUCT_ID_SILHOUETTE_CAMEO3:
      resp = self.send_receive_command("TC")
      if resp:
        # response '0,0'
        print("TC: '%s'" % resp, file=self.log)


  def setup(self, media=132, speed=None, pressure=None,
            toolholder=None, pen=None, cuttingmat=None, sharpencorners=False,
            sharpencorners_start=0.1, sharpencorners_end=0.1, autoblade=False,
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
        toolholder : int, optional
            range is [1..2]. Defaults to 1.
        pen : bool, optional
            media dependent. Defaults to None.
        cuttingmat : Any key in CAMEO_MATS, optional
            setting the cutting mat. Defaults to None.
        sharpencorners : bool, optional
            Defaults to False.
        sharpencorners_start : float, optional
            Defaults to 0.1.
        sharpencorners_end : float, optional
            Defaults to 0.1.
        autoblade : bool, optional
            Defaults to False.
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


    if leftaligned is not None:
      self.leftaligned = leftaligned

    self.initialize()

    self.set_cutting_mat(cuttingmat, mediawidth, mediaheight)

    if media is not None:
      if media < 100 or media > 300: media = 300

      # Silhouette Studio does not appear to issue this command
      if self.product_id() not in PRODUCT_LINE_CAMEO3_ON:
        self.send_command("FW%d" % media)

      if pen is None:
        if media == 113:
          pen = True
        else:
          pen = False
      for i in MEDIA:
        if i[0] == media:
          print("Media=%d, cap='%s', name='%s'" % (media, i[4], i[5]), file=self.log)
          if pressure is None: pressure = i[1]
          if speed is None:    speed = i[2]
          if depth is None:    depth = i[3]
          break

    tool = SilhouetteCameoTool(toolholder)

    if toolholder is None:
      toolholder = 1

    if self.product_id() in PRODUCT_LINE_CAMEO3_ON:
      toolsel = tool.select()
      if toolsel is not None:
        self.send_command(toolsel)

    print("toolholder: %d" % toolholder, file=self.log)

    # cameo 4 sets some parameters two times (force, acceleration, Cutter offset)
    if self.product_id() in PRODUCT_LINE_CAMEO4:
      if pressure is not None:
        if pressure <  1: pressure = 1
        if pressure > 33: pressure = 33
        self.send_command(tool.pressure(pressure))
        print("pressure: %d" % pressure, file=self.log)

        # on first connection acceleration is always set to 0
        self.send_command(self.acceleration_cmd(0))

      if speed is not None:
        if speed < 1: speed = 1
        if speed > 30: speed = 30
        self.send_command(tool.speed(speed))
        print("speed: %d" % speed, file=self.log)

      # set cutter offset a first time (seems to always be 0mm x 0.05mm)
      self.send_command(tool.cutter_offset(0, 0.05))

      # lift tool between paths
      self.send_command(tool.lift(sharpencorners))

      if pen:
        self.send_command(tool.sharpen_corners(0, 0))
      else:
        # start and end for sharpen corners is transmitted in tenth of a millimeter NOT in SUs
        sharpencorners_start = int((sharpencorners_start + 0.05) * 10.0)
        sharpencorners_end = int((sharpencorners_end + 0.05) * 10.0)
        self.send_command(tool.sharpen_corners(sharpencorners_start, sharpencorners_end))

      # set pressure a second time (don't know why, just reproducing)
      if pressure is not None:
        if pressure <  1: pressure = 1
        if pressure > 33: pressure = 33
        self.send_command(tool.pressure(pressure))
        print("pressure: %d" % pressure, file=self.log)
        self.send_command(self.acceleration_cmd(3))

      # set cutter offset a second time (this time with blade specific parameters)
      if pen:
        self.send_command(tool.cutter_offset(0, 0.05))
      else:
        self.send_command(tool.cutter_offset(bladediameter, 0.05))
    else:
      if speed is not None:
        if speed < 1: speed = 1
        if speed > 10: speed = 10
        if self.product_id() == PRODUCT_ID_SILHOUETTE_CAMEO3:
          self.send_command(tool.speed(speed))
        else:
          self.send_command("!%d" % speed)
        print("speed: %d" % speed, file=self.log)

      if pressure is not None:
        if pressure <  1: pressure = 1
        if pressure > 33: pressure = 33
        if self.product_id() == PRODUCT_ID_SILHOUETTE_CAMEO3:
          self.send_command(tool.pressure(pressure))
        else:
          self.send_command("FX%d" % pressure)
          # s.write(b"FX%d,0\x03" % pressure);       # oops, graphtecprint does it like this
        print("pressure: %d" % pressure, file=self.log)

      if self.product_id() == PRODUCT_ID_SILHOUETTE_CAMEO3:
        if pen:
          self.send_command(tool.cutter_offset(0, 0.05))

      if self.leftaligned:
        print("Loaded media is expected left-aligned.", file=self.log)
      else:
        print("Loaded media is expected right-aligned.", file=self.log)

      # Lift plotter head at sharp corners
      if self.product_id() == PRODUCT_ID_SILHOUETTE_CAMEO3:
        self.send_command(tool.lift(sharpencorners))

        if pen:
          self.send_command(tool.sharpen_corners(0, 0))
        else:
          # TODO: shouldn't be this also SU? why * 10 ?
          sharpencorners_start = int((sharpencorners_start + 0.05) * 10.0)
          sharpencorners_end = int((sharpencorners_end + 0.05) * 10.0)
          self.send_command(tool.sharpen_corners(sharpencorners_start, sharpencorners_end))

      # robocut/Plotter.cpp:393 says:
      # It is 0 for the pen, 18 for cutting. Default diameter of a blade is 0.9mm
      # C possible stands for curvature. Not that any of the other letters make sense...
      # C possible stands for circle.
      # This value is the circle diameter which is executed on direction changes on corners to adjust the blade.
      # Seems to be limited to 46 or 47. Values above does keep the last setting on the device.
      if self.product_id() == PRODUCT_ID_SILHOUETTE_CAMEO3:
        if not pen:
          self.send_command([
            tool.cutter_offset(0, 0.05),
            tool.cutter_offset(bladediameter, 0.05)])
      else:
        if pen:
          self.send_command("FC0")
        else:
          self.send_command("FC%d" % _mm_2_SU(bladediameter))

    if self.product_id() in PRODUCT_LINE_CAMEO3_ON:
      if autoblade and depth is not None:
        if toolholder == 1:
          if depth < 0: depth = 0
          if depth > 10: depth = 10
          self.send_command(tool.depth(depth))
          print("depth: %d" % depth, file=self.log)

    self.enable_sw_clipping = sw_clipping
    self.clip_fuzz = clip_fuzz

    # if enabled, rollers three times forward and back.
    # needs a pressure of 19 or more, else nothing will happen
    if trackenhancing is not None:
      if trackenhancing:
        self.send_command("FY0")
      else:
        if self.product_id() in PRODUCT_LINE_CAMEO3_ON:
          pass
        else:
          self.send_command("FY1")

    #FNx, x = 0 seem to be some kind of reset, x = 1: plotter head moves to other
    # side of media (boundary check?), but next cut run will stall
    #TB50,x: x = 1 landscape mode, x = 0 portrait mode
    if self.product_id() in PRODUCT_LINE_CAMEO3_ON:
      pass
    else:
      if landscape is not None:
        if landscape:
          self.send_command(["FN0", "TB50,1"])
        else:
          self.send_command(["FN0", "TB50,0"])

      # Don't lift plotter head between paths
      self.send_command("FE0,0")


  def do_regmark(self, regsearch, regoriginx, regoriginy, regwidth, reglength):
    self.send_command("TB50,0") #only with registration (it was TB50,1), landscape mode
    self.send_command("TB99")
    self.send_command("TB52,2")     #type of regmarks: 0='Original,SD', 2='Cameo,Portrait'
    self.send_command("TB51,400")   # length of regmarks
    self.send_command("TB53,10")    # width of regmarks
    self.send_command("TB55,1")

    if regsearch:
      # automatic regmark test
      # add a search range of 10mm
      self.send_command(self.automatic_regmark_test_mm_cmd(reglength, regwidth, regoriginy - 10, regoriginx - 10))
    else:
      # manual regmark
      self.send_command(self.manual_regmark_mm_cmd(reglength, regwidth))

    #while True:
    #  s.write("\1b\05") #request status
    #  resp = s.read(timeout=1000)
    #  if resp != "    1\x03":
    #    break;

    if self.dry_run:
      self.mock_response = b"    0\x03"
    resp = self.read(timeout=40000) ## Allow 20s for reply...
    if resp != b"    0\x03":
      raise ValueError("Couldn't find registration marks. %s" % str(resp))

    ## Looks like if the reg marks work it gets 3 messages back (if it fails it times out because it only gets the first message)
    #resp = s.read(timeout=40000) ## Allow 20s for reply...
    #if resp != "    0\x03":
      #raise ValueError("Couldn't find registration marks. (2)(%s)" % str(resp))

    #resp = s.read(timeout=40000) ## Allow 20s for reply...
    #if resp != "    1\x03":
      #raise ValueError("Couldn't find registration marks. (3)")


  def pre_plot(self, width, height):
    if self.product_id() not in PRODUCT_LINE_CAMEO3_ON:
      self.send_command([
        self.upper_left_mm_cmd(0, 0),
        self.lower_right_mm_cmd(height, width),
        "L0",
        "FE0,0",
        "FF0,0,0"])


  def home_to_start(self):
    """ Return commands to home the head back to the start """
    if self.product_id() in PRODUCT_LINE_CAMEO3_ON:
      new_home = [
        "L0",
        self.upper_left_mm_cmd(0, 0),
        self.move_mm_cmd(0, 0),
        "J0",
        "FN0",
        "TB50,0"]
    else:
      new_home = "H"
    return new_home

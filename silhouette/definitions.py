"""Definitions of Media types, mats, USB ids, command and response codes"""

MEDIA = [
# CAUTION: keep in sync with sendto_silhouette.inx
# media, pressure, speed, depth, cap-color, name
  ( 100,   27,     10,   1,  "yellow", "Card without Craft Paper Backing"),
  ( 101,   27,     10,   1,  "yellow", "Card with Craft Paper Backing"),
  ( 102,   10,      5,   1,  "blue",   "Vinyl Sticker"),
  ( 106,   14,     10,   1,  "blue",   "Film Labels"),
  ( 111,   27,     10,   1,  "yellow", "Thick Media"),
  ( 112,    2,     10,   1,  "blue",   "Thin Media"),
  ( 113,   18,     10,None,  "pen",    "Pen"),
  ( 120,   30,     10,   1,  "blue",   "Bond Paper 13-28 lbs (105g)"),
  ( 121,   30,     10,   1,  "yellow", "Bristol Paper 57-67 lbs (145g)"),
  ( 122,   30,     10,   1,  "yellow", "Cardstock 40-60 lbs (90g)"),
  ( 123,   30,     10,   1,  "yellow", "Cover 40-60 lbs (170g)"),
  ( 124,    1,     10,   1,  "blue",   "Film, Double Matte Translucent"),
  ( 125,    1,     10,   1,  "blue",   "Film, Vinyl With Adhesive Back"),
  ( 126,    1,     10,   1,  "blue",   "Film, Window With Kling Adhesive"),
  ( 127,   30,     10,   1,  "red",    "Index 90 lbs (165g)"),
  ( 128,   20,     10,   1,  "yellow", "Inkjet Photo Paper 28-44 lbs (70g)"),
  ( 129,   27,     10,   1,  "red",    "Inkjet Photo Paper 45-75 lbs (110g)"),
  ( 130,   30,      3,   1,  "red",    "Magnetic Sheet"),
  ( 131,   30,     10,   1,  "blue",   "Offset 24-60 lbs (90g)"),
  ( 132,    5,     10,   1,  "blue",   "Print Paper Light Weight"),
  ( 133,   25,     10,   1,  "yellow", "Print Paper Medium Weight"),
  ( 134,   20,     10,   1,  "blue",   "Sticker Sheet"),
  ( 135,   20,     10,   1,  "red",    "Tag 100 lbs (275g)"),
  ( 136,   30,     10,   1,  "blue",   "Text Paper 24-70 lbs (105g)"),
  ( 137,   30,     10,   1,  "yellow", "Vellum Bristol 57-67 lbs (145g)"),
  ( 138,   30,     10,   1,  "blue",   "Writing Paper 24-70 lbs (105g)"),
  ( 300, None,   None,None,  "custom", "Custom"),
]

SILHOUETTE_MATS = dict(
  no_mat=('0', False, False),
  cameo_12x12=('1', 12, 12),
  cameo_12x24=('2', 24, 12),
  portrait_8x12=('3', 8, 12),
  cameo_plus_15x15=('8', 15, 15),
  cameo_pro_24x24=('9', 24, 24),
)

#  robocut/Plotter.h:53 ff
VENDOR_ID_GRAPHTEC = 0x0b4d
PRODUCT_ID_CC200_20 = 0x110a
PRODUCT_ID_CC300_20 = 0x111a
PRODUCT_ID_SILHOUETTE_SD_1 = 0x111c
PRODUCT_ID_SILHOUETTE_SD_2 = 0x111d
PRODUCT_ID_SILHOUETTE_CAMEO =  0x1121
PRODUCT_ID_SILHOUETTE_CAMEO2 =  0x112b
PRODUCT_ID_SILHOUETTE_CAMEO3 =  0x112f
PRODUCT_ID_SILHOUETTE_CAMEO4 =  0x1137
# The following seems like a good bet:
# PRODUCT_ID_SILHOUETTE_CAMEO4PLUS = 0x1138
# but I don't have one to check and did not want to jump to conclusions.
PRODUCT_ID_SILHOUETTE_CAMEO4PRO = 0x1139
PRODUCT_ID_SILHOUETTE_PORTRAIT = 0x1123
PRODUCT_ID_SILHOUETTE_PORTRAIT2 = 0x1132
PRODUCT_ID_SILHOUETTE_PORTRAIT3 = 0x113a

PRODUCT_LINE_CAMEO4 = [
  PRODUCT_ID_SILHOUETTE_CAMEO4,
  # PRODUCT_ID_SILHOUETTE_CAMEO4PLUS,  # uncomment when verified
  PRODUCT_ID_SILHOUETTE_CAMEO4PRO
]

PRODUCT_LINE_CAMEO3_ON = PRODUCT_LINE_CAMEO4 + [PRODUCT_ID_SILHOUETTE_CAMEO3, PRODUCT_ID_SILHOUETTE_PORTRAIT3]

# End Of Text - marks the end of a command
CMD_ETX = b'\x03'
# Escape - send escape command
CMD_ESC = b'\x1b'

### Escape Commands
# End Of Transmission - will initialize the device,
CMD_EOT = b'\x04'
# Enquiry - Returns device status
CMD_ENQ = b'\x05'
# Negative Acnowledge - Returns device tool setup
CMD_NAK = b'\x15'

### Query codes
QUERY_FIRMWARE_VERSION = b'FG'

### Response codes
RESP_READY    = b'0'
RESP_MOVING   = b'1'
RESP_UNLOADED = b'2'
RESP_FAIL     = b'-1'
RESP_DECODING = {
  RESP_READY:    'ready',
  RESP_MOVING:   'moving',
  RESP_UNLOADED: 'unloaded',
  RESP_FAIL:     'fail'
}

SILHOUETTE_CAMEO4_TOOL_EMPTY = 0
SILHOUETTE_CAMEO4_TOOL_RATCHETBLADE = 1
SILHOUETTE_CAMEO4_TOOL_AUTOBLADE = 2
SILHOUETTE_CAMEO4_TOOL_DEEPCUTBLADE = 3
SILHOUETTE_CAMEO4_TOOL_KRAFTBLADE = 4
SILHOUETTE_CAMEO4_TOOL_ROTARYBLADE = 5
SILHOUETTE_CAMEO4_TOOL_PEN = 7
SILHOUETTE_CAMEO4_TOOL_ERROR = 255
